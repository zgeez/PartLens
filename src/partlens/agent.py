"""The PartLens agent: one LLM that clarifies, investigates, plans and explains over the tool registry.

The model never produces a verification result. Compatibility status comes only from ``check_substitute`` (and
sourcing status from ``check_availability``); the model's job is to choose which checks to run, ask for what is
missing, and explain the recorded results with their evidence.
"""

from __future__ import annotations

import json
import re
import os
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Callable, Protocol

from .core.model import to_jsonable
from .records import output_digest
from .secrets import redact
from .session import Session, ToolError
from .tools import BY_NAME, anthropic_tools, run_tool, validate_arguments

SYSTEM_PROMPT = """\
You are PartLens, the component-selection and BOM engineering agent of Cirquill.

How you work:
- Use the tools to establish facts. Start from describe_design / match_parts / find_missing_information.
- Tool arguments must match their JSON schema exactly. Tools operate on the current imported design:
  describe_design, match_parts, find_missing_information and list_requirements take {} with no design key.
  After a tool error, correct the arguments using its schema and retry; never invent missing tool results.
- Ask the user one targeted question at a time with ask_user when information that changes a decision is
  missing. Do not ask for what the tools can establish.
- When the user states a requirement, record it with record_requirement and pass their exact words in
  user_quote. Never invent a user quote: a requirement without one is provisional and not binding.
- Compatibility verdicts come only from check_substitute; sourcing verdicts only from check_availability. Never
  call a part verified, compatible or a drop-in replacement unless check_substitute returned "verified".
  "unverified" means the evidence is incomplete: say what is missing, never present it as a pass.
- When memory returns an earlier decision for the same pair, mention it with its source.
  Search memory using part identities and engineering terms; run IDs identify returned sources but may not
  occur in the searchable decision text. If a search misses, try relevant engineering terms within the budget.
- In explanations, cite the evidence the checks returned (source and value), and keep numbers exactly as the
  tools gave them. Cost figures come only from estimate_cost / optimise_cost.
- You do not edit design files or place orders.
- Distinguish original-specification equivalence from compatibility with evidenced circuit conditions.
  A rejected equivalence check alone does not prove a part unsafe in this circuit.
  A verified equivalence result qualifies only that scope; never claim full application compatibility
  while the tool's application result remains unverified.
  Changing application conditions cannot relax an original-specification no-downgrade check or reverse
  its rejection. Cite direct source URLs for the key engineering claims in the final explanation.
- Never substitute absolute maximum ratings for recommended operating limits. Part identity includes its
  manufacturer; matching MPN text from different manufacturers does not establish equivalence.
Be concise."""

MAX_STEPS = 40
STABLE_EXCLUDE = {"check_substitute": {"prior_decisions_from_memory", "stored_in_memory", "context"}}


def stable_view(name: str, output: Any) -> Any:
    """The part of a tool output that must reproduce on replay (memory state is excluded)."""
    if isinstance(output, dict) and name in STABLE_EXCLUDE:
        return {k: v for k, v in output.items() if k not in STABLE_EXCLUDE[name]}
    return output


@dataclass
class ToolCall:
    id: str
    name: str
    input: dict[str, Any]


@dataclass
class Turn:
    text: str
    tool_calls: list[ToolCall]
    assistant_content: Any          # what to append to the message history as the assistant turn
    stop_reason: str
    usage: dict[str, Any] = field(default_factory=dict)


class Provider(Protocol):
    name: str

    def next_turn(self, system: str, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> Turn: ...


class AnthropicProvider:
    """Claude via the Anthropic Messages API (manual tool loop)."""
    requires_workflow = True

    def __init__(self, model: str | None = None, effort: str = "high", *, fallback: bool | None = None) -> None:
        if os.environ.get("PARTLENS_ALLOW_PAID_INFERENCE") != "owner_authorized":
            raise ValueError("Paid inference disabled; explicit owner authorization is required before selecting Anthropic")
        import anthropic

        self.client = anthropic.Anthropic(timeout=45.0, max_retries=0)
        self.model = model or os.environ.get("PARTLENS_ANTHROPIC_MODEL", "claude-sonnet-5-5")
        self.effort = effort
        setting = os.environ.get("PARTLENS_MODEL_FALLBACK", "disabled")
        if setting not in {"disabled", "default"}:
            raise ValueError("PARTLENS_MODEL_FALLBACK must be disabled or default")
        self.fallback = fallback if fallback is not None else setting == "default"
        self.name = f"anthropic:{self.model}"

    def next_turn(self, system: str, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> Turn:
        options = {"betas": ["server-side-fallback-2026-07-01"], "fallbacks": "default"} if self.fallback else {}
        resp = self.client.beta.messages.create(
            model=self.model,
            max_tokens=16000,
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            tools=tools,
            messages=messages,
            output_config={"effort": self.effort},
            **options,
        )
        calls = [ToolCall(b.id, b.name, dict(b.input)) for b in resp.content if b.type == "tool_use"]
        text = "\n".join(b.text for b in resp.content if b.type == "text")
        usage = {"input": resp.usage.input_tokens, "output": resp.usage.output_tokens,
                 "cache_read": getattr(resp.usage, "cache_read_input_tokens", None), "model": resp.model,
                 "requested_model": self.model, "response_id": resp.id, "fallback_enabled": self.fallback}
        if not self.fallback and resp.model != self.model:
            raise ModelMismatch(self.model, resp.model, resp.id)
        if resp.stop_reason == "refusal":
            return Turn("The model declined this request.", [], resp.content, "refusal", usage)
        return Turn(text, calls, resp.content, resp.stop_reason or "", usage)


class ModelMismatch(RuntimeError):
    def __init__(self, requested: str, actual: str, response_id: str) -> None:
        self.requested, self.actual, self.response_id = requested, actual, response_id
        super().__init__(f"baseline model mismatch: requested {requested}, received {actual}")


class ScriptedProvider:
    """Deterministic stand-in for an LLM, for tests and offline demos.

    ``script`` is a list of steps; each step is either a list of (tool name, input) pairs, a final string, or a
    callable taking the tool results of the previous step and returning one of those.
    """

    name = "scripted"

    def __init__(self, script: list[Any]) -> None:
        self.script = list(script)
        self.step = 0
        self.last_results: list[dict[str, Any]] = []

    def next_turn(self, system: str, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> Turn:
        if messages and messages[-1]["role"] == "user" and isinstance(messages[-1]["content"], list):
            self.last_results = [json.loads(b["content"]) for b in messages[-1]["content"]
                                 if b.get("type") == "tool_result"]
        if self.step >= len(self.script):
            return Turn("(script finished)", [], [{"type": "text", "text": "(script finished)"}], "end_turn")
        item = self.script[self.step]
        self.step += 1
        if callable(item):
            item = item(self.last_results)
        if isinstance(item, str):
            return Turn(item, [], [{"type": "text", "text": item}], "end_turn")
        calls = [ToolCall(f"call_{self.step}_{i}", n, a) for i, (n, a) in enumerate(item)]
        content = [{"type": "tool_use", "id": c.id, "name": c.name, "input": c.input} for c in calls]
        return Turn("", calls, content, "tool_use")


def provider_from_env() -> Provider:
    kind = os.environ.get("PARTLENS_LLM_PROVIDER", "ollama")
    if kind == "ollama":
        from .local_provider import OllamaProvider
        return OllamaProvider()
    if kind == "anthropic":
        return AnthropicProvider()
    raise ValueError(f"unsupported PARTLENS_LLM_PROVIDER {kind!r}")


class Agent:
    def __init__(self, session: Session, provider: Provider, ask: Callable[[str], str],
                 system: str = SYSTEM_PROMPT, *, max_steps: int = MAX_STEPS, max_tool_calls: int = 120,
                 max_repeated_calls: int = 3, max_total_tokens: int = 400_000,
                 tool_names: set[str] | None = None) -> None:
        self.session = session
        self.provider = provider
        self.ask = ask
        self.system = system
        self.messages: list[dict[str, Any]] = []
        self.tools = anthropic_tools(tool_names)
        if any(type(v) is not int or v < 1 for v in (max_steps, max_tool_calls, max_repeated_calls, max_total_tokens)):
            raise ValueError("agent budgets must be positive whole numbers")
        self.max_steps, self.max_tool_calls, self.max_repeated_calls = max_steps, max_tool_calls, max_repeated_calls
        self.max_total_tokens = max_total_tokens
        session.recorder.log("agent_start", provider=provider.name, tools=[t["name"] for t in self.tools],
                             limits={"model_turns": max_steps, "tool_calls": max_tool_calls,
                                     "identical_tool_requests": max_repeated_calls, "total_tokens": max_total_tokens},
                             system_digest=output_digest(system), requested_model=getattr(provider, "model", None),
                             fallback_enabled=getattr(provider, "fallback", False),
                             sources=[getattr(c, "provenance", {"name": c.name}) for c in session.catalogs])
        for catalog in session.catalogs:
            while hasattr(catalog, "base"):
                catalog = catalog.base
            if hasattr(catalog, "client") and hasattr(catalog.client, "recorder"):
                catalog.client.recorder = session.recorder

    def send(self, text: str, *, origin: str = "user", workflow=None) -> str:
        if workflow is None and getattr(self.provider, "requires_workflow", False):
            self.session.recorder.log("workflow_rejected", reason="live provider requires explicit task scope",
                                      task=text, origin=origin, provider=self.provider.name)
            raise ValueError("Live inference requires an explicit WorkflowRequest; use the controlled CLI/UI or supply its scope")
        if workflow is not None:
            return self._send_controlled(text, workflow, origin=origin)
        rec = self.session.recorder
        rec.log("user_message", text=text, origin=origin)
        self.messages.append({"role": "user", "content": text})
        calls_used = 0
        repeated: Counter[str] = Counter()
        for _ in range(self.max_steps):
            try:
                started = time.perf_counter()
                turn = self.provider.next_turn(self.system, self.messages, self.tools)
            except Exception as exc:
                rec.log("provider_error", error_type=type(exc).__name__, message=str(exc),
                        requested_model=getattr(self.provider, "model", None),
                        actual_model=getattr(exc, "actual", None), response_id=getattr(exc, "response_id", None))
                raise
            rec.log("assistant_turn", text=turn.text, stop_reason=turn.stop_reason, usage=turn.usage,
                    latency_ms=round((time.perf_counter() - started) * 1000),
                    tool_calls=[{"id": c.id, "name": c.name, "input": c.input} for c in turn.tool_calls])
            self.messages.append({"role": "assistant", "content": turn.assistant_content})
            if not turn.tool_calls:
                if turn.stop_reason not in {"end_turn", "stop_sequence"}:
                    rec.log("agent_incomplete", reason=turn.stop_reason)
                    return f"Incomplete analysis ({turn.stop_reason}). " + turn.text
                return turn.text
            results = []
            for call in turn.tool_calls:
                signature = output_digest({"name": call.name, "input": call.input})
                repeated[signature] += 1
                reason = ("tool-call budget" if calls_used >= self.max_tool_calls else
                          "repeated identical tool request" if repeated[signature] > self.max_repeated_calls else None)
                if reason:
                    rec.log("agent_stopped", reason=reason, tools_executed=calls_used, pending_tool=call.name)
                    return f"Incomplete analysis: stopped at {reason}; inspect the saved evidence and missing inputs."
                results.append(self._execute(call))
                calls_used += 1
            self.messages.append({"role": "user", "content": results})
        rec.log("agent_stopped", reason=f"step limit {self.max_steps}")
        return f"Incomplete analysis: stopped after {self.max_steps} model turns."

    def _send_controlled(self, text, request, *, origin) -> str:
        from .results import FinalResult
        from .workflow import WorkflowController, compact_output

        rec = self.session.recorder
        controller = WorkflowController(request)
        self.controller = controller
        rec.log("workflow_start", request=request, max_total_tokens=self.max_total_tokens)
        rec.log("user_message", text=text, origin=origin)
        self.messages.append({"role": "user", "content": text})
        calls_used, tokens_used = 0, 0
        repeated = Counter()
        last_draft = ""
        previous_phase = "import"

        def finish(reason=None):
            result = FinalResult.build(controller, self.session, last_draft, stopped_reason=reason)
            rec.log("agent_result", result=result.as_dict(), rendered=result.render(),
                    tools_executed=calls_used, total_tokens=tokens_used, context_digest=self.session.context_digest())
            self.last_result = result
            return result.render()

        def dispatch(call, actor="model"):
            nonlocal calls_used
            signature = output_digest({"name": call.name, "input": call.input})
            repeated[signature] += 1
            if calls_used >= self.max_tool_calls or repeated[signature] > self.max_repeated_calls:
                return None
            calls_used += 1
            choices = controller.line_choices(self.session, call.name)
            valid_question = call.name != "ask_user" or call.input.get("gap_id") in {
                g["id"] for g in controller.snapshot(self.session)["unasked_questions"]}
            valid_scenario = call.name != "compare_cost_scenarios" or call.input.get("hypothetical_boards", 60) == 60
            if call.name not in controller.permitted(self.session) or (choices is not None and
                    call.input.get("line_id") not in choices) or not valid_question or not valid_scenario:
                output = {"error": "Workflow prerequisite missing; " + controller.guidance(self.session)}
                rec.log("tool_call", call_id=call.id, name=call.name, input=call.input, output=output,
                        error=output["error"], deterministic=False, actor=actor, controller_blocked=True)
                block = {"type": "tool_result", "tool_use_id": call.id, "content": json.dumps(output), "is_error": True}
            else:
                # The operator chooses the design, not a model-proposed replacement input file.
                from pathlib import Path
                if call.name == "import_bom" and Path(call.input.get("path", "")).resolve() != Path(request.bom_path).resolve():
                    output = {"error": "Import only the operator-requested BOM"}
                    rec.log("tool_call", call_id=call.id, name=call.name, input=call.input, output=output,
                            error=output["error"], deterministic=False, actor=actor, controller_blocked=True)
                    block = {"type": "tool_result", "tool_use_id": call.id, "content": json.dumps(output), "is_error": True}
                else:
                    self._unanswered_allowed = True
                    try:
                        block = self._execute(call, actor=actor)
                    except Exception as exc:
                        if call.name != "ask_user":
                            raise
                        block = {"type": "tool_result", "tool_use_id": call.id,
                                 "content": json.dumps({"unanswered": True, "error": f"No owner answer: {type(exc).__name__}"}),
                                 "is_error": True}
                    finally:
                        self._unanswered_allowed = False
                    output = json.loads(block["content"])
            controller.observe(call.name, call.input, output, bool(block.get("is_error")), actor=actor)
            if not block.get("is_error"):
                block["content"] = json.dumps(compact_output(call.name, output), ensure_ascii=False)
            rec.log("model_tool_view", call_id=call.id, full_tool_event_seq=rec.seq,
                    content=json.loads(block["content"]), actor=actor)
            rec.log("workflow_state", snapshot=controller.snapshot(self.session))
            follow = None
            if actor == "model" and not block.get("is_error"):
                quantity = re.fullmatch(r"\s*(\d+)\s*(?:boards?|pcs|units)?\s*\.?\s*", str(output.get("answer") or ""), re.I)
                if call.name == "ask_user" and call.input.get("gap_id") == "design.board_quantity" and quantity:
                    # The owner's typed answer is the quote; a model paraphrase would never confirm it and the
                    # controller would block every later phase on the unrecorded quantity.
                    follow = ToolCall(f"controller-quantity-{rec.seq+1}", "record_requirement",
                                      {"subject": "design", "parameter": "board_quantity", "op": "==",
                                       "value": quantity.group(1), "user_quote": output["answer"]})
            if follow:
                rec.log("controller_action", reason="deterministic follow-up to " + call.name, tool=follow.name, input=follow.input)
                extra = dispatch(follow, "controller")
                view = json.loads(block["content"])
                if extra is not None and isinstance(view, dict):
                    view["controller_followup"] = {"tool": follow.name, "result": json.loads(extra["content"])}
                    block["content"] = json.dumps(view, ensure_ascii=False)
            return block

        for step in range(self.max_steps):
            # A model may omit rechecking recalled decisions. The controller cannot omit it.
            if controller.pending_rechecks():
                for memory in controller.pending_rechecks():
                    call = ToolCall(f"controller-recheck-{rec.seq+1}", "reverify_decision", {"memory_id": memory["id"]})
                    rec.log("controller_action", reason="mandatory recall reverification", tool=call.name, input=call.input)
                    block = dispatch(call, "controller")
                    if block is None:
                        return finish("tool/repetition budget exhausted during mandatory recall verification")
                    self.messages.append({"role": "user", "content": "Controller executed mandatory "
                                          "reverify_decision (not a model call): " + block["content"]})
            if tokens_used >= self.max_total_tokens:
                return finish("token budget exhausted")
            allowed = controller.permitted(self.session)
            guidance = controller.guidance(self.session)
            snapshot = controller.snapshot(self.session)
            phase = next((s["id"] for s in snapshot["states"] if s["status"] == "pending"), "final")
            if step and phase != previous_phase:
                context = controller.model_context(self.session)
                rec.log("controller_context", phase=phase, content=context)
                self.messages = [{"role": "user", "content": text},
                                 {"role": "user", "content": json.dumps(context, ensure_ascii=False)}]
            previous_phase = phase
            rec.log("controller_guidance", text=guidance, permitted_tools=sorted(allowed))
            try:
                started = time.perf_counter()
                turn = self.provider.next_turn(self.system + "\n\n" + guidance, self.messages,
                                               controller.tool_schemas(self.tools, self.session))
            except Exception as exc:
                rec.log("provider_error", error_type=type(exc).__name__, message=str(exc),
                        requested_model=getattr(self.provider, "model", None), actual_model=getattr(exc, "actual", None))
                return finish(f"provider failure: {type(exc).__name__}")
            rec.log("assistant_turn", text=turn.text, stop_reason=turn.stop_reason, usage=turn.usage,
                    latency_ms=round((time.perf_counter()-started)*1000),
                    tool_calls=[{"id": c.id, "name": c.name, "input": c.input} for c in turn.tool_calls])
            tokens_used += sum(v for k in ("input", "output") if type(v := turn.usage.get(k)) is int and v >= 0)
            self.messages.append({"role": "assistant", "content": turn.assistant_content})
            last_draft = turn.text
            if not turn.tool_calls:
                if turn.stop_reason not in {"end_turn", "stop_sequence"}:
                    return finish(f"incomplete model response: {turn.stop_reason}")
                current = controller.snapshot(self.session)
                if current["operations_complete"]:
                    return finish()
                if not any(s["status"] == "pending" for s in current["states"]):
                    # Only blocked work remains (e.g. unmatched lines); further model turns cannot resolve it.
                    return finish("unresolved: " + ", ".join(current["missing_actions"]))
                focus = next(s for s in current["states"] if s["status"] == "pending")
                auto = next((t for t in ("find_missing_information", "match_parts") if t in focus["permitted_tools"]), None)
                if auto:
                    # A stalled model cannot block a deterministic step that takes no choices; the controller runs it.
                    call = ToolCall(f"controller-{auto}-{rec.seq+1}", auto, {})
                    rec.log("controller_action", reason="model stalled on a no-input deterministic step", tool=auto, input={})
                    block = dispatch(call, "controller")
                    if block is None:
                        return finish("tool/repetition budget exhausted")
                    self.messages.append({"role": "user", "content": f"Controller executed {auto} (not a model call): "
                                          + block["content"]})
                    continue
                if controller.recoveries >= request.max_recoveries:
                    return finish("workflow recovery budget exhausted")
                controller.recoveries += 1
                guidance = controller.guidance(self.session)
                rec.log("controller_recovery", attempt=controller.recoveries, reason="premature final answer", text=guidance)
                self.messages.append({"role": "user", "content": guidance})
                continue
            blocks = []
            for call in turn.tool_calls:
                block = dispatch(call)
                if block is None:
                    return finish("tool/repetition budget exhausted")
                blocks.append(block)
            self.messages.append({"role": "user", "content": blocks})
        return finish("model-turn budget exhausted")

    def _execute(self, call: ToolCall, *, actor: str = "model") -> dict[str, Any]:
        rec = self.session.recorder
        if call.name == "ask_user":
            try:
                validate_arguments(BY_NAME[call.name], call.input)
            except ToolError as exc:
                rec.log("tool_call", call_id=call.id, name=call.name, input=call.input,
                        output={"error": str(exc)}, error=str(exc), deterministic=False)
                return {"type": "tool_result", "tool_use_id": call.id,
                        "content": json.dumps({"error": str(exc)}), "is_error": True}
            question = str(call.input.get("question", ""))
            rec.log("question", question=question, gap_id=call.input.get("gap_id"))
            try:
                answer = self.ask(question)
            except Exception as exc:
                rec.log("tool_call", call_id=call.id, name=call.name, input=call.input,
                        output={"error": str(exc)}, error=str(exc), deterministic=False)
                raise
            if answer is None:
                output = {"unanswered": True, "note": "No owner answer available; requirement remains unresolved"}
                rec.log("tool_call", call_id=call.id, name=call.name, input=call.input, output=output,
                        error=None, deterministic=False, actor=actor)
                return {"type": "tool_result", "tool_use_id": call.id, "content": json.dumps(output)}
            if answer == "__AI_DELEGATE__":
                rec.log("user_message", text="Delegate requirement to AI provisional default.", in_reply_to=question)
                output = {"delegated_to_ai": True, "unanswered": False,
                          "note": "Operator delegated this requirement to AI; set a provisional (non-binding) default."}
                rec.log("tool_call", call_id=call.id, name=call.name, input=call.input, output=output,
                        error=None, deterministic=False, actor=actor)
                return {"type": "tool_result", "tool_use_id": call.id, "content": json.dumps(output)}
            rec.log("user_message", text=answer, in_reply_to=question)
            output = {"answer": answer}
            rec.log("tool_call", call_id=call.id, name=call.name, input=call.input, output=output,
                    error=None, deterministic=False)
            return {"type": "tool_result", "tool_use_id": call.id, "content": json.dumps(output)}
        # One clock per call, recorded, so replay sees the same time.
        fixed = self.session.now
        clock = fixed or datetime.now(UTC).replace(microsecond=0)
        self.session.now = clock
        try:
            if call.name not in BY_NAME:
                raise ToolError(f"unknown tool {call.name}")
            output = to_jsonable(run_tool(self.session, call.name, call.input))
            error = None
        except ToolError as e:
            output, error = {"error": str(e)}, str(e)
        except Exception as e:  # tool bug or source failure: report to the model and the record, keep going
            error = redact(f"{type(e).__name__}: {e}")
            output = {"error": f"internal error {error}"}
        finally:
            self.session.now = fixed
        output, error = redact(output), redact(error)
        rec.log("tool_call", call_id=call.id, name=call.name, input=call.input, output=output, error=error,
                actor=actor, context_digest=self.session.context_digest(),
                deterministic=BY_NAME[call.name].deterministic if call.name in BY_NAME else False,
                stable_digest=output_digest(stable_view(call.name, output)),
                clock=clock.strftime("%Y-%m-%dT%H:%M:%SZ"))
        block = {"type": "tool_result", "tool_use_id": call.id, "content": json.dumps(output, ensure_ascii=False)}
        if error:
            block["is_error"] = True
        return block

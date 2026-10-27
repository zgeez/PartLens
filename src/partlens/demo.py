"""Two independent live agent sessions over the approved demo and genuine decision memory."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from .agent import Agent, provider_from_env
from .evaluation import evaluate_run
from .memory.hmem import DecisionMemory, HMemBridge
from .records import RunRecorder, read_events
from .session import Session
from .sources.catalog import Catalog
from .optimise.cost import AssemblyFees
from .workflow import WorkflowRequest

from .paths import resource_root

DEMO_BOM = resource_root() / "examples/easyduino-rp2040/bom.csv"


def run_live_demo(catalogs: list[Catalog], state: Path, ask: Callable[[str], str],
                  *, notify: Callable[[str], None] = print, fees: AssemblyFees | None = None) -> list[dict]:
    reports: list[dict] = []
    prior: Path | None = None
    for phase in ("baseline", "recall"):
        rec = RunRecorder.create(state / "runs")
        rec.log("baseline_setup", phase=phase,
                catalogs=[c.name for c in catalogs], prior_record=str(prior) if prior else None)
        notify(f"{phase} run {rec.run_id} -> {rec.path}")
        try:
            provider = provider_from_env()
            if getattr(provider, "fallback", False):
                raise ValueError("Live baseline requires PARTLENS_MODEL_FALLBACK=disabled")
            with HMemBridge(state / "hmem") as bridge:
                rec.log("memory_engine", info=bridge.info)
                session = Session(rec, catalogs, memory=DecisionMemory(bridge, "easyduino-rp2040"), fees=fees)
                if prior:
                    session.restore_quantity(prior)
                rec.log("cost_configuration", fees=fees)
                agent = Agent(session, provider, ask)
                if phase == "baseline":
                    prompt = (
                        f"Import the approved demo BOM at {DEMO_BOM} as easyduino-rp2040. Review sourcing risk "
                        "and alternatives. Identify missing requirements and ask me for build quantity using "
                        "gap_id design.board_quantity before costing. Record my answer exactly. Investigate "
                        "genuine supplier evidence, run deterministic checks to find a qualified alternative, "
                        "an unverified alternative and an invalid replacement, and explain the engineering "
                        "evidence. Evaluate cost and sourcing at my quantity. If other circuit conditions or "
                        "fees are unavailable, leave them unknown and report the consequences. Decisions must "
                        "be stored in Meterless by the tools. End with a concise sourced explanation."
                    )
                else:
                    prompt = (
                        f"Start a new session for easyduino-rp2040; its BOM is at {DEMO_BOM}. Use Meterless "
                        "to recall a relevant decision from the preceding session, cite its run/decision source, "
                        "and explain the decision and its evidence. Re-run deterministic checks if evaluating "
                        "compatibility again; memory alone cannot verify a replacement."
                    )
                notify(agent.send(prompt, origin="baseline_task", workflow=WorkflowRequest(
                    str(DEMO_BOM), lines=("L1", "L11", "L18"), research=phase == "baseline",
                    costs=phase == "baseline", recall_run=prior.stem if prior else None)))
                rec.log("run_finished", phase=phase)
        except Exception as exc:
            rec.log("setup_error" if not any(e["type"] == "agent_start" for e in read_events(rec.path)) else "run_failed",
                    error_type=type(exc).__name__, message=str(exc))
            notify(f"{phase} did not complete ({type(exc).__name__}); see {rec.path}")
        report = evaluate_run(rec.path, prior_path=prior)
        rec.log("evaluation", report=report)
        reports.append(report)
        if not report["baseline_model_confirmed"] or report["failures"]:
            break
        prior = rec.path
    return reports

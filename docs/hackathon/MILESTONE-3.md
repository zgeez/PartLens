# Milestone 3: submission-ready engineering agent

Status: **partially complete**, 2026-10-22. The desktop workflow, deterministic engineering checks,
quantity scenarios, sourcing constraints and real H-MEM operations were improved. Earlier real Zetaris
queries succeeded; the gateway was unavailable during the later local-model retest. Anthropic credits are
exhausted. The owner selected local inference and Sonnet for future cloud use. No HackOS entry was created
or submitted. Track 02 remains the target; eligibility has not been certified.

## Implementation and modified files

| Area | Changes | Main files |
|---|---|---|
| Desktop | Original/candidate identity, per-check evidence, scope/status filter, missing requirements, stock/price/MOQ details, eight tabs, conditional costs, actionable errors, deterministic cold recall | `src/partlens/ui.py`, `scripts/smoke_ui.py` |
| Engineering | Recommended/absolute rating separation; missing IC pinout/function/timing evidence; explicit capacitor application gaps; strict numeric parsing and percentage display | `checks/compat.py`, `core/parts.py`, `core/units.py`, `sources/catalog.py` |
| Provenance | Restore original owner quantity without fabricating a fresh answer; invalidate decisions after changed requirements/BOM; read-only part views; manufacturer/MPN conflict rejection | `session.py` |
| Costs | Process fees and applicability separate from classification; fee freshness; incomplete totals/savings; empty/missing catalogue handling; hypothetical quantity tool | `optimise/cost.py`, `optimise/search.py`, `session.py`, `tools.py`, `cli.py` |
| Agent | Turn/tool/repetition budgets, schema errors before dispatch, recorded latency/incomplete responses, configurable provider in UI/demo/CLI | `agent.py`, `tools.py`, `demo.py`, `evaluation.py` |
| Local model | Native Ollama tool calls and result history; loopback-only transport; no cloud fallback; actual model/digest/context logging | `local_provider.py`, `.env.example`, `scripts/start_local_llm.ps1`, `scripts/evaluate_local.py` |
| Memory/replay | Design/line scope, exact run-source retrieval, independent recorder binding, hidden Windows bridge, recorded quantity/fee replay and sorted process derivations | `memory/hmem.py`, `replay.py` |
| Validation/docs | Synthetic regressions, real integration/scenario scripts, preserved test output and this report/runbook | `tests/`, `scripts/verify_milestone3.py`, `scripts/validate.py`, `DEVELOPMENT.md`, `AGENTS.md`, `THIRD_PARTY.md` |

Paths in the first column's source entries are relative to `src/partlens/` unless a repository prefix is shown.
No routing, placement, production design edits, ordering or undocumented supplier collection was added.

## Desktop verification

Actual interactive inspection covered BOM import, a live model review, source/parameter inspection,
verified/rejected/unverified comparisons, sourcing and individual part selection. It exposed a stale detail
panel after changing the status filter; the panel now selects the first visible decision or clears itself.
Live credit failures are preserved and displayed as incomplete analysis. Read-only refresh no longer queries
remote catalogues or mutates the audit. A new session restores the original quantity and resets the agent.

The owner interrupted computer control before final visual verification of every tab and recall completed.
No further UI control was performed. The final changes were verified programmatically: run
`20261022T165124Z-661cc9` loaded 19 rows/eight tabs, selected supplier evidence, compared all three qualification
statuses, checked the rejected-only filter/detail pairing and confirmed that no quantity was invented.
This is a programmatic pass, not complete visual acceptance. The manual procedure is in the runbook.

## Engineering corrections and gaps

Exact identity remains **UMW XC6206P332MR**, supplier code C347376, rather than an established Torex device.
The reviewed [official UMW datasheet](https://www.umw-ic.com/static/pdf/db5d7ec139677efdcb3bf5b5558e8bbd.pdf)
gives 1.8–8 V in its electrical table (page 4), 9 V in its limits (page 3), and the exact ordering code on
page 12. Torex's [separate XC6206 product](https://product.torexsemi.com/en/series/xc6206) specifies 1.8–6 V.
The 8 V fixture value is consistent with the reviewed UMW device; manufacturer identity prevents transferring
Torex ratings to it. Operating and absolute-maximum evidence remain separate; an untyped or absolute rating
cannot pass an operating-voltage check. Full regulation, thermal, current and stability qualification is open.

Equivalence and circuit application are separate outputs. The 25 V replacement resistor fails the original
50 V specification; this alone does not prove the part unsafe in the actual circuit. Capacitor equivalence
checks nominal value, voltage, tolerance, dielectric and known temperature constraints. Application checks
retain missing footprint/land-pattern, DC-bias/effective capacitance, ESR/ripple and operating-context gaps.
IC replacements require evidenced identity, operating conditions, pinout/land pattern, function/interfaces
and timing; package naming alone cannot approve them. Nonfinite or malformed engineering/stock/MOQ values
fail closed. Current requirement/BOM identity must match the optimiser's decision.

Flash stock is still zero in the retained timestamped fixture; proposed flash alternatives remain unverified
without pinout/function/timing evidence. BOM information grounds the unresolved headers as vertical 2.54 mm
through-hole, 1×20 for J3/J4 and 1×03 for J5. Exact manufacturer/MPNs, pin/mating geometry, finish and electrical
ratings remain missing; the owner was asked, with no answer available. No header was fabricated or qualified.
Further source context is in [the engineering review](ENGINEERING-REVIEW.md).

## One-board and 60-board manufacturing comparison

The binding requirement remains one board from `user:20261022T043042Z-84edf9#seq13`, exact answer `1`.
Restoration validates the original recorded quotation, binding status, actual user origin, value and source
hash. Sixty boards is `scenario:hypothetical; not an owner requirement`; it never overwrites the owner answer.

| Scenario | Covered component purchasing subtotal | Known conditional manufacturing subtotal including covered parts | Complete assembled total / official quote | Proposed changes |
|---|---:|---:|---|---|
| Owner, 1 board | USD 11.10 | USD 23.88 | Unavailable / unavailable | None accepted for assembled-cost savings |
| Hypothetical, 60 boards | USD 166.34 | USD 179.12 | Unavailable / unavailable | None accepted for assembled-cost savings |

These are incomplete totals over 15 priced BOM lines, not a quote or purchasable complete BOM. MOQ, order
multiples, quantity price breaks, shared purchasing and stock constraints are applied with Decimal arithmetic.
The cost model separates loading/classification, attrition, joints, PCB cost, setup, stencil and named process
charges. A lower unit price does not prove lower assembled cost. Missing classifications exclude alternatives
from that claim; missing costs produce no assembled savings. The scenario report preserves every excluded
candidate and sourcing constraint.

The [official JLCPCB table](https://jlcpcb.com/help/article/pcb-assembly-price) was reviewed at 07:12 UTC:
Economic setup USD 8.18, stencil 1.53, extended loading 3.07 and SMT labor 0.0016 per joint in the stated tier.
The local fee artifact is `.partlens/fees/jlcpcb-economic-m3-20261022T071230Z-b93cfd.json`. Packaging zero is
conditional on the cited Economic rule, not an assumed universal free fee. PCB quote, service eligibility,
13 part classifications, assembly procurement prices, joint counts, attrition and applicable manual/X-ray/
placement-confirmation charges remain unresolved; shipping/taxes are outside a completed quote as well.
Only two classification overlays have official sources. Unknown process applicability remains unknown.

The real Zetaris scenario run `20261022T071501Z-b76fab` recorded 104 tools and 165 successful SQL queries,
with 21 verified-equivalence, 38 rejected and 27 unverified decisions. Artifact:
`.partlens/scenarios/milestone3-20261022T071501Z-731aba.json`. These deterministic checks are not an LLM run.
A local-fixture replay matched 104/104 at `20261022T072802Z-a2c1f2`, audit `20261022T072807Z-bf7867`, before the
final percentage-display correction. Earlier 103/104 replay failure is preserved; process-fee derivation order
was sorted. This historical replay pass does not assert unchanged output across later software revisions.
The final corrected deterministic scenario run `20261022T165602Z-935224` also matched **104/104**, audit
`20261022T165606Z-b8d862`; artifact `.partlens/scenarios/milestone3-final-20261022T165602Z-fe4f13.json`.

## Supplier and sponsor operations

Zetaris performed actual queries through the owner's local authenticated gateway, not a CSV export or mock.
Independent-process validation records `20261022T071829Z-b3d4ae` and `20261022T071831Z-0e0173` contain 18 and 16
successful SQL operations respectively, HTTP 200 status, SQL, result identifiers, response hashes and server
elapsed timing. The gateway supplies no server query/request ID; those fields stay null. Source clients are
bound to the correct run recorder. UI refresh was verified to issue zero new SQL calls or audit mutations.

At 16:50 UTC the gateway refused connections and Docker's daemon was unavailable. The failed live local
attempt `20261022T165002Z-c0a945` preserves five failed query operations. Current availability is blocked,
distinct from earlier genuine operational integration. The local fixture remains timestamped internal data,
not live stock/pricing. No new LCSC records were collected. DigiKey credentials were absent in
`20261022T071126Z-2a7484`; no authenticated lookup succeeded. Mouser remains investigated, not integrated.

H-MEM write and cold recall used independent bridge processes and a fresh isolated memory store. The above
07:18 runs stored all three decision statuses, recalled the exact preceding rejection with its source and
rechecked it against current evidence. Negative tests reject unrelated design/line memories. Persistence is
distinct from relevant recall; memory never becomes current verification. The UI recall button executes
deterministic retrieval/rechecks. Live-agent recall is evaluated separately below.
Fresh deterministic local-fixture/H-MEM validation also passed in independent processes at
`20261022T165515Z-26dcec` / `20261022T165516Z-a087cd`. This retest does not claim current Zetaris access.

## Live model results versus scripted reference

Historical Opus evidence is retained. Milestone 2 run `20261022T043042Z-84edf9` used 11 model turns/40 tools,
asked for and recorded the owner's actual quantity, found all three statuses and persisted decisions; run
`20261022T043403Z-d587d5` recalled the new rejection. Its requested/observed model remains `claude-opus-5-5`.
See [Milestone 2](MILESTONE-2.md) for the outcome comparison, source IDs and replays. Intermediate tool order
is not required to match the scripted reference.

Milestone 3 UI run `20261022T065521Z-b8a8c6` finished after 12 Opus turns/46 tools with seven verified,
three rejected and six unverified checks, plus one recoverable cost error. A concurrent external quantity
relay annotation created a duplicate sequence number; diagnostic audit `20261022T070914Z-f4f020` preserves
that defect. It is not a pristine acceptance record. Run `20261022T070859Z-365063` used eight actual Opus
turns/38 tools/92 real SQL queries, then failed on exhausted credits. It has no completed final explanation.

Current new-run defaults are local Ollama **Qwen3.5 9B** and cloud Sonnet (`claude-sonnet-5-5`, explicitly selectable).
No Sonnet API operation was attempted without credits. Ollama v0.40.8's standalone archive was SHA-256
verified; inference binds loopback with cloud disabled. The initial `qwen3:8b` Q4_K_M manifest digest is
`500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41`. Runtime/weights remain ignored dependencies.

Initial Qwen3 runs are negative evidence: `20261022T164800Z-dd2bb1` generated unsupported `design` arguments;
after actionable schema validation, `20261022T165042Z-97ce97` used 11 tools on the local fixture, detected
missing information and priced both scenarios, but skipped compatibility checks and misleadingly called
the hypothetical build an order/quote. It created no engineering decisions and its second session
`20261022T165114Z-b0efbc` had nothing relevant to recall. These are genuine local LLM operations, not a passing
engineering-agent evaluation. Their generated text is not trusted as a verdict or cost source.

The newer `qwen3.5:9b` Q4_K_M model is installed locally with manifest digest
`56671c2ab9385f9cfcb404638e32cd62d88e3501d44822208363c010179a3c90` (6.55 GB on disk). It reports native tool
support and ran on the owner's GPU. Its first broader review (`20261022T165524Z-e4ef45`) used 16 turns/15
tools, made four verified-equivalence and one unverified decision, but found no rejected alternative and
omitted the cost task. A revised broad review (`20261022T165711Z-f9fc96`) used ten turns/nine tools but
skipped compatibility checks. Both incomplete outcomes are retained.

| Current local evaluation | Observed result |
|---|---|
| Guided engineering review | `20261022T170159Z-31e215`: nine actual Qwen3.5 turns/eight tools, no tool/provider errors, 26.36 seconds summed model latency |
| Research scope | Operator-specified candidate pairs, not autonomous candidate discovery and not a scripted provider |
| Deterministic results | L1/C105883 verified equivalence; L11/C53109434 rejected (25 V versus original 50 V); L18/C1857757 unverified; all three stored in actual H-MEM as mem-1/2/3 |
| Requirements/costs | Imported BOM, matched parts, detected missing inputs and called the one/60 scenario tool; original one-board source restored, no fresh user answer fabricated |
| Second live session | `20261022T170226Z-80a4fd`: six Qwen3.5 turns/five tools, no tool/provider errors, 16.14 seconds summed model latency |
| Actual recall | New process retrieved all three preceding-run source IDs via real H-MEM exact design/run lookup |
| Remaining failure | The model did **not** call the required current compatibility recheck; it said the memories needed rechecking. Recall succeeded; agent reverification did not. |
| Narrative failure | The review explanation misleadingly called the hypothetical 60-board build an order. Recorded requirements and deterministic costs remain correctly labelled. |

These runs demonstrate local native tool use, supplier-fixture engineering checks, persistence and actual
cold recall without any paid model call. They do **not** meet the entire autonomous/interactive baseline:
candidate discovery was guided, no new quantity question was needed, sourcing used the local fixture while
Zetaris was down, and reliable task completion/narrative accuracy/current recall rechecking remain open.
Do not equate local reasoning performance with the historical Opus reference. Sonnet remains configured
but untested live in this change.

An H-MEM diagnostic (`20261022T170050Z-06e4b2`) found that a broad text query could miss an existing decision,
while exact candidate lookup retrieved it. `recall_decisions` now accepts optional `run_id`: a real H-MEM
design-tag lookup followed by exact stored-source filtering. Returned items explicitly say
`exact_design_and_run_source` and have no invented relevance score; query is not claimed to rank those
results. The UI recall button uses this route and still rechecks deterministically. Ordinary hybrid search
remains available. Evaluator correction audit `20261022T170413Z-910334` requires a current check on the
recalled pair and a genuine final turn; retrieved memory or intermediate commentary alone cannot pass.

The scripted reference still verifies deterministic expected outcomes; it does not substitute for model
planning. Meterless inference/Nemotron portability was investigated via official documentation, but no
authorized runtime/key was available and a loopback models probe failed (`20261022T071735Z-797f10`). No
Nemotron operation or comparison is claimed. Local Qwen is not labelled Nemotron or Meterless inference.

## Tests, signing and remaining work

The prior 102-test baseline is preserved. The first local-provider suite passed 148 tests
(`tests-20261022T164622Z-4eb070.txt`). A subsequent new regression assertion incorrectly expected JSON null
instead of the existing display value `n/a`: failure record `tests-20261022T165226Z-e820d0.txt` preserves
151 passes/one failure. The assertion was corrected without changing unknown costs into numeric values.
Earlier test/replay failures and every prior run remain on disk; no record was rewritten to make it pass.
Final full suite: **156 passed, no skips/failures**, 5.30 seconds,
`.partlens/validation/tests-20261022T170819Z-9b8a3c.txt`. Coverage includes native history/tools, no cloud
construction in local mode, Sonnet default, malformed/remote/mismatched/truncated/context-exhausted local
responses, schema rejection, exact H-MEM design/run scoping and rejection of recall without a current check
in both evaluation and the live-demo CLI exit status. The earlier 155-pass result is preserved separately.
Workspace audit `20261022T170019Z-03292a` confirms configured secrets absent from inspected source files,
ignored secret/runtime paths, the original owner record unchanged since the earlier 07:15 validation and
the retained supplier fixture's original hash unchanged. Runtime logs confirm cloud inference disabled.

SSH signing remains enabled (`commit.gpgsign=true`, `gpg.format=ssh`). The signing agent is stopped/disabled
and `ssh-add -l` cannot connect. No commit was attempted, no unsigned bypass used, and work remains in the
existing staged/unstaged/untracked state. The owner can unlock locally in an elevated PowerShell:

```powershell
Set-Service ssh-agent -StartupType Manual
Start-Service ssh-agent
ssh-add "$env:USERPROFILE\.ssh\id_ed25519_signing"
```

The owner alone enters any passphrase. A later signed commit should include the reviewed work after final
checks. No secret values were printed, copied into Git or placed in demo artifacts.

Remaining blockers: a passing full autonomous local engineering-agent evaluation and live-agent recall
reverification; currently stopped Zetaris; exhausted
Anthropic credits; full final visual UI acceptance; exact header identity; flash evidence/stock; incomplete
manufacturing eligibility/prices/fees; licensing review for internal supplier fixtures; absent official
DigiKey/Mouser access and Nemotron runtime; unsigned working tree. Cursor was intentionally not used per
owner instruction; its hackathon eligibility implication remains unresolved. No submission was performed.

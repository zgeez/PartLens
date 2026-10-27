# Milestone 4: reliable autonomous agent and hackathon readiness

Report date: 2026-10-23 UTC (2026-10-22 in the owner's local evening).

**Status: submission readiness remains partial. The bounded unguided Qwen engineering/cost evaluation
passed twice, and live cross-session recall/reverification passed.** The controller and factual renderer
now enforce the previously missing workflow. This is evidence for the approved demo scope, not a guarantee
of arbitrary-model or arbitrary-design reliability. Final visual acceptance, supplier-data redistribution
rights, complete manufacturing inputs and hackathon eligibility remain open. No HackOS entry was submitted.

## Implementation and architecture

The existing single-model/session/tool architecture remains. `WorkflowRequest` states the operator's BOM,
target lines, research/cost/clarification scope and optional prior memory run. `WorkflowController` records
actual successful/failed operations and exposes completion status, prerequisites, evidence, failure reasons,
permitted transitions and tools for import, requirements, clarification, supplier access, discovery, checks,
investigation, sourcing, costs, persistence, recall and reverification. Final results separately expose the
completion check and publication status. Unmatched requested lines cannot silently disappear from coverage.

The model chooses candidates from source research and proposes tool calls. Only deterministic checks can
produce qualification results. The controller restricts the next tools and eligible lines, spreads further
investigation across discovered lines, and corrects premature endings. It never fabricates a desired status.
Missing application voltages do not prevent running original-specification checks; their application result
remains unverified. Required unanswered questions stay unresolved, and answered requirements must be recorded
with original quotation provenance. Reusing a quote while changing its electrical number/unit does not bind.

At stage boundaries, the model receives an audited summary of actual tool facts, removing obsolete model
plans from active context. Compact model-tool views are also logged alongside complete original outputs;
source evidence is not deleted. Limits are 40 turns, 70 tool attempts for evaluation, three identical requests,
five premature-ending recoveries and 400,000 cumulative tokens. Qwen uses 65,536 context tokens on the owner's
16 GB GPU. Exhaustion, missing inputs and provider failures produce useful partial results. Direct live calls
without an explicit workflow scope are rejected. Scripted references remain explicitly separate.

Zetaris supplies records, Meterless H-MEM supplies historical context, Qwen proposes investigations, and the
engineering/cost tools calculate results. `FinalResult` renders the authoritative explanation. No multi-agent
system, PCB placement/routing, production design modification or ordering was added.

## Main changed files

- `src/partlens/workflow.py`, `results.py`: state/completion controller and authoritative final model/rendering.
- `agent.py`, `local_provider.py`, `tools.py`: controlled live loop, budgets, schema/gap/line restrictions,
  transparent controller actions, compulsory live scope and explicit paid-inference prohibition by default.
- `session.py`, `memory/hmem.py`: saved identity/requirement context, quote/value consistency, current-source
  reads and deterministic memory reverification without inheriting old verdicts.
- `ui.py`, `cli.py`, `demo.py`, `evaluation.py`, `replay.py`: controlled entry points, trusted explanation,
  visible costs/uncertainty, current-context views and memory-dependent replay exclusions.
- `scripts/evaluate_milestone4.py`, `smoke_milestone4_ui.py`, `sample_demo.py`, updated local evaluator:
  genuine local model evaluation, labelled fault injection, programmatic desktop acceptance and public fallback.
- `tests/test_workflow.py`, provider tests and fixture documentation: historical-failure regressions and
  explicit synthetic-data licensing. README, DEVELOPMENT, AGENTS and the current runbook document the workflow.

Source paths above are under `src/partlens/` unless a repository prefix is shown. No runtime dependency was added.

## Genuine autonomous Qwen results

Requested and observed model: `qwen3.5:9b`, Q4_K_M, installed manifest digest
`56671c2ab9385f9cfcb404638e32cd62d88e3501d44822208363c010179a3c90`, Ollama v0.40.8.
All inference was local; no paid model call or silent fallback occurred. Sonnet remains an untested selectable
cloud option, blocked unless the owner explicitly authorizes it. Cursor was not used.

| Evaluation | Recorded outcome | Evidence in `.partlens/runs/` |
|---|---|---|
| A + D: first unguided research and costing | Pass: 16 model turns, 36 tool attempts, 45 successful real SQL operations; five verified, one rejected and three unverified decisions | `20261023T010255Z-a7a43c.jsonl` |
| A + D: repeat | Pass: 17 turns, 24 tool attempts, 43 real SQL operations; original quantity preserved, all required workflow operations completed | `20261023T010658Z-c93572.jsonl` |
| B: incomplete electrical requirements | Pass for honest incomplete handling: questions asked, no owner answers invented, final status partial; ten turns/eight attempts/15 SQL operations | `20261023T010835Z-eb07d2.jsonl` |
| C: independent live-session recall | Pass: nine turns/13 attempts/30 SQL operations; five retrieved decisions actually rechecked, including controller-enforced calls | `20261023T010809Z-8f9eac.jsonl` |
| E: injected supplier timeout once | Pass: recovered and completed research/cost operations; 21 turns/26 attempts/44 successful SQL operations | `20261023T010516Z-bd06e8.jsonl` |
| E: injected malformed tool arguments | Pass: original valid model proposal preserved separately, injector adds a bad key; model recovers; seven turns/six attempts/15 SQL operations | `20261023T010557Z-ca28a9.jsonl` |
| E: injected unavailable source | Pass for honest failure: partial result with missing actions; zero successful sponsor queries in this test | `20261023T010627Z-f787f0.jsonl` |
| E: real two-tool budget | Pass for safe stop: partial result after two tool attempts; no claimed source/engineering completion | `20261023T010711Z-27d414.jsonl` |
| E: stale context version | Pass: all five retrieved memories reported changed_context and received current checks; actual file and owner requirement unchanged | `20261023T010830Z-0a38e6.jsonl` |

A's task did **not** supply candidate pairs. Qwen searched the catalogue and chose its own candidates;
its failed alternatives received actual engineering failures, not model-assigned labels. The source was
real Zetaris access over the retained timestamped fixture, not refreshed live supplier inventory. Evaluation
D is the cost portion of A, not a separate invented model run. Missing flash datasheet/pinout/function
evidence is exercised in the genuine data; it stays unverified.

The repeat A run blocked six disallowed model proposals and had **zero failed executed tools**; the first
blocked 16 proposals and also had zero failed executed tools. These proposals remain in the audit and are
not hidden as successes. Repeat C blocked three proposals and included five controller-performed rechecks,
which are identified separately from model calls. Recorded summed model latency was 115.19 s for first A,
64.39 s for repeat A, 17.76 s for repeat C and 17.09 s for the context fault test. These are observations under
the local evaluation workload, not a performance guarantee.

Per-turn model IDs/digests, token counts, controller guidance/state, original outputs, compact views, queries,
operation actors, final facts and pass/fail criteria are retained. Bundles include
`.partlens/milestone4/20261023T010255Z-99ff6d/` and `20261023T010658Z-9f4fa2/`.

## Recall and reverification

New H-MEM memories retain BOM/line fingerprints, manufacturer/MPN identities and requirement context beside
their actual decision source. `reverify_decision` reads the stored item through the real design-scoped engine,
checks context, retrieves applicable source records again and calls the deterministic checker. It reports
unchanged, changed, changed_context or cannot_reverify. An unverified current result stays unverified. A
legacy item without context cannot prove equivalence of historical/current conditions. No historical memory
was rewritten to add evidence it did not originally have.

The controller executes omitted rechecks itself before accepting completion; model prose is irrelevant to
this gate. Every memory returned in the bounded retrieval must be addressed. Exact run-source retrieval
returns at most five records; this does not claim every stored decision was retrieved. Re-reading the retained
source does not refresh its supplier timestamp. Current reads and historical sources remain distinct.

The live C runs reopened the store in separate bridge processes. Actual source IDs, memory IDs and comparison
outcomes are in the records above. The stale-context test changes only an explicitly injected in-memory
version marker; it is not evidence that the actual BOM changed. Unknown or mismatched identity/context is
never inherited as a current pass.

## Trustworthy explanations and cost language

The factual result contains actual identities, requirements/sources, decisions/checks, sourcing, prices,
currencies, cost completeness, gaps and memory comparisons from tools. Model output can select known
decision/gap references. Free-form factual prose or invented references are rejected and replaced with
deterministic explanations; the original draft remains in the audit. Both passing A runs used that repair.
This demonstrates pipeline reliability, not that raw Qwen prose became reliable.

The renderer consistently distinguishes the original user-confirmed one board, hypothetical 60 boards,
covered component subtotal, conditional manufacturing subtotal, incomplete assembled cost and an unavailable
official quotation. A verified equivalence is never rendered as full application safety. The UI excludes raw
model drafts from Explanation and marks old result/cost contexts historical after relevant changes.

## Manufacturing and supplier coverage

| Recorded scenario | Component subtotal | Known conditional subtotal including covered components | Complete assembled total / quote |
|---|---:|---:|---|
| Owner: 1 board | USD 11.10 | USD 23.88 | Unavailable / unavailable |
| Hypothetical: 60 boards | USD 166.34 | USD 179.12 | Unavailable / unavailable |

No assembled-cost replacement savings were asserted. Decimal price breaks, MOQ/multiples, pooled stock and
attrition rules remain active. The dated JLCPCB Economic schedule and two official classification overlays
are separate from LCSC component prices. Thirteen matched-part classifications, service eligibility,
assembly procurement prices, PCB fabrication, joint counts, attrition and applicable process fees remain
unknown; taxes/shipping are not a completed quote. Unknown charges never become confirmed zero. Fee source
and retrieval time are retained. See [engineering evidence](ENGINEERING-REVIEW.md) and the Milestone 3 fee record.

The retained flash listing records zero stock; its substitutes remain unverified without engineering
evidence. J3/J4 are grounded as vertical 1×20 and J5 as 1×03, 2.54 mm through-hole headers; exact MPNs,
mechanical/mating details, finish and ratings remain unanswered. DigiKey/Mouser credential checks found no
configured access; no authenticated lookup or integration claim was made. Undocumented LCSC collection
remains disabled. Manufacturer identity/rating-domain protections, including UMW versus Torex XC6206,
remain enforced.

## Zetaris operational status

The owner-local Docker/WSL deployment was already running when inspected. No destructive recovery or dataset
registration was needed. `docker compose ps --all` reported healthy API/UI/driver/Postgres and completed
one-shot init/bootstrap jobs. The existing `./verify.sh` passed **all nine checks**, including its actual
login/query operation; sanitized evidence is `20261023T003623Z-6d8d32.jsonl`.

The normal PartLens smoke queried the existing approved dataset with HTTP 200, matching part IDs and server
timing: `20261023T003610Z-173282.jsonl`. The A/C/E records above then performed genuine model/controller-driven
queries bound to their own run record. SQL, returned identifiers, HTTP/execution status, response hashes
and server elapsed times are retained. The gateway supplies no server query/request IDs; null remains null.
Client UUIDs are never described as server-issued IDs. No volumes, accounts or namespaces were reset.

## UI verification

Native desktop interaction was unavailable; this milestone makes **no final visual-acceptance claim**.
Programmatic testing used actual Tk widgets, callbacks, worker/queue and real source/memory tools. It found
and fixed a real defect: a generic note handler hid both cost scenarios. It also ensures current checks from
reverification appear in Qualifications and current memory comparisons appear in Explanation.

The final programmatic run passed 19 rows/eight tabs, all three filter/detail pairings, source evidence,
conditional/hypothetical cost labels, original quantity and the actual recall button after closing/reopening
the memory process. Records:
`.partlens/ui-validation/20261023T005329Z-e7fafe/runs/20261023T005330Z-be46aa.jsonl` and
`20261023T005332Z-ee9e2f.jsonl`. The earlier cost-display failure is preserved at
`20261023T005251Z-93a61b/runs/20261023T005252Z-e6fb85.jsonl`. The runbook provides a manual acceptance checklist.

## Failures and testing

Earlier M4 runs were not relabelled as passes:

- `20261023T004458Z-9044f9`: token budget exhausted without compatibility checks.
- `20261023T004849Z-09dfe9`: context budget reached after some checks.
- `20261023T005125Z-45942a`, `20261023T005431Z-aed48f`, `20261023T005634Z-045a65`: redundant investigations
  and/or cumulative token exhaustion before sourcing/cost completion.
- `20261023T010054Z-395ff5`: model refused equivalence checks because it confused missing application conditions
  with prerequisites; recovery budget stopped it honestly.
- `20261023T010514Z-75e43f`: a missing question gap ID exposed a partial-rendering TypeError. Controlled questions
  now require a valid pending gap; unanswered/cancelled cases render safely. The corrected B run passed.
- Test record `tests-20261023T004804Z-1a86cc.txt`: a new cost test omitted the newly mandatory sourcing stage;
  171 tests passed/one failed. The test now executes sourcing before costing. No failure evidence was removed.

The initial full baseline independently passed **156 tests** (`tests-20261023T003544Z-2b42d3.txt`). Later suites
passed 172, 174, 175, 178 and 179 as regressions were added. Coverage includes skipped checks/early endings,
question provenance and units, missing gap IDs, cancellations, safe budget stops, disallowed tools, actual
H-MEM cold context checks, stale/current distinctions, malformed local responses, paid-provider prohibition,
structured factual rendering and cost/qualification UI behavior.

The prior 104-output deterministic scenario replay was independently reverified **104/104** at
`20261023T004621Z-aeb443.jsonl`. Later scope/gap explanatory wording is an intentional software change;
historical run files remain unchanged. Replay skips blocked proposals and memory-dependent reverification;
it does not claim to establish autonomous task completion or real memory operation. Actual operational
records above establish those separately.

Final full suite: **183 passed, no skips or failures**, 10.46 seconds,
`.partlens/validation/tests-20261023T012804Z-55a20e.txt`. All original safety assertions remain; live provider
failure tests now require explicit controlled scope and assert an audited partial result before any tool
execution rather than relying on an uncaught exception. Additional guards cover a wrong hypothetical
quantity, unmatched requested lines and mismatched quoted text/numeric values.

A fresh final-code deterministic scenario run matched **104/104** replay outputs:
`20261023T012638Z-44178f`, audit `20261023T012643Z-f1addb`, artifact
`.partlens/scenarios/milestone4-20261023T012638Z-9a7f76.json`.
The final UI smoke also passed after the later guards:
`.partlens/ui-validation/20261023T012815Z-06ead7/runs/20261023T012815Z-bc4bde.jsonl` and
`20261023T012817Z-e06404.jsonl`. It remains a programmatic result.

Workspace audit `20261023T012912Z-f578b6` found no configured-secret matches in inspected source/staged public
files, verified ignored credential/runtime paths and confirmed the original owner's record and retained
supplier fixture hashes unchanged. Local model digest/runtime and disabled paid inference were verified.
`.partlens/milestone4/acceptance-20261023T012915Z-91c4f7.json` indexes **31 observations across code iterations**,
including failures, and identifies the nine accepted evidence records used here. This is not a claim of
31 identical final-system trials or a broad model success rate.

The final repository/link check `20261023T013332Z-52f9aa` additionally scanned **all 56 staged index entries**,
confirmed no excluded artifacts or local secret/state files were staged, found no configured secrets in
their contents, and validated documentation links. `git diff --check` passed; Git reported only existing
CRLF-to-LF normalization notices. Existing staging was preserved because signing remained unavailable.

## Acceptance and remaining submission work

| Gate | Observation |
|---|---|
| Original tests | Full baseline retained; expanded suite green |
| Mandatory engineering actions | Controller completion/allowed-tool gates; unmatched requested lines stay missing |
| Memory rechecks | Actual tool execution forced for every retrieved item; explicit context/result comparison |
| Unguided local end-to-end run | Two observed passes, A/D, without supplied candidate pairs |
| Factual explanation | Validated structured references or deterministic replacement; drafts retained separately |
| Quantity and cost language | Owner one board, hypothetical 60, partial subtotals, unknown totals/quotes |
| Unknown fees/specifications | Retained as unknown/unverified, never inferred zero/pass |
| Incomplete tools/data | Observed honest partial results; bounded retries and recovery |
| Real H-MEM sessions | Persistence and cold live/model-controller recall/rechecks observed |
| Zetaris | Actual deployment verification and authenticated demo queries succeeded |
| UI | Programmatic end-to-end pass; final human visual acceptance remains open |
| Reproduction/demo | Current runbook, labelled distributable sample, architecture and three-minute script provided |

Qwen still generates disallowed/redundant proposals and unreliable free-form claims. The controller contains
those failures; broad unguided reasoning performance is not established by two demo passes. Before a credible
public submission: manually accept the final UI; clear supplier-data retention/redistribution terms or obtain
official authorized supplier access; resolve header/flash/application evidence; obtain actual manufacturing
eligibility/pricing inputs; address the owner's no-Cursor eligibility implication; and create a signed commit.
No fabricated complete quote or sponsor operation is used to fill those gaps.

SSH signing remains enabled. The agent is stopped/disabled and `ssh-add -l` cannot connect; no commit was
attempted and no signing bypass used. Completed changes remain staged/unstaged/untracked in the existing
working tree. The owner alone unlocks the signing key locally using the commands in Milestone 3. Credentials,
runtime weights, internal snapshots and run records remain ignored. No private data was inspected or copied.

Subsequent owner-authorized work added an operational official component source, genuine read-only Zetaris
queries of that data and conservative quantity-price arithmetic. This does not resolve supplier-data public
redistribution or unknown manufacturing terms. The original Milestone 4 evidence above remains unchanged;
see the separate [official API integration report](JLCPCB-INTEGRATION.md) for new operations and checks.

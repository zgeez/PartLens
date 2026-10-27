# Final design workflow and demonstration

2026-10-24. This milestone extends the 290-test baseline, preserves Existing BOM and all historical
evidence, and adds no circuit patterns, PCB layout, paid inference or private design access.

## Implemented

New CLI/UI sessions journal `design_interaction_mode`; older sessions retain their previous report shape.
Current unconfirmed gaps are ranked by feature and architectural impact: LED protocol/count/current,
runtime/charging, NFC function, microphone purpose, mechanical limits, quantity and budget. Runtime
failures raise energy questions. The initial delegated workflow asks two high-value questions and exposes
remaining assumptions for editing. It does not require an exhaustive questionnaire.

New interactive sessions use a strict native-array `propose_design_requirements` tool rather than
requiring Qwen to serialize a JSON array inside a string. Extra fields, duplicate parameters and invented
confirmation states are rejected; the existing typed/provenance gates still own every entry. The old
string tool remains for historical replay. The prompt requests one tool per turn; the controller still
validates every actual call independently.

Explicit typed answers are recorded by the controller through the existing quotation gate. Unanswered
dialogs, delegation and unitless engineering values cannot become confirmation. The actual earlier
**Monochrome** reply may be relayed verbatim; that is not a new owner answer. Numeric defaults remain
inferred. Model restatements of the same confirmed value preserve the owner's provenance; model text
cannot weaken established targets to erase failures.

**Edit and revalidate** records the operator's actual answer, invalidates prior current results, retains
previous circuits/failures, regenerates the prior architecture, compares a bounded converter trial and
reruns source/qualification/cost/configured memory operations. These are controller actions, with no extra
inference. The display clears during revision and exposes incomplete results if an operation fails.

## Independent tradeoffs

The original and higher-current converter references are checked against the same requirements; a trial
never accepts a complete design. Runtime options analyze larger capacity, lower average LED current,
reduced effective average-duty factor and the separately compared power architecture using Decimal.

For channel count N, average current i, rail V, runtime t, cell maximum B and capacity C, necessary ideal
LED-only capacity is `t*V*N*i/B` in consistent Ah/A units. Allowable ideal current per channel is
`C*B/(t*V*N)`. Relative load factor is bounded by allowable/current recorded average load. Calculation
locators retain circuit fingerprints and inputs. Numerical boundary trials round capacity up/current down;
they do not select real cell sizes or programming resistors. Cloned counterfactuals rerun architecture
checks without changing actual requirements, provenance or the current circuit.

Removing the optimistic LED-only failure leaves runtime **unverified**: real efficiency, total load,
usable capacity and temperature are missing. An average-load factor is not an absolute PWM duty; peak
current, present duty, scan ratio and brightness are unknown. Size, mass, charging/protection and cost
consequences remain qualitative/unknown. Every option is unapplied/unaccepted and requires confirmation
before changing a requirement. No battery availability/safety rating or fee is invented.

## BOM and presentation

Bounded official lookups use established identities/leads and existing deterministic qualification.
Sourcing triage distinguishes missing user conditions, manufacturer evidence, exact identity, incompatible
candidates, observed zero stock, supply constraints, failed supplier operations and unknown manufacturing
terms. A failed query is not zero stock or absence of a matching part. Rejected observations remain saved.

Overview, Requirements, Architecture, Alternatives, Generated BOM, Checks, Sourcing, Cost and Explanation
are readable. Provenance/Audit retain structured details and run/export paths. Requirements separate
confirmation from assumptions; components show role equivalence beside application status. Failures and
unverified screens precede conditional passes. Costs explicitly label partial bookkeeping subtotals: zero
known subtotal is not a free BOM. Currency, MOQ/multiples, assembly eligibility/fees and fabrication remain
unknown when unsupported. The same renderer writes internal `design-review.md` with JSON/BOM CSV.

## Preserved failures and recovery

| Record | Observation |
|---|---|
| `tests-20261024T183205Z-b82b04.txt` in `.partlens/validation/` | Baseline 290 passes, 16.30 s. |
| `tests-20261024T183750Z-ee603b.txt` | New test collection failed on an assignment expression; fixed, retained. |
| `tests-20261024T184531Z-346891.txt` | One test incorrectly expected runtime pass at a necessary bound. Implementation correctly retained unverified; expectation corrected. |
| `.partlens/final-workflow-live/new-design-runs/20261024T184017Z-ace4ab.jsonl` | Ollama unavailable; no model turn/cloud fallback. Failure banner corrected. |
| `20261024T184253Z-39238c` in that directory | Genuine 11-turn Qwen attempt, 123,496 tokens, 24 tool attempts; Monochrome confirmed, runtime unanswered. One official JLC request, 22 failed Zetaris queries; no sourced decisions/memory writes. Not operational completion. |
| `.partlens/runs/20261024T184803Z-1efa26.jsonl` | Zetaris smoke failed during startup. |
| `.partlens/runs/20261024T184932Z-451f4b.jsonl` | Actual SELECT after recovery: HTTP 200, five rows; locator `zetaris:9d396c7a-df0d-4a77-bcd8-9fd6861c3b7c`. Server IDs unavailable. |
| `.partlens/final-workflow-final/new-design-runs/20261024T185048Z-23a6f1.jsonl` | Two model turns, then local Ollama HTTP 500/tool parser XML failure; no architecture or source operations. |
| `20261024T185415Z-2db8d5` in that directory | Five model turns, actual Monochrome relay and unanswered runtime; local tool-parser HTTP 500 before architecture. Retained; motivated native-array requirement schema. |
| `.partlens/final-workflow-native/new-design-runs/20261024T185907Z-e40c87.jsonl` | One successful model turn then local parser HTTP 500. Native-array schema does not eliminate all local parser failures; no blanket reliability claim. |

The existing workspace Ollama launcher restored loopback inference/cloud disabled using installed weights.
Existing Docker Desktop and the stopped Zetaris driver were started. No dataset, account, namespace or
volume was recreated. Recovery record: `.partlens/validation/final-workflow/20261024T184724Z-494f4e.jsonl`.

## Validation and limits

The complete final suite passed **304 tests in 21.60 s**, no skips:
`.partlens/validation/tests-20261024T185739Z-817868.txt`. All 290 original tests remain, with 14 new synthetic
interaction/provenance/runtime/revision/triage/presentation cases. Mocked/offline tests are separate from
operational evidence. Final live/visual/check-out results are indexed below.
The preceding 303-test workspace and clean-checkout results are retained; they predate the native-array fix.

Independent final checkout `.partlens/partlens-source/20261024T185940Z-301633` contains 136 authored files.
Its editable install, locked Node dependencies, pinned public H-MEM setup, genuine bridge smoke, both
original deterministic examples and complete suite all exited zero: **304 passed in 20.25 s**, no skips,
local record `tests-20261024T190034Z-d46efa.txt`. Preparation journal:
`.partlens/source-preparation/20261024T185940Z-301633.jsonl`. The earlier 303-pass tree
`20261024T185432Z-3f5768` is preserved separately.

The previous corrected design and actual-owner revision still replay **12/12** and **10/10** against
current code, respectively: `.partlens/runs/replays/20261024T185550Z-dab6a4.jsonl` and
`20261024T185551Z-74493e.jsonl`. These are offline checks, not fresh integration or recall claims.

Scoped public/index audit `.partlens/validation/audits/20261024T191247Z-700598.jsonl` checked 136 authored
files and 56 older staged blobs: no configured-secret/personal-path matches or missing checked links.
The original retained supplier fixture hash is unchanged. Working-tree `git diff --check` passes; the
older staged index has not been refreshed into a release. Signing remains true/SSH, ssh-agent is stopped
and disabled, and no remote exists. No commit or publication was attempted. Final documentation-only
source synchronization retains the initial manifest and separately records final authored hashes.

See [DESIGN-DEMO.md](DESIGN-DEMO.md), [STANDALONE-READINESS.md](STANDALONE-READINESS.md) and the preserved
[architecture report](ARCHITECTURE-CORRECTION.md) for the original 22-role inventory, manufacturer sources,
temperature-product evaluation and historical replay limitations.

Cell/charger/protection, LED programming, peripheral/address/timing, exact land patterns and pin
connectivity remain unresolved. No complete accepted circuit, measured runtime, manufactured hardware,
schematic/ERC or assembled quotation is claimed.

## Final genuine local run and desktop acceptance

Run `.partlens/final-workflow-native/new-design-runs/20261024T190054Z-ec6c85.jsonl` began with only the
original generic badge description typed into the desktop. Actual usage reports `qwen3.5:9b` with no
fallback: **12 model turns, 125,418 input/output tokens, 18 tool attempts**. Twelve requests originate in
model turns; six are controller operations (typed answer recording plus generation/source/qualification/
cost/memory). One answered `ask_user` entry lacks its actor field in the shared older logger; its call ID
traces to the model turn. Two model requests were blocked: unsupported `inspect_design_patterns` and an
out-of-phase question. The model recovered using permitted tools and the native requirement-array tool.

The actual displayed questions were LED type and row count. The earlier owner reply **Monochrome** was
relayed; row count was cancelled/unanswered. Only LED type is confirmed. The model proposed 8 rows × 16
columns, 15 mA average/channel, 8 h, 500 mAh, 3.0–4.2 V cell envelope, 3.3 V rail, off-while-charging, tag,
sound-reactive microphone and quantity 10. These are **12 provisional assumptions**, not owner requirements.
Size, budget and remaining confirmation gaps are unresolved. The model rationale incorrectly calls that
matrix 64 elements; deterministic arithmetic correctly uses **128**. Rationale prose is not engineering
evidence, and no incorrect count enters the power calculation.

| Outcome | Actual result |
|---|---|
| Architecture | Nine reference blocks, including TPS63802; compared TPS63031 under unchanged requirements. No alternative satisfies complete acceptance. |
| Power | 0.5 A conservative controller reserve + 1.92 A proposed LED average = 2.42 A; both conditional converter screens fail. |
| Runtime | Optimistic LED-only bound about 0.3314 h versus proposed 8 h; fails. Other loads/losses make the actual profile unresolved. |
| Capacity counterfactual | Necessary ideal LED-only bound about 12,068.57 mAh; removes that failure to **unverified**, while current budget still fails. Not a selected/available/fitting cell. |
| Current/duty counterfactual | Ideal maximum about 0.62145 mA average/channel, about 0.04143 of the proposed average load; independent screens remove both failures but retain 57 unverified checks. Not an absolute PWM duty, brightness promise or accepted design. |
| BOM | 39 roles; 18 supplier-identified, 16 exact expected manufacturer/MPN matches, 13 verified role equivalences, 26 unverified. Every application remains unverified. Twenty-one roles have no selected supplier identity. |
| Costs | Model-proposed ten and hypothetical sixty; incomplete components and assembled cost. A 0.00 known bookkeeping subtotal is not a free/complete BOM. No confirmed badge quantity or currency is inferred. |

One fresh bounded official JLCPCB POST succeeded, HTTP 200, `cached=false`, retrieval
`2026-10-24T19:04:08Z`, client request `940975ab1f8ca371fa763b0d6319cccc`. **21/21 real Zetaris SELECTs**
succeeded, with result identifiers/SQL/status/digests in the internal journal. Example:
`zetaris:f252c67d-3c11-4839-995a-6bc51e1c5c1b`. **18 actual H-MEM decision writes** succeeded. These are
persistence results, not a new cold-recall demonstration. Real supplier records remain ignored/internal.

All eleven desktop tabs were opened and visually reviewed: Overview, Requirements, Architecture,
Alternatives, Generated BOM, Checks, Sourcing, Cost, Explanation, Provenance and Audit. Scrolling exposed
the lower-current trial and both ten/sixty cost scenarios. No public screenshots/video are claimed.

The editor then relayed the same actual Monochrome reply again, preserving its meaning rather than
inventing a numeric edit. The display visibly cleared during invalidation; prior failures were preserved.
Eight controller operations, **zero model turns**, **21/21 additional real Zetaris SELECTs** and **18 new
H-MEM writes** completed. Official observations were reused from the in-memory catalogue: **no new JLC
POST or disk-cache-hit event** occurred in this phase. Both original failures remain and acceptance is
still false. This demonstrates owner-driven revalidation, not a fresh owner answer or changed numerical target.

Initial artifacts: `.partlens/final-workflow-native/new-design/20261024T190054Z-ec6c85/artifacts/`.
Separate revision: `revisions/214/artifacts/` under the same root. Both include a readable requirements/
architecture/BOM/check/alternatives/cost comparison in `design-review.md` plus JSON and BOM CSV.
Journal reports exactly match their JSON exports, and readable exports exactly match the shared renderer:
`.partlens/validation/final-workflow/20261024T190839Z-270395.jsonl`. This establishes UI/CLI data parity;
it does not imply every offscreen provenance field was visually inspected.

The complete run plus desktop revision replays **20/20**, six question/blocked/memory/report operations
skipped, no mismatches: `.partlens/final-workflow-native/new-design-runs/replays/20261024T190748Z-2666b8.jsonl`.
Replay performs no live supplier, Zetaris or memory operation. Earlier failures and source trees remain intact.

After closing the saved New Design window, **Load demo** in Existing BOM completed visibly with 19
Easyduino rows: 15 matched supplier identities, two unmatched connector rows and two not-purchased rows.
Parent record: `.partlens/final-workflow-native/runs/20261024T185822Z-9b214b.jsonl`. This is a new
import/match visual retest, not a claimed fresh full Existing BOM model/recall evaluation. The complete
304-test suite retains its existing verification/cost/memory regressions. No earlier visual or run record
is replaced by these observations.
Observation record: `.partlens/validation/final-workflow/20261024T191137Z-67da63.jsonl`.

## Demonstration recommendation

Demonstrate incomplete idea → genuine clarification → preliminary role BOM → independently exposed
engineering failures → unapplied alternatives → actual-owner revision/revalidation → transparent unknowns.
Use the current [timed runbook](DESIGN-DEMO.md); warm the local runtime/services before narration. Native
Qwen/Ollama parsing failed in three preserved attempts after services recovered, and the subsequent run
succeeded. The native-array tool improves input structure but does **not** establish universal reliability.
Keep the clearly labeled deterministic contingency. Complete the final recording and owner approvals
before claiming a submission-ready public repository. Signing, eligibility, supplier permissions, exact
engineering contracts and complete manufacturing terms remain blockers.

# Milestone 2: live agent, engineering evidence and manufacturing costs

Status on 2026-10-22: **partially complete**. The first full live Claude workflow and second-session Meterless
recall succeeded. Real local Zetaris dataset queries now succeed; a Cursor AI coding task remains blocked. No PCB routing,
placement or full layout infrastructure was implemented. PartLens remains the Track 02 priority.

## Live execution versus the scripted reference

| Evidence | Observed result |
|---|---|
| Live baseline | `.partlens/runs/20261022T043042Z-84edf9.jsonl` |
| Model | Requested and observed `claude-opus-5-5`; fallback disabled on every request |
| Execution | 11 model turns, 40 recorded tool calls, no tool/provider errors |
| Requirements | Imported the demo, identified gaps, asked quantity; owner's exact answer `1` recorded at seq 13 |
| Quantity provenance | Binding `design.board_quantity == 1`, source `user:20261022T043042Z-84edf9#seq13`; annotation records chat-to-stdin relay |
| Qualifications | 1 verified equivalent, 5 unverified alternatives, 2 rejected alternatives; every result came from deterministic checks |
| Supplier evidence | Genuine retained timestamped LCSC fixture; source URLs and snapshot/review fingerprints recorded; no new endpoint collection |
| Live second session | `.partlens/runs/20261022T043403Z-d587d5.jsonl`; 6 tool calls |
| Recall | Retrieved `mem-14`, source `partlens:run:20261022T043042Z-84edf9:decision:f032395cc262bb75`; deterministic recheck agrees |
| Replay | First session 37/37 replayable outputs match; second 5/5; memory/interactive reads excluded |

The live agent qualified capacitor C105883 against the original specification, left flash alternatives
unverified, rejected the wrong-value/dielectric capacitor C191909 and rejected resistor C53109434's 25 V
rating against the original C25905's 50 V rating. It also reported the original flash C2843335 out of stock.
It kept full application qualification unverified without circuit evidence.

Outcome comparisons are preserved in `.partlens/evaluations/20261022T043612Z-c6abbc.jsonl` and
`20261022T043612Z-c9a4fe.jsonl`. Both automated live baseline and recall criteria are met; intermediate
tool-call order/count was not compared for equality.

The preserved Milestone 1 reference (`20261022T002237Z-0f69c8`) demonstrates quantity clarification, qualified
and unverified results, but its 18 recorded tool events do **not** exercise the rejection described in the
Milestone 1 narrative. That discrepancy is retained, not silently repaired. A new engineering-only scripted
reference (`20261022T042128Z-b6adcf`, recall `20261022T042128Z-b1b5ec`) demonstrates the rejection and real
cross-process memory. It leaves quantity unanswered rather than inventing a new owner's answer. Its 9
replayable outputs matched 9/9.

Manual review found ambiguous wording in the live second-session conclusion about a requirement change
reversing equivalence. The prompt now explicitly states that circuit conditions cannot relax the original
no-downgrade policy. A focused live audit (`20261022T043719Z-c70cc4`) produced a corrected explanation with
direct evidence URLs; its 6 replayable outputs matched 6/6. Its ad-hoc harness hit a Windows Unicode output
error **after** the final model turn was saved. The failure and recovery annotation remain in the record.
The CLI and validation helper use UTF-8 output.

The initial missing-authentication attempt (`20261022T034713Z-0cb09b`) is also preserved. It had no live tool
use and is not counted as a successful run. Later owner configuration enabled the actual successful runs.

## Zetaris and Mouser

**Zetaris is operational on the owner's local instance.** After the owner configured credentials, the supplied
`:8888/api/v1.0` route returned 404. The official SQL helper's gateway works on port 3000. Those two nonsecret
local settings (gateway/table) were corrected without modifying credential fields. An empty engine ID works.

| Evidence | Observed result |
|---|---|
| Server discovery | `20261022T055728Z-2156b4`: version 2.4.3.1, build cb88df0b |
| Real registration and queries | `.partlens/runs/20261022T060243Z-616750.jsonl` |
| Dataset | 64 retained supplier records; 19 approved BOM rows; container file SHA-256 values verified |
| Server-executed join | 17 placed lines returned, 15 supplier matches, two unresolved header lines |
| Normal CLI operation | `20261022T060306Z-c9f3aa`: HTTP 200, five matching demo supplier IDs, response digest and server elapsed time |
| Catalogue round trip | `20261022T060327Z-d4604a`: all 64 records equal the original fixture, including timestamps and engineering parameters |

SQL, execution/HTTP status, returned result identifiers and response digests are logged. The gateway supplies
execution timing but no server-issued query/request IDs; those remain null. Client-generated UUIDs are not
labelled server IDs. Default smoke SQL filters to the approved demo BOM's supplier IDs. This is a real
Zetaris operation over an internal timestamped fixture, not refreshed supplier availability.

Earlier missing-access records (`20261022T034717Z-13f21c`, `20261022T043754Z-afa68b`), 404 probes, unsupported
SQL and response-parser failures remain preserved. Restricted local paths were rejected. JSON Lines imported
only one record; the row-count checks correctly failed those attempts (`20261022T060152Z-e46ba5`,
`20261022T060214Z-2a139d`). Complete JSON arrays under the configured shared filesystem root succeeded.
Failed namespaces are retained. The reproducible setup script never downloads more supplier records or
overwrites existing namespaces. No cloud resources were created. Secret values and authorization data are
kept out of Git and recorded evidence. See [access details](SPONSOR-ACCESS.md) and [the runbook](MILESTONE-2-RUNBOOK.md).

A further **full live agent** engineering run used only the real Zetaris catalogue plus the explicit UMW
datasheet review (`20261022T060443Z-998b88`): four Opus model turns, eight tool calls, 19 successful real SQL
queries, no tool errors. It produced one verified, one rejected and one unverified alternative, storing
`mem-15`, `mem-16` and `mem-17`. A separate live session (`20261022T060513Z-b2c4b2`) used four model turns,
seven tools and 18 successful SQL queries. It retrieved the exact new source
`partlens:run:20261022T060443Z-998b88:decision:1db6296bd9554c26`, independently rechecked the resistor rejection,
and stored `mem-18`. Both observed `claude-opus-5-5`, with fallback disabled. The audit is
`20261022T060756Z-990823`.

These were engineering follow-ups, not replacement baseline runs. No new quantity answer or cost requirement
was manufactured; the owner's original one-board provenance stays in `20261022T043042Z-84edf9#seq13`.
The second session correctly separates a 25 V versus 50 V equivalence failure from application safety,
which remains unknown. Live remote-query locators change on each fetch, so no identical-digest replay is
claimed for these new remote sessions. The original fixture baseline and its replay results remain preserved.

Standard CLI/UI sessions also bind remote query evidence to their own recorder, including through reviewed
catalogue overlays. Sources are bound independently so a later session cannot redirect an earlier session's
query events. A real standard-session check (`20261022T060959Z-825a01`) recorded all 18 SQL operations and
the same verified/rejected/unverified outcomes. It was deterministic validation, not another live LLM run.

Mouser's official Search API was investigated as the permitted alternative to further undocumented LCSC
collection. No authenticated Mouser operation occurred. See [access research](SPONSOR-ACCESS.md).

## Engineering corrections

The supplier listing for U1 is UMW XC6206P332MR. Its official datasheet supports an 8 V electrical-characteristic
input maximum and a separate 9 V limit; Torex's distinct device operates over 1.8-6 V. Manufacturer identity
therefore matters to interpreting the apparent discrepancy. The exact review, source links and fetch limits
are in [the engineering review](ENGINEERING-REVIEW.md).

The implementation now separates original-specification equivalence from application compatibility, requires
manufacturer identity for non-passive MPN equivalence, separates rating domains, and retains capacitor
voltage/dielectric/tolerance/temperature checks. Missing DC-bias, effective-capacitance, ESR, ripple, thermal
and circuit evidence remain gaps. A lower rating alone does not establish an unsafe application.

## Manufacturing cost coverage

Working coverage includes exact decimal price breaks, MOQ/order-multiple rounding, attrition, shared purchases
across BOM lines, aggregate stock constraints and optimiser exclusion of unavailable or unclassifiable choices.
Unknown classifications/fees no longer default to free. Setup, stencil, loading, placement/joint labor and PCB
fabrication are distinct terms. Solder joints are not inferred from component placements.

JLCPCB fee evidence and two service-specific classifications are retained separately in local reviewed files.
C1525 is Basic; C347376 is Extended. Classification and fee services must match, and stale classification
evidence cannot support a complete estimate. Remaining classes and actual board eligibility are unknown.

For the owner's **1-board** live run:

| Cost view | Result |
|---|---|
| Component subtotal, 15 priced lines | USD 11.10; incomplete sourcing/BOM coverage |
| Known conditional subtotal including sourced setup/stencil/loading | USD 23.88 |
| Estimated assembled total / per board | Unavailable; incomplete |

The subtotal includes MOQ purchases, not just the parts physically used. Two header lines remain unidentified,
the flash has no stock, and 13 classifications are unknown. Joint count, service component prices, attrition,
PCB fabrication, manual/X-ray applicability and other charges still need evidence/quotes. No full assembled
cost or complete saving is claimed. Developer quantity-sensitivity scenarios are labelled as scenarios, not
owner requirements, in `20261022T043021Z-af58db`.

## Interface and Cursor

`partlens ui --catalog .partlens/cache/lcsc-easyduino.json` opens the local desktop workflow. It provides demo
import, deterministic/live review, user clarification and a new session for recall, with parts, requirements,
qualification scopes, source evidence, sourcing, conditional costs, explanations and audit records.

Programmatic smoke verification loaded 19 rows, checked all 8 tabs and verified selecting a part opens evidence
without inventing quantity (`20261022T043022Z-e1e87f`). Interactive visual inspection could not complete because
computer-use app approval timed out. This is a remaining verification limit.

Cursor was absent from discovered app/window inventories and the standard installation path. **No Cursor AI
coding task was completed.** The concrete pending task is documented in [access research](SPONSOR-ACCESS.md).
Codex implementation does not satisfy that requirement.

## Tests, records and signing

Latest suite: **102 passed**, including actual H-MEM engine persistence/recall. The preserved test record is
`.partlens/validation/tests-20261022T060936Z-25e362.txt`. The earlier 100-pass record remains at
`.partlens/validation/tests-20261022T060502Z-d1c938.txt`, and the earlier 95-pass record remains at
`.partlens/validation/tests-20261022T044006Z-334033.txt`. New coverage checks the observed Zetaris gateway
headers/data format, malformed column names, server timing without fabricated IDs, and recorded invalid configuration.
Two additional cases verify query-event isolation across independent sessions with and without review overlays.

The initial baseline had 34 passes and 6 temporary-directory permission errors; workspace-local temporary
directories then restored all 40 original passes. Intermediate failures from changed cost semantics, a wrong
test price expectation, a synthetic MPN mismatch and the UI tool-argument collision were retained and corrected.
New tests cover these regressions along with provider controls, provenance, rating/identity gates, price/stock,
classification freshness/service matching and Zetaris failure normalization. No failure record was deleted.

Live replay audits are `20261022T043550Z-2873a3`, `20261022T043551Z-78735c` and
`20261022T044005Z-7544bd` under `.partlens/runs/replays/`. They do not claim to replay LLM reasoning or memory.

SSH signing remains enabled. `ssh-add -l` could not contact an unlocked agent at the signing check. No commit
was attempted, no passphrase was handled and no signing/hook bypass was used. Changes remain uncommitted.

## Remaining hackathon blockers

- A meaningful Cursor AI coding task with evidence of that workflow.
- Interactive UI visual verification and an unlocked signing key for a signed commit.
- Supplier-data licensing review; Mouser access/terms review before operational use.
- Flash sourcing, header identities, circuit conditions and remaining manufacturing classifications/quotes.

Use [the runbook](MILESTONE-2-RUNBOOK.md) to resume these operations. Do not call the whole milestone complete
while the Cursor requirement remains unmet.

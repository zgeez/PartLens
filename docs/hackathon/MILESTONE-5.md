# Milestone 5 — official supplier end-to-end demonstration

The bounded local Qwen research workflow completed using authenticated official JLCPCB component reads,
actual Zetaris queries and real Meterless H-MEM persistence. A separate local-agent session recalled five
decisions and the controller enforced fresh deterministic rechecks. Engineering and manufacturing
uncertainties remain explicit. This is a working internal demonstration, not a complete manufacturing
quotation, procurement guarantee or confirmed hackathon submission.

Operational records use UTC identifiers; the principal evaluation ran on October 22, 2026 in the owner's
America/New_York timezone. This report was completed October 23 locally. Internal artifacts below are
ignored and are intentionally absent from a public clone. Historical reports and failures remain intact.

## What changed

- Official-source discovery now follows at most six explicit code leads per search from the existing
  retained internal fixture, then retrieves official records. No candidate pairs were supplied in the
  evaluation prompt or harness. Lead specifications, prices, stock and qualification do not transfer.
- `--jlc --zetaris` uses the official catalogue through real read-only Zetaris queries; it no longer
  automatically adds the historical Zetaris supplier fixture as a second source. An explicit `--catalog`
  remains an operator-selected source, not an implicit official fallback.
- The official client enforces per-session HTTP and distinct-code budgets in addition to bounded batches,
  timeouts, cache age and retry/backoff. Retries count against the HTTP budget. Response metadata logging
  uses a non-secret allowlist; cookies, authorization and arbitrary headers are not recorded.
- Lossless supplier-operation journals support offline deterministic replay. Decimal parameters, evidence,
  source identities, price intervals and unknown terms survive round trips. Missing, altered or differently
  ordered observations fail closed. Replay does not assert a new supplier, Zetaris or memory operation.
- The existing desktop shows readable commercial uncertainty and both cost scenarios before long evidence
  details. A separate preview rechecks the actual live-agent selections with new official reads; it is
  labeled deterministic and makes no new model call.

Core changes: `src/partlens/sources/jlcpcb.py`, `sources/audit.py`, `session.py`, `replay.py`, `cli.py`,
`ui.py`; evaluation/preview scripts and eleven synthetic regression cases in `tests/test_milestone5.py`.
No new core runtime dependency or layout functionality was added.

## Genuine local model execution versus scripted reference

Bundle: `.partlens/milestone5/20261023T030853Z-2d6982/`.

| Observation | Research A | Cold recall C |
|---|---|---|
| Run ID | `20261023T030853Z-988c1b` | `20261023T031043Z-53c2ef` |
| Actual model returned by local provider | `qwen3.5:9b` | `qwen3.5:9b` |
| Model turns | 14 | 7 |
| Tool attempts, including blocked proposals | 31 | 10 |
| Blocked model proposals | 10 | 1 |
| Executed tool failures | 0 | 0 |
| Actual official HTTP attempts | 4 | 6 |
| Successful actual Zetaris queries | 58 | 30 |
| H-MEM Node process | 47268 | 13012 |
| Workflow operations | Complete | Complete |

Per-session ceilings: 32 turns, 60 tool attempts, 300,000 cumulative tokens, 12 HTTP attempts including
retries, 40 distinct codes and 25 codes per request. Fresh cache namespaces were used for A and C.
No paid call or cloud fallback occurred. The eight executed research checks were model-selected; controller
guards rejected invalid/redundant proposals without treating them as successful operations.

Research imported the approved Easyduino BOM, identified missing requirements, matched official parts,
discovered and checked alternatives, checked sourcing, compared quantities and persisted eight decisions:
**three verified equivalences, one rejection and four unverified alternatives**. Candidate checks include:

- L1 `jlcpcb:C71629` and L11 `jlcpcb:C965250` / `jlcpcb:C2791532`: verified original-specification
  equivalence; application suitability unverified because circuit conditions are missing.
- L1 `jlcpcb:C1557`: rejected because 27 pF does not meet the original 100 nF requirement. Its higher
  voltage rating cannot compensate for the wrong capacitance. The application check also has an evidenced
  nominal-value failure; a rejection here is justified without inventing operating voltage.
- Flash alternatives and L1 `jlcpcb:C106994`: unverified where parameters, exact package/land pattern,
  pinout, recommended supply, timing or functional evidence are absent. No model text supplies a pass.

The previous deterministic reference still reproduces **104/104 outputs**. The live run is assessed by
completed outcomes, provenance and independent checks, not matching its intermediate sequence. One research
trial and one cold session establish this observed success, not a general autonomous reliability rate.

The original A evaluator incorrectly required every application outcome to be unverified, so `A.json`
reports `passed: false` despite completed operations. That would wrongly reject an evidenced nominal-value
failure. The original report was preserved. Regression-tested reassessment permits evidenced application
rejection while forbidding unsupported application passes; both A and C pass the corrected gates.
Correction record `20261023T031346Z-60d653` and its separately appended reassessment file changed no
engineering result and made no model or supplier call.

## Operational supplier, Zetaris and memory evidence

All ten evaluation supplier requests succeeded with HTTP 200 and validated business success. JLCPCB server
trace examples: A `ea46eea781bc2c08bf37a55c4a883184`; C `30234e1d41bd21f8707fb452203f30d5`.
The complete requested code sets, response fields, timestamps, response digests and traces are in the runs.
Only the approved HTTPS POST `getComponentDetailByCode` was called. No private library, list extraction,
PCB/PCBA quote, upload, order or purchasing operation was performed.

The **88 actual Zetaris SELECTs** in A/C operated on normalized official supplier observations. Session
tools related the returned identities and parameter/classification evidence to the imported BOM; this
does not claim a new persisted supplier table or a SQL join against the legacy BOM table. Runs contain exact SQL, client
query identifiers, HTTP/execution status, result identifiers/digests and server elapsed times. The gateway
does not expose a server query/request ID; those fields remain unknown. The existing deployment and demo
namespace were preserved; no DDL or dataset reset was used. Local CSV export is not counted as integration.

Eight A decisions were persisted through the real H-MEM bridge. C reopened the same store in a different
Node process, retrieved `mem-1` through `mem-5`, and fetched applicable current official evidence. Qwen
requested recall but did not select the five reverification calls; the **controller executed all five**:

- `mem-1`, `mem-2`, `mem-5`: unchanged after fresh deterministic checks.
- `mem-3`, `mem-4`: `cannot_reverify`, because fresh checks still lack required engineering evidence.

Persistence, recall and successful qualification are distinct outcomes. The latter two items did not gain
verified status from historical memory. Offline replay excludes memory operations; the actual C run,
not replay counts, proves memory retrieval and current reverification attempts.

## SDK and commercial investigation

Reviewed approved PDFs, official [basic rules](https://api.jlcpcb.com/docs/start),
[signing](https://api.jlcpcb.com/docs/api-request-signature),
[API list](https://api.jlcpcb.com/docs/api-list),
[SDK guide](https://api.jlcpcb.com/docs/sdk-usage-guide) and
[agreement](https://api.jlcpcb.com/docs/agreement), plus actual response fields and safe response metadata.
Targeted official-domain searches did not supply missing field definitions.

The owner-provided root SDK archive is ignored in Git and Cursor. It contains `Business SDK.jar`, Maven
artifact `com.szjlc.overseas:overseas-openapi-sdk-java:1.0.6-SNAPSHOT`, with compiled component DTO/client
classes but no bundled source, Javadocs or field-definition documents. It was not executed, decompiled or
copied into PartLens. `javap` was unavailable; no claim of inspecting Java public method signatures is made.
Archive/JAR hashes and entry inventory: `20261023T031346Z-68086d`.

Actual inspected response metadata included Content-Type and Date, with no currency/locale field among
the allowlisted headers. This does not establish absence of every possible undocumented header. No guessed
currency controls were sent. Body and documentation omissions remain unresolved:

| Term | Current treatment |
|---|---|
| Price currency | Unknown; neither USD nor CNY assumed |
| MOQ / order multiples | Unknown; first price-tier quantity is not treated as MOQ |
| `libraryType` | Raw value retained; Basic/Extended mapping is corroborated inference, not a documented exhaustive enum |
| `assemblyComponentFlag` | Raw boolean retained; does not establish assembly eligibility |
| `stockCount` | Timestamped observation, not reservation or procurement guarantee |
| `solderJointCount` | Part-level observation, not complete board-level billable joints |
| PCB/PCBA quote API | Listed publicly, not among the four approved component permissions; required board/process inputs unavailable; not called |

[Support questions](JLCPCB-SUPPORT-QUESTIONS.md) are prepared, not sent. API approval does not confer
permission to redistribute supplier records or imply endorsement; public-data/branding permission remains
unresolved. Real responses, internal recordings and the SDK stay out of the public repository.

## Engineering and cost scope

Manufacturer specifications, supplier assertions, source-query provenance and inferred assembly
classification remain separate. The existing exact-manufacturer/MPN review for the UMW XC6206 must not
be transferred to Torex or an unconfirmed expanded manufacturer label. Torex's recommended range and
absolute maximum are distinct; the earlier supplier 8 V discrepancy is not resolved by substituting a
different manufacturer's datasheet. See [engineering review](ENGINEERING-REVIEW.md) and the original
[integration report](JLCPCB-INTEGRATION.md). The official-only run does not inherit the old review as proof.

Capacitor equivalence checks retain capacitance, voltage rating, dielectric and tolerance evidence.
Application qualification still needs applied voltage, temperature, DC-bias/effective capacitance,
ESR/ripple and physical fit where relevant. A lower-rated replacement failing no-downgrade equivalence
does not automatically establish danger in an uncharacterized circuit.

The owner's **one board** remains bound to the original quoted `1` at
`user:20261022T043042Z-84edf9#seq13`. **Sixty boards** is explicitly hypothetical. Both scenarios use
official inclusive price intervals and Decimal arithmetic at nominal demand. Missing currency/MOQ/multiples
prevent a purchase quantity, currency-qualified component total and assembled quotation. Per-line nominal
arithmetic is visible separately and is not converted to USD or added to USD assembly fees.

The dated JLC Economic fee schedule remains sourced and conditional. Board/service eligibility,
fabrication, attrition, actual billable joints, manual work, X-ray, panel/size and other quote applicability
remain unresolved; shipping/tax are excluded. Supplier joint counts and classification inference do not
close these gaps. Flash stock zero and unidentified headers remain sourcing risks. Both assembled totals
and savings are unavailable; no partial subtotal is advertised as full-board savings.

## Verification, visual acceptance and history

- Baseline: **234 passed**, `tests-20261023T025823Z-e38c63.txt`.
- Final code: **245 passed**, no failures/skips, 12.69 seconds;
  `.partlens/validation/tests-20261023T032336Z-e92ebf.txt`.
- Historical reference: **104/104**, zero skips, replay `20261023T032629Z-960e5b`.
- A source-observation replay: **21/21**, ten blocked proposals skipped;
  `20261023T032525Z-3db570`.
- C source-observation replay: **3/3**, seven memory/blocked operations skipped;
  `20261023T032526Z-5e2ffa`. This is not five memory checks replayed.
- Desktop deterministic preview: **14/14**, zero skips; `20261023T032629Z-8d6bd2`.
- Distributable synthetic deterministic fallback succeeded, explicitly no live integrations:
  `.partlens/sample-runs/20261023T032527Z-fe190f.jsonl`.

Actual native Windows visual inspection used the computer-use skill on the existing desktop. Requirements,
parts, selected exact identities/timestamps, qualification filters/matrix, classification confidence,
sourcing, both cost scenarios, audit and recalled/current comparisons were inspected. An initial cost
layout hid scenario headings behind details; the overview fix passed a regression and visual recheck.
The owner interrupted an earlier inspection with Escape; automation stopped and resumed only after
`continue`. This is acceptance on one Windows display, not cross-platform or accessibility certification.

Final preview record: `.partlens/milestone5-ui/20261023T032305Z-6791c7/runs/20261023T032305Z-2438d4.jsonl`.
Its actual button-triggered new session `20261023T032537Z-c68b2d` retrieved five items and rechecked three
distinct selections: two unchanged, one still unverified. The preview makes no model call and is separate
from the genuine A/C evaluation. Native visual/security audit: `20261023T063750Z-2fc942`.

All negative records remain, including the original evaluator false result, blocked model proposals and
a final reference-replay setup error caused by a nonexistent review path (`20261023T032615Z-0edd2a`).
The correct historical source paths were recovered from its original run; the subsequent 104/104 result
did not rewrite that failure. Prior milestone failures and original staged changes were preserved.

Final post-document audit `20261023T064115Z-c30662` inspected 108 public files, all 56 staged blobs and
22 new operational/cache files: no configured-secret matches or excluded staged artifacts. Secret/local
state and the owner SDK archive are ignored, retained fixture hash unchanged, and `git diff --check`
passed. New report/runbook/support-question local links passed in `20261023T064117Z-e2da96`.

## Signing and remaining submission blockers

SSH signing remains `commit.gpgsign=true`, `gpg.format=ssh`; the configured public key is
`~/.ssh/id_ed25519_signing.pub`. The Windows signing agent is stopped/disabled. No commit was attempted,
no bypass/hook suppression occurred, and no passphrase was requested or handled. Work remains uncommitted.
The owner can enable/start the existing agent in an elevated PowerShell:

```powershell
Set-Service ssh-agent -StartupType Manual
Start-Service ssh-agent
```

Then, in the owner's normal PowerShell, unlock the configured key locally:

```powershell
ssh-add "$env:USERPROFILE\.ssh\id_ed25519_signing"
```

The owner alone enters the passphrase. Commit only after signed operation works; preserve changes if it fails.

Remaining blockers are commercial field definitions and a real manufacturing quotation, missing circuit
and IC evidence, header identities/flash supply, written public-data/branding permission, local signing-key
availability, and hackathon eligibility confirmation. **Cursor was not used**, as directed; no claim that
the earlier Cursor-related eligibility condition is satisfied. No HackOS entry was submitted. See the
[three-minute runbook and architecture](MILESTONE-5-RUNBOOK.md).

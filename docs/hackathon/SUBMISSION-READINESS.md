# Submission readiness — PartLens

Latest finalization status: [HACKATHON-FINALIZATION.md](HACKATHON-FINALIZATION.md) and
[STANDALONE-READINESS.md](STANDALONE-READINESS.md) record the current 318-test working/independent
baseline, separate source-only candidate, bounded local successes/failures, CMD service recovery and
remaining owner actions. Earlier counts/checklists below remain historical. No publication or submission
readiness is claimed; signing, eligibility, permitted final recording and owner approval remain unresolved.

**Status: materials prepared locally; NOT submission-ready.** No HackOS submission or GitHub publication
has occurred. Signing, a repository destination, permitted public demo evidence, eligibility confirmation
and owner approval remain outstanding. No Milestone 6 features or working architecture changes were made.

This report uses UTC evidence IDs. See [MILESTONE-5.md](MILESTONE-5.md) for the genuine end-to-end trial,
its exact model/controller attribution, preserved negative evaluator result and engineering/cost limits.

## Prepared materials

| Material | Location / status |
|---|---|
| Public project explanation, architecture, install/local setup, tests, limits and licensing | [README](../../README.md), refreshed for the official supplier workflow |
| Narrator script, approximate timings, precise clicks, executable commands, capture checklist and labeled contingency | [SUBMISSION-DEMO.md](SUBMISSION-DEMO.md) |
| Concise presentation outline | [SUBMISSION-PRESENTATION.md](SUBMISSION-PRESENTATION.md); outline only, no slide deck claimed |
| HackOS copy, sponsor attribution, pre-existing work and owner fields | [HACKOS-DRAFT.md](HACKOS-DRAFT.md); draft, not submitted |
| Concise commercial/permission inquiry | [JLCPCB-SUPPORT-MESSAGE.md](JLCPCB-SUPPORT-MESSAGE.md); not sent |
| Detailed commercial follow-up | [JLCPCB-SUPPORT-QUESTIONS.md](JLCPCB-SUPPORT-QUESTIONS.md) |
| Licences, provenance and pre-existing references | [THIRD_PARTY.md](../../THIRD_PARTY.md), [DISCLOSURE.md](DISCLOSURE.md), adjacent Easyduino licence |

## Verified implementation and integrations

- Full freeze suite: **245 passed**, no failures or skips, 10.51 seconds;
  `.partlens/validation/tests-20261023T065651Z-67bd72.txt`.
- Isolated public-source reproduction: a new virtual environment installed `.[dev]` and executed the
  synthetic sample without credentials or owner data. Initially 232 tests passed and 13 optional tests
  skipped. After the documented `npm ci`/pinned H-MEM setup, 240 passed and five optional SDK tests skipped.
  Installing `.[dev,llm]` enabled the synthetic cloud-adapter tests: **245 passed, no skips**, 9.35 seconds.
  No paid inference was called. The package imported from the isolated public source, not the original
  editable checkout. Copy/manifest: `.partlens/submission/20261023T070823Z-caa5f2/`; final test log:
  `public/.partlens/validation/tests-20261023T071212Z-7b3ce9.txt`. Earlier skip results are preserved.
- Official JLCPCB smoke: genuine uncached authenticated component read, HTTP 200 and valid business result;
  `20261023T065726Z-85a481`, server trace `1cff9c52e4e3421180d2bfe787eaf6cf`.
- Zetaris smoke: actual configured legacy-demo table SELECT, HTTP 200, five returned identities,
  273 ms; `20261023T065726Z-e6b50d`, client query `4e13817f-7453-4f77-a736-13d5536ffebe`.
  This smoke is not a new official-source autonomous evaluation; Milestone 5 A/C proves that separately.
- Meterless smoke: actual `meterless-hmem-reference` bridge opened successfully. A bridge status check
  alone is not proof of persistence/recall; the real Milestone 5 cold sessions provide that evidence.
- Local model metadata inspection succeeded without inference: `qwen3.5:9b`, Q4_K_M, native tools
  capability, installed digest recorded in `20261023T071018Z-567f6e`.
- Replays revalidated for the freeze: historical **104/104** (`20261023T070910Z-1c71f7`), research
  **21/21** with ten blocked proposals skipped (`20261023T070909Z-87e1c3`), cold **3/3** with seven
  memory/blocked operations skipped (`20261023T070909Z-9558ca`). No new live model run is claimed.
- Previously validated native Windows UI: exact identities/evidence, engineering status filter/matrix,
  requirements, source risks, one/60 cost overview, audit and real new-session recall/rechecks. Existing
  desktop architecture remains unchanged. The current preparation does not claim a newly recorded video.

The bounded official-source trial remains A `20261023T030853Z-988c1b` and cold C
`20261023T031043Z-53c2ef`: eight decisions, ten successful official HTTP requests, 88 successful actual
Zetaris queries, eight memory writes, five recalled items and five controller-enforced fresh rechecks.
Three rechecks were unchanged; two could not reverify because evidence remained missing. Qwen selected
the research actions and recall; the controller selected the mandatory cold-session rechecks.

The original evaluator's false result was preserved and corrected separately; no source/check result was
rewritten. Replays establish deterministic reproducibility, not fresh service or memory operations.

README installation/sample/full-test commands were actually exercised in the isolated copy. UI/evaluation/
preview flags were checked against their installed CLI parsers; the final-explanation display command
successfully read the actual preserved structured result. No new runtime code or UI behavior changed
during submission preparation. The complete click workflow was previously exercised and inspected natively
in Milestone 5; a new final recording has not been made. Documentation links passed in
`20261023T071301Z-1a7549`; `git diff --check` passed (existing CRLF normalization notices only).

## Public repository and safety

The working branch is `main`, with no commits and no GitHub remote at the initial preparation audit.
Existing staged additions, later working changes and untracked implementation files are preserved. A new
GitHub URL, remote, push or publication has not been invented. All required public files must be included
in the eventual audited signed commit; the old staged Milestone 1 subset is not the finished implementation.

Local `.env.local`, `.partlens/`, supplier responses/snapshots, owner SDK, vendored engine/model/runtime
and excluded private work remain ignored. Do not use `git add .` or copy an entire workspace into a public
archive. Audit a scoped manifest and all staged blobs before commit. Original code/fixtures and the open
Easyduino BOM are distributable under their respective licences; real supplier data is not assumed so.

Scoped public review `20261023T070823Z-c5ebf5` inspected 107 approved files and all 56 originally staged
blobs, with no configured-secret matches or owner personal paths/contacts. The review copy contains no
`.env.local`, private designs, real supplier snapshots, SDK or internal run records. A final source-only
review archive is prepared at `.partlens/submission/20261023T070823Z-caa5f2/final-public-source.zip`;
its manifest and final audit are retained alongside it. This is a local review artifact, not a signed
release, GitHub publication or redistribution of supplier data. Later signing/publication must use the
reviewed manifest and repeat the staged-content check, rather than assume the old index is current.

Public demo fallback is synthetic and deterministic. Operational run files and owner configuration are
absent from a clean public checkout by design. Sponsor setup requires independently authorized access;
the authentic owner-local reproduction additionally requires non-public quantity/lead/fee evidence.

## Required owner actions and blockers

1. **Unlock signing locally.** The observed Windows ssh-agent service is Stopped/Disabled and `ssh-add -l`
   cannot connect. In elevated PowerShell:

   ```powershell
   Set-Service ssh-agent -StartupType Manual
   Start-Service ssh-agent
   ```

   Then in the owner's normal PowerShell:

   ```powershell
   ssh-add "$env:USERPROFILE\.ssh\id_ed25519_signing"
   ```

   Enter the passphrase locally only. `commit.gpgsign=true`, `gpg.format=ssh` remain enabled. No signing
   bypass, hook suppression or private-key/passphrase handling is permitted. The agent can audit/stage and
   create a signed commit after the key is available; if signing fails, preserve work and stop that attempt.
2. **Choose the GitHub destination and approve publication.** No remote is configured. Provide/approve
   the intended repository and visibility; publish only the reviewed signed commit. This is separate from
   preparing files locally and does not authorize a HackOS submission.
3. **Resolve demo-data permission.** Review/send the prepared JLCPCB message through the authorized
   channel. Do not publish internal responses, screenshots or an unlisted real-data recording on an
   assumption of permission. A synthetic public demonstration can be used, with its actual limitations.
4. **Confirm current organizer rules/eligibility.** Cursor was not used. Do not tick a Cursor compliance
   field or represent Codex as Cursor. Track 02 and any sponsor requirements need organizer confirmation.
5. **Record and approve the final demo.** Use the exact runbook and mode labels, inspect all frames and
   complete video/repository/team fields privately. The narrator script and evidence checklist are ready;
   no captured/edited final video or hosting URL is claimed.
6. **Approve submission explicitly.** Review the draft and final commit/video. No HackOS action will occur
   without approval. Commercial definitions, circuit/IC evidence and complete manufacturing quotation
   remain product limitations even if the organizers accept an honestly scoped prototype.

## Final submission checklist

- [x] Preserve implementation/history and prohibit new feature scope, paid inference and Cursor.
- [x] Prepare README, architecture, quick-start sample, configuration and licensing guidance.
- [x] Prepare timed narration, click sequence, contingency and capture evidence list.
- [x] Prepare presentation outline and transparent HackOS draft.
- [x] Prepare unsent support message and disclose missing commercial semantics.
- [x] Re-run full suite and supported read-only integration smokes.
- [x] Verify isolated public-source installation/sample, full optional test setup and documentation/security scope.
- [ ] Owner unlocks signing; audited final content receives a verified signed commit.
- [ ] Owner approves destination; repository published and link/commit verified.
- [ ] Permitted final demo/video captured, reviewed and linked.
- [ ] Organizer eligibility/Cursor condition resolved accurately.
- [ ] Owner approves final form and submission.

Until these remaining items are resolved, the project is **not marked submission-ready**.

## Subsequent owner-authorized New Design expansion

Current scope pointer: the later [final workflow report](FINAL-DESIGN-WORKFLOW.md),
[New Design demo](DESIGN-DEMO.md) and [standalone readiness report](STANDALONE-READINESS.md) supersede
earlier implementation counts below. The current suite has 304 passing tests. Earlier results remain
historical. Signing, supplier permissions, Cursor eligibility, release review, final recording and owner
publication approval remain unresolved; this update does not mark the submission ready.

The owner superseded the implementation freeze with a Design-from-Idea request. The preceding checklist,
245-test result and source ZIP remain historical evidence of the earlier scope, not acceptance of the new
feature or a current release archive. See [DESIGN-GENERATION.md](DESIGN-GENERATION.md) for generated-BOM,
local-agent, fresh supplier/Zetaris, cold memory, regression and engineering-limit evidence.

Current source changes are uncommitted; signing remains enabled but the owner's agent is unavailable.
Before publication, repeat the current source/staged audit and clean-install validation, prepare a new
review archive, adapt the pitch/demo if presenting New Design, visually accept its full result workflow,
and resolve the same owner/eligibility/data-permission prerequisites above. The new design is preliminary
with failed power/runtime constraints and incomplete costs; it cannot be presented as validated hardware.
No repository was created, remote added, old archive replaced or HackOS entry submitted.

New Design validation: 275 owner-local tests passed; isolated Python-only install/examples passed with
266 tests and nine optional H-MEM skips. Source-checkout service setup remains required for the bridge.
Working-tree whitespace is clean; the older staged index still has an extra blank EOF line in
`src/partlens/session.py` and is not the current release. Refresh and audit it after owner-local signing
becomes available. Historical/index failures are retained rather than described as completed release checks.

## Subsequent architecture-correction milestone

The owner subsequently authorized bounded redesign, sourcing completion, a second product and full
desktop acceptance. Current observed results and independent source-checkout preparation are in
[ARCHITECTURE-CORRECTION.md](ARCHITECTURE-CORRECTION.md). The prior 275-test expansion is historical;
the current owner-local suite has 290 passes. The converter trial clears its supported budget screen
without changing requirements. Only the actual owner's Monochrome reply binds; runtime and other
application/evidence gaps remain unresolved. Neither product passes the final engineering acceptance gate.

The temperature-monitor workflow and all result tabs were reviewed visually, followed by Existing BOM
demo import. This does not validate hardware or authorize publishing real supplier screens. A separate
source-only editable checkout, including genuine H-MEM bootstrap/smoke, is prepared and tested; the older
freeze archive remains historical. Signing, current staging, organizer eligibility, data permissions,
publication/video destination and owner approval still prevent a submission-ready claim.

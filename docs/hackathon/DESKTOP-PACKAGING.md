# Unified Windows desktop — implementation and verification

The owner authorized one executable and in-app settings, with Ollama/models and Zetaris retained as
external services. This supersedes the previous feature freeze for packaging/usability only. Engineering
checks, requirement provenance, source restrictions and all earlier evidence remain in force.

## Delivered

- `dist/PartLens.exe`: Windows x64 one-file application, **45,685,295 bytes** (about 43.6 MiB).
- SHA-256: `912d25bbfc5c1d86cefbce55cd816bbb8f766c4defdddbf50a4e4944d2d44f2b`.
- Real bundled Python/Tk, Node 24.12.0 and pinned H-MEM reference/bridge; no external Python/Node/npm
  installation is required by the application. Ollama/model weights and Zetaris remain external.
- Settings for local model/transport/context/timeout, supplier mode, JLCPCB and Zetaris configuration.
  Credentials are masked and encrypted with current-user Windows DPAPI. Settings changes start a new
  session; earlier evidence remains. No cloud/paid fallback is exposed.
- Existing BOM demo/import/review, compatibility/application/sourcing/cost views, memory recall and
  New Design requirements/architecture/generated-role workflow in the same app.
- A simpler application-first README; old README retained with corrected archive-relative links.
  Developer CLI/evaluation scripts, historical reports, fixtures and previous source candidates remain.

The owner's existing authorized `.env.local` was imported into a new encrypted user-local app profile.
The original file was unchanged; no credential values were printed or bundled. The user can change
details from **Settings**. Normal startup is a double-click; no supplier/model flags are required.

## Executed verification

| Check | Actual result / internal evidence |
|---|---|
| Full CMD workspace suite | **336 passed**, no skips, 23.80 s; `.partlens/validation/tests-20261025T215511Z-9f0ec7.txt` |
| Independent clean source install | Editable `.[dev,llm]`, locked Node dependencies, pinned H-MEM setup/smoke and both deterministic examples succeeded; `.partlens/source-preparation/20261025T195534Z-9fe569.jsonl` |
| Independent CMD suite | **336 passed**, no skips, 22.24 s; `.partlens/partlens-source/20261025T195534Z-9fe569/.partlens/validation/tests-20261025T215621Z-2c3260.txt` |
| Final one-file build | `.partlens/desktop-builds/20261025T215523Z-9d6847.jsonl`; exact executable hash above |
| Isolated packaged acceptance | Launched away from source with external Python/Node removed from `PATH`; real bundled H-MEM write and cold recall, synthetic verified/rejected/unverified decisions, 37 New Design roles/exports, DPAPI round-trip and construction of actual Tk/settings widgets succeeded |
| Packaged live checks, isolated profile | `.partlens/desktop-live-check/preflight.json`, all four services available; one fresh official read and real Zetaris query, no model inference |
| Final packaged live checks, normal owner profile | `.partlens/desktop-owner-final-services.json`, all four available after reading the encrypted default profile; earlier profile checks remain preserved |
| Archive inventory | Final checks under `.partlens/desktop-audits/`: bundled Node/H-MEM and notices present; no forbidden configuration, state, private fixture or model filenames. Earlier audit `20261025T214937Z-674573` is retained. |
| Scoped source/index audit | `.partlens/validation/audits/20261025T214833Z-c637b8.jsonl`: 148 then-current authored files and 56 historical staged blobs; no configured-secret/personal-path matches or checked missing links. The later documentation-only addition is audited separately. |

The final executable's normal-profile service check performed a genuine official JLCPCB C1525 read at
2026-10-25 21:57:26 UTC: HTTP 200, client ID `1846e94c8b64e732f9fc1be288f9d983`, server trace
`ef9d617bd69911b25507d2a31e9d8c42`. Zetaris returned five demo rows, HTTP 200, locator
`zetaris:d9396ba2-b540-47a7-9595-82affd5e68db`. Server query/request IDs were not supplied. H-MEM hello/stats
used the bundled runtime; Ollama inspection confirmed the installed local model. These are startup
operations, not a fresh LLM design run or proof of future availability. Raw responses/credentials remain internal.

The packaged synthetic New Design stays **not accepted**, with application/engineering gaps retained.
Packaging never converts missing evidence into verification. Actual Tk widget construction was tested
from CMD; no new visual desktop acceptance or final public recording is claimed.

An additional regression addresses one-file resource lifetime: licensed public/synthetic BOM inputs are
copied to persistent content-addressed example folders before use. Temporary extraction cleanup cannot
invalidate their recorded input paths, and updated examples retain previous revisions. Earlier 335-test
results and successful binaries remain preserved; the final suites above include this new durability case.

## Preserved failures and build boundaries

The first build (`20261025T194520Z-5d72d0`) stopped when the PyInstaller COPYING file was sought at its
old package location. The build now finds its installed distribution license and includes it. That attempt
and later successful builds remain preserved. Initial source smoke attempts could not write the default
user-data directory inside the restricted sandbox; explicit ignored `--data-dir` profiles passed, followed
by a successful normal owner-profile check with authorized filesystem access. No permission/security or
signing bypass was used. Earlier parser, repetition, replay and engineering failures remain in the milestone reports.

Builds collect explicit public code/resources, the approved BOM, original synthetic fixtures and runtime
notices. No `.env.local`, encrypted profile, supplier snapshot, SDK, private design, model, operational
journal or unrelated Cirquill directory enters the executable. Source snapshots exclude dependencies and
build outputs. Bundled runtime files are temporary; persistent settings/evidence use the user-local directory.
The internal profile initialization record is `.partlens/desktop-profile-setup/20261025T214633Z-734584.jsonl`.

The executable is not Authenticode-signed; no application certificate was supplied. Git SSH signing remains
enabled, the owner signing agent is still stopped/disabled, and no unsigned commit was attempted. No remote,
push, upload or publication occurred. The working tree remains uncommitted; older staged/release snapshots
were retained. This app build does not resolve Cursor eligibility, supplier redistribution permission,
complete manufacturing costs or engineering application qualification.

Launch/settings/build instructions: [docs/DESKTOP.md](../DESKTOP.md). Licensing and pre-existing work:
[THIRD_PARTY.md](../../THIRD_PARTY.md), [DISCLOSURE.md](DISCLOSURE.md). Earlier submission/release readiness
documents remain historical and do not mean that this binary or project was submitted or published.

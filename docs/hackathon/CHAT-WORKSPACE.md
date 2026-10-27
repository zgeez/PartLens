# PartLens conversation workspace

The Windows application now opens an original chat interface with a dark jade conversation sidebar,
warm neutral workspace, rounded message/composer surfaces, branded welcome illustration and an optional
Evidence panel. The existing detailed BOM workspace and Settings remain available from the sidebar.
The logo, PNG variants and Windows icon are in [assets/brand](../../assets/brand/BRAND.md); that document
contains both exact image prompts and the built-in generation provenance. The illustration is decorative.

## Use

Launch `dist/PartLens.exe`. Select the local model and supplier connection in Settings. Describe an idea
and send it, or choose **Review a BOM** / **Attach BOM** for an existing CSV. Requirement questions appear
in the conversation. Actual answers go through the existing exact-quote controller; skipping a question
does not create an answer. The assumptions toggle permits proposals only.

Actual tool operations report their actor and phase. **Evidence** shows authoritative recorded results,
including unresolved checks and cost terms. The recorded stamp does not imply fresh inventory. **Open
report** opens the local report folder. Recheck independently repeats design operations; **Update
requirement** applies an explicit typed answer, invalidates dependent results and generates a new report.
Follow-up chat explains the saved report using the configured local model, with tools disabled. It is
explicitly labeled commentary and cannot apply changes. Start a new conversation for a new investigation.

Chat journals, engineering runs, report revisions and per-conversation H-MEM stores stay in user-local
state. Older revisions are retained. The sidebar scrolls through saved conversations; **Earlier messages**
reveals older transcript entries. Settings start a new workspace without erasing history. Existing
pre-chat records remain in their original locations; they are not silently imported as chat messages.

## Verification and boundaries

The original 336-test suite passed again before the new tests were added. Ten additional synthetic
regressions cover history, owned paths, unsupported reports, tool-less commentary, cancellation, negative
summaries, context integrity, a scripted design with real H-MEM and cold typed revalidation, and native
chat/settings/question widgets. A BOM adapter regression checks genuine deterministic verified/rejected/
unverified results against an unsupported model claim using a synthetic one-line BOM. The full CMD suite
reached **346 passing**. All earlier logs are retained.

The scripted adapter evaluation is not a live Qwen run. It checks that a real owner quotation survives
new report revisions, independent sourcing/qualification/cost operations occur, and prior artifacts remain
unchanged. Commentary tests deliberately include an unsupported model claim and verify it does not enter
the engineering report. Engineering authority stays with the existing deterministic checks.

The executable acceptance runs outside the checkout with external Python/Node removed from PATH. It
checks synthetic verified/rejected/unverified alternatives, real bundled H-MEM persistence and cold recall,
DPAPI round-trip, New Design export and construction of both chat and detailed BOM/settings widgets.
The first branded build passed these checks. A running app was visually inspected; opening Evidence exposed
an oversized-panel defect, which was corrected before final packaging. Visual inspection and automated
CMD tests are separate activities. No styling test is presented as a fresh supplier or model operation.
The final panel width, welcome screen and explicitly labeled synthetic conversation were inspected separately.

An initial expanded regression failed because its scripted provider expected tool results as the last
message while the real controller appends a status message. The test adapter now finds the actual tool
results. The failure remains at `.partlens/validation/tests-20261025T232024Z-572d20.txt`; the corrected
targeted run passed at `.partlens/validation/tests-20261025T232951Z-b5a0ad.txt`. The first complete
345-test record is `.partlens/validation/tests-20261025T233041Z-c5bfaf.txt`. Final build/test/audit records
are under the existing ignored desktop-builds, source-preparation and validation directories.

An additional BOM regression initially tried checking one line before the controller's required discovery
on every imported line (`tests-20261025T233635Z-61d8d8.txt`). The test now imports a scoped, one-line synthetic
BOM; controller prerequisites were preserved. The ten targeted tests passed at
`.partlens/validation/tests-20261025T233757Z-1f834d.txt`. Multi-line unresolved identities and bounded-agent
failures remain workflow limitations; this interface does not bypass them. A release-copy attempt also
encountered a Windows lock while the preview was open; the accepted candidate and prior executable were
preserved, and the final rebuild succeeded after the PartLens preview closed.

The visual fixture also exposed a late-layout scroll issue. The transcript now follows new messages as
rounded surfaces finish resizing, while manual scrolling disables that behavior. A long-message regression
covers it. Final CMD suite: `.partlens/validation/tests-20261025T234158Z-9110fe.txt` — 346 passed in 32.18 s.

Initial chat-release executable (superseded by the magnifying-glass logo revision): 48,134,570 bytes, SHA-256
`50004781ed87385b6c6813f16284abf7388397d31dba61eda4bce54e8c511f1b`.
Build/acceptance record: `.partlens/desktop-builds/20261025T234147Z-62a7fd.jsonl`.
Current logo revision and executable verification: [LOGO-REVISION.md](LOGO-REVISION.md).
The SSH agent remains stopped/disabled, signing stays enabled, and no commit was attempted.

This change does not improve the model's reasoning reliability, add supported circuit patterns, complete
commercial semantics or make preliminary designs manufacturing-ready. A stopped model request may finish
or time out before cancellation takes effect; completed evidence is preserved. No paid inference, Cursor,
private material, orders, publication or signing bypass was used. Windows Authenticode and Git signing
are separate; neither is claimed for this release.

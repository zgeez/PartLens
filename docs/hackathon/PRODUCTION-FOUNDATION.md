# Reviewed BOM production foundation

Date: 2026-10-26. Owner-authorized follow-up to the [production-readiness assessment](../PRODUCT-READINESS.md).
This milestone adds a usable saved-project/review boundary. It is not a production-release certification.

## Implemented

- Standard-library SQLite project store with schema v1, foreign keys, transactions and a single-writer
  OS profile lease. No new runtime dependency or replacement engineering architecture.
- Immutable original BOM bytes and versioned inputs; project/revision selection in the shared web UI.
- Per-tool checkpoints and recorded job transitions; interrupted operations require explicit recheck.
- Historical reopening without inference/supplier access or restoration of controller verified status.
- Same-revision build-quantity recovery through the existing exact user-provenance validator.
- Project-scoped real H-MEM storage/tags; independently checked recall follows actual stored source runs.
- Explicit policy family/parameter coverage and hash. Human review remains separate from checks.
- Named, reasoned accept/reject/needs-evidence history. Acceptance cannot override rejected/unverified
  results, requires application-scope acknowledgement, and binds to the run, revision, context and decision.
- Reviewed-proposal BOM/change CSV, evidence/review JSON, original input, run/quantity provenance and
  hash manifest. Derived CSVs escape spreadsheet formulas. Costs remain the recorded scenarios, not an
  invented quotation for the manually selected proposal. Manufacturing readiness remains false.

Usage, storage, recovery and remaining limits are in [PROJECTS.md](../PROJECTS.md). Existing conversations,
legacy workflows, previous candidates, internal supplier fixtures and historical failures are preserved.
No private design, Cursor, paid inference, new supplier interface, order or publication is involved.

## Verification record

The prior 359-test baseline remains the reference. The initial new-test run had 8 failures because its
synthetic answer callback was installed after the test's agent had captured the original callback;
the operation correctly waited for user input. That test setup was corrected. The failed result remains
at `.partlens/validation/tests-20261026T222659Z-a5ba67.txt`. Targeted rerun: 26 passing tests at
`.partlens/validation/tests-20261026T222815Z-5f94ea.txt`.

First complete expanded suite: **372 passed**, 75.46 s, at
`.partlens/validation/tests-20261026T222914Z-ed2673.txt`. Further regressions/packaged acceptance are
recorded below once completed.

The first expanded source renderer run failed; the initial high-level self-test report retained a
RuntimeError. The diagnostic run `.partlens/production-renderer-runs/20261026T223045Z-985196.jsonl`
identified missing recall after an identical check reinforced an earlier source run. The controller was
corrected to query actual persisted source runs. The subsequent real WebView2 run
`.partlens/production-renderer-runs/20261026T223149Z-a12a6f.jsonl` passed project/review/export/reopen,
verified/rejected/unverified checks, one-board/hypothetical-sixty costs, DPAPI forms and **3 real H-MEM
rechecks**, without model or supplier calls. A nonfatal WebView2 disposed-object warning occurred during
test window teardown; it did not change the saved successful result. It is preserved, not hidden.

## Remaining production gates

Application qualification is still incomplete, especially circuit context, pinout/footprint and dynamic
operating behavior. Active-IC substitution is not generally qualified. Follow-up chat remains commentary,
not a durable continued investigation. Broader licensed supplier coverage, known currency/order terms,
assembly pricing, representative large-BOM performance and real engineer pilot measurements are still
needed. Reviews are local asserted names, not authenticated accounts or digital signatures. Automated
backup/restore, signed updates, application signing and team workflow remain future work.

No fresh local-model or official supplier/Zetaris operation is claimed for this foundation task. Previously
successful integration evidence remains historical. SSH signing remains enabled; the owner alone unlocks
the signing key. No submission, push or release publication is authorized by this work.

## Final root and packaged verification

Final root CMD suite: **376 passed**, 88.79 s, including 17 new project/recovery/review regressions and
all previous tests, at `.partlens/validation/tests-20261026T225120Z-698e89.txt`. Conflicting newly observed
evidence invalidates the review/export boundary even if the model omitted a new check.

The retained legacy Tcl/Tk settings case failed after the native chat case in a shared pytest process,
while the individual case, its complete module, and a standalone three-interpreter lifecycle passed.
This was also reproduced in the first independent installation. No claim is made about the underlying
Tcl runtime cause. Both legacy widget tests now execute their unchanged assertions in fresh child
interpreters from CMD; they are not skipped or mocked. The complete 375-test run then passed at
`.partlens/validation/tests-20261026T224851Z-b67d28.txt`, before the final evidence-change regression
brought the suite to 376. Earlier 374-pass/one-failure logs remain at
`.partlens/validation/tests-20261026T223349Z-c4bde3.txt`,
`.partlens/validation/tests-20261026T223607Z-f4c7ab.txt` and the first source-copy record
`.partlens/source-preparation/20261026T223851Z-b856b3.jsonl`.

Final executable: `dist/PartLens.exe`, **50,373,659 bytes**,
SHA-256 `c5d9dc31b26137c04923d9c8a0d1e951c8fdb8f59a64a26a57dd092d0b15049f`.
Build/acceptance: `.partlens/desktop-builds/20261026T225121Z-a3822b.jsonl` and its `release.json`.
The EXE was tested away from the repository with external Python/Node removed from PATH: bundled real
H-MEM cold recall, DPAPI round-trip, all three deterministic outcomes, preliminary New Design (37 roles,
not accepted), real WebView2 forms/pages, project persistence, review/export, original quantity recovery,
stale-approval rejection, cross-project memory isolation and three independent memory rechecks passed.
No live supplier or model operation is inferred from these synthetic checks.

A separate source renderer run with project isolation also passed at
`.partlens/production-renderer-runs/20261026T223401Z-d87d0e.jsonl`. Automated renderer acceptance is not
visual acceptance. A computer-use launch of the isolated preview timed out waiting for app approval;
no alternate launch bypass was attempted and no owner application was closed. The new controls still
need an owner visual walkthrough:

1. Open BOM workspace, create/select a project and import the synthetic demo.
2. Check that project/revision selectors, historical/interrupted notices and evidence tabs fit the window.
3. Run checks, answer quantity if asked, and open Engineer review.
4. Inspect original/candidate attributes, check messages, source details, reviewer/rationale and scope acknowledgement.
5. Accept a verified attribute proposal; verify rejected/unverified candidates cannot be accepted.
6. Export the proposal, inspect its path/packet, reopen the project and confirm historical results require recheck.

Git remains uncommitted with the existing index preserved. `commit.gpgsign=true`, `gpg.format=ssh`;
the local signing-agent service remains stopped/disabled. No signing bypass or passphrase handling occurred.
Broader product readiness and visual/pilot acceptance remain open; this is a completed implementation
foundation rather than a claim of a production release.

The final independent source-only tree `.partlens/partlens-source/20261026T225317Z-68995a` installs in a
new virtual environment and passes locked bridge setup, a genuine local H-MEM smoke, both deterministic
examples and its complete suite. Its append-only record is
`.partlens/source-preparation/20261026T225317Z-68995a.jsonl`. The preceding failed source candidate is kept.

Final public/staged audit: `.partlens/validation/audits/20261026T225340Z-025bd4.jsonl` inspected 179 public
source files and 56 existing staged blobs with no configured-secret, personal-path or checked-link
findings. The retained internal LCSC fixture hash is unchanged. Final EXE archive and seven-size icon
audits passed at `.partlens/desktop-audits/20261026T225338Z-e179c1.jsonl` and
`.partlens/desktop-audits/20261026T225340Z-188d11.jsonl`: no settings, private files, supplier snapshots,
model weights or Tk runtime are bundled. These local artifacts and internal data are not public releases.

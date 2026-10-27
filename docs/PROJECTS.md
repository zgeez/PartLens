# Saved BOM projects and engineer review

The BOM workspace now saves local projects and immutable BOM revisions. This is a foundation for a
reviewed engineering workflow, not a manufacturing-release system. New Design remains preliminary;
its existing conversation history is separate from these BOM projects.

## Use the workflow

1. Open **BOM workspace**. Choose **New project**, enter a name, then **Import CSV**. Importing without
   a project creates one automatically. **Load demo** imports the configured synthetic or Easyduino BOM.
2. Each import creates a new revision. The original file is untouched. Select projects and revisions
   using the two selectors above the workspace. Reimporting identical bytes still creates a revision.
3. Choose **Run checks**, or **Local agent review** for a bounded local Ollama investigation. Answer the
   build quantity with your actual words. Supplier mode remains the one selected in Settings.
4. Inspect **Replacements**, **Sources**, **Requirements**, **Costs** and **Qualification scope**. A verified
   result covers the evidenced reference attributes checked by the policy. Circuit, footprint/pinout
   and operating-characteristic qualification remains separate.
5. Open **Engineer review** and click **Review** for a candidate. Inspect its attribute comparison,
   checks and full evidence. Enter a reviewer name and rationale. Choose **Needs evidence**, **Reject
   proposal**, or **Accept checked attributes**. Acceptance requires the scope acknowledgement and a
   verified deterministic result. Names are locally asserted, not authenticated engineering identities.
6. Choose **Export reviewed proposal**. The app displays the new folder path; **Copy folder path** lets
   you open it in Explorer. The export contains the proposed BOM, changes, evidence, review records,
   original input, recorded provenance and a SHA-256 manifest. It never overwrites the imported BOM.

The export is explicitly **not manufacturing-ready**. It retains unresolved application checks, input
issues and commercial/cost uncertainties. Recorded cost scenarios are not automatically recalculated as
a quote for the manually selected proposal. A later rejection supersedes acceptance without deleting
the previous review. Conflicting accepted candidates for one line block export until resolved.

Derived CSV cells escape spreadsheet formula prefixes. `original.csv` retains the exact original bytes
for provenance and is unescaped. Review packets can contain supplier data and reviewer information;
they are internal artifacts. Check licensing and privacy before sharing them.

## Reopen and recover

The last selected project/revision opens automatically. Saved decisions are marked **historical**.
Opening a project makes no model or supplier request and loads no prior verified decisions into the
new controller session. Click **Run checks** to start a new operation from the saved input. Fresh checks
are required before a new review/export; earlier approvals never authorize a different run or revision.

The build quantity can be restored only from a validated original user-message record belonging to
the same revision. It retains the original user source and is not recorded as a new confirmation.
Other requirements are not silently reconstructed from model text or reports. Missing context remains
unresolved. A different BOM revision does not inherit quantity confirmation.

Checkpoints are saved after completed tool operations, including live-agent operations. If a process
ends during an operation, the next desktop instance marks its job **interrupted**, retaining checkpoints
and journals. No inference or API request resumes automatically. Explicit recheck restarts controller
work; it does not resume a partially generated model turn. An in-flight external read may have completed
before the process ended without a saved final response.

Memory storage and tags are scoped to the project. Recall is context only and independently reruns
checks. An identical decision can reinforce an earlier H-MEM entry; recall follows the entry's actual
source run rather than assuming the newest run created it. Prior generic desktop memory is preserved
and is not automatically moved between projects.

## Storage and limits

- Default profile: `%LOCALAPPDATA%\PartLens`; projects/checkpoints/reviews are in
  `state\projects.sqlite3`. Immutable input bytes are held transactionally in SQLite; verified owned
  copies used by the controller live in `state\projects\<project>\<revision>\bom.csv`.
- Existing append-only run journals stay under `state\web-bom-runs`; memory is under
  `state\project-memory\<project>`. Exports use a new folder under `state\exports`.
- One desktop writer may hold a profile at a time. Close that profile's other app window to reopen it.
  Do not terminate owner applications to remove the lock. Different test profiles remain independent.
- Project imports accept UTF-8 CSVs of at most 8 MiB and 10,000 parsed component lines. These are safety
  bounds, not measured performance guarantees. Large-BOM performance remains a pilot/release gate.
- SQLite foreign keys/transactions and record/input hashes detect incomplete or accidental changes.
  They do not provide authenticated, tamper-proof audit signatures or multiuser authorization.
- No retention cleanup deletes history. Automatic backup/restore, storage quotas, migration beyond
  schema v1, project sharing and team review are not implemented. Unknown future schemas fail closed.
- To make an owner-managed backup, close PartLens normally and copy the entire profile to authorized
  local backup storage. Keep the original. This is not a tested automated restore feature. DPAPI secrets
  normally need the original Windows user/computer; configure credentials locally on another machine.

The foundation is tested with synthetic data and the real local memory engine. It does not broaden
supplier permissions, engineering coverage or paid-provider access. See the
production assessment and implementation/verification record.

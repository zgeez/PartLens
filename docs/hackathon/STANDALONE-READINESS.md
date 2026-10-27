# Standalone PartLens checkout readiness

Subsequent owner-authorized desktop packaging: [DESKTOP-PACKAGING.md](DESKTOP-PACKAGING.md) and
[the desktop guide](../DESKTOP.md) record the new one-file Windows app, settings, 336-test baseline and
separate clean source checkout. Earlier 140-file/318-test candidates below are preserved historical
releases, not the current executable. No publication or signed-commit readiness is implied.

## Current finalization candidate

**Source and test preparation complete locally; not publication/submission-ready.**
Current implementation: 318 automated tests passing in the working tree and independently installed tree.
No cloud inference, Cursor, private design access, supplier catalogue extraction, orders or publication.

- Independent installed tree: `.partlens/partlens-source/20261024T224303Z-f337ee`.
  Clean editable `.[dev,llm]` installation, locked Node dependencies, pinned H-MEM bootstrap, actual bridge
  smoke and both original deterministic examples succeeded. Initial 317-test installation evidence is in
  `.partlens/source-preparation/20261024T224303Z-f337ee.jsonl`. Later corrections and final hashes are
  separate records/manifests; the initial manifest is preserved.
- Final CMD working-tree suite: 318 passed in 26.69 s, no skips,
  `.partlens/validation/tests-20261025T190900Z-c0c5aa.txt`.
- Final CMD independent suite: 318 passed in 30.06 s, no skips,
  `.partlens/partlens-source/20261024T224303Z-f337ee/.partlens/validation/tests-20261025T190942Z-8b5d85.txt`.
- Source-only repository candidate: `.partlens/standalone-release/finalization-20261025/PartLens`.
  Its parent contains `SOURCE-MANIFEST.json`, `COMMIT-FILES.txt` and the release audit. These identify the
  exact 140 authored files intended for the first signed commit. Verification dependencies/state are not
  copied into the candidate. Source hashes must match the independent tree's final authored manifest.
  No remote, commit, push, source-history migration or publication is part of this preparation.

Included: Python package/CLI, both desktop workflows, synthetic tests/examples, approved licensed
Easyduino BOM, Node bridge/lockfile/bootstrap, architecture/evidence reports, README/license/notices.
Excluded: credentials, real supplier snapshots/responses, operational journals, models, private designs,
SDK archives, verification environments, dependency/vendor directories and unrelated platform work.
Synthetic public examples need no API account; real sponsor operations require owner-authorized access.

The current bounded model results, negative trials, real integration identifiers, cold recall and replay
limitations are in [HACKATHON-FINALIZATION.md](HACKATHON-FINALIZATION.md). Setup, preflight, narration and
labeled deterministic contingency are in [DESIGN-DEMO.md](DESIGN-DEMO.md). A successful test suite does
not establish a safe circuit, complete cost quote, reliable autonomous completion or sponsor eligibility.

## Signing and publication — owner actions

The observed Windows ssh-agent is stopped/disabled; `ssh-add -l` cannot connect. Signing remains SSH and
enabled. No passphrase was requested/read and no unsigned commit was attempted. The prepared local
repository keeps signing required. The original working tree/index remains separate and unchanged by
release staging; its older 56-file staged baseline is not the standalone release.

Owner only, in elevated PowerShell:

```powershell
Set-Service ssh-agent -StartupType Manual
Start-Service ssh-agent
```

Then owner only in normal PowerShell, entering the passphrase locally:

```powershell
ssh-add "$env:USERPROFILE\.ssh\id_ed25519_signing"
ssh-add -l
Set-Location 'E:\Coding Proj\Cirquill\.partlens\standalone-release\finalization-20261025\PartLens'
git config --get commit.gpgsign
git config --get gpg.format
git status --short
git diff --cached --check
```

After reviewing the manifest/index and confirming signing works, create the signed commit normally.
Keep signing and hooks enabled; stop if signing fails. Verify using the owner's trusted allowed-signers
configuration. The owner must separately approve a repository destination/visibility and publication;
no GitHub remote or HackOS submission is authorized here. Real supplier screens/data need permission
and final capture review. Cursor was not used; eligibility must be clarified rather than claimed.

Remaining blockers: signing/uncommitted release, publication authorization/destination, final permitted
recording, supplier commercial/data-use questions, Cursor/organizer eligibility, intermittent model
completion and the documented engineering/application gaps. No manufacturing-ready claim is permitted.

## Preparation system and historical candidate

Supported distribution: editable source checkout plus the Node H-MEM bridge, Python 3.12+, Node 20+ and
local Ollama for inference. No remote creation, history migration, push, submission or publication occurred.

```powershell
.\.venv\Scripts\python.exe scripts/validate.py
.\.venv\Scripts\python.exe scripts/prepare_partlens_tree.py --verify
```

Preparation creates a new ignored `.partlens/partlens-source/<run>` from explicit approved roots, scans
configured secret values, excludes private/runtime/dependency material and writes a SHA-256 manifest.
Verification makes a clean venv, installs `.[dev,llm]`, runs locked Node dependencies/pinned public H-MEM
bootstrap, actual bridge smoke, both deterministic examples and the full suite without owner credentials.
Network dependency download is required; installing the optional SDK does not call paid inference.

Keep the initial manifest. Record any final documentation sync separately and verify every authored hash.
Verification-generated `.venv`, Node dependencies, vendored H-MEM and test state are outside authored
source; do not publish the verification directory wholesale. No credentials, internal responses, licensed
fixtures, model weights, persistent memory or private design data belong in public artifacts.

## Owner actions and remaining limits

Previous independently verified tree: `.partlens/partlens-source/20261024T185940Z-301633`, 136 authored files,
304 tests passing in 20.25 s without skips, real Node H-MEM bootstrap/smoke and both deterministic examples
successful. Full preparation record: `.partlens/source-preparation/20261024T185940Z-301633.jsonl`.
Keep its initial manifest and later final-documentation manifest; distribute only audited authored source.

- The generic Python-only wheel does not automatically bundle/locate the Node bridge; use the checkout.
- Clean tests establish package/bridge reproducibility, not supplier/model/Zetaris success or hardware safety.
  Current observed results are in [FINAL-DESIGN-WORKFLOW.md](FINAL-DESIGN-WORKFLOW.md); old trees remain historical.
- Current work and the older staged index require final release review. Keep SSH signing; only the owner
  unlocks the key. Instructions remain in [SUBMISSION-READINESS.md](SUBMISSION-READINESS.md).
- Supplier redistribution/recording permissions, commercial semantics and Cursor eligibility remain unresolved.
  Cursor was not used, and compliance is not claimed.
- The owner must approve destination, final capture, disclosure and publication/submission.

Source/install artifacts are reviewable. **Public-repository/submission readiness is not claimed** while
signing, licensing, eligibility, release review and publication prerequisites remain unresolved.

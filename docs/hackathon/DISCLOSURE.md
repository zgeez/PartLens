# Disclosure of pre-existing material

Open Agent Hackathon 2026, build window opened 2026-10-22 00:00 UTC. The repository was created at
2026-10-22 00:00 UTC; all code in it was written during the window unless listed below.

## Pre-existing material used as reference (not copied into this repository)

| Material | Created | How it is used |
|---|---|---|
| Private PCB tool benchmark (routing/placement engines on a private board) | before 2026-10-22 | Design lessons only: fail-closed verification, separating hard checks from quality metrics, provenance-tagged requirements, replayable run records. No code, data or configuration copied. |
| Cirquill architecture notes (requirement/provenance model, verifier API, trial records) | 2026-10-21 | Conceptual reference for the PartLens core model. Re-implemented from scratch for the BOM domain. |
| PartLens hackathon plan (scope, schedule, demo outline) | 2026-10-21 | Planning only. |

## Third-party material

Listed in [THIRD_PARTY.md](../../THIRD_PARTY.md) with licences. In addition, public documentation was used as
reference while writing new code (nothing copied):

| Reference | Licence | Used for |
|---|---|---|
| zetaris/getting-started (commit 98a2d306), `scripts/zetaris_api.py`, `scripts/query_zetaris.py`, `docs/connections/client-setup.md` | Apache-2.0 | REST run-query path, headers and environment variable names for `sources/zetaris.py` |
| zetaris/getting-started, `docs/guides/zetaris-lightning-sql-commands.md`, reviewed 2026-10-22 | Apache-2.0 | Lightning file-table registration syntax for the owner-local approved demo setup; no implementation copied |
| Meterless `templates/agentathon-starter` (commit 1742dec5) | Apache-2.0 | vendoring approach (degit of `engines/hmem/reference`) for the H-MEM bridge |
| LCSC product pages / product-detail JSON | LCSC website terms | runtime supplier data (local snapshots, not committed) |
| Ollama native tool-calling/API/Windows documentation, reviewed 2026-10-22 | Public documentation; Ollama runtime MIT | New stdlib local provider and local launcher; protocol guidance, no implementation copied |
| Anthropic model overview, reviewed 2026-10-22 | Public documentation | Selectable Sonnet model ID; historical Opus evidence unchanged |

The pre-existing Ollama runtime and Qwen3/Qwen3.5 model weights are downloaded local dependencies, not hackathon
authored work. Their versions/digests and licences are recorded in [THIRD_PARTY.md](../../THIRD_PARTY.md).
Cursor was not used for Milestone 3, following the owner's explicit instruction. Any hackathon requirement
for Cursor AI development remains unresolved; Codex work is not evidence of Cursor usage.

Milestone 4 also uses Codex only. Its controller, factual renderer, evaluation harness and synthetic sample
workflow were written during the build window. The synthetic sample reuses this repository's original
Apache-2.0 test fixtures; it includes no supplier snapshot. Existing third-party runtime/model/engine
dependencies and their licences remain listed separately. No new pre-window implementation was copied.

If any pre-existing code is reused later in the window it will be added here before it is committed.

The subsequent official component adapter was also written with Codex during the build window. Its request
contract comes from JLCPCB's public signing/API/SDK guides and the owner's four approved endpoint PDFs.
No pre-existing supplier adapter or SDK implementation was copied. Only synthetic responses enter tests;
real supplier data and licensed documentation remain local. See [JLCPCB-INTEGRATION.md](JLCPCB-INTEGRATION.md).

Milestone 5 reference: the owner supplied the JLCPCB Business SDK Java archive, version `1.0.6-SNAPSHOT`
(bundled Maven metadata dated August 2026, before the build window). Only archive/class names and Maven
metadata were inspected; no SDK implementation was copied, decompiled or executed. The artifact and real
API data remain ignored internal materials under their existing terms. New Python discovery, bounded
requests and source-observation replay were written during the build window. Cursor was not used.

Final submission preparation freezes the Milestone 5 runtime implementation. README, narrator/click
runbook, presentation outline, unsent commercial inquiry, readiness report and draft HackOS copy were
prepared with Codex. An isolated public-source installation exercised the synthetic sample and full tests;
installing the optional Anthropic SDK for mocked tests did not invoke paid inference. No Milestone 6,
Cursor usage, public publication or HackOS submission is claimed.

The owner's subsequent Design-from-Idea request superseded that freeze. New requirements, original
reference-role definitions, circuit intent, BOM generation, bounded local agent, desktop entry and
synthetic regressions were written with Codex during the build window, reusing this repository's existing
supplier/check/cost/memory code. The smart product example is original to this request; no private design,
benchmark or implementation was inspected or copied. The owner delegated choices rather than confirming
numeric requirements. Manufacturer references and their limitations are listed in
[DESIGN-GENERATION.md](DESIGN-GENERATION.md) and [THIRD_PARTY.md](../../THIRD_PARTY.md); their pre-existing
documents inform paraphrased facts, not copied code/schematics. Local Qwen and H-MEM remain pre-existing
dependencies. Real supplier/run data stays internal. No Cursor, paid inference, CAD validation, new remote,
repository publication or submission is claimed.

The next owner-authorized correction milestone adds bounded independent architecture comparison,
requirement-change guards, typed pattern selection, support-part investigation and a second original
temperature-monitor scenario. Its implementation, tests, packaging/verification script and report were
written with Codex during the build window. Pre-existing official manufacturer documentation informs
original reference facts; no vendor schematic or implementation was copied. Qwen proposes architectures;
the controller/check engine handles mandatory validation and factual status. Negative local trials and
test failures are retained. The actual owner reply “Monochrome” was relayed verbatim and is the only
new confirmed badge specification. Independent source-checkout setup downloads the already-disclosed
public bridge/dependencies; it does not publish source or private data. Cursor and paid inference were
not used. See [ARCHITECTURE-CORRECTION.md](ARCHITECTURE-CORRECTION.md).

The final workflow milestone adds original clarification ranking, controller-owned typed-answer recording,
desktop requirement revision, unapplied arithmetic counterfactuals, sourcing triage and readable views.
It reuses the disclosed pattern/check/source/memory implementations; no new vendor circuit code or
private design is reused. Codex wrote and tested these changes during the build window. Actual Qwen
turns, controller operations, service outages/recovery and failed trials remain separately journaled.
Repeated Monochrome relays refer to the same earlier owner answer. No paid inference, Cursor usage,
submission or publication is claimed. See [FINAL-DESIGN-WORKFLOW.md](FINAL-DESIGN-WORKFLOW.md).

Finalization preserves that implementation and adds original count/geometry clarification and consistency
checks, startup service checks and an explicitly selected Ollama JSON-schema action transport using its
official documented API. The existing tool/controller/checking boundary is retained; no new circuit pattern,
vendor implementation or private design is reused. Codex wrote the corrections, synthetic regressions,
evaluation helper and finalization materials during the build window. Genuine native/structured trials,
provenance-helper and repetition failures, service checks and clean installation are reported separately.
The owner's further delegation is not a numeric confirmation. No paid inference or Cursor was used.
See [HACKATHON-FINALIZATION.md](HACKATHON-FINALIZATION.md).

The owner subsequently authorized a unified Windows executable and in-app settings. Codex wrote the
desktop entry point, validated settings/Windows credential storage, resource resolution, build/audit
script and synthetic regressions during the build window. Original engineering/check/controller code,
the approved BOM and pinned real H-MEM are reused. The executable bundles the existing Node runtime,
Python/Tk and the pinned public memory engine with their notices; PyInstaller and esbuild are disclosed
build tools. Ollama models and Zetaris remain external. No private design, supplier snapshot, owner
configuration, paid inference or Cursor work is included. Earlier reports, source candidates, failures
and developer reproduction commands remain preserved. See [the desktop guide](../DESKTOP.md).

The owner then requested a modern chat interface and original branding. Codex implemented the native
chat presentation, append-only conversation journal and adapters over the existing bounded agents,
deterministic engineering tools, local provider, encrypted settings and H-MEM bridge. Existing engineering
patterns and checks were reused; chat prose receives no engineering authority. The built-in image-generation
tool created the project logo and decorative hero art; prompts and derivative provenance are recorded in
[BRAND.md](../../assets/brand/BRAND.md). No private design, real supplier record, paid PartLens inference,
Cursor work, publication or additional sponsor integration is claimed for this interface change.

The owner subsequently requested replacing the desktop framework because secondary Tkinter windows
still looked dated. Codex implemented an original shared HTML/CSS/JavaScript presentation for Chat,
Settings, BOM review, evidence and requirement dialogs, hosted by pywebview 6.2.1 with explicit WebView2.
The existing engineering/controller, suppliers, settings encryption and real H-MEM are reused. New desktop
dependencies and SDK notices are listed in THIRD_PARTY.md. No Electron, React, paid inference, Cursor,
new supplier interface or private circuit material is used. Preserved Tkinter code/tests are historical
compatibility material; they are excluded from the new executable. Actual renderer acceptance and the
distinction between DOM tests, visual review and live integrations are recorded in
[WEB-DESKTOP.md](WEB-DESKTOP.md).

The owner approved proceeding from the production assessment. Codex wrote the original standard-library
SQLite project/revision/checkpoint and local human-review/export implementation, shared desktop controls,
synthetic regressions and documentation during the build window. Existing deterministic checks, official
supplier adapters, exact user-provenance validator, pywebview and pinned real H-MEM are reused. No new
third-party implementation, private design, supplier interface, Cursor work or paid inference is added.
Review is explicitly narrower than manufacturing approval. See [PRODUCTION-FOUNDATION.md](PRODUCTION-FOUNDATION.md).

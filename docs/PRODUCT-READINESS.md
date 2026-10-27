# PartLens production-readiness assessment

Assessment date: 2026-10-26. This is a review of the approved source, tests, packaging and recorded
evaluations. It does not constitute a new live-model evaluation, supplier query, security certification
or hardware validation. No feature implementation is included in this assessment.

## Judgment

Follow-up: the owner authorized the [saved-project/review foundation](PROJECTS.md) after this assessment.
Its [implementation report](hackathon/PRODUCTION-FOUNDATION.md) records the delivered persistence,
recovery and review/export boundary. The gaps below describe the assessed prototype; broader engineering,
data, distribution and pilot gates remain open. This assessment is retained as the original baseline.

PartLens is a credible engineering-assistant prototype with a useful trust architecture. Its strongest
near-term product is a **BOM review and replacement-research workbench**. It is not yet a production
replacement-approval system or a general autonomous hardware designer.

An engineer can use it today to organize research, inspect source evidence, execute a narrow set of
deterministic comparisons and retain decisions. An engineer would still need to establish circuit
conditions, verify broader part behavior and perform the normal design/release review outside PartLens.
The new desktop makes the workflow easier to access; it does not expand its engineering coverage.

## What is already present

| Area | Current implementation and evidence |
|---|---|
| Desktop | Packaged Windows EXE; shared local HTML/CSS/JS Chat, Settings, BOM and Evidence views in WebView2; no frontend CDN; original Part + Lens branding. |
| Local inference | Ollama/Qwen tool use, explicit transport selection, bounded calls/context/timeout and no silent paid fallback. Successful and failed genuine trials are preserved. |
| Existing BOM | CSV import, grouped references/quantities, identity matching, candidate discovery, deterministic comparison, sourcing checks and cost scenarios. KiCad schematic-to-BOM import exists in the source CLI. |
| Preliminary design | Requirements interview, provisional defaults, a bounded manufacturer-referenced pattern library, architecture screens/alternatives, supporting component roles and preliminary BOM/report export. |
| Trust model | The LLM cannot assign a verified result. Passes need evidence. Confirmed requirements require recorded user quotations. Equivalence, application suitability and sourcing are separate. |
| Supplier/data integrations | Official JLCPCB read operations, real Zetaris queries and real Meterless H-MEM operations succeeded in recorded bounded runs. Existing internal LCSC fixtures are retained under collection restrictions. |
| Cost foundations | Decimal arithmetic, quantity price breaks, MOQ/order multiples when known, stock constraints, sourced classification/fees and explicit incomplete/conditional totals. |
| Memory/audit | Append-only journals, source locators/timestamps, decisions, cold memory recall and independent rechecks. Replay exists, with documented limits and preserved mismatches. |
| Local privacy | User-scoped Windows DPAPI credentials, masked forms, restricted native bridge, escaped message text, explicit native file selection and private-material guards. |
| Regression/reproduction | Latest reviewed suite: 359 passes. Independent source installation and actual packaged WebView2/H-MEM acceptance succeeded. These do not establish field reliability. |

The detailed operational records are summarized in [HACKATHON-FINALIZATION.md](hackathon/HACKATHON-FINALIZATION.md)
and [WEB-DESKTOP.md](hackathon/WEB-DESKTOP.md). The latter renderer test uses synthetic components; it is
not a fresh Qwen/JLCPCB/Zetaris end-to-end trial.

## Specific gaps found in the implementation

### 1. There is no completed application-qualification path

[`check_application`](../src/partlens/checks/compat.py) unconditionally adds unverified operating-characteristic
and footprint checks, plus effective-capacitance/ESR/ripple gaps for capacitors. Consequently this checker
cannot currently produce fully verified application compatibility, even after some input conditions are
provided. This is intentional conservative behavior, but it leaves no finished qualification workflow.

The substitution policy has explicit parameter comparisons for resistors, capacitors, inductors, ferrite
beads and LEDs. Different active IC identities largely remain unverified pending operating, pinout and
functional evidence. A package name is not a validated land pattern. A deterministic pass is meaningful
only within the checks and source facts actually covered.

Production needs a declared capability envelope and reviewed per-family rules. For supported cases,
capture actual operating conditions and evaluate the characteristics that matter. Unsupported conditions
must remain unresolved; removing these guards to obtain green badges would make the product worse.

The required evidence is application-dependent. For example, Murata discusses capacitor self-heating
under AC/pulse loading and confirmation in the actual circuit. A nominal capacitance/voltage/package
match cannot establish every relevant characteristic. See [Murata's guidance](https://www.murata.com/en-global/support/faqs/capacitor/ceramiccapacitor/char/0001)
and [DC-bias/temperature comparison](https://www.murata.com/en-global/support/faqs/capacitor/siliconcapacitors/char/0004).

### 2. The system is BOM-centric rather than circuit-aware

[`import_kicad_schematic`](../src/partlens/core/bom.py) exports a grouped BOM. It does not build a persistent
net/pin/rail model. The desktop import picker currently accepts CSV. The New Design export explicitly
declares no schematic/netlist/ERC scope in [`design/cli.py`](../src/partlens/design/cli.py).

Production review needs stable reference/part identities tied to design revisions, relevant net connectivity,
rail envelopes, loads, interfaces, pin mapping and mechanical/footprint context. Start with read-only ECAD
import and schematic cross-probing where practical, not an entire routing engine. KiCad exposes BOM,
netlist and ERC commands separately; importing a BOM is not equivalent to performing those other operations.
[KiCad CLI documentation](https://docs.kicad.org/9.0/en/cli/cli.html#_schematic_netlist_export).

### 3. Chat history is not a durable project system

[`DesktopBridge`](../src/partlens/web_desktop.py) creates a new BOM Session on initialization. The BOM
workspace uses the generic `desktop-bom` design label and a shared memory store. Chat has per-conversation
stores, but no first-class project/revision/approved-BOM model. Independent rechecks reduce the risk of
trusting recalled decisions; the storage organization still needs genuine project isolation.

Jobs run in daemon threads. There is cancellation between operations, but no durable checkpoint/resume
queue for interrupted model/supplier work. JSONL journals preserve evidence, yet
[`RunRecorder`](../src/partlens/records.py) is not a transactional project database or a multi-process
writer-coordination mechanism. Settings use atomic replacement, which is a good existing boundary.

Add project-scoped persistence, revision invalidation, crash recovery, idempotent job steps, concurrency
control and backup/restore. A local transactional store is sufficient initially; preserve existing journals
as audit evidence and H-MEM as recall rather than making semantic memory the sole project database.

### 4. Follow-up chat is deliberately limited

[`ChatEngine.explain`](../src/partlens/chat_engine.py) sends the saved report and current question to a
tool-less model call. Earlier conversational turns are not included in that request, and free-form follow-up
does not initiate another research or revision cycle. Requirement changes use a separate explicit UI action.

This protects engineering state, but it falls short of a normal engineer's iterative investigation.
Moreover, a read-only model can still make misleading prose claims even though it cannot alter the
authoritative result. Production needs grounded, source-linked answers, explicit unsupported-claim handling
and a controlled way to continue investigations against the current project revision. Keep confirmation
and revalidation boundaries intact.

### 5. Data access and commercial meaning are incomplete

The primary operational supplier adapter is JLCPCB. Zetaris is a data/query layer, not independent
manufacturer validation. Mouser/DigiKey and other providers are not established as operational broad
catalogue integrations in this implementation. A developer-approved API is not a universal supplier service
for all future users.

Existing reports retain unresolved currency, ordering-term, assembly-eligibility and fee questions. Some
classification meanings have evidence, but that does not complete the quotation. See
[JLCPCB-INTEGRATION.md](hackathon/JLCPCB-INTEGRATION.md). Production needs customer-authorized access,
permitted caching/redistribution terms, exact manufacturer/order-code normalization, source conflict
handling, freshness and lifecycle/PCN evidence. Do not infer absent commercial values.

The data model already preserves per-field evidence. Extend it toward a reviewed canonical component
identity with separate supplier offers, assembly-service terms and project approvals. General-purpose
manufacturer-document ingestion with page/table/condition provenance is still needed; the curated reference
facts are not an arbitrary-datasheet engineering extraction service.

### 6. Cost comparison is a foundation, not a purchasing or PCBA quotation

The arithmetic and explicit unknowns are useful. Complete costs still depend on ordering terms, eligible
assembly service, applicable loading/setup/stencil/labor charges and other project/order inputs.
[`optimise/search.py`](../src/partlens/optimise/search.py) excludes unverified substitutes and alternatives
with missing required assembly classification/loading-fee information. This is conservative, but limits
usefulness when only component pricing is established.

Provide distinct component-only and assembled-cost optimization modes, each with its actual coverage,
currency, retrieval time and exclusions. Add relevant attrition, packaging, shipping/duties and fabrication
inputs only when the product scope requires them and evidence is available. Unknown fees are not zero.
Keep original-specification equivalence distinct from a future explicitly supported, application-approved
substitution policy; a lower nominal rating alone does not prove an unsafe application.

### 7. Engineers need decisions and handoff, not only conversations

The current app can show evidence and generated artifacts. Production needs a structured review queue:
accept/reject/request-more-evidence, reviewer/reason, affected references, revision applicability and an
exportable change set. An approval must not turn a failed deterministic check into a pass; exceptional
engineering signoff is a separate recorded action with a clear scope.

Improve import field mapping/preview, exact internal/manufacturer/supplier identities, DNP and variant
handling, side-by-side part comparisons, direct source navigation and actionable missing-data requests.
Expose usable reviewed BOM/diff/report exports through the desktop. Netlist/ECAD/PLM integrations can
follow a focused read-only integration; do not require a full CAD replacement to deliver value.

### 8. Release and operational maturity are unfinished

The app is a local build at version 0.1.0, not an installed/supported production release. It is not
Authenticode-signed. Windows runtime/model/service prerequisites remain partly manual. Dependency pins,
Node lockfiles, notices and reproducibility checks exist, but a complete supported release lifecycle does
not follow from those alone.

Production needs a tested installer/bootstrap flow, signed/versioned artifacts, upgrade/rollback and data
migration, dependency/security review, support diagnostics with redaction, and failure recovery. Git SSH
commit signing and Windows executable signing are different controls. For team deployment, add project
permissions, approval roles and agreed data-handling controls when needed; accounts/cloud sync are not
prerequisites for a good single-engineer local product. [NIST SSDF](https://csrc.nist.gov/projects/ssdf)
provides a useful secure-development reference, not evidence that this app complies with a standard.

The 359 tests are regression evidence, not a measure of autonomous reasoning correctness. Recorded local
model runs include successes, repetition limits and parser/provenance failures. There is no representative
engineer-reviewed pilot evaluation establishing general performance or safety. Large BOM performance,
long sessions, interrupted operations, malformed data, source disagreements, unavailable services and
real supported circuit conditions need measured coverage.

## Recommended product boundary and development order

The first production promise should be:

> Import a BOM, identify sourcing/identity risks, investigate alternatives, explain checked differences,
> collect engineer review and export a traceable approved change set.

Keep Design-from-Idea visibly preliminary while this workflow becomes dependable.

| Order | Deliverable | Completion criterion |
|---|---|---|
| 1 | Supported scope and reviewed qualification rules | For each supported family, users can see required inputs, checked conditions, evidence and exclusions. Unsupported cases never appear fully qualified. |
| 2 | Durable project/revision and job lifecycle | Reopen the same project, preserve approvals, invalidate dependent results, resume after interruption and isolate memories between projects. |
| 3 | Dependable supplier/manufacturer evidence | Resolve exact identities, compare source facts with locations/conditions, refresh stale offers and retain licensing/commercial unknowns. |
| 4 | Engineer review and ECAD/BOM handoff | Map an imported BOM correctly, compare parts, record accountable review and export a revision-specific change set without changing design files in place. |
| 5 | Production release and pilot validation | Install/update reliably on supported Windows machines; validate the supported workflow with hardware engineers using authorized designs and measured outcomes. |

Pilot measures should include import fidelity, evidence correctness, false-qualification observations,
task completion, time saved versus manual review, recovery behavior and quote completeness. Select release
thresholds for the declared supported scope before evaluating the pilot. A proposed clean test matrix can
include 50/250/1,000-line BOMs and adversarial source conflicts; these are future test sizes, not completed
performance results. Zero observed false qualifications is an acceptance goal on the reviewed corpus,
not a guarantee about every future component or circuit.

After this boundary is validated, expand supported IC/application checks, design patterns, manufacturing
coverage and team workflows. Defer broad autonomous circuit generation, PCB routing, a PLM replacement
and another desktop-framework migration. The main production gaps are domain coverage, dependable work
completion and integration into engineering review—not the current WebView2 shell.

# HackOS submission draft — owner review required

Historical Existing BOM submission draft. The owner subsequently authorized New Design; its actual scope
and limitations are documented in [DESIGN-GENERATION.md](DESIGN-GENERATION.md). This draft needs owner
review and a scope update before submission; the original measurements below remain historical.

**Not submitted.** This is copy for the owner, not a verified map of current HackOS form fields or rules.
Do not publish until the signed repository, permitted demo evidence, eligibility and owner approval are
resolved. No external form or account was accessed to prepare this draft.

## Project name

PartLens — evidence-backed electronics sourcing, by Cirquill

## Short description

A local AI agent investigates an electronics BOM, retrieves official supplier evidence, runs independent
engineering checks and explains what is verified, rejected or still unknown. Decisions retain provenance
and are rechecked when recalled in another session.

## Problem and solution

Component substitution involves electrical requirements, package fit, changing inventory and assembly
charges. Unit-price comparisons alone conceal missing evidence. PartLens combines iterative investigation
with a bounded workflow controller and deterministic Python checks. The LLM chooses investigations; it
cannot assign verified status, invent a binding requirement or override a failed check.

The desktop presents requirements, exact part identities, evidence, qualification matrices, sourcing
risks, separate quantity scenarios and structured explanations. Missing commercial terms or application
evidence remain explicit rather than becoming confident recommendations.

## Why an agent

The next useful action depends on what is missing: ask about build quantity, inspect a source, research an
alternative or compare a recalled decision with current evidence. A local tool-using model handles that
sequence, while the controller enforces required steps, budgets and current verification. Final factual
claims are rendered from authoritative tool results, not free-form model assertions.

## Demonstrated stack and sponsor usage

- Local Ollama `qwen3.5:9b`: genuine bounded native tool-use evaluation, no paid cloud inference/fallback.
- Official JLCPCB: approved authenticated public component-detail reads for explicit C codes. No private
  library, catalogue extraction, ordering, upload or quotation operation is claimed.
- Zetaris: actual read-only SQL queries over normalized official supplier observations, with recorded SQL,
  execution status, identifiers and result digests. Session tools relate returned data to the imported BOM.
  No local export is counted as sponsor operation; no new persisted official table or legacy-table join is claimed.
- Meterless H-MEM: real reference-engine persistence, separate-process recall and controller-enforced fresh
  verification. Persistence, retrieval and successful engineering qualification are reported separately.
- Deterministic Python: exact Decimal units/costs, provenance-tagged requirements and evidence-backed checks.

Track 02 is the intended track, subject to organizer confirmation. Service usage is documented, not an
endorsement or a claim of award/eligibility. Cursor was not used, following the owner's instruction; the
earlier Cursor workflow condition remains unresolved and is not satisfied by Codex usage.

## Measured results

The documented Milestone 5 official-source research trial and cold session produced eight decisions:
three verified original-specification equivalences, one evidenced rejection and four unverified
alternatives. Application suitability was not promoted without circuit evidence. Ten authenticated
supplier requests and 88 actual Zetaris SELECTs succeeded. Five recalled decisions received fresh
controller-enforced checks: three unchanged and two still lacking required evidence.

The latest reported freeze suite has 245 passing tests. The historical deterministic reference reproduces
104/104 outputs. Official-run deterministic replay reproduced 21/21 research outputs and 3/3 cold-session
outputs, excluding blocked/memory-dependent operations; replay does not prove new service operations.
The original overly strict evaluator false result was retained with a separate correction. These are
observations from bounded trials, not a broad autonomous success-rate claim.

## Limitations

Price currency, MOQ, order multiples and assembly eligibility remain undocumented. Complete purchase and
assembled-board quotations and savings are unavailable. Supplier stock is timestamped, not guaranteed.
IC functionality/pinout/land-pattern evidence and circuit conditions remain incomplete. Raw assembly flags
and inferred classifications cannot establish board-service eligibility.

Actual supplier responses, licensed snapshots and internal recordings are not distributed. The public
fallback is explicitly synthetic and deterministic and proves no live integration. Public capture or
redistribution of real supplier evidence requires permission. Commercial and eligibility questions remain
open; no boards are ordered and no production design files are modified.

## What was built and what existed before

PartLens core, deterministic checks, workflow controller, supplier adapter, bridge integration, UI,
evaluation/replay and original synthetic fixtures were authored during the stated build window from
2026-10-22 00:00 UTC. Existing Cirquill planning/architecture references informed concepts; excluded private
research implementation/data was not copied. The public Easyduino BOM, pinned Meterless reference engine,
Ollama runtime and Qwen model are pre-existing third-party materials with their own licences. Official
documentation and owner-supplied SDK metadata were references; SDK implementation was not copied or run.
Codex was used for development; historical Claude runs are preserved; Cursor usage is not claimed.

Full disclosures: [DISCLOSURE.md](DISCLOSURE.md), [THIRD_PARTY.md](../../THIRD_PARTY.md),
[MILESTONE-5.md](MILESTONE-5.md).

## Owner fields to complete before submission

- Public repository URL and frozen signed commit SHA: **pending**.
- Approved demo/video URL and permission-safe evidence: **pending**.
- Team/member/contact fields: owner to enter directly; no personal details in this public draft.
- Organizer confirmation of track, current rules and Cursor eligibility: **pending**.
- Final measurements: copy only from the latest completed readiness report.
- Owner review and explicit approval to submit: **pending**.

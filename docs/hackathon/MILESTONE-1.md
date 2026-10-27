# Milestone 1: end-to-end agent operation on real data

Status at 2026-10-22 ~00:25 UTC.

## What works

One PartLens workflow runs end to end on real design and supplier data, with persistent memory and a
replayable record:

1. Import the open-source Easyduino RP2040 BOM (CSV, or straight from the KiCad schematic via `kicad-cli`).
2. Resolve 15 purchased lines to LCSC records (real snapshot: parameters, stock, price breaks, lifecycle,
   datasheet links, retrieval time).
3. `find_missing_information` lists what blocks verification and costing (board quantity, fee schedule, PCB
   cost, unidentified pin headers, operating voltages of capacitor lines, input limits of ICs).
4. The planner asks one question; the answer becomes a **user_confirmed** requirement only because the quoted
   words appear verbatim in the recorded user message (otherwise it would be provisional, never binding).
5. Research: candidates from the catalogue (including LCSC's suggested alternates as leads).
6. Deterministic checks decide: e.g. 5 alternates for C1525 verified with per-parameter evidence; an LCSC
   suggested alternate for C25905 **rejected** (25 V vs 50 V rating); diode/connector/IC alternates
   **unverified** (no datasheet equivalence evidence); U3 (W25Q16JVUXIQ) **fails the stock check** (0 in stock
   vs 60 needed).
7. Every decision is written to Meterless H-MEM with its run and decision id; the next run recalls it with
   provenance; identical decisions reinforce the memory (ledgered feedback) instead of duplicating it.
8. The run record replays: 18/18 tool outputs reproduce.

The planner in this run is scripted (no LLM key available). The LLM provider is implemented and uses the same
tools; only the decision of which tool to call next differs.

## Sponsor integrations

| Sponsor | Status |
|---|---|
| Meterless (H-MEM) | **Working**, real engine (reference implementation, pinned commit) through a Node bridge; persistence, recall, ledger history and feedback exercised by tests and the real-data run |
| Zetaris | **Blocked on access.** Client written against the documented REST run-query endpoint, catalogue adapter and CSV export for a file source ready; no instance or credentials on this machine. Needs: Zetaris Cloud account, `zetaris-platform.zip` + registry credentials (local Docker, which meets the requirements here) or a managed AWS cluster |
| NVIDIA | Not started. Plan: evaluate a Nemotron model on datasheet parameter extraction against a labelled set (local GPU: RTX 5070 Ti 16 GB, or NVIDIA API key) |
| Cursor | Requires the owner to develop part of the project in Cursor; `.cursorignore` keeps `experiments/` and credentials out of indexing |

## Tests

`pytest`: 40 passed (units/BOM import, checks, cost and optimiser, LCSC mapping and CSV round trip, H-MEM memory
on the real engine, scripted end-to-end agent workflow with replay).

Required evaluation fixtures, status:

| Fixture | Covered by |
|---|---|
| Missing requirements trigger clarification | `test_end_to_end_agent_workflow` (gap -> ask_user -> user_confirmed requirement); provisional without quote |
| Electrically incompatible alternative | LDO with lower max input voltage rejected (`test_electrically_incompatible_ic_...`) |
| Same nominal value, incompatible characteristics | Y5V and X5R vs X7R, 6.3 V vs 16 V/12 V applied |
| Missing / stale supplier information | missing dielectric -> unverified; 60-day-old data -> availability unverified |
| Quantity-dependent pricing | price break crossing between 60 and 100 boards |
| Assembly fees outweigh unit-price savings | extended part rejected by the optimiser at 60 boards, chosen at 10 000 |
| Prior rejected decision retrieved from memory | second session recalls the rejection with its run/decision provenance |
| Accurate, reproducible cost | hand-calculated totals; repeated estimate identical; replay digests |

## Known limitations / failures

- No LLM-driven run yet (no API key). Replay covers deterministic tools only; memory reads are excluded.
- Supplier data: LCSC retail prices, not assembly-service prices; LCSC does not state basic/extended classes,
  so loading fees cannot be computed for the real design yet (reported as a problem, not guessed).
- The LCSC endpoint is the website's product-detail JSON, not a documented API; use is low-rate and local.
- XC6206 regulator: LCSC lists "operating voltage 8V"; datasheet confirmation not implemented (needed before
  any input-voltage claim).
- Non-passive equivalence (diodes, connectors, ICs, crystals) is always unverified until datasheet evidence
  checks exist.

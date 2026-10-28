# PartLens — hackathon submission

PartLens, by Cirquill, is a Windows desktop app for evidence-backed electronics design and BOM review.
You describe a board idea or import a BOM. A local AI agent interviews you for requirements, proposes a
reference-based architecture and gathers official supplier evidence. Independent deterministic checks
decide compatibility. The app explains what is verified, rejected or still unknown, and keeps every decision
with its provenance.

## Links

| Item | Link |
|---|---|
| GitHub repository (README) | https://github.com/zgeez/PartLens |
| Demo video (1–4 min) | [PartLens-demo.mp4](https://github.com/zgeez/PartLens/releases/latest/download/PartLens-demo.mp4) (2:32, narrated) |
| Slide deck | [docs/PartLens-deck.pdf](../PartLens-deck.pdf) (10 slides) |
| Live demo / Windows executable | [PartLens.exe](https://github.com/zgeez/PartLens/releases/latest/download/PartLens.exe) from the latest GitHub release (desktop app; there is no hosted web demo) |
| Start guide | [docs/START-GUIDE.md](../START-GUIDE.md) |

## Headline demo

A dual-rail breadboard power supply, run live in the desktop app:

- The prompt asks for USB-C input, a 3.3 V rail and a 5 V rail at 500 mA each, and 5 boards. PartLens asks
  for the missing input-voltage limits, and the owner's typed answers become confirmed requirements.
- The XC6206 LDO trial fails two checks: current (0.5005 A needed against its 0.25 A limit) and thermal
  dissipation (0.976 W against 0.25 W). PartLens switches to a TPS63031 buck-boost, which clears both.
  The failed trial stays in the history.
- The 16-role BOM moves into the BOM workspace with one click. 14 roles match official JLCPCB parts. The
  1.5 µH inductor and the 2×2 rail headers stay visibly unmatched instead of being invented.
- Cost stays *incomplete*: JLCPCB does not document currency, minimum order or order multiple.

## How Zetaris is integrated

- `src/partlens/sources/zetaris.py` runs read-only Lightning SQL through the Zetaris REST (UI proxy) API.
  It uses the configuration names from the official getting-started guide (`ZETARIS_BASE_URL`,
  `ZETARIS_ORG_ID`, `ZETARIS_API_KEY`).
- In **Official JLCPCB through Zetaris** mode (`JLCZetarisCatalog`), official JLCPCB observations are
  queried as a relation with real `SELECT`s. The session then relates the returned rows to the imported BOM
  lines and requirements. If either service fails, the app does not silently fall back.
- Every query is journalled: SQL text, request ID, execution time, row count, server identifiers and a
  result digest. Evidence in the app points back to the query that produced it.
- Measured: 88 Zetaris `SELECT`s succeeded in the Milestone 5 official-source trial, and 18 + 16 SQL
  operations succeeded in independent validation on 2026-10-22
  ([SPONSOR-ACCESS.md](SPONSOR-ACCESS.md)). The deployment is owner-local (Docker). When it is not
  running, **Check local services** reports Zetaris as unavailable rather than faking success.

## How Meterless is integrated

- PartLens stores every substitution decision (verified, rejected or unverified) in Meterless **H-MEM**,
  with its run record, decision ID and the checks that produced it (`src/partlens/memory/hmem.py`).
- H-MEM runs as the pinned Meterless reference engine in a separate Node process
  (`integrations/hmem-bridge`), spoken to over JSON lines. The Windows executable bundles this real bridge.
- **Recall & recheck** brings earlier decisions back in a new session. A recalled decision is context, not a
  verdict: the controller forces the deterministic checks to run again on current data and flags any
  disagreement.
- Measured: five recalled decisions were re-verified in a cold session. Three were unchanged; two still
  lacked required evidence and stayed unverified.

## How Cursor was used

Cursor was not used. Development used Codex, Claude Code and Antigravity; none of them are in the
product's runtime path.

## Where NVIDIA contributes

- All AI inference runs locally on an **NVIDIA GeForce RTX 5070 Ti (16 GB)**. Ollama loads the
  `qwen3.5:9b` model (Q4_K_M, 6.1 GB) entirely into GPU memory and runs it on the GPU.
- Local GPU inference keeps the agent private and free of API credits. It also lets PartLens refuse any
  silent cloud fallback: paid inference is disabled in the shipped app.
- No NVIDIA cloud API or NIM endpoint is used.

## Pre-existing components (declared)

| Component | Status |
|---|---|
| Ollama runtime and Qwen `qwen3.5:9b` weights | Pre-existing third-party; downloaded locally, own licences |
| Meterless H-MEM reference engine (commit `1742dec5…`) | Pre-existing, Apache-2.0; vendored by setup, not committed |
| Easyduino RP2040 example BOM | Pre-existing public design, CERN-OHL-P-2.0 |
| pywebview, WebView2, Node.js and Python dependencies | Pre-existing third-party; see [THIRD_PARTY.md](../../THIRD_PARTY.md) |
| Cirquill planning and architecture notes | Informed concepts only; no code copied |
| Official JLCPCB / Zetaris documentation | Reference only; no SDK code copied |

PartLens itself was written during the build window from 2026-10-22 00:00 UTC: the core, deterministic
checks, workflow controller, supplier adapters, memory bridge integration, desktop UI and tests. Full
details: [DISCLOSURE.md](DISCLOSURE.md).

## Limits

New designs are preliminary: there is no validated schematic, ERC, PCB layout or manufacturing output.
Supplier stock is timestamped, not guaranteed. Unknown fees and ordering terms are never invented.
PartLens does not order parts or certify hardware.

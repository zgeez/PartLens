# Development

For everyday use, double-click `dist/PartLens.exe` and use **Settings**. The unified Windows app,
encrypted user-local configuration, external-service requirements and reproducible build are documented
in [docs/DESKTOP.md](docs/DESKTOP.md). Commands below remain developer/reproduction interfaces.

## Requirements

- Python 3.12+ (developed on 3.14)
- Node.js 20+ (Meterless H-MEM bridge)
- Optional: KiCad 10 (`kicad-cli`) to import BOMs straight from schematics
- Optional: a Zetaris instance (local Docker or managed AWS) for the data-access integration
- Ollama with a locally installed tool-capable model for the interactive agent; no API credits needed
- Optional: an Anthropic API key and credits to explicitly select Sonnet (automated tests use synthetic providers)

## Setup

```sh
python -m venv .venv
. .venv/Scripts/activate              # Windows Git Bash; .venv/bin/activate elsewhere
pip install -e ".[dev,llm]"

cd integrations/hmem-bridge
npm install
npm run setup                         # vendors H-MEM reference at a pinned commit into vendor/ (gitignored)
cd ../..

python scripts/validate.py             # preserves results; uses workspace-local temporary directories
partlens smoke-hmem
```

## Layout

```
src/partlens/
  core/        units, typed requirements + provenance, evidence, check results, decisions, BOM import, parts
  checks/      deterministic substitution and sourcing checks (dielectric rules, no-downgrade policy)
  optimise/    assembled-cost model (exact decimals, derivations) and the substitute search
  sources/     catalogue interface; LCSC snapshot adapter; Zetaris REST client and catalogue
  memory/      decision memory on Meterless H-MEM (Node bridge)
  design/      separate New Design requirements, circuit patterns, generated BOM, local agent and UI
  session.py   session state and the operations behind the tools
  tools.py     tool registry (agent now, Cirquill MCP later)
  agent.py     bounded LLM tool loop; explicit workflow required for live providers
  workflow.py  task states, prerequisites, permitted transitions/tools, completion and recovery
  results.py   authoritative factual results, validated references and deterministic explanations
  local_provider.py  loopback-only Ollama provider; explicit native/JSON-schema transport, no cloud fallback
  preflight.py       bounded service/model checks with independent per-service failure reporting
  records.py   append-only run records; replay.py re-executes them
  cli.py       partlens chat | replay | smoke-hmem | smoke-zetaris
integrations/hmem-bridge/   JSON-lines bridge to the H-MEM reference engine
examples/easyduino-rp2040/  open-source demo design (CERN-OHL-P-2.0) and the milestone run script
tests/                      unit, integration and end-to-end tests; synthetic fixtures in tests/fixtures
```

## Configuration and credentials

Credentials are read from the environment or a local `.env.local` (gitignored); see `.env.example`.
**Never commit credentials.** Local state (run records, memory store, supplier snapshots) lives in `.partlens/`
(gitignored).

## Supplier data

Existing LCSC snapshots remain timestamped internal fixtures pending licensing review. Network collection
through the undocumented endpoint is disabled: `fetch_raw()` and `snapshot()` fail before any network or file
write. Do not collect additional records. Official Mouser Search API access is under investigation; it is not
an operational integration yet. Snapshots, reviewed manufacturer evidence and fee schedules stay in
`.partlens/` and are never committed.

## Milestone 2 workflow

```sh
partlens ui --catalog .partlens/cache/lcsc-easyduino.json
partlens live-demo --catalog .partlens/cache/lcsc-easyduino.json
partlens smoke-zetaris                 # queries demo BOM supplier IDs in the configured Zetaris table
```

The desktop interface supports demo import, deterministic review, live review and a new session for recall.
The owner's current selection is local Ollama (`qwen3.5:9b`), with no paid fallback. The selectable cloud default
is `claude-sonnet-5-5`; older Milestone 2 Opus records retain their original model IDs. `live-demo`, `chat` and
the UI all honor `PARTLENS_LLM_PROVIDER`. Anthropic fallback is opt-in with `PARTLENS_MODEL_FALLBACK=default`;
`live-demo` requires it disabled. Both requested and observed model IDs are logged.
Missing credentials, model mismatches and refusals cannot count as a completed baseline.

The Zetaris client uses the official SQL UI gateway origin (`http://localhost:3000` for the local bundle),
not the native API's `:8888/api/v1.0` path. To register the approved internal dataset in the owner's running
local instance, use `python scripts/setup_zetaris_demo.py --catalog .partlens/cache/lcsc-easyduino.json`.
It creates a fresh demo namespace, verifies container file hashes, and requires actual server row counts and
a BOM/supplier join. The instance's configured filesystem root must match `--container-data-root` (default
`/home/zetaris/customer-data/shared`). Set `PARTLENS_ZETARIS_PARTS_TABLE` to the returned table, then run the
smoke command. `partlens ui --zetaris` and `partlens chat --zetaris` use that catalogue directly.

`--evidence FILE` loads operator-reviewed manufacturer evidence without changing the original supplier
fixture. The exact MPN and manufacturer must match. `--fees FILE` selects an explicit fee schedule; unknown
fees remain unknown. Both options are available for `ui`, `chat` and `live-demo`.

See [the Milestone 2 runbook](docs/hackathon/MILESTONE-2-RUNBOOK.md),
[status report](docs/hackathon/MILESTONE-2.md) and [sponsor access research](docs/hackathon/SPONSOR-ACCESS.md).

## Local agent and Milestone 3

The current Windows workspace has official standalone Ollama v0.40.8 in `.partlens/local-llm/runtime` and
Qwen3.5 9B Q4_K_M weights in `.partlens/local-llm/models` (both ignored). Restart the hidden local server with:

```powershell
.\scripts\start_local_llm.ps1
```

For a fresh machine, obtain the Windows standalone archive from the
[official Ollama releases](https://github.com/ollama/ollama/releases), verify its published SHA-256, and extract
it into `.partlens/local-llm/runtime`. Run the script with `-Pull` to download `qwen3.5:9b` (about 6.6 GB).
The launcher binds loopback and disables Ollama cloud features with `OLLAMA_NO_CLOUD=1`. See the
[official Windows instructions](https://docs.ollama.com/windows) and
[cloud-disable setting](https://docs.ollama.com/faq#how-do-i-disable-ollamas-cloud-features).
Local inference requires no Anthropic SDK, key, or credits. It needs sufficient RAM/VRAM for the configured
context. The tested GPU is an RTX 5070 Ti with 16 GB VRAM; local reasoning quality requires separate evaluation.

`.env.local` selects `PARTLENS_LLM_PROVIDER=ollama`, `PARTLENS_LOCAL_MODEL=qwen3.5:9b`, and
`PARTLENS_LOCAL_URL=http://127.0.0.1:11434`. The adapter refuses remote origins, redirects, remote model
metadata, missing tool support, malformed calls and unexpected actual model IDs. Every model turn records
the installed digest, context, token counts and latency. No automatic cloud fallback exists. To select
Sonnet later, explicitly set `PARTLENS_LLM_PROVIDER=anthropic`; the
[official model ID](https://platform.claude.com/docs/en/models/overview) is `claude-sonnet-5-5`. No new Sonnet
API operation was attempted while credits were exhausted.

Run the full local agent and a second independent H-MEM session:

```powershell
python scripts/evaluate_local.py --catalog .partlens/cache/lcsc-easyduino.json --evidence .partlens/reviews/umw-xc6206-20261022T035447Z.json --evidence .partlens/reviews/jlcpcb-classifications-20261022T042918Z.json --fees .partlens/fees/jlcpcb-economic-m3-20261022T071230Z-b93cfd.json --quantity-record .partlens/runs/20261022T043042Z-84edf9.jsonl
```

This restores the original owner answer of one board with its existing message provenance; it does not
fabricate a fresh owner reply. Unattended evaluation leaves other missing inputs unanswered. The review is
bounded to 28 turns/50 tool calls; failures remain recorded. `live-demo` is the separate interactive baseline
for testing a fresh quantity question with an actual user answer.
Use `--zetaris` instead of `--catalog FILE` once the owner's local gateway is running; it was unavailable
at the latest retest. Add `--focused` for guided review of the three documented candidate pairs. That live
model run demonstrated all three statuses and exact-source cold recall, but the model skipped the requested
current recheck and mislabelled a hypothetical scenario in prose. Broader autonomous reviews remain
incomplete. Exact known-run retrieval uses `recall_decisions` with `run_id`; ordinary text search is approximate.

The UI command accepts `--quantity-record` with the same source. Select **Live agent review** to use the local
LLM, inspect the Qualifications comparison and its status filter, then **Compare costs: owner / 60** for the
explicitly hypothetical build. **New session + recall** performs real deterministic memory retrieval and
current checks; it does not itself call an LLM. `scripts/evaluate_local.py` tests recall under the LLM.
See [Milestone 3 results](docs/hackathon/MILESTONE-3.md) and the
[three-minute demo and verification runbook](docs/hackathon/MILESTONE-3-RUNBOOK.md).

## Milestone 4 controlled workflow

Use the [current runbook](docs/hackathon/MILESTONE-4-RUNBOOK.md) and
[acceptance report](docs/hackathon/MILESTONE-4.md). Desktop live review, chat, live-demo and both local
evaluation scripts now supply an explicit `WorkflowRequest`. Direct live-provider `Agent.send()` calls
without that scope are rejected; the legacy uncontrolled path remains for scripted reference tests only.
Provider/model failures inside a controlled run produce an audited partial result. No fabricated owner reply
is created when a clarification is unanswered or cancelled. In controlled mode each question requires a
valid pending gap ID; a stated electrical number/unit must match its quoted owner evidence before binding.

The controller restricts tools/line choices to pending stages, checks all requested lines (including unresolved
identities), spreads investigation across discovered lines, and rebases model context at stage boundaries on
recorded facts. Every rebase and compact model-tool view is audited alongside the complete original outputs.
It retries premature endings up to five times; normal evaluation limits are 40 model turns, 70 tool attempts,
three identical requests and 400,000 cumulative input/output tokens. The installed Qwen uses a 65,536-token
context on the owner's 16 GB GPU. Smaller machines can lower `PARTLENS_LOCAL_CONTEXT`; exhaustion returns
partial results. Budgets are ceilings, not proof the model will complete an arbitrary task.

`reverify_decision` reads the actual H-MEM item, checks design/BOM line, manufacturer/MPN and requirement
context, obtains source records again and executes the deterministic checker. It reports `unchanged`,
`changed`, `changed_context` or `cannot_reverify`. Historical context missing from legacy records is not
invented. Re-reading a fixture does not refresh its inventory timestamp. The controller performs omitted
rechecks itself, with `actor=controller`; these are never counted as model-selected calls.

Final factual prose comes only from `FinalResult`. The model may select actual decision/gap references;
free-form factual drafts are rejected and replaced deterministically. Drafts remain in the audit, not the
Explanation tab. Complete preliminary operations do not mean complete application qualification or costs.
Missing fees, stock/identity issues and hypothetical quantities stay explicit.

`PARTLENS_ALLOW_PAID_INFERENCE=disabled` is the default. A future authorized cloud run requires both explicit
owner approval and the owner setting that value to `owner_authorized`; selecting Sonnet alone cannot trigger
paid inference. No paid call was made in Milestone 4. Do not change this setting on the owner's behalf.

Run `python scripts/sample_demo.py` for the synthetic deterministic fallback. It needs neither a model nor
Node/sponsor credentials, and does not modify or invent the owner's one-board requirement. For real local
model evaluation, use `scripts/evaluate_milestone4.py`; source selection and fault injection are explicit.

## Repository rules

- `experiments/` (a private local research environment) is excluded by `.gitignore` and `.cursorignore`.
- No private design files, fixtures or project-specific configuration from other projects.
- Demo and test designs must be openly licensed; record the licence next to the files.
- Every compatibility *pass* must be produced by a check with evidence. Do not add code paths where an LLM
  output becomes a verification result.
- PartLens must not modify design files in place or order components.

## Commit log and timestamps

Commit timestamps are the record of when work was done. Notable steps are also listed in
[docs/hackathon/TIMELINE.md](docs/hackathon/TIMELINE.md).

## Official component source

`partlens smoke-jlc --code C1525` performs a bounded official public-component lookup. Configure
`JLC_APP_ID`, `JLC_ACCESS_KEY`, `JLC_SECRET_KEY` in ignored `.env.local`; `JLC_APP_NAME` is optional metadata.
Add `--jlc` to UI/chat/cost commands for this supplier. `--jlc --zetaris` executes read-only Zetaris SELECTs
over the official responses without creating tables. All real responses and run records stay in `.partlens/`.
Currency, MOQ, order multiples and assembly eligibility are currently unknown: nominal arithmetic is not a
USD purchase quotation. See [the integration report](docs/hackathon/JLCPCB-INTEGRATION.md) for observed
operations, provenance, cache/retry bounds, tests, data-usage restrictions and reproduction commands.

Milestone 5 adds `--jlc-leads FILE` for discovery from an existing retained internal fixture. Its codes are
leads only: checked specifications, price intervals and stock must come from subsequent official reads.
With `--jlc --zetaris`, the default source is solely the official catalogue through real Zetaris SELECTs;
the legacy table is not automatically added. Use `--catalog` only for an explicitly selected additional source.

`scripts/evaluate_milestone5.py` runs bounded local Qwen research and a separate cold H-MEM session.
`scripts/preview_milestone5.py` instead rechecks actual live-agent selections in the existing desktop,
without calling a model. `partlens replay RUN --recorded-sources` uses lossless source observations offline;
it cannot establish a new supplier or memory success. See the
[Milestone 5 report](docs/hackathon/MILESTONE-5.md) and
[three-minute runbook](docs/hackathon/MILESTONE-5-RUNBOOK.md). Keep the owner's SDK archive and all real
supplier/cache/run artifacts ignored and internal pending data-usage review.

## New Design from an idea

The owner subsequently authorized a separate workflow; Existing BOM behavior remains supported. Read
[DESIGN-GENERATION.md](docs/hackathon/DESIGN-GENERATION.md) for schemas, actual results and limitations.
The local-only entry point requires the Node H-MEM setup above. With configured read-only services:

```powershell
.\.venv\Scripts\python.exe scripts/new_design_demo.py
.\.venv\Scripts\partlens.exe new-design --idea "Design a rechargeable smart LED badge with Bluetooth phone control, an LED matrix, NFC, microphone and IMU." --allow-proposals --unattended --jlc --zetaris
.\.venv\Scripts\partlens.exe ui --jlc --zetaris
```

The first command is an original deterministic reference with no external operations. The second calls
local Qwen; `--allow-proposals` delegates choices as inferred assumptions, never confirmed requirements.
Omit it and `--unattended` for actual interactive clarification. Do not restore an Easyduino quantity into
a new design. `--jlc --zetaris` uses only bounded official observations through actual SELECTs; no private
fixture is needed. Failed/missing evidence yields an incomplete preliminary result and can produce exit 1.
Exports and all real data stay ignored in `.partlens/`. Model evaluation and cold controller recall are
different operations; the documented recheck script does not invoke a second model.

New Design is available from the desktop's top mode bar. The architecture-correction report records the
full temperature-product walkthrough; current badge interaction results are in
`docs/hackathon/FINAL-DESIGN-WORKFLOW.md`. No schematic,
pin-validated netlist, ERC or manufacturing-ready export is implemented.

Use the editable checkout for service workflows: the Python-only wheel does not bundle the Node H-MEM
bridge, whose CLI default path is repository-relative. A general wheel deployment requires explicit bridge
resource configuration and validation; the isolated core/synthetic install does not establish that.

## Architecture correction and independent checkout

Current New Design CLI/UI sessions enable engineering version 2: enumerated full-block selection,
high-impact questions, bounded independent alternatives, target-change confirmation and mandatory
controller completion. Model-selected defaults remain inferred. Supplier-identified leads and exact
reference matches are counted separately; verified role equivalence remains distinct from application.
The original pattern registry/replay path is retained for historical records.

Current CLI/UI sessions additionally journal interaction mode: ranked feature-specific clarification,
typed owner-answer recording, readable views and an **Edit and revalidate** selector. Edits preserve the
quoted answer and rerun controller operations without new inference or accepting the design. Runtime
comparisons include unapplied capacity/current bounds and a relative average-duty factor, with independent
counterfactual checks. Provenance/Audit retain full detail; internal exports add `design-review.md`.

```powershell
.\.venv\Scripts\python.exe scripts/correct_architecture.py --run .partlens/runs/20261023T210850Z-8dbb3c.jsonl --jlc --zetaris
.\.venv\Scripts\python.exe scripts/prepare_partlens_tree.py --verify
```

The correction command restores actual historical provenance, regenerates both trial BOMs, and makes
current read-only source/check/memory operations; it does not call a model. The export command creates a
new audited source-only tree under `.partlens/partlens-source/`, then independently installs an editable
checkout, locked Node bridge dependencies and the pinned public H-MEM reference. Its new venv runs the
real bridge smoke, both original deterministic examples and the entire suite without owner credentials.
It does not initialize Git, add a remote or publish. See
[ARCHITECTURE-CORRECTION.md](docs/hackathon/ARCHITECTURE-CORRECTION.md) for actual results and limitations.

`scripts/revise_design.py` is an operator-only path for relaying a genuine verbatim owner answer to a
recorded design, invalidating prior results and rechecking current evidence. Do not use it to fabricate
evaluation answers. `--answer Monochrome` in the milestone run records the one real asynchronous reply,
not a new simulated answer on every reproduction. No complete cell, charging/protection or pin-level
implementation has been qualified.

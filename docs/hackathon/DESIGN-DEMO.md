# Three-minute New Design demonstration

Current product variant. [SUBMISSION-DEMO.md](SUBMISSION-DEMO.md) retains the earlier Existing BOM demo.
This is a runbook, not a claimed video/submission. Owner approval and supplier-data permissions remain.

Current finalization evidence and failed transport trials are in
[HACKATHON-FINALIZATION.md](HACKATHON-FINALIZATION.md). The interview now separates total LED count,
matrix dimensions, physical arrangement, brightness and drive topology. The latest owner instruction
delegates choices; it does not make 32 LEDs or any geometry a confirmed requirement.

## Exact setup and startup checks (PowerShell)

Run from the authored PartLens source root. Python 3.12+, Node 20+ and Tkinter are required. Installation
needs access to public package registries and the pinned public H-MEM repository.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev,llm]"
Push-Location integrations/hmem-bridge
npm ci
npm run setup
Pop-Location
.\.venv\Scripts\python.exe scripts/validate.py
.\.venv\Scripts\python.exe scripts/sample_demo.py
.\.venv\Scripts\python.exe scripts/new_design_demo.py
if (-not (Test-Path -LiteralPath .env.local)) { Copy-Item -LiteralPath .env.example -Destination .env.local }
```

Configure the owner-authorized values locally as described in [README.md](../../README.md). Do not show
the file during recording. Obtain/checksum the official standalone Ollama runtime first as described in
[DEVELOPMENT.md](../../DEVELOPMENT.md); this restart reuses installed weights. Use `-Pull` only for an
intentional first installation. Start the existing authorized Zetaris deployment/driver without recreating
data, accounts, volumes or namespaces.

```powershell
.\scripts\start_local_llm.ps1
$env:PARTLENS_LLM_PROVIDER='ollama'
$env:PARTLENS_ALLOW_PAID_INFERENCE='disabled'
$env:PARTLENS_MODEL_FALLBACK='disabled'
$env:PARTLENS_LOCAL_PROTOCOL='native'
.\.venv\Scripts\partlens.exe preflight
if ($LASTEXITCODE -ne 0) { throw 'Service unavailable. Inspect the preserved preflight record; use the labeled contingency.' }
.\.venv\Scripts\partlens.exe ui --jlc --zetaris
```

Native is the original/default transport. To explicitly try the separately recorded JSON-schema mode,
set `$env:PARTLENS_LOCAL_PROTOCOL='json-schema'` before starting the UI; it uses documented Ollama
structured outputs and the same checks. A failure never triggers an automatic protocol/model switch.
The desktop **Check services** button shows the same independent startup results. Model inspection is
not inference; fresh JLC HTTP, a Zetaris SELECT and H-MEM hello/stats are distinct operations.
If a service is unavailable, retain its failure record and act on the displayed setup instruction.

## Preparation outside the timed segment

1. Install the editable source checkout/pinned Node bridge following [DEVELOPMENT.md](../../DEVELOPMENT.md).
2. Start local Ollama/Qwen3.5:9b with cloud disabled and the existing authorized Zetaris deployment/driver.
   Never reset storage to repair a demo. Configure JLC/Zetaris in `.env.local` without displaying secrets.
3. Run `partlens smoke-hmem`, `partlens smoke-zetaris` and the complete suite. Process health is not a
   successful query, and a smoke is not proof of the agent's subsequent operation.
4. Run `partlens ui --jlc --zetaris`. Click **New Design from an idea** and type only:
   “Design a rechargeable smart LED badge with Bluetooth phone control, an LED matrix, NFC, microphone and IMU.”
5. Check **Delegate missing choices as provisional assumptions**; click **Generate with local agent**.
   Relay only actual owner answers. Identify an earlier Monochrome relay as historical, not a new response.
   Cancel unanswered questions. Leave model numbers provisional.
   Inspect `led_count`, `led_rows`, `led_columns`, `led_arrangement`, `brightness` and `led_drive` separately.
   A derived count such as 8 × 16 = 128 is visibly provisional. A conflicting explicit count fails its check.
6. Allow model/network latency before the timed narration. Preserve a separate labeled capture of the
   original idea, dialogs, model ID and timestamp. Do not imply a prepared result is fresh three-minute inference.
7. Inspect the run for actual JLC HTTP responses versus cache hits, real Zetaris SELECTs and memory write
   IDs. Do not claim failed operations. Keep real supplier evidence internal until permission is established.

## Timed narration and exact controls

| Time | Action | Narration |
|---|---|---|
| 0:00–0:20 | Idea and Overview | “PartLens starts with an incomplete idea. This preliminary architecture and BOM came from the recorded local Qwen run.” |
| 0:20–0:40 | Requirements | “Monochrome is owner-confirmed. Numeric choices remain assumptions. Missing answers affect the architecture.” |
| 0:40–1:00 | Architecture, Checks | “Reviewed references define blocks. Independent checks identify supply/energy problems. Named nets are not a verified schematic.” |
| 1:00–1:30 | Alternatives; scroll to runtime options | “Converters are compared against the same targets. More output current does not create battery energy. Capacity/current bounds do not invent a cell or PWM setting.” |
| 1:30–1:50 | Generated BOM, Sourcing | “Exact supplier identity, role equivalence and application safety are different. Missing evidence, rejected candidates and stock constraints have distinct reasons.” |
| 1:50–2:15 | Requirement selector, **Edit and revalidate** | “An actual owner edit invalidates dependent results and reruns checks; prior failures remain.” Use only a real answer. Otherwise open and Cancel. A repeated Monochrome relay is a confirmation/recheck, not a changed numeric target. |
| 2:15–2:35 | Cost | “Quantities are labeled confirmed or hypothetical. Partial component arithmetic is not a full purchase or assembly quote; unsupported terms remain unknown.” |
| 2:35–3:00 | Explanation, Audit | “Structured results drive this explanation. The journal separates model choices, controller checks, live calls, cache and memory writes. Remaining uncertainty prevents a finished-circuit claim.” |

If revision exceeds the slot, show the running state then a visibly labeled recorded result. Do not hide
asynchronous waits as fresh completion. New Design memory writes do not prove cold recall; show the
separately documented Existing BOM recall only with its own date/run and independent recheck evidence.

The owner supplied delegation again, not a new numeric answer. A changed numeric owner revision therefore
cannot honestly be included in the current real demo. Show the existing Monochrome confirmation/recheck
with its historical source, or open **Edit and revalidate** and Cancel. Label synthetic numeric-revision
tests as synthetic. Do not narrate reconfirmation as a changed count, runtime or power target.

## Contingency and capture

`python scripts/new_design_demo.py` is the original distributable deterministic architecture example;
`python scripts/sample_demo.py` covers synthetic Existing BOM checks. Keep their banners visible: neither
is Qwen or live JLC/Zetaris/H-MEM. `partlens replay RUN --recorded-sources` is offline; it cannot establish
fresh inventory or memory. Historical source-version limitations remain in milestone reports.

For the public contingency, close the live run after its recorded failure and execute the two deterministic
scripts above from the authored source root. Keep their mode banners visible. Narrate: “This is the original
synthetic deterministic example. It demonstrates the requirements/checking logic; it makes no fresh Qwen,
JLCPCB, Zetaris or Meterless operation.” Show its exported report/BOM and the preserved failure separately.
No real supplier response or owner memory store is needed for this path.

## Separate real cold-memory operation (outside the timed model segment)

The following is the actual recorded desktop trial's controller-only cold recheck. It restores its
requirements/model-selected patterns, opens the existing H-MEM store, recalls and independently rechecks
current sources. It does not run another model or invent an owner revision. These paths exist only in
the owner's internal development state; a public checkout needs its own completed run/store.

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/recheck_generated_design.py `
  --run .partlens/finalization-ui-v2/new-design-runs/20261024T224040Z-4889f0.jsonl `
  --memory-store .partlens/finalization-ui-v2/new-design/20261024T224040Z-4889f0/hmem `
  --no-revision --jlc --zetaris
```

Observed original recheck: five bounded recalled memories, four unchanged, one cannot_reverify;
`.partlens/runs/20261024T225001Z-4bfafe.jsonl`. Capture the timestamp/model_called=false label and
current outcomes. Do not imply all 18 persisted decisions were recalled, or that unchanged role
equivalence verifies the full application. Retain the explicit unresolved result.

Capture the idea/model/run/time, unanswered question and exact owner quote; confirmed/assumed blocks;
preserved failures/revision; converter and runtime checks; separate identity/role/application status;
source/retrieval/cache/HTTP/query evidence; incomplete costs; actual memory IDs; final explanation/export.
Inspect every frame for credentials, personal information and restricted supplier content. Use synthetic
scenes when public supplier-record permission is unavailable. Final capture/export needs owner review.

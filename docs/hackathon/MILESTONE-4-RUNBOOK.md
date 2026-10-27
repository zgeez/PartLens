# Milestone 4: reproduce and demonstrate

All timestamps and source identifiers are retained in ignored local run records. Do not distribute the
internal supplier cache or secret configuration. The public fallback uses original synthetic fixtures.
No ordering, design editing, Cursor use or HackOS submission is part of this workflow.

## Fresh judge environment

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe scripts/sample_demo.py
.\.venv\Scripts\python.exe scripts/validate.py
```

The sample is explicitly **synthetic and deterministic**. Its data in `tests/fixtures/` is Apache-2.0;
it is not live Qwen, supplier inventory, Zetaris or Meterless evidence. The open Easyduino BOM and its
CERN-OHL-P-2.0 licence remain under `examples/easyduino-rp2040/`. Actual supplier snapshots remain local.

For genuine local runs, install Node 20+ and the pinned H-MEM bridge as described in DEVELOPMENT.md;
obtain the official standalone Ollama runtime and pull `qwen3.5:9b` using `scripts/start_local_llm.ps1 -Pull`.
The owner-local copy is already installed. `.env.example` lists nonsecret settings; keep real values solely
in `.env.local`. Start Ollama on loopback with cloud disabled. The tested context is 65,536 on a 16 GB GPU.
Paid inference must remain disabled unless the owner separately authorizes it.

## Verify the existing Zetaris instance

```powershell
wsl -e bash -lc 'cd ~/zetaris-install/zetaris-platform && docker compose ps --all && ./verify.sh'
.\.venv\Scripts\partlens.exe smoke-zetaris
```

The first command is read-only verification. If services are stopped, use the existing deployment's normal
non-destructive startup. Never remove volumes, reset accounts, recreate the dataset or overwrite its
namespace. The gateway is `http://localhost:3000`; the existing owner table remains configured locally.
Require actual successful queries, result IDs, HTTP status, response hashes and server timing bound to the
current run. Server query/request IDs remain null when the gateway does not supply them. Client UUIDs are
not server IDs. Reading the retained dataset through Zetaris does not refresh supplier stock/prices.

## Genuine Qwen evaluations

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/evaluate_milestone4.py --scenarios A,C,B,E_timeout,E_arguments,E_unavailable,E_budget,E_stale --zetaris --evidence .partlens/reviews/umw-xc6206-20261022T035447Z.json --evidence .partlens/reviews/jlcpcb-classifications-20261022T042918Z.json --fees .partlens/fees/jlcpcb-economic-m3-20261022T071230Z-b93cfd.json --quantity-record .partlens/runs/20261022T043042Z-84edf9.jsonl
```

A includes autonomous research and cost evaluation D. No candidate pairs are supplied in its prompt.
C opens a separate H-MEM process and recalls/rechecks A's actual decisions. B asks missing electrical
questions; an unattended callback supplies no answer. Its acceptance pass means honest partial reporting,
not fabricated completion. E tests explicitly injected timeout, malformed arguments, source outage,
context-version mismatch and real budget exhaustion. The argument injector preserves the original model
proposal; it is not blamed on the model. The stale-context test changes only an in-memory context marker,
never a design file or owner requirement. All injected failures are labelled; they are not sponsor outages.
Missing flash engineering evidence is exercised in the genuine A data without inventing a datasheet.

Use `--catalog .partlens/cache/lcsc-easyduino.json` instead of `--zetaris` for internal local-fixture runs,
and label the operation accordingly. Reports live in a fresh `.partlens/milestone4/<id>/` directory;
full run records remain under `.partlens/runs/`. Both passing and failed attempts are preserved.

## Desktop and programmatic acceptance

Restart any existing PartLens window to load the new code/configuration.

```powershell
.\.venv\Scripts\partlens.exe ui --zetaris --evidence .partlens/reviews/umw-xc6206-20261022T035447Z.json --evidence .partlens/reviews/jlcpcb-classifications-20261022T042918Z.json --fees .partlens/fees/jlcpcb-economic-m3-20261022T071230Z-b93cfd.json --quantity-record .partlens/runs/20261022T043042Z-84edf9.jsonl
.\.venv\Scripts\python.exe -X utf8 scripts/smoke_milestone4_ui.py --zetaris --evidence .partlens/reviews/umw-xc6206-20261022T035447Z.json --evidence .partlens/reviews/jlcpcb-classifications-20261022T042918Z.json --fees .partlens/fees/jlcpcb-economic-m3-20261022T071230Z-b93cfd.json --quantity-record .partlens/runs/20261022T043042Z-84edf9.jsonl
```

The second command tests actual Tk widgets/callbacks, supplier tools and a cold memory process. It is not
visual acceptance. Native desktop interaction was unavailable in this session; no Milestone 4 screenshot
or full visual pass is claimed. The owner should manually check all eight tabs, scrolling, source URLs and
timestamps, status/detail pairing, and one/60 labels. Confirm application uncertainty is visible beside a
verified equivalence; historical results are labelled after context changes. Check that partial errors and
unanswered questions remain visible. Inspect both cost scenarios rather than just their note. Start a new
session and inspect the actual memory source and current comparison outcome.

## Three-minute demonstration

| Time | Show | Claim supported by the display |
|---|---|---|
| 0:00–0:20 | Demo BOM, Requirements | Nineteen rows; the owner's one board retains its original message source. Sixty is hypothetical. |
| 0:20–1:20 | Live agent review, workflow states and run record | Qwen selects candidates; the controller requires actual checks and prevents premature completion. Allow model startup outside the timed segment. |
| 1:20–1:50 | Qualification filters and Evidence | A verified equivalence, rejected rating/value and unverified flash option; application safety remains separate. Show the actual source/check. |
| 1:50–2:10 | Sourcing and a successful SQL event | Actual Zetaris operation over retained timestamped data; original flash recorded stock zero, unresolved headers. Do not claim live stock refresh. |
| 2:10–2:35 | Cost comparison | Component subtotals USD 11.10/166.34 and known conditional subtotals 23.88/179.12 at the recorded inputs; complete assembled totals and quotations unavailable. |
| 2:35–2:55 | New session + recall | Real H-MEM source, context match and current check. This UI button is deterministic; separate live-Qwen C records show controller-enforced rechecks. |
| 2:55–3:00 | Authoritative explanation | Scope, remaining gaps and audit references. The factual display comes from tools, with model drafts retained separately. |

If a live run fails, show the actual partial result or dated prior evidence and disclose the failure.
Use the labelled synthetic fallback when required services/data are unavailable; do not describe it as
live integration. Do not submit anything to HackOS.

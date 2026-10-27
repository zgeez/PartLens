# Milestone 3: run and demonstrate

Use only the approved Easyduino RP2040 BOM. Local state paths below are owner-local, ignored files; do not
publish them or recordings containing configuration. Requirements, compatibility and prices come from the
tools, not model prose. All runs, including failures, remain under `.partlens/runs/`.

## Start locally, without API credits

```powershell
.\scripts\start_local_llm.ps1
```

Select Ollama in `.env.local` as shown in `.env.example`. New processes load that selection; an already
running desktop process must be restarted to discard older provider environment values. **Live agent review**
uses this provider. No Anthropic calls or paid fallback occur in local mode. The documented Sonnet option is
for later explicit selection when credits are available; it has not been live tested in this change.

```powershell
.\.venv\Scripts\partlens.exe ui --catalog .partlens/cache/lcsc-easyduino.json --evidence .partlens/reviews/umw-xc6206-20261022T035447Z.json --evidence .partlens/reviews/jlcpcb-classifications-20261022T042918Z.json --fees .partlens/fees/jlcpcb-economic-m3-20261022T071230Z-b93cfd.json --quantity-record .partlens/runs/20261022T043042Z-84edf9.jsonl
```

The quantity record restores the original answer `1` with its original source; it is not a new live answer.
For a fresh live clarification test, omit that flag and answer the actual displayed question yourself.
Do not type a scripted response and describe it as a new owner's live confirmation.

## Check the real integrations

The local Zetaris gateway was unavailable at the last retest. Start the owner's existing Docker Desktop and
Zetaris deployment locally using its authorized setup. Keep `.env.local` gateway/table unchanged. Then:

```powershell
.\.venv\Scripts\partlens.exe smoke-zetaris
.\.venv\Scripts\python.exe -X utf8 scripts/verify_milestone3.py --zetaris --evidence .partlens/reviews/umw-xc6206-20261022T035447Z.json --quantity-record .partlens/runs/20261022T043042Z-84edf9.jsonl
```

Require an actual HTTP 200 query, matching demo result IDs, SQL, execution status, response digest and server
timing. The gateway does not expose server query IDs; do not present client UUIDs as server IDs. `--zetaris`
instead of `--catalog FILE` selects server-side catalogue access in the UI and local-agent evaluation.
Local JSON execution does not prove Zetaris availability. H-MEM validation must persist a new decision,
close its process, reopen another process, recall its exact source and rerun the deterministic check.
For a known preceding run, pass its `run_id` to `recall_decisions` for exact design/source lookup. Ordinary
text search is approximate and can miss persisted decisions. Exact retrieval is labelled and carries no
synthetic relevance score; it still cannot establish current compatibility without a recheck.

For the full bounded local LLM and cold agent recall, use the `scripts/evaluate_local.py` command in
[DEVELOPMENT.md](../../DEVELOPMENT.md). The example uses the retained local fixture; select `--zetaris`
when the gateway is running. Do not call a partial/failed model run a pass.
Add `--focused` to evaluate the three documented operator-specified candidate pairs. This remains a real
LLM tool loop but does not demonstrate autonomous candidate discovery. The latest guided local run produced
all three qualification statuses and the second session recalled them; the model skipped its requested
current recheck and mislabelled the hypothetical scenario in prose. Inspect authoritative Qualifications,
Requirements and Cost tabs, and disclose these limits. The UI's deterministic recall button does perform
current checks; do not confuse it with the incomplete live-agent recall workflow.

## Three-minute demo

| Time | Show | What to say accurately |
|---|---|---|
| 0:00–0:25 | Import demo; Requirements/Parts | PartLens identifies the BOM and missing evidence; owner quantity is one with original message provenance. |
| 0:25–0:55 | Live agent review; run tab | The selected local LLM chooses tools. Show actual model ID and real calls; disclose a model failure if it occurs. |
| 0:55–1:35 | Qualifications and Evidence | Compare original/candidate manufacturer and MPN; show a verified equivalence, evidenced rejection and unverified flash alternative from recorded deterministic checks. Application qualification is separate. |
| 1:35–2:00 | Sourcing and SQL record | Show zero flash stock and unresolved headers. Demonstrate a real Zetaris query only if the server actually succeeds now; otherwise show dated prior evidence and the current blocker. |
| 2:00–2:30 | Compare costs: owner / 60 | One-board and explicitly hypothetical 60-board subtotals; MOQ/stock and separate manufacturing terms. Assembled totals and savings are incomplete, not quotes. |
| 2:30–2:50 | New session + recall | Show the actual H-MEM source and a current deterministic recheck. This button is deterministic; distinguish a separate live-agent recall run. |
| 2:50–3:00 | Explanation and run record | The useful recommendation includes evidence, rejected alternatives and missing information. No order or design edit occurs. |

Prepare relevant prior records before recording; allow actual model startup time outside the three minutes.
If a live model has not demonstrated all outcomes, the **Deterministic review** button can inspect the
engineering workflow, explicitly labelled as deterministic execution rather than live model performance.
Do not claim that a local model or Sonnet matches the historical Opus baseline without evidence.

## Final manual checks and automated validation

The owner interrupted computer control before final visual acceptance. Manually inspect all eight tabs,
horizontal/vertical scrolling, original/candidate fields, URLs/times and expected/observed values. Switch
the qualification filter among all three statuses and ensure the detail follows the visible selection.
Inspect the complete one/60 cost report and its missing inputs. Start a new session, recall and inspect
memory provenance/rechecked outcomes. Confirm provider errors remain visible and partial results survive.

```powershell
.\.venv\Scripts\python.exe scripts/validate.py
.\.venv\Scripts\python.exe -X utf8 scripts/smoke_ui.py --catalog .partlens/cache/lcsc-easyduino.json
```

The UI smoke is programmatic, not a visual pass. The full tests use synthetic records; external integration
proof comes from actual operational records. See [the report](MILESTONE-3.md) for failures, signing and gaps.
Use Codex only; the owner prohibited Cursor. No HackOS submission is authorized by this runbook.

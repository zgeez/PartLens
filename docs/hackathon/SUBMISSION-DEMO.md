# Three-minute submission demonstration

Historical Existing BOM demonstration. The owner subsequently authorized a separate New Design workflow;
use [DESIGN-DEMO.md](DESIGN-DEMO.md) for the current interactive demonstration and
[FINAL-DESIGN-WORKFLOW.md](FINAL-DESIGN-WORKFLOW.md) for measured results and limits.
The procedure below retains its original scope and evidence; it does not demonstrate the new workflow.

Status: executable owner-local procedure; public recording/export permission is unresolved. No video has
been fabricated or published. A three-minute walkthrough does not mean the full model evaluation finishes
in three minutes. Use an honest preflight and keep its complete audit, including failures.

## Choose the mode before recording

| Mode | What actually happens | Required label |
|---|---|---|
| Fresh autonomous evaluation | Local Qwen calls tools; official HTTP reads, actual Zetaris queries, H-MEM persistence and a cold agent session | Live local-agent evaluation; show this run's IDs and outcomes |
| Desktop walkthrough | New deterministic official reads/checks of selections made by the recorded live agent; actual UI cold recall | Recorded live-agent selections; current deterministic review; no new model call |
| Recorded evidence | Open the earlier genuine run or offline deterministic replay | Historical run / offline replay; original timestamps; no fresh service operation |
| Public contingency | Synthetic BOM and supplier fixtures with deterministic tools | SYNTHETIC DETERMINISTIC SAMPLE; no live model or sponsor operation |

Do not show supplier API content in a public recording until written permission is resolved. Use the
synthetic contingency for public capture, with an explicit statement that authentic operations are
documented internally. Private reviewer access also requires applicable permission; do not assume an
unlisted video or private link resolves the data-use restriction.

## Preflight from the repository root

1. Follow README setup; keep paid inference disabled, Ollama cloud off and all credentials local.
2. Run the validation and supported smoke tests. Stop on failures; retain their new records.
3. Ensure the existing Zetaris gateway and authorized demo table are available. Do not reset the deployment.
4. Confirm the original quantity record, retained code-lead fixture and reviewed fee file exist. They are
   intentionally absent from a public checkout; do not replace them with fabricated owner evidence.
5. Prepare a clean desktop/capture region. Hide terminals containing configuration, account pages,
   personal windows and filesystem usernames. Do not record `.env.local`, tokens or SDK download URLs.

```powershell
.\.venv\Scripts\python.exe scripts/validate.py
.\.venv\Scripts\partlens.exe smoke-hmem
.\.venv\Scripts\partlens.exe smoke-zetaris
.\.venv\Scripts\partlens.exe smoke-jlc --code C1525 --refresh
```

To run a new genuine local-agent evaluation, not a script pretending to be the model:

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/evaluate_milestone5.py --jlc-leads .partlens/cache/lcsc-easyduino.json --quantity-record .partlens/runs/20261022T043042Z-84edf9.jsonl --fees .partlens/fees/jlcpcb-economic-m3-20261022T071230Z-b93cfd.json
```

It prints the new A/C run paths and preserves a new bundle. Candidate pairs are not supplied. Inspect the
new reports rather than assuming earlier results repeat. The approved reference is A
`20261023T030853Z-988c1b` and cold C `20261023T031043Z-53c2ef`; their evaluator correction is preserved in
`20261023T031346Z-60d653`. Budgets and observed outcomes are in [MILESTONE-5.md](MILESTONE-5.md).

Open the existing UI using the observed live reference selections and fresh deterministic supplier reads:

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/preview_milestone5.py --run .partlens/runs/20261023T030853Z-988c1b.jsonl --quantity-record .partlens/runs/20261022T043042Z-84edf9.jsonl --fees .partlens/fees/jlcpcb-economic-m3-20261022T071230Z-b93cfd.json
```

For a newly accepted A run, substitute its actual path after inspecting it. The preview prints its own new
run path. Its banner states no new LLM call. The populated Parts table proves import; this preview imports
before opening the window. Do not pretend a later Load demo click was the original import.

For a fresh, initially empty UI instead:

```powershell
.\.venv\Scripts\partlens.exe ui --jlc --zetaris --jlc-leads .partlens/cache/lcsc-easyduino.json --quantity-record .partlens/runs/20261022T043042Z-84edf9.jsonl --fees .partlens/fees/jlcpcb-economic-m3-20261022T071230Z-b93cfd.json
```

Click **Load demo**, wait for completion, then **Live agent review**. This really calls Qwen and can take
longer than the narration. Allow bounded completion; if partial, show it as partial. Do not click
Deterministic review and describe it as Qwen. Finish the model review before capturing a timed walkthrough.

## Narration and click sequence

Use the tested reference preview for predictable navigation. Status-filter menu items are identified by
label rather than screen coordinates so the instructions survive display scaling.

| Time | Exact action | Narrator script |
|---|---|---|
| 0:00–0:20 | Parts tab; point to imported L1, L11, L18. If using the empty-UI mode, capture Load demo separately before the timed walkthrough. | “PartLens reviews an electronics BOM. This is the open Easyduino example. The selections came from a recorded live Qwen investigation; this window performs current deterministic checks.” |
| 0:20–0:35 | Requirements tab; show board quantity, binding provenance and missing conditions. | “The owner asked for one board. Sixty is a separate hypothetical scenario. Missing circuit conditions remain gaps.” |
| 0:35–0:55 | Sourcing tab; point to the flash stock failure. Then Parts, select L1 to open its Evidence. | “The genuine Qwen run investigated sourcing. PartLens reads official JLCPCB data through actual Zetaris queries. Here are exact identity, source and retrieval time; inventory is not guaranteed procurement.” |
| 0:55–1:15 | Qualifications tab, status filter verified; select L1. Read original/candidate identities and scroll the check matrix. | “The model chose a candidate. Independent checks establish specification equivalence. Application suitability remains unverified until circuit evidence is supplied.” |
| 1:15–1:35 | Filter rejected; select L1's C1557 candidate. Scroll to capacitance failure. Then filter unverified; select L18. | “A higher voltage rating cannot rescue the wrong capacitance: 27 pF is not 100 nF. The flash alternative remains unverified because package, pinout and function evidence is incomplete.” |
| 1:35–1:55 | Cost tab; show both overview rows and native nominal observations. | “One board and hypothetical sixty use quantity price tiers. Currency, MOQ and order multiples are unknown, so these are not complete purchase or assembled-board prices. No complete savings is claimed.” |
| 1:55–2:20 | Click New session + recall once. Wait for Finished. Explanation tab; show historical sources and current comparisons. | “A new session retrieves real Meterless memories. The controller reruns checks with applicable evidence; recalled verified text cannot authorize a new replacement.” |
| 2:20–2:40 | Qualifications tab; show current verified/unverified columns. Run record tab; note new run path. | “The UI rechecks up to three distinct items. The separate live cold-session evaluation rechecked all five returned items: three unchanged, two still impossible to verify.” |
| 2:40–3:00 | Show the genuine recorded agent explanation using the command below, then the README architecture. | “This is the recorded live agent's evidence-backed result, not a fresh model call. The controller, deterministic checks and provenance constrain the agent. Unknown manufacturing terms and eligibility remain disclosed.” |

Display the authentic preserved final explanation without calling the model or modifying a record:

```powershell
.\.venv\Scripts\python.exe -X utf8 -c "from partlens.records import read_events; e=read_events('.partlens/runs/20261023T030853Z-988c1b.jsonl'); print(next(x['rendered'] for x in reversed(e) if x['type']=='agent_result'))"
```

For a fresh UI Live agent review, its own Explanation tab displays its structured result instead; identify
that actual run. Do not combine recordings from different runs without visible labels and timestamps.
Cold recall creates a new context; compare costs before it, because prior-context cost output is not reused
as a newly confirmed estimate.

## Contingency and public-safe capture

```powershell
.\.venv\Scripts\python.exe scripts/sample_demo.py
```

Keep its synthetic banner onscreen. Show import, independent checks and explicit unknowns. Say:
“This is the distributable synthetic fallback. It demonstrates the verification design, not live Qwen,
JLCPCB, Zetaris or Meterless. Actual operations are documented separately; access and publication limits
remain.” It has no owner quantity, live sourcing claim or H-MEM recall. Do not fabricate those missing
scenes; use clearly labeled architecture slides for explanation.

For an internal audit demonstration only:

```powershell
.\.venv\Scripts\partlens.exe replay .partlens/runs/20261023T030853Z-988c1b.jsonl --recorded-sources
```

State “offline deterministic replay.” It reuses recorded observations and skips blocked/memory-dependent
operations. A/C's actual memory operations must be evidenced by their operational records.

## Onscreen evidence checklist

- Mode/run label, original timestamps and actual `qwen3.5:9b` identity from the genuine run.
- Imported BOM and original one-board quotation/message source; sixty visibly hypothetical.
- Official source, exact MPN/manufacturer, retrieval time, request status/trace and Zetaris query locator.
- Check matrix with one verified equivalence, one evidenced failure and one unverified alternative.
- Separate application status; raw classification confidence and unresolved assembly eligibility.
- Stock risk, unknown purchase terms and incomplete cost/savings labels.
- H-MEM historical source, new session ID and fresh comparison outcomes with model/controller attribution.
- Structured explanation and replay counts, with excluded operations disclosed.
- Before any export: inspect every frame for secrets, personal information and restricted supplier content.

Native Windows UI review and successful operational evidence already exist in the Milestone 5 report.
The final capture/edit/export and owner approval are still required; this document is not a claimed video.

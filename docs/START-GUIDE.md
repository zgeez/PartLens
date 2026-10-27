# PartLens start guide

PartLens helps you design a small electronics board from an idea, or review an existing bill of materials
(BOM). A local AI model asks questions and runs the investigation. Independent checks, not the AI, decide
whether a part is compatible. Anything without evidence stays **unverified**.

## 1. Before you start

| You need | Why | How |
|---|---|---|
| Windows 10/11 x64 | The app is a Windows executable | — |
| Microsoft WebView2 Runtime and .NET Framework 4.6.2+ | The app's window | Already present on most Windows 11 machines |
| [Ollama](https://ollama.com) with `qwen3.5:9b` | The local AI model; no cloud, no API credits | Install Ollama, then run `ollama pull qwen3.5:9b` |
| JLCPCB open-platform keys (optional) | Real part data from JLCPCB's official API | Your own JLCPCB developer account |
| Zetaris (optional) | Query supplier data through your own Zetaris SQL gateway | Docker Desktop running the Zetaris "run locally" deployment |

Without supplier keys, PartLens uses clearly labelled synthetic example data, so you can still try every
workflow.

## 2. First launch

1. Double-click **`PartLens.exe`**.
2. The **Add your API keys** screen opens. It also appears once for existing profiles after this update;
   keys you already saved show as *Saved securely* and stay unless you replace them:
   - Enter all three JLCPCB values (Application ID, Access key, Secret key), or leave them all empty.
   - Optionally enter your Zetaris gateway origin, organization ID, API key and existing supplier table.
   - **Save keys** encrypts them for your Windows user on this computer. They are never written to the
     project, the executable or browser storage.
   - **Import .env file** reuses an existing `.env.local` file.
   - **Skip for now** starts with synthetic examples. You can add keys later in **Settings**.
3. The in-app **Start guide** tour starts next. It moves through Conversations, the BOM workspace and
   Settings, highlighting each control and explaining it (Next, Back, Skip tour; arrow keys and Esc work).
   Replay it any time from **Start guide** in the sidebar. Change keys later in **Settings › Suppliers**.
4. Click **Check local services** (bottom of the sidebar) to see which services actually respond:
   Ollama, JLCPCB, Zetaris and the Meterless memory engine. A saved key is not proof the service works;
   this check is.

## 3. Design a board from an idea

1. In **Conversations**, choose **New design** mode and describe what you want, for example:
   *"Design a breadboard power supply PCB powered from USB-C with a 3.3 V and a 5 V rail, 500 mA each.
   Build 5 prototype boards."*
2. PartLens asks about missing requirements one at a time. For each question you can:
   - **Specify in chat**: type your answer. Your exact words become a confirmed requirement.
   - **Let AI set requirement**: the AI picks a sensible value. It stays *provisional* (an assumption,
     not your requirement) until you confirm it in your own words.
   - **Leave unanswered**: the requirement stays open and is reported as unresolved.
3. PartLens proposes an architecture and runs deterministic checks, such as current budget and thermal
   dissipation. If a choice fails, it tries an alternative, and the failed attempt stays in the history.
4. The report lists requirements, architecture, generated BOM roles, alternatives, supplier evidence and
   cost scenarios. Open **Evidence** (top right) to inspect each result and its source.
5. Click **Open in BOM workspace** to move the generated BOM into the review workspace.

You can keep typing or attach a BOM while PartLens works. A message sent mid-job waits above the message
box (with **Cancel**) and is sent when the job finishes; while a question is open, what you type answers it.
A BOM attached in BOM review mode starts its own review conversation.

The result is a **preliminary design**. It is not a validated schematic, PCB layout or manufacturing file.

## 4. Review a BOM

1. Open **BOM workspace**, then **Load demo** or **Import CSV** (KiCad-style CSV with LCSC/MPN columns).
2. **Run checks**: deterministic matching, availability and replacement checks. No AI is involved.
3. **Local agent review**: the local model investigates and asks questions such as the build quantity.
   It cannot override a failed check or confirm a requirement for you.
4. **Compare costs**: your confirmed quantity versus a hypothetical 60-board scenario. Unknown currency,
   minimum order or fees keep the cost marked *incomplete*.
5. **Recall & recheck**: brings back earlier decisions from Meterless memory and re-runs the checks on
   current data.
6. **Engineer review**: accept, reject or mark proposals as needing evidence. **Export reviewed
   proposal** writes a reviewed copy; your original BOM is never modified.

Badges: **Verified** means the evidence supports it. **Rejected** means a check failed.
**Unverified** means evidence is missing. **Unmatched identity** means no supplier part was matched.

## 5. Where your data lives

- Settings and encrypted keys: `%LOCALAPPDATA%\PartLens\settings.json`
- Conversations, run records, caches and memory: `%LOCALAPPDATA%\PartLens\state`

Nothing is deleted when you start a new session; earlier records and failures are kept.

## 6. Troubleshooting

| Symptom | Cause and fix |
|---|---|
| Zetaris shows *unavailable* | The gateway is not running. Start Docker Desktop and your Zetaris deployment, check that `http://localhost:3000` opens, then **Check local services** again. If Docker started before WSL, the `zetaris-driver` container exits (code 127) while the UI stays up: run `docker start zetaris-driver-1` and wait until it is healthy. |
| Ollama shows *unavailable* | Start Ollama and make sure `qwen3.5:9b` is installed (`ollama list`). |
| "Supplier lookup limit reached" | JLCPCB requests are capped per session. Those lines stay unverified; start a **New session** to check them again. |
| Every BOM line shows *Unmatched identity* | Synthetic mode cannot match real JLCPCB codes, or supplier keys are missing. Add keys in **Settings**, then **Run checks**. |
| Settings could not be loaded | Credentials are encrypted for the Windows user who saved them. Sign in as that user; the file is kept, not overwritten. |

More detail: [desktop guide](DESKTOP.md) · [saved projects and reviews](PROJECTS.md)

# PartLens Windows application

Double-click `dist/PartLens.exe`. No Python, Node, npm or command-line switches are needed to launch it.
The executable contains the local HTML/CSS/JavaScript desktop, engineering controller, synthetic examples,
approved Easyduino BOM, Python runtime and real pinned Meterless H-MEM bridge with its Node runtime. It is a Windows x64 build,
not a cross-platform executable. It extracts read-only runtime files to a temporary directory on launch.

The desktop uses pywebview with an explicitly selected Microsoft WebView2 renderer. Windows must have
WebView2 Runtime and .NET Framework 4.6.2+ installed; PartLens does not silently fall back to Internet
Explorer. These are Windows platform components, separate from the app's bundled Python and Node.
The app does not launch a website or expose a local HTTP API. All frontend resources are bundled.

## Settings

Click **Settings** in the sidebar. Categories in the same window configure:

- **Local model:** installed Ollama model ID, loopback URL, native/JSON-schema transport, context and timeout.
- **Suppliers:** synthetic demonstration, official JLCPCB, official JLCPCB through Zetaris, or an existing
  Zetaris supplier table; JLCPCB application credentials and optional app name.
- **Zetaris:** authorized SQL gateway origin, organization/key, optional engine, supplier table and supplier type.
- **Storage & services:** current settings/evidence location, external dependencies and bundled notices.

**Import .env.local** stages authorized values in Python; credential values are never returned to the form.
**Save changes** validates
and applies them. It keeps earlier sessions/evidence. Saving is blocked while an operation is active.
Missing connection fields do not prevent opening Settings. A new installation
starts in explicitly labeled synthetic mode; it never pretends to have live supplier access.

Preferences and encrypted credentials live in `%LOCALAPPDATA%\PartLens\settings.json`; run records, caches
and H-MEM state are under its `state` folder. Credentials use Windows user-scoped DPAPI, not plaintext JSON.
They normally require the same Windows user/computer to decrypt ([Microsoft DPAPI documentation](https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptprotectdata)); importing an authorized `.env.local`
again is the supported way to configure another machine. Do not publish either settings or runtime state.
Source/developer `.env.local` remains supported separately. The executable never embeds those values.

Approved demo BOM inputs are retained in hash-addressed `examples` folders next to the user's state,
with their licenses. Run records therefore keep usable input paths after one-file extraction cleanup.
Updates create new example revisions; old inputs and evidence are not overwritten.

The model provider stays local Ollama with cloud/paid fallback disabled. Credentials are masked. The
settings screen cannot change engineering checks, verification status or requirement provenance.
Saved credential fields are blank and masked. Leave blank to retain a key; use **Clear saved value** and
save to remove one explicitly. Credentials never enter browser history or local/session storage. Applying
new settings clears the previous service-availability display until new checks succeed.

## Daily workflow

1. Install Ollama and pull the selected model. On launch PartLens tries to start a stopped loopback
   `ollama serve` in the background; it never downloads models or contacts a remote/cloud provider. The
   authorized Zetaris deployment is optional and only needed for the Zetaris supplier modes.
2. Click **Check local services** in the sidebar for real diagnostics. A stopped service is reported independently.
3. Describe an idea in **New design** mode and click **Send**. Each requirement question offers three
   choices: type an exact answer in the composer (**Specify in chat**), **Let AI set requirement** (recorded
   as a provisional, non-binding agent default) or **Leave unanswered**. Only typed answers bind.
   Assistant commentary renders as formatted Markdown and stays labeled as commentary.
4. Choose **Review a BOM** on the welcome screen for the demo, or **Attach BOM** to select a CSV.
   Synthetic mode selects the distributable synthetic BOM; official modes select the approved Easyduino example.
5. Open **Evidence** for recorded requirements, architecture, checks, sourcing, costs and tool activity.
   Results render as structured cards with PASS / FAIL / UNVERIFIED badges and source links.
   **Open in BOM workspace** (on a New Design report) imports the generated BOM as a new immutable project revision and runs
   matching, availability and replacement checks; unsourced mechanical placeholders are marked DNP.
   **Update requirement** records an explicit typed owner answer and independently revalidates its effects.
   **Recheck** re-executes the current design checks/sourcing without calling the model.
6. Follow-up messages explain the saved report. They are labeled **Commentary, not a decision** and cannot
   change requirements or engineering results. For a new investigation, start **New conversation**.
7. Saved chats appear in the sidebar; the delete control hides a chat (a tombstone is appended and its
   journal stays on disk). **BOM workspace** opens the detailed review page in the same window.
   Load a demo or CSV, choose **Run checks** for deterministic review or **Local agent review** for actual
   model tool use, inspect replacement scope/application results, compare costs, or **Recall & recheck**.
   BOM questions use the shared web dialog. File pickers remain native Windows dialogs.

Keyboard shortcuts: Enter sends, Shift+Enter inserts a line, Ctrl+N starts a conversation, Ctrl+J toggles
Evidence and Ctrl+, opens Settings. **Stop** takes effect between operations; an in-flight request may
finish or time out first. Records and older report revisions remain preserved.

Manufacturing-ready schematics, routing, placement and purchasing are not implemented. Unknown power,
battery, pin/footprint, commercial and application evidence remains unverified. The LLM cannot approve a
failed check. Earlier local-agent repetition failures remain relevant; an executable is not a reliability fix.

## Build from the source checkout

For durable BOM work, use [saved projects and engineer review](PROJECTS.md). Imports create immutable
revisions; reopening displays historical results until rechecked. Reviewer acceptance covers checked
reference attributes and exports a proposal; it does not authorize manufacturing or override a check.

Python 3.12+, Node and the pinned H-MEM source are required on the **build** machine. The current tested
build uses CPython 3.14, Node 24.12.0, PyInstaller 6.22.3, pywebview 6.2.1 and pythonnet 3.2.1.

```cmd
.venv\Scripts\python.exe -m pip install -e ".[dev,llm,desktop,desktop-build]"
```

Install locked bridge dependencies/pinned H-MEM as documented in [DEVELOPMENT.md](../DEVELOPMENT.md),
then build and run tests from CMD:

```cmd
.venv\Scripts\python.exe -X utf8 scripts\build_desktop.py
.venv\Scripts\python.exe scripts\validate.py
```

Output: `dist/PartLens.exe` (gitignored). Build logs, input lists, license sources/hashes, earlier binaries
and acceptance reports remain in `.partlens/desktop-builds/<run>`. Build data comes from an explicit
allowlist: no environment files, encrypted settings, supplier snapshots, SDK archives, model weights,
private designs, operational records or unrelated platform directories. Developer CLI/scripts remain
available for reproducibility; users do not need to choose between them to launch the application.

Prepared brand assets are included in source. Regenerating their size/format variants is optional: install
development-only `Pillow==13.0.0`, then run `python scripts/prepare_brand.py`. The original image prompts
are in [BRAND.md](../assets/brand/BRAND.md). Pillow is not needed to run or package the prepared app.

The build executes the actual one-file application away from the repository with external Python/Node
removed from `PATH`. Its offline acceptance checks real bundled H-MEM persistence/cold recall, synthetic
verified/rejected/unverified engineering decisions, New Design generation/exports, DPAPI credential
round-trip and the actual WebView2 renderer. It navigates Chat/Settings/BOM, verifies masked credential
forms and escaped message HTML, imports the synthetic BOM, executes deterministic checks, compares
one-board/hypothetical 60-board costs and independently recalls/rechecks H-MEM decisions. This is CMD
acceptance, not a visual walkthrough or a live model/supplier claim. Earlier Tkinter tests remain in the
source suite; the new EXE excludes Tkinter. Source-only `partlens ui` remains a historical developer entry
point; use `partlens-app` or `python -m partlens.desktop` for the supported web desktop.

Optional CMD diagnostics use fresh output filenames:

```cmd
dist\PartLens.exe --self-test --data-dir .partlens\desktop-check --report .partlens\desktop-check.json
dist\PartLens.exe --check-services --data-dir .partlens\desktop-services --import-env .env.local --report .partlens\desktop-services.json
```

The second command performs genuine authorized read-only service operations and writes encrypted local
configuration. It does not start paid inference or silently switch protocols/providers.

## Distribution and provenance

The executable is built locally and is not Authenticode-signed. No Git signing bypass, remote creation,
upload or publication is performed. SSH Git signing and Windows application signing are separate concerns.
Original code remains Apache-2.0; bundled runtimes keep the notices in **Settings → Storage & services →
View bundled licenses and notices** and [THIRD_PARTY.md](../THIRD_PARTY.md). The old README is retained in
the historical snapshot. Earlier standalone candidates and all
negative runs remain historical, rather than being replaced by this application build.

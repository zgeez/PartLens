# Unified web desktop

PartLens now uses original local HTML/CSS/JavaScript hosted in **pywebview 6.2.1 / Microsoft WebView2**.
Chat, Settings, BOM review, evidence, requirement editing, service results and notices share the same
design system. The primary application no longer opens the earlier Tkinter Settings/BOM windows.
Native Windows file pickers are retained. The final Part + Lens component/magnifier mark is used in the
sidebar, window and EXE icon. No new circuit patterns or supplier interfaces were introduced.

The owner asked whether Electron would be better. Electron is also suitable for a web desktop and bundles
its own Chromium/Node engine. The selected WebView2 approach reuses the Windows runtime and preserves the
existing Python engine and one-EXE build. This is a Windows application, not a cross-platform Electron
package. UI quality comes from the shared web presentation rather than the host shell alone.
References: [Electron process model](https://www.electronjs.org/docs/latest/tutorial/process-model),
[WebView2 distribution](https://learn.microsoft.com/en-us/microsoft-edge/webview2/concepts/evergreen-vs-fixed-version),
[pywebview Windows requirements](https://pywebview.flowrl.com/guide/installation).

## Architecture and retained authority

The frontend is bundled and loaded from in-memory HTML; it serves no HTTP API and loads no CDN scripts,
fonts or application assets. A single native `request` method exposes an explicit action allowlist.
Per-process bridge authentication and the current local-document URL are checked before dispatch.
All engineering operations remain in the existing Python agent/controller, deterministic checks,
supplier adapters, Decimal cost model and real H-MEM bridge. Unknown inputs still fail closed.

Conversation journals from the prior interface remain readable. Chat explanations remain labeled
commentary; they cannot edit results. Actual typed requirement answers and explicit requirement edits
still pass through exact-quote provenance and independent revalidation. New report revisions and old
failures remain preserved. BOM review supports demo/CSV import, deterministic checks, local model review,
confirmed-versus-hypothetical cost comparison, and a new-session H-MEM recall with current rechecks.
Report folders retain full journals, including audit details not rendered in summary tables.

Windows DPAPI storage is unchanged. Existing credentials are not returned to browser forms: forms show
configured flags, masked empty inputs and an explicit clear control. Imports are staged in Python.
Blank inputs retain existing credentials. No credentials enter browser local/session storage or frontend
logs. Settings are blocked during active operations and clear old service-availability indicators.
Native file selection is required for imports; callers cannot supply arbitrary file paths through the
bridge. Private material remains excluded. Dynamic model/source text uses DOM text nodes rather than HTML.

The content policy blocks remote connections, forms, frames and object content. Inline scripts/styles
are the bundled application; `unsafe-eval` is required by pywebview's native JS bridge/evaluation API.
No model or supplier text is evaluated. Chromium is checked explicitly before launch: an unavailable
WebView2 renderer raises a startup error rather than opening an Internet Explorer fallback. Temporary
browser profiles use unique, absolute subdirectories verified to remain inside application state.

## Verification

The full CMD suite reached **359 passing** (346 preserved baseline tests plus 13 bridge regressions):
`.partlens/validation/tests-20261026T202911Z-0dd379.txt`. These cover bridge authentication, navigation
away from the local document, allowed actions, unchanged/corrupt journals, revision polling, credential
privacy/retention/clearing, invalid/paid settings rejection, restricted file selection, actual inline
answers/skips, cancellation and deterministic BOM import.

Actual WebView2 acceptance succeeded at
`.partlens/web-renderer-acceptance/20261026T202357Z-31152f/result.json`. It rendered all three pages, checked
five local-model fields and three masked supplier fields, saved encrypted settings, escaped an HTML/script
injection fixture, imported five synthetic BOM rows, executed verified/rejected/unverified checks,
compared an owner-answer one-board scenario with hypothetical 60, and performed three real H-MEM recall
rechecks. The reported browser was Chromium/Edge 155. No model or real supplier operation was called.

The first packaged web build also passed this renderer acceptance outside the source checkout with
external Python/Node removed from PATH:
`.partlens/desktop-builds/20261026T202934Z-639c9d.jsonl`. Final build/acceptance and archive/source audits
are recorded in the ignored desktop-builds, desktop-audits, source-preparation and validation folders.
DOM acceptance is not visual acceptance. Visual review, when completed, is recorded separately.

Preserved negative results include two renderer probes using a relative WebView2 cache path, which
failed initialization; an absolute path resolved that failure. The first successful renderer revealed
a BOM bridge argument-name collision, corrected without changing the engineering controller. The full
restricted test run had a legacy Tk file-loading failure (358 tests passed):
`.partlens/validation/tests-20261026T202757Z-2a56d0.txt`. The subsequent CMD run under normal Windows
permissions passed all 359. The legacy code/tests remain in source and their failure was not suppressed.

## Installation and limitations

Use [DESKTOP.md](../DESKTOP.md). The one-file Windows EXE includes Python, HTML/CSS/JS, the native bridge,
SDK controls and Node/H-MEM. It requires installed Microsoft WebView2 Runtime and .NET Framework 4.6.2+;
Ollama/model weights and authorized Zetaris remain external. It installs no Windows runtime automatically.
New dependency licenses and the exact SDK redistribution notice are included in the EXE notices and
listed in [THIRD_PARTY.md](../../THIRD_PARTY.md).

This presentation migration does not improve local-model reasoning reliability, complete quotations,
validate manufacturing-ready circuits or resolve sponsor/eligibility/data-permission questions. Existing
source-only legacy UI entry points and tests are retained for history; the supported application is
`PartLens.exe`, `partlens-app` or `python -m partlens.desktop`. No paid inference, Cursor, private designs,
orders, publication or signing bypass was used. Git signing remains enabled; no new commit is claimed.

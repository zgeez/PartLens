# Third-party components

| Component | Licence | How it is used | Committed? |
|---|---|---|---|
| Meterless H-MEM reference engine (`engines/hmem/reference`, github.com/Meterless/Meterless, commit `1742dec56a66e58eef9dda2d2b865823758ca8cd`) | Apache-2.0 | Decision memory engine, run in a Node process behind `integrations/hmem-bridge` | No: vendored by `npm run setup` into `integrations/hmem-bridge/vendor/` (gitignored) |
| tsx (npm) | MIT | Runs the TypeScript bridge | No (npm dependency) |
| Easyduino RP2040 design by Hanqaqa (github.com/Hanqaqa/Easyduino, commit `53b14b66d64f25c55f88971c1c1b51656126bd30`) | CERN-OHL-P-2.0 | Demo design: BOM exported read-only from its schematic | Yes: `examples/easyduino-rp2040/bom.csv` and the licence text |
| anthropic (Python SDK) | MIT | LLM provider for the agent (optional extra) | No (pip dependency) |
| Node.js, existing build runtime v24.12.0 | MIT and bundled dependency notices | Runs the bundled real H-MEM bridge in the Windows executable | No binary in Git; executable includes node.exe and the versioned official LICENSE text |
| CPython 3.14 | PSF and component-specific licenses | Bundled Python engineering engine | No runtime binaries in Git; executable includes interpreter and license notices |
| Tcl/Tk | Component-specific licenses | Earlier desktop; retained in source for historical tests | No longer bundled in the web desktop executable |
| pywebview 6.2.1 | BSD-3-Clause | Local HTML/CSS desktop with explicit WebView2 renderer | Pip dependency; license bundled, source not vendored |
| pythonnet 3.2.1 / clr_loader 0.3.1 | MIT | Windows .NET interop for the webview | Pip dependencies; licenses bundled |
| Microsoft.Web.WebView2 SDK 1.0.3856.49 | Microsoft BSD-style redistribution terms | WebView2 .NET controls/loader shipped by pywebview | SDK binaries in executable; exact [NuGet license](https://www.nuget.org/packages/Microsoft.Web.WebView2/1.0.3856.49/License) extracted and included |
| WebView2 Evergreen Runtime / .NET Framework | Microsoft terms | Shared Windows prerequisites | Not bundled or installed automatically by PartLens |
| bottle 0.13.4 / proxy_tools 0.1.0 | MIT | pywebview dependencies; frontend uses in-memory HTML, no HTTP API server | Pip dependencies; notices bundled |
| cffi 2.1.1 / pycparser 3.12 / typing_extensions 4.16.0 | MIT-0 / BSD-3-Clause / PSF-2.0 | Desktop bridge dependencies | Pip dependencies; license files bundled |
| PyInstaller 6.22.3 | GPL with bootloader distribution exception | One-file Windows build and bootloader | Build dependency; COPYING/exception included in executable notices |
| [Ollama](https://github.com/ollama/ollama), official standalone v0.40.8 | MIT; bundled dependencies retain their notices | Local inference runtime; published release archive SHA-256 verified | No: `.partlens/local-llm/runtime/` (gitignored) |
| [Qwen3-8B](https://huggingface.co/Qwen/Qwen3-8B), Ollama `qwen3:8b` Q4_K_M | Apache-2.0 | Local tool-use model; installed manifest digest `500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41` | No: weights in `.partlens/local-llm/models/` (gitignored) |
| [Qwen3.5-9B](https://huggingface.co/Qwen/Qwen3.5-9B), Ollama `qwen3.5:9b` Q4_K_M | Apache-2.0 | Selected local tool-use model after bounded evaluation; manifest digest `56671c2ab9385f9cfcb404638e32cd62d88e3501d44822208363c010179a3c90` | No: weights in `.partlens/local-llm/models/` (gitignored) |

The Zetaris platform is accessed over its REST API; no Zetaris code or images are included.

The desktop executable additionally contains an esbuild-produced bundle of the already-disclosed pinned
H-MEM reference, original bridge code and the installed Node runtime. It retains the pinned engine's
official Apache-2.0 license and source attribution. esbuild is a build tool (MIT), not a runtime dependency
in the executable. Python, Node, the web desktop dependencies and PyInstaller notices are collected explicitly into the executable's
`licenses` resources. Build inputs never include `.env.local`, user settings, real supplier records,
SDK archives, operational evidence or model weights. Ollama and Zetaris remain external services.

The web desktop's original HTML/CSS/JavaScript is Apache-2.0. It loads no frontend framework, font or
script from a CDN. Existing requirements, deterministic checks, Decimal costs, supplier adapters, run
journals and H-MEM remain Python/Node operations behind a restricted native bridge. The prior Tkinter
implementation and its tests are retained as historical/source compatibility material; primary application
Chat, Settings, BOM workspace and dialogs share the new web presentation.

The official component API is accessed under the owner's approved JLCPCB developer application and
[API agreement](https://api.jlcpcb.com/docs/agreement). Supplier responses, normalized snapshots and
comparisons are internal ignored runtime data, not Apache-2.0 data or a redistributed catalogue. Official
documentation informed an original Python implementation; no Java Parts SDK implementation is included.
The optional local `pypdf` 6.21.2 installation (BSD-3-Clause) was used only to read approved documentation,
not as a PartLens runtime dependency. Details and restrictions:
[integration report](docs/hackathon/JLCPCB-INTEGRATION.md).

The owner-provided JLCPCB Business SDK archive contains Java artifact
`com.szjlc.overseas:overseas-openapi-sdk-java:1.0.6-SNAPSHOT`. Its archive/class inventory and Maven metadata
were inspected as a contract reference; no implementation was executed, decompiled, copied or incorporated.
No source/Javadocs were bundled. The original archive and ignored local JAR retain their third-party terms;
they are not Apache-2.0 project artifacts and are not redistributed. See the
Milestone 5 investigation.

Rules: third-party code and data keep their licences and notices; anything vendored at setup time is recorded
here with its source URL and revision.

## Project visual identity

The original PartLens lens/circuit mark and decorative welcome illustration were generated for this
project with the built-in image-generation tool. [Asset provenance and exact prompts](assets/brand/BRAND.md)
identify the source images and their PNG/icon derivatives. These are project artwork, not manufacturer
documents, sponsor marks, copied chat-app graphics or engineering evidence. No claim of exclusivity or
trademark clearance is made. Pillow 13.0.0 was used only during development for PNG metadata removal,
resizing and Windows icon encoding; it is not a runtime dependency or bundled in the executable.

## New Design reference facts

The original `src/partlens/design/patterns.py` definitions use paraphrased facts and supporting-component
roles from Espressif, TI, Lumissil, STMicroelectronics, Microchip and Samsung manufacturer documents. Exact
links, relevant locations and review limits are listed in
the Design Generation record. The Knowles microphone remains an unreviewed
lead. Manufacturer PDFs, schematics, trademarks and supplier responses are not project-licensed assets
or bundled documents. No vendor circuit implementation, SDK code or CAD library was copied. Original
pattern/check code and the from-scratch deterministic concept example are Apache-2.0; cited source
documents and third-party data retain their respective terms. A same-named part from another manufacturer
does not inherit reference evidence. SKiDL/KiCad documentation was investigated; neither exporter was
installed or incorporated for this feature.

The correction milestone adds original reference-role/check definitions informed by the official TI
TPS63802/TMP117 datasheets, Espressif module/SoC pin and reset documentation, and Samsung 4.7/1 µF product
pages. Exact source links and limits are in
the Architecture Correction record. No manufacturer PDF, circuit
implementation or supplier response is bundled. Uniroyal code leads are not independently qualified
resistor reference data. No new runtime dependency was introduced; independent checkout setup retrieves
the existing declared Python dependencies, locked bridge dependencies and pinned H-MEM engine, retaining
their licenses. Generated local design/source-check trees and all genuine responses remain ignored.

## Local project database

The project/review store uses Python's standard-library `sqlite3` wrapper (PSF license) and the SQLite
runtime distributed with CPython; the current Windows build reports SQLite 3.50.4. SQLite dedicates its
deliverable library to the public domain; see the [official copyright statement](https://www.sqlite.org/copyright.html).
No SQLite build scripts, extensions or external database service are incorporated. The application uses
the existing CPython distribution rather than adding a pip database dependency.

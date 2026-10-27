# Autonomous architecture correction and BOM completion

Observed milestone results, October 24, 2026. This extends [DESIGN-GENERATION.md](DESIGN-GENERATION.md)
and preserves its 275-test baseline, original designs, failed evaluations and source records. **Neither
demonstrated product is an accepted complete circuit or a manufacturing-ready BOM.** No schematic,
pin-accurate netlist, ERC, assembled hardware or complete manufacturing price is claimed.

## Delivered behavior

- Bounded alternative comparison recalculates circuits against the same requirement fingerprint. A new
  converter can be investigated only if it resolves a recorded failure without adding one. Investigation
  invalidates the previous BOM/qualification/cost state; it is explicitly a research trial, not final acceptance.
- The original converter and failures remain in architecture history and the append-only journal. A
  necessary ideal battery-capacity lower bound is calculated rather than inventing a larger selected cell.
- Established targets cannot be changed by model proposals to make constraints pass. Changing a confirmed
  target requires an actual new quoted user answer. Current results are invalidated and rechecked.
- Exact capacitor choices, additional bounded resistor leads and explicit I2C pull-up roles extend support
  component research. Rejected/unverified candidates and missing identities remain visible. An incompatible
  candidate is retained in research history and excluded from selected sourcing results.
- A distinct temperature-monitor product exercises the same session, source, checks, cost and memory code.
- The desktop has an Alternatives tab and uses the same authoritative report/factual renderer as the CLI.
- An audited source-only checkout can be prepared and independently installed with the real pinned H-MEM
  bridge. No Git repository, remote, push or publication was created.

## Architecture and acceptance

`design/extensions.py` adds only two justified extensions: a higher-current buck-boost alternative for the
recorded failure, and a temperature sensor for the second product. Original `PATTERNS` definitions remain
unchanged. `all_patterns()` makes the additions available to engineering-mode sessions. Historical
New Design records without a `design_engineering_mode` event retain the original workflow on replay.
Existing BOM tools, supplier clients, compatibility engine and memory implementation were not replaced.

`design/iteration.py` compares at most three choices: the current architecture and reviewed power-block
alternatives. Each gets independent checks, failed/new/resolved constraints and unresolved acceptance
gates. Requirements are unchanged. At most two improvement trials are permitted. The present comparator
does not synthesize arbitrary power paths, battery chemistries, matrix protocols or load profiles.

`design/validation.py` adds evidence-backed module-pin existence, unique/excluded GPIO checks and GPIO
matrix capability; conditional converter input/startup/output/current checks; feedback derivation; bus,
pull-up, package/land-pattern and thermal/peak-load gates. **Module-pin existence and routing capability
are separate from actual pin mux, peripheral concurrency, firmware configuration or physical connections.**
I2C address straps, clocks, capacitance/rise time and sink limits remain unverified. SPI mode/CS/timing
contracts and complete peripheral allocation are not established by this limited library. No interface
passes merely because its name appears in a pattern.

Final acceptance fails closed on any failed or unverified circuit check, unresolved requirement
confirmation, missing role/application qualification or incomplete sourcing qualification. All demonstrations
remain `accepted=false`. Passing the conditional supply comparison is not complete regulator or battery
signoff. The MCU supply reserve is not average consumption.

New tools are `select_design_patterns`, `compare_design_alternatives` and
`investigate_design_alternative`. The first uses enumerated pattern IDs and requires every applicable
block, avoiding abbreviated or invented IDs. High-impact questions are asked before pattern selection;
delegation permits inferred assumptions, never a fabricated answer. After model proposal/comparison,
the controller executes mandatory generation/source/check/cost/memory steps without further inference.
Each operation records its actual actor. Model and controller tool counts must not be conflated.

The normal agent budget remains 40 model turns, 80 tool attempts and a 300,000 cumulative token stopping
threshold between turns. A final model turn can exceed that threshold. Reference/controller operations
are reported separately from autonomous model evaluations.

## Independent references and limits

| Reference | Facts used / remaining limits |
|---|---|
| [TI TPS63802 Rev. D](https://www.ti.com/lit/ds/symlink/tps63802.pdf), pp.1, 5–6, 17–20 | Conditional 2 A output at input ≥2.3 V/output 3.3 V; startup >1.8 V. Typical circuit uses 0.47 µH, 10 µF input, 22 µF output and a feedback divider. The 511k/91k example gives about 3.308 V nominal; tolerance, transient, thermal, effective capacitance and inductor margins remain unverified. |
| [TI TMP117 Rev. D](https://www.ti.com/lit/ds/symlink/tmp117.pdf), pp.5–7, interface/application sections, p.35 | Recommended operating voltage, digital I2C contract and 100 nF bypass. ADD0 wiring, pull-ups, bus speed, package/pads, sensor mounting and application accuracy remain unverified. No medical-use claim. |
| [Espressif module v2.2](https://documentation.espressif.com/esp32-c3-mini-1_datasheet_en.pdf), p.11; [SoC v2.4](https://documentation.espressif.com/esp32-c3_datasheet_en.pdf), p.36 | Exact exposed GPIO/module-pin numbers and digital matrix capability. Firmware routing, debug configuration, timing and endpoint connectivity remain unresolved. |
| [Espressif reset guidance](https://espressif.github.io/esp32-c3-book-en/chapter_5/5.2/5.2.2.html) | 10k/1 µF RC is a starting recommendation, subject to actual supply/reset timing. Role presence is not a boot/reset timing signoff. |
| [Samsung 4.7 µF](https://product.samsungsem.com/mlcc/CL10A475KO8NNN.do), [1 µF](https://product.samsungsem.com/mlcc/CL05A105KA5NQN.do) | Exact packaging suffixes, capacitance, package, rated voltage, dielectric and tolerance. The selected older 4.7 µF family is NRND; lifecycle/application risks remain explicit. Bias/ESR/temperature and implementation are not qualified. |

Primary PDF application pages were inspected visually. The Uniroyal manufacturer catalogue could not be
retrieved through the document reader because of its size; no resistor family qualification was invented
from that failed read. Public JLCPCB pages establish explicit-code leads only. All runtime stock, pricing,
classification and distributor specifications come from the approved authenticated adapter through actual
Zetaris SELECTs. Manufacturer labels are not silently aliased, including ISSI/Lumissil, Espressif labels
or Microchip labels. No undocumented interface, private library or catalogue mirroring was used.

## Recorded failure redesigned with unchanged requirements

The original `20261023T210850Z-8dbb3c` badge architecture was restored with original typed provenance,
not imported as a BOM. In current controller run **`20261024T052540Z-df42ff`**:

1. Regenerate and independently source/check the original architecture, including additional support roles.
2. Compare TPS63031 with TPS63802 using exactly the same requirement fingerprint.
3. Investigate the improving converter reference; regenerate/source/requalify/cost it and persist decisions.
4. Retain the original failed design and all current unverified gates.

The conservative reserve plus proposed LED load is 0.692 A. The original conditional 0.5 A capability
fails the screen; the replacement's conditional 2 A reference clears that screen. The six-hour/500 mAh
runtime bound still fails. The derived ideal LED-only necessary capacity is about 905 mAh before other
loads/losses; it is **not a selected battery or a sufficient runtime guarantee**. No requirements were
changed and no complete design was accepted.

This operation made two fresh official POSTs (HTTP 200, bounded 14-code then one-code responses), 44
actual Zetaris SELECTs and real H-MEM writes. Example query locator:
`zetaris:933189a3-7b21-4738-9bde-da0c1ec11596`, HTTP 200, one row. The journal retains SQL, result
identifiers, times, response digests and actual client/available server traces; absent server IDs are not
invented. It is **controller-operated, with no model call**, not an independent autonomous LLM result.

Before/after exports are in `.partlens/architecture-correction/20261024T052540Z-df42ff/`.
Earlier corrections `20261024T045016Z-7c7ac8` and `20261024T050721Z-0db97c` remain intact. A subsequent review fixed missing named-net
intent entries for newly added pull-ups; the latest run above includes that correction. Endpoint pins
remain `null` and all net intent remains unvalidated.

## The original 22 unsourced roles

Line numbers in this inventory refer to the original 35-role run, not the expanded/reordered BOM. New
roles and all candidate observations/check matrices are exported in `role_inventory` and `sourcing_history`.
The table reports public identities/reference requirements, not redistributable supplier response records.

| Original role | Requirements / current outcome |
|---|---|
| L1 charger | MCP73831T-2ACI/OT lead C424093 queried. Manufacturer-label discrepancy and exact application/package contract remain unresolved; no alias forced. |
| L2 charger input bypass | Reviewed Samsung CL10A475KO8NNNC / C19666, 4.7 µF, 0603, 16 V, X5R, 10%. Official identity/spec evidence supports role match; effective capacitance/application and NRND risk remain. |
| L3 charger battery bypass | Same reviewed 4.7 µF choice; exact cell/charge environment remains unverified. |
| L4 programming resistor | Charge-current target, exact cell charge limits and thermal conditions missing. No arbitrary RPROG value or suitable candidate selected. |
| L5 BLE module | ESP32-C3-MINI-1-N4X / C9900263492 queried. Manufacturer label/land pattern, RF, boot/configuration and observed availability prevent completion. |
| L8 enable pull-up | 10k/0402 lead 0402WGF1002TCE / C25744 queried and supplier identity retained. Independent exact resistor reference/rating/application qualification remains unverified. |
| L9 enable delay | Samsung CL05A105KA5NQNC / C52923, 1 µF, 0402, 25 V, X5R, 10%; role match qualified, actual reset timing unverified. |
| L10 reset button | Contact function known; actuator/mechanical dimensions, exact footprint and rating contract missing. No arbitrary switch selected. |
| L11 boot button | Boot/strap sequencing, exact switch/mechanical/pad contract missing. |
| L12 programming header | UART/EN/BOOT/GND roles retained; connector series, pitch/orientation and exact pin mapping need selection. |
| L13 charging connector | Input/contact/power and mechanical requirements missing. No implicit USB-C circuit or guessed CC resistors. |
| L16 LED driver | IS31FL3731-QFLS2-TR / C191206 queried; ISSI distributor identity does not inherit Lumissil manufacturer evidence. Discrete monochrome reference only. |
| L17 current resistor | 20k/0402 lead 0402WGF2002TCE / C25765 queried; remains unverified, including REXT/PWM/current/brightness implementation. |
| L20 individual LEDs | Exact color/brightness, forward voltage/current, scan duty and footprint requirements missing. No LED chosen to fill the line. |
| L25 NFC antenna | Coil geometry/inductance/matching/RF placement absent; no arbitrary inductor or coil purchased/selected. |
| L27 original inductor | Exact suffix/current/saturation/DCR not established. Redesign replaces this role with a 0.47 µH reference; exact orderable part/current margins still unverified. |
| L28 original input bulk | Reviewed Samsung CL10A106KP8NNNC / C19702 supplies the 10 µF role. Bias, thermal and transient application checks remain open. |
| L29 original output bulk | Original pattern can use the reviewed 10 µF choice for its two roles. Redesign instead requires a 22 µF role, whose exact identity/effective capacitance remains unresolved. |
| L31 protector | BQ29700DSER reference retained. Variant thresholds and exact cell/protection contract not established; no unsupported supplier code guessed. |
| L32 protection FETs | Cell current, trip thresholds, RDS(on), saturation/thermal and connection constraints missing. No arbitrary FET pair selected. |
| L33 protection filters | Exact variant/application values not established; no invented filter resistor values. |
| L35 cell | Exact chemistry, capacity/discharge profile, charge limits, protection, mechanical fit and safety/certification missing. A calculated necessary capacity is not a selected cell. |

Unspecified physical or safety contracts cannot justify a meaningful exact official lookup. Those rows
remain blocked by explicit missing requirements rather than querying random catalogue entries. Completing
all 22 rows is therefore **not achieved**. The expanded converter also introduces unresolved feedback,
power-good and output-filter roles; added I2C pull-ups likewise need actual electrical sizing.

The corrected badge trial has **39 roles, 18 supplier-identified roles, 16 matches to the exact expected
manufacturer/MPN, and 13 independently verified role equivalences (12 capacitor roles plus the converter
identity/package match)**. Twenty-six roles remain unverified. All application suitability remains
unverified. Two resistor leads have supplier identities but lack independent reference qualification.
Earlier live metadata named the total identified count `exact_sourced_roles`; this overstated that
distinction by two for A and one for B. Current code separates `supplier_identified_roles` from
`exact_role_matches`; historical files remain unchanged and this correction is explicit.

## Genuine local Qwen evaluations

Both product prompts contain only the product description, no architecture, part pairs or final BOM.
The model inspects pattern/tool contracts. All inference is local `qwen3.5:9b`; there is no paid fallback.
These are development observations, not a general success-rate benchmark.

| Evaluation | Observed result |
|---|---|
| A, final badge model run `20261024T045553Z-0d7d78` | Eight model turns, 53,094 cumulative input/output tokens, 15 tool attempts: ten model attempts (including one blocked extra question), five controller completion operations. Generated 39 roles, 18 supplier-identified roles, 13 qualified role matches and 18 real H-MEM writes. One fresh official HTTP 200 lookup and 21 real Zetaris SELECTs. |
| A questions/alternatives | Asked runtime and LED type; unattended answers remained unavailable. Model proposed six hours, addressable 8×8 LEDs, 500 mAh, 15 mA/LED and quantity 100, all provisional. It selected TPS63802 initially and compared TPS63031. Addressable protocol/capacity and runtime fail; the inferior converter adds a supply failure, so it is not adopted. No final accepted design. |
| Actual owner answer and revision | The owner subsequently answered **“Monochrome”**. Current controller run **`20261024T052555Z-723162`** relays that one actual reply verbatim, confirms only `led_type=mono`, invalidates old results and regenerates/source-checks the same architecture. The LED incompatibility clears; runtime still fails. One fresh official HTTP 200 read, 42 actual Zetaris queries; no model call or new fabricated owner answer. Earlier revisions `20261024T045821Z-98a36e` and `20261024T050844Z-ec39b3` are retained. |
| B, actual desktop run `.partlens/correction-ui/new-design-runs/20261024T045932Z-c5eadf.jsonl` | Rechargeable Bluetooth room-temperature monitor. Eleven model turns, 64,976 tokens and 16 tool attempts: eleven model attempts, five controller completion operations. Generated 29 roles/31 component instances, 11 supplier-identified roles (ten expected-identity matches), nine qualified role matches and 11 actual H-MEM writes. One fresh official HTTP 200 read and 13 actual Zetaris queries. |
| B questions/alternatives | Runtime and available cell capacity/discharge capability were displayed in the UI and canceled by the operator, leaving no owner answer. Model proposed 72 hours, 500 mAh, 3.0–4.2 V, 3.3 V and quantity 100. It selected TPS63802/TMP117 and compared TPS63031. There are 21 conditional passes, **43 unverified checks, zero failures and no accepted design**. Runtime cannot be inferred from MCU supply reserve or sensor typical current. No badge roles or quantity provenance were inherited. |

All quantities above are model scenarios, not confirmed builds. Only the actual owner's Monochrome reply
binds. The corrected owner-revision exports are under
`.partlens/owner-revisions/20261024T052555Z-723162/{before,after}/`.
The live model-selected designs still leave cell, circuit, timing, footprint and commercial requirements
unresolved. The fully evidenced acceptance gate was **not satisfied** for either product.

### Preserved negative results and corrections

- Baseline: 275 tests passed, `tests-20261024T043750Z-2be399.txt`.
- Initial additive pattern registration broke 11 original tests because the old reference selection
  enumerated every block. The failure is retained in `tests-20261024T044529Z-51feae.txt`. Extension lookup
  was separated from the original registry; all original tests pass again without removing coverage.
- Interactive run `20261024T044845Z-3aa14e` exhausted repetition handling around a question after an
  unavailable answer; no BOM or integration success claimed. The actual later owner reply was handled
  separately, never backdated into this run.
- Run `20261024T045222Z-6c6e24` exhausted 324,073 tokens across 29 model turns, including incorrect pattern
  IDs, an attempted unsupported target revision and a partial architecture; no BOM. The stop threshold
  is checked between turns. Enumerated architecture selection and mandatory controller completion were
  introduced afterward. The model's request to weaken LED assumptions was not accepted.
- Review found missing named-net intent for added pull-ups. That representation was corrected and a
  regression checks every role/reference against its intended named nets. It does not validate pin numbers.
- Final provenance review found new extension/manufacturer references inheriting the October 23 baseline
  date despite being reviewed October 24. New references now retain their actual October 24 review date;
  original references keep their earlier dates. Current correction/owner-revision runs above include the
  fix. Supplier retrieval timestamps were already genuine and are unchanged. This changes evidence and
  circuit digests, so earlier engineering-version-2 records need their matching source snapshot for exact
  replay. B replays **6/11** against corrected current code (audit `20261024T052635Z-441119`) and **11/11**
  against its preserved source in `.partlens/partlens-source/20261024T052006Z-cd94a7` (audit
  `20261024T052635Z-c19176`). Both outcomes remain recorded. This is an explicit historical replay
  compatibility limitation; the old 11/11 result must not be represented as current-code equality.

## Costs and sourcing meaning

The two model runs use their provisional 100-board and hypothetical 60-board scenarios. The existing
Easyduino owner quantity of one remains separate. Official prices retain unknown native currency, MOQ/
multiples and eligibility where undocumented. Actual stock and Basic/Extended observations remain
distributor data; assembly eligibility is a separate unresolved field. Zero-stock observations do not
become available parts. No PCBA fee, charge current, joint count or fabrication quote was invented.

The existing cost engine can show `parts_total=0.00`/`known_subtotal=0.00` when **zero lines have complete
purchase terms**; `component_complete=false`, missing-term problems and assembled `total=n/a` are
authoritative. This is a partial bookkeeping subtotal, not a free BOM or complete USD price. The report's
default denomination does not establish official native price currency. A complete component or assembled
cost is unavailable. See [the official integration report](JLCPCB-INTEGRATION.md) for unresolved semantics.

## Desktop and CLI acceptance

The actual desktop was operated visually through the computer-use skill. The second generic description
was typed into New Design, provisional delegation enabled, and the real local-agent operation completed.
Both actual question dialogs were inspected and left unanswered. All nine tabs were reviewed: Requirements,
Architecture, Alternatives, Generated BOM, Checks, Sourcing, Cost, Explanation and Audit. The explanation
states `accepted=False`, lists compared converter choices and separates conditional passes from remaining
unknowns. Source identities/timestamps, incomplete costs, record path and export directory were visible.

The result UI uses detailed JSON views plus the factual explanation, not a polished component editor.
Some evidence requires scrolling; proposed architecture justifications are model text, not check results.
No assertion is made that every offscreen field was visually compared. Shared presentation tests compare
the report's requirements/BOM/checks/source research/cost/acceptance and factual renderer; actual UI export
and journal parity is checked separately. Recorded-source replay is offline and cannot establish a new
supplier, Zetaris or memory operation.

After closing the saved New Design window, Existing BOM still imported and matched the approved Easyduino
demo in parent UI run `20261024T045657Z-6b431c`. Its independent original tests also pass. A fresh owner
quantity was not fabricated for this UI check. No private design or unrelated desktop dialog was operated.

## Reproduction and standalone source

Follow [DEVELOPMENT.md](../../DEVELOPMENT.md) for editable Python installation, local Ollama, approved
`.env.local` credentials and the pinned public Node H-MEM bootstrap. Supplier reads are read-only and
bounded; no entire catalogue, order or private file is involved.

```powershell
.\.venv\Scripts\python.exe scripts/validate.py
.\.venv\Scripts\partlens.exe new-design --idea "Design a rechargeable smart LED badge with Bluetooth phone control, an LED matrix, NFC, microphone and IMU." --allow-proposals --unattended --jlc --zetaris
.\.venv\Scripts\partlens.exe new-design --idea "Design a rechargeable battery-powered Bluetooth temperature monitor that reports room temperature to a phone." --allow-proposals --unattended --jlc --zetaris
.\.venv\Scripts\partlens.exe ui --jlc --zetaris

# Controller-only historical correction: no model invocation.
.\.venv\Scripts\python.exe scripts/correct_architecture.py --run .partlens/runs/20261023T210850Z-8dbb3c.jsonl --jlc --zetaris

# Relay only actual quoted owner words; this example records the real reply received in this milestone.
.\.venv\Scripts\python.exe scripts/revise_design.py --run .partlens/runs/20261024T045553Z-0d7d78.jsonl --parameter led_type --value mono --answer Monochrome --jlc --zetaris

# Safe source-only tree and independent editable/Node setup, no Git creation or publication.
.\.venv\Scripts\python.exe scripts/prepare_partlens_tree.py --verify
```

The source-preparation script walks only explicit public source roots and approved text/code types,
checks configured credential values, excludes private material/local state/dependencies, creates a new
ignored tree and SHA-256 manifest, then optionally installs in a fresh venv, runs `npm ci`/pinned H-MEM
setup, genuine bridge smoke, both deterministic examples and all tests. No actual supplier response,
credential, persistent memory or model weight is copied. Setup subsequently downloads its declared
public dependencies. The original workspace and every earlier tree remain intact.

First independent tree `.partlens/partlens-source/20261024T045343Z-07e1e8` passed 287 tests with the real
bridge and no skips. This predates final added regressions; final tree/results are recorded below. The
supported service distribution is a source checkout plus bridge setup. A general Python-only wheel still
does not bundle/locate the Node bridge automatically. No destructive history rewrite, destination,
remote or publication is authorized or performed. SSH signing remains enabled; owner-local unlocking
is required before a signed commit. Existing staged content is older than this milestone.

## Final scope recommendation

Demonstrate PartLens as an evidence-controlled engineering assistant: Existing BOM review plus preliminary
design generation, a documented converter redesign, exact owner-answer revision and transparent unresolved
alternatives. Do not pitch autonomous finished electronics. Priority remaining engineering work is exact
cell/charge/protection, LED/current implementation, pin/address/timing and package contracts, followed by
commercial definitions. Wider circuit-template counts, CAD generation and PCB layout would not resolve
these evidence gaps. Organizer/Cursor eligibility, supplier-data permissions, signing, repository
publication and a permitted final video remain separate submission prerequisites.

## Final verification index

- Owner workspace after provenance correction: **290 passed in 15.87 s**, no skips;
  `.partlens/validation/tests-20261024T052437Z-95d310.txt`. This retains all original 275 tests and adds 15
  correction/provenance/candidate/presentation regressions.
- Final independent tree after provenance correction: **290 passed in 15.74 s**, no skips, including genuine H-MEM tests after bootstrap.
  Tree `.partlens/partlens-source/20261024T052717Z-884a9f`; preparation record
  `.partlens/source-preparation/20261024T052717Z-884a9f.jsonl`; its local test record
  `tests-20261024T052808Z-38d7ef.txt`. Editable install, `npm ci`, pinned H-MEM setup, actual bridge smoke
  and both deterministic examples all exited zero. No external inference or supplier success is claimed
  from these clean-checkout tests.
- Actual A/B journal/export parity and visual observations:
  `.partlens/validation/record-parity/20261024T051743Z-ff9f70.jsonl`. Compared requirements, architecture,
  BOM, cost, memory, acceptance, alternatives, source failures and sourcing history all match their exports.
- Current corrected historical design replay **12/12**, owner-answer revision replay **10/10**:
  `.partlens/runs/replays/20261024T053053Z-44eed8.jsonl` and `20261024T053053Z-51daa9.jsonl`.
  Actual B replay **11/11** using its preserved pre-correction source snapshot, five memory/question
  operations skipped: `.partlens/correction-ui/new-design-runs/replays/20261024T052635Z-c19176.jsonl`.
  Current code matches **6/11** for that historical run because the corrected evidence review dates
  change derived digests; negative audit `20261024T052635Z-441119` is retained. See the provenance
  correction above. Earlier successful replays remain historical, not a current compatibility claim.
- Historical reference still **104/104**, M5 research **21/21**:
  `20261024T051746Z-2d6d50` and `20261024T051747Z-873503` in `.partlens/runs/replays/`.
  Replays do not prove a live integration or memory recall. This milestone measured real memory writes,
  not a new autonomous cold-recall trial; earlier measured recall evidence remains historical.
- Final scoped public/index audit `20261024T053135Z-fe28d9` inspected **130 authored public files and 56 staged blobs**:
  no configured-secret/personal-path matches or missing checked document links. The original supplier
  fixture SHA-256 remains `f4e2460af70321b4631df63ec63dbf064b4ecd796d2df78d81eb90b22a48619c`.
  Working-tree `git diff --check` passes. The old index still has its historical extra blank EOF line;
  it has not been refreshed into a release. No run/test record or old source tree was deleted.
- Signing is still `commit.gpgsign=true`, `gpg.format=ssh`; Windows ssh-agent is **Stopped/Disabled**.
  No commit was attempted and no remote exists. Owner-local unlock instructions remain in
  [SUBMISSION-READINESS.md](SUBMISSION-READINESS.md). No passphrase, private key or signing bypass was used.

The prepared tree is an owner-local review/install artifact, not a published repository or a release
containing redistributed supplier responses. Its initial source manifest is retained; a documentation-only
final manifest records the final report/timeline synchronization after validation. Current engineering
limitations and owner publication/signing actions remain explicit.

The previous independently tested tree `20261024T051548Z-2c42a8` also passed 290 tests, but final manifest
comparison caught generated `egg-info/SOURCES.txt` changing during editable installation. Failure record
`20261024T052006Z-8f8edb` is retained. The exporter now excludes generated package metadata; the final tree
above includes 130 authored files. The earlier 136-file audit included that metadata and is historical.
The final manifest is checked against the current workspace after synchronizing these final documents;
generated dependencies/build outputs are outside that manifest and must not be packaged as authored source.

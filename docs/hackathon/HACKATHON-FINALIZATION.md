# Hackathon finalization — PartLens

Status: implementation and source/test materials prepared locally; no publication or submission.
The 304-test starting baseline remains covered. This change adds narrowly scoped interview, provider
transport and startup-check corrections. No new circuit templates, schematic generation or integrations.

## Requirements and acceptance

The LED interview distinguishes physical count, rows/columns, physical arrangement, brightness and drive
topology. A deterministic check compares an explicit count with rows times columns. A contradiction fails;
missing dimensions remain unverified. The readable Requirements view displays the derived count and
explicitly says that arithmetic does not confirm an owner requirement. Electrical color-channel count is
separate from physical positions. The reviewed driver remains a bounded monochrome reference.

The owner replied **“make your own decisions for the design”** to the final count/arrangement question.
That delegates provisional choices; it does not confirm 32 LEDs, 4 × 8, a brightness, runtime or topology.
The earlier actual **“Monochrome”** reply can be relayed with its historical provenance. A repeated quote
is not a fresh answer or a meaningful numeric change. No invented numeric owner revision is demonstrated.
Synthetic tests exercise actual numeric revisions, conflict detection, invalidation and historical retention.

Failed architecture checks or application gaps prevent acceptance. Role equivalence remains separate from
electrical suitability. Battery usable energy, charging/discharge safety, efficiency, regulator margins,
current programming, pin mux, footprints, physical fit, assembly eligibility and full costs remain unresolved.
No generated result is a validated circuit or a purchase/fabrication/assembly quote.

## Ollama reliability investigation

Earlier native tool-call trials retained HTTP 500 failures associated with XML tool-parser errors, including
`<function>`/`</parameter>` mismatches. Those records remain in [FINAL-DESIGN-WORKFLOW.md](FINAL-DESIGN-WORKFLOW.md).
Native-array requirement arguments reduced escaping but did not remove those failures. Context exhaustion
already fails closed; silently dropping requirement/evidence history would compromise correctness.

Ollama documents [JSON-schema structured outputs](https://docs.ollama.com/capabilities/structured-outputs)
through the [`format` field of `/api/chat`](https://docs.ollama.com/api/chat). An explicit
`PARTLENS_LOCAL_PROTOCOL=json-schema` now requests one structured action per turn without sending a
native `tools` field. Historical assistant actions/results are serialized as data for this transport.
Malformed actions cannot execute; registry validation and controller prerequisites still apply. Model
text does not become evidence, a check, a confirmed requirement or a cost. Native mode remains the default;
no retry or silent transport/cloud switch hides a failed attempt. Usage records identify the actual protocol.

Temperature remains zero, thinking disabled, output ceiling 4096, configured context/timeout bounded.
The installed runtime is 0.40.8, Qwen3.5:9b Q4_K_M, digest prefix `56671c2ab938`. A small trial set cannot
establish a statistical failure rate, general model quality or reliable unattended operation.

| Trial / internal record | Observed outcome |
|---|---|
| Native `20261024T223550Z-6d5edc` | 12 genuine model turns, 154851 cumulative tokens, no provider error; operational pipeline completed. Initial historical-answer relay used an unsupported origin label and stayed provisional; gate correctly refused confirmation. This provenance negative is retained. |
| JSON schema `20261024T223728Z-0f9792` | Six genuine turns, 57457 tokens, no parser error; repeated requirement reads hit the tool/repetition limit before architecture/sourcing. Not a successful workflow. Historical Monochrome relay correctly bound after the helper correction. |
| Desktop JSON schema `20261024T224040Z-4889f0` | Ten genuine turns, 125729 cumulative tokens, no provider error; workflow completed. One confirmed Monochrome choice, 14 provisional assumptions, 39 generated roles. |
| Final bounded JSON schema `20261024T224725Z-8a720a` | Thirteen genuine turns, 187797 tokens, no provider error; tool/repetition budget reached before an architecture. No supplier or memory operation succeeded in this trial. |

The first evaluation helper also counted fresh JLC responses from the wrong event level; its printed
zero is retained. Inspection of the underlying response establishes one actual fresh HTTP 200 lookup,
client ID `59f97718316948b423bbaebd8c24e52b`, server trace `a719a3b202934ffa933519f78baeb272`,
at 22:36:48 UTC. This is a correction to the summary counter, not a rewritten run. The native run also
performed 21 real Zetaris SELECTs and 18 H-MEM writes. Its provisional 32-position 4 × 8 design has
30 conditional passes, one runtime-bound failure and 56 unverified checks; application qualification is incomplete.

After the negative structured trial, the interactive controller stopped offering another requirements
read in the mandatory interview phase once it had already returned them. This enforces asking the next
question; it does not select an answer or change an engineering verdict. The structured schema emits the
action before its brief explanation. Final desktop evaluation and source validation are recorded below.

The successful desktop run made one fresh official HTTP 200 request at 22:43:35 UTC, client
`a88e3bbe202a66a95e937eae2fb218cf`, server trace `8aab8df0efc92c8d5c240c7ae0e31e38`, followed by 21
successful Zetaris queries and 18 H-MEM writes. Ten model requests and six controller operations are
distinguishable in the journal (one answered model question uses the shared logger's omitted actor field).
There were 18 supplier-identified roles, 16 exact reference matches, 13 verified role-equivalence decisions
and 26 unverified roles. **All application qualifications remained unverified.** The agent chose provisional
32 LEDs, 4 × 8, 10 mA/LED, 500 mAh and 8 h. The optimistic LED-only runtime bound is about 1.989 h;
the failure is retained. The 0.82 A reserve/load screen fits the conditional 2 A converter reference, but
that does not validate losses, transients or temperature. The smaller converter alternative adds a supply
failure; it was compared and not accepted. Necessary battery/current counterfactuals remain unapplied.

The desktop displayed Overview, Requirements, Architecture, Alternatives, Generated BOM, Checks,
Sourcing, Cost and Explanation with provisional/role/application boundaries visible. Earlier full-tab
acceptance remains in the prior report. No final video/public screenshot is claimed. Costs show a
model-proposed one-board scenario and hypothetical 60 boards, both incomplete; this does not import the
separate owner-confirmed Easyduino quantity. Arrangement/brightness/drive and exact LED identity remain gaps.
The historical Monochrome reply was relayed, with the separate audit
`.partlens/validation/finalization/20261024T224146Z-cb982f.jsonl`; no numeric owner answer was fabricated.

The desktop run's first offline replay matched 10/13 operations and retained three mismatches
(`.partlens/finalization-ui-v2/new-design-runs/replays/20261024T224545Z-f0eab2.jsonl`). Investigation found
that sorted JSON journal keys changed input-object iteration order, hence check/bus list ordering.
Architecture construction now canonicalizes pattern keys. A synthetic regression records a whole
shuffled-selection workflow and reproduces all eight operations through replay. The earlier failure is
not rewritten or described as a passing live-record replay. The subsequent bounded model trial did not
reach architecture; its recorded-sources replay correctly refused absent supplier observations. No
successful fresh end-to-end replay is claimed for that failed model trial.

Four bounded evaluations therefore include both workflow successes and repetitions/provenance negatives.
The new transport avoided HTTP 500 in these attempts, but repeated-tool failures remain. This is evidence
for retaining an explicitly labeled contingency, not proof of reliable autonomous operation. No further
model attempts were made to obtain a more favorable result.

## Cold Meterless verification

The separate controller process `.partlens/runs/20261024T225001Z-4bfafe.jsonl` reopened the successful
desktop run's actual H-MEM store. It retrieved five memories (bounded search, not all 18 writes), read and
independently rechecked them: four unchanged, one cannot_reverify. Requirements were restored through
their original quoted provenance; no model was called and no owner requirement changed. Current
sourcing/checks ran again. Recall never conferred application verification.

`scripts/recheck_generated_design.py --memory-store ... --no-revision` now supports this desktop/custom
state path, refuses missing/outside-state stores and retains the source engineering/interaction mode.
The default historical hypothetical-revision behavior remains available separately; it is not an actual
owner edit. Exact reproduction is in the demo runbook; real memory/response files are internal.

## Startup and live service evidence

`partlens preflight` and desktop **Check services** attempt all services even after a failure. Output includes
safe evidence identifiers and actionable unavailability messages. It does not print credentials/raw supplier
records. The JLC check is one explicit, fresh public C1525 lookup. The Zetaris check runs a bounded read-only
SELECT against the approved existing Easyduino dataset. H-MEM starts in an isolated smoke store and executes
hello/stats; this is a real bridge operation, not cold decision recall. Ollama inspection does not infer.

- Restricted-sandbox record `.partlens/preflight/20261024T223414Z-fe2898.jsonl`: JLC transport failed; other
  checks succeeded. Preserved as a failure, not reported as an API authentication failure.
- Authorized-network retry `.partlens/preflight/20261024T223429Z-5d611c.jsonl`: all four checks succeeded.
  Fresh official JLC HTTP 200 at 22:34:29 UTC, client `8164f2e9da3c4fccb5aba80cb7da998c`, server trace
  `4da0ad601f41d4b3234bd8d069f9a457`. Zetaris HTTP 200 returned five demo rows; locator
  `zetaris:0b67adb6-0e4f-4b54-bdc7-b058a7704117`. Server query/request IDs were not supplied.
- Desktop service summary visibly showed all four available. Its separate record is
  `.partlens/finalization-ui/preflight/20261024T223832Z-e2564f.jsonl`.

These successful checks do not promise later uptime or imply the subsequent agent used every service.
All raw operational evidence remains ignored/internal, with earlier failures preserved.

## Tests, source tree and release boundary

Baseline revalidation: 304 passed, 24.61 s, record `tests-20261024T223102Z-7a281d.txt`.
Intermediate expanded suites: 316 passed, 22.42 s (`223610Z-2a2cc0`), then 317 passed, 25.82 s
(`223948Z-2e12f5`). New synthetic cases cover transport isolation/malformed output, startup failures,
LED interview distinctions, count consistency and interview progress. They do not mock a live success.
The final CMD suite has **318 passes**, no skips: working tree 26.69 s
(`.partlens/validation/tests-20261025T190900Z-c0c5aa.txt`) and independent tree 30.06 s
(`.partlens/partlens-source/20261024T224303Z-f337ee/.partlens/validation/tests-20261025T190942Z-8b5d85.txt`).
The same independent tree completed clean dependency installation, pinned H-MEM setup/smoke and both
deterministic examples. Later authored corrections/documentation are recorded separately, preserving
the original manifest. The current deterministic New Design command also replayed 7/7 operations
(`.partlens/design-reference-runs/replays/20261025T191058Z-9c1d90.jsonl`), with no live-operation claim.

On the next day's CMD preflight (`.partlens/preflight/20261025T190902Z-bb792e.jsonl`), JLC and H-MEM
succeeded but Ollama and Zetaris were stopped. The existing loopback runtime and Docker/driver were
restarted without model downloads or storage recreation. This outage remains preserved separately.
Recovery preflight `.partlens/preflight/20261025T191305Z-cf9153.jsonl` passed all four checks from CMD:
fresh official JLC HTTP 200 (client `9696a87356780f020c59a6ea1035a7b3`, trace
`26569a836de6458ebf886196c25e2c6c`), real five-row Zetaris query
`zetaris:eb935dbe-70a0-4666-854d-3fc92a78b5c6`, installed local Qwen inspection and H-MEM hello/stats.
The public synthetic Existing BOM example also completed from CMD; New Design's deterministic example
and 7/7 replay succeeded. These are separate from the genuine model trials above.

The scoped public/index audit at `20261024T224834Z-c2aacb` checked 140 authored files and 56 old staged
blobs: no configured-secret matches, personal paths or checked missing links. The retained internal LCSC
fixture hash remained `f4e2460af70321b4631df63ec63dbf064b4ecd796d2df78d81eb90b22a48619c`.
Final release checks repeat that audit. No SDK, real supplier data, model weights or operational records
are included in authored source. The clean source-only candidate and exact commit-file inventory are
identified in the standalone report. SSH signing stays enabled; the unavailable owner signing agent
prevents a commit. Nothing was pushed, published or submitted.

See [STANDALONE-READINESS.md](STANDALONE-READINESS.md) for the exact authored source manifest, supported
Node bridge setup and owner-only signing/publication steps. See [DESIGN-DEMO.md](DESIGN-DEMO.md) for exact
commands, timing and contingency. Older reports/source trees remain historical evidence.

No new dependency or third-party source was copied for these corrections. Original code/tests are
Apache-2.0; the open Easyduino example and pinned H-MEM retain the notices in [THIRD_PARTY.md](../../THIRD_PARTY.md).
Read-only supplier access is not redistribution permission. Real responses, screenshots and recordings
remain internal until permission/owner review. Cursor was not used; its eligibility condition remains unresolved.

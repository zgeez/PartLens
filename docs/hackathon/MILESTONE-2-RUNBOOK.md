# Milestone 2 runbook

Run from the repository root with `.venv` active. Secrets belong only in the gitignored `.env.local`; use
`.env.example` for names. Do not paste keys into chat or place them in command arguments. Keep SSH signing
enabled; the owner unlocks the key locally.

## Local verification

```sh
python scripts/validate.py
python scripts/smoke_ui.py --catalog .partlens/cache/lcsc-easyduino.json
partlens ui --catalog .partlens/cache/lcsc-easyduino.json
```

The validation helper writes a new `.partlens/validation/tests-<id>.txt` for every invocation. It avoids the
default Windows pytest temporary-directory permission issue. Failed records are retained.

The interface provides a selectable BOM table, requirements and provenance, original-specification and
application results, evidence, sourcing checks, conditional costs, agent explanation and audit events.
Use **Load demo** first. **Deterministic review** asks for quantity and exercises tools without an LLM;
its record is labelled scripted. **Live Claude review** uses the real provider; failures remain visible.
**New session + recall** creates an independent agent session over the existing H-MEM store.

## Reviewed local evidence

The review and fee files created during this milestone are internal local artifacts:

- `.partlens/reviews/umw-xc6206-20261022T035447Z.json`
- `.partlens/reviews/jlcpcb-classifications-20261022T042918Z.json`
- `.partlens/fees/jlcpcb-economic-20261022T042918Z.json`

Use them explicitly; they are not installed as universal default assumptions:

```sh
partlens ui --catalog .partlens/cache/lcsc-easyduino.json --evidence .partlens/reviews/umw-xc6206-20261022T035447Z.json --evidence .partlens/reviews/jlcpcb-classifications-20261022T042918Z.json --fees .partlens/fees/jlcpcb-economic-20261022T042918Z.json
```

The review checks exact manufacturer/MPN identity, separates operating and absolute limits, and keeps the
original supplier values unchanged. A datasheet review does not refresh stock/price timestamps.
The fee schedule is conditional: economic-service eligibility, remaining assembly classifications, joint count and
several other charges remain unresolved. LCSC retail component prices are not a JLCPCB assembly quote.

## Live baseline and recall

After the owner configures Anthropic access:

```sh
partlens live-demo --catalog .partlens/cache/lcsc-easyduino.json --evidence .partlens/reviews/umw-xc6206-20261022T035447Z.json --evidence .partlens/reviews/jlcpcb-classifications-20261022T042918Z.json --fees .partlens/fees/jlcpcb-economic-20261022T042918Z.json
```

This runs the full `Agent` with Anthropic `claude-opus-5-5`, with fallback forced off. Answer the agent's actual
quantity question at the prompt. Do not pre-fill a made-up owner response. The first run must demonstrate
requirements, genuine evidence, deterministic qualifications and memory persistence; the second must recall
the relevant first-session decision. Requested/actual model IDs, response IDs, tools, outputs, failures and
source fingerprints are recorded. Programmatic task text cannot confirm an owner requirement.

An unavailable model or rejected authentication ends that attempt honestly. Configure access or resolve the
model issue and create a new run; do not overwrite the failed record or silently change models.

## Scripted comparison

```sh
python scripts/reference_review.py --catalog .partlens/cache/lcsc-easyduino.json --evidence .partlens/reviews/umw-xc6206-20261022T035447Z.json
partlens evaluate <run.jsonl>
partlens evaluate <second-session.jsonl> --prior <first-session.jsonl>
partlens compare --reference <reference.jsonl> --live <first-session.jsonl> --recall <second-session.jsonl>
partlens replay <run.jsonl> --catalog .partlens/cache/lcsc-easyduino.json --evidence .partlens/reviews/umw-xc6206-20261022T035447Z.json
```

The new scripted reference covers engineering decisions and cross-process H-MEM recall; it deliberately leaves
quantity unanswered. The preserved Milestone 1 reference also covers quantity clarification. Evaluate both
against live outcomes, without requiring identical intermediate tool calls. Automated flags do not replace
review of the explanation, citations and recall relevance.

Replay re-executes deterministic tools; it does not verify model behavior or memory retrieval. Audit results,
including mismatches, are preserved next to the source run. Old records can differ after engineering/schema
corrections; preserve and explain those differences instead of rewriting their digests.

## Zetaris operation

Follow [the official access research](SPONSOR-ACCESS.md). The local bundle's working SQL gateway is
`ZETARIS_BASE_URL=http://localhost:3000`; `:8888/api/v1.0` is not the documented gateway used by this client.
The owner-configured key and organization remain in `.env.local`. An empty engine ID works locally.

The current registered table is `PARTLENS_EASYDUINO_20261022T060243Z_616750.parts`. Its source files are in the
owner's local Docker data volume under `/home/zetaris/customer-data/shared/partlens-20261022T060243Z-616750`.
The local setup manifest is `.partlens/zetaris/partlens-20261022T060243Z-616750/manifest.json`.
No setup rerun is needed while this namespace and its files remain available.

To create a new independent demo namespace on the owner's local instance:

```sh
python scripts/setup_zetaris_demo.py --catalog .partlens/cache/lcsc-easyduino.json
```

Docker access is required. Use `--base-url` to override the configured gateway, `--container` for another
driver container, or `--container-data-root` to match that instance's `ZETARIS_LOCAL_FILE_SYTEM_ROOT_PATH`.
Only the approved BOM and the supplied existing fixture are exported; the script never downloads supplier data.
It copies files into a unique directory, checks their container hashes, creates a separate Lightning namespace,
then requires the actual Zetaris counts and join to match. Complete JSON array documents are intentional:
the observed gateway read only one record from JSON Lines even with `multiLine false`. Failed setup objects
and records remain preserved. No existing namespace is overwritten or deleted.

Set `PARTLENS_ZETARIS_PARTS_TABLE` locally to the returned `.parts` table, then run:

```sh
partlens smoke-zetaris
partlens ui --zetaris
```

Review the saved SQL, HTTP/execution status, server IDs if supplied, response digest and returned demo part IDs.
The local gateway supplies server timing but no server query/request IDs; client UUIDs must not be presented
as server-issued identifiers. `20261022T060243Z-616750` and `20261022T060306Z-c9f3aa` contain real dataset-query
evidence. This uses retained supplier fixtures; querying them through Zetaris does not refresh prices or stock.
CLI/UI sessions record each remote query in their own session log, including with `--evidence` overlays.
Independent sessions retain separate recorders. A live remote fetch creates new source query locators, so
identical source-digest replay is not expected across separate remote requests; retain the original evidence.
Do not count missing configuration, local exports, mocked unit-test responses or diagnostic `SELECT 1` as the
required dataset operation. Keep the raw credential configuration out of recordings.

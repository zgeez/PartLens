# Milestone 2 access research

Reviewed on 2026-10-22. No platform account or cloud resources were created. No sponsor operation is claimed
on the basis of this research.

## Zetaris

The [official starter](https://github.com/zetaris/getting-started/blob/main/START-HERE.md) directs participants
to their own local deployment or a cluster in their AWS account. It supplies recipes, not platform accounts.

The [official local installation guide](https://github.com/zetaris/getting-started/blob/main/docs/install/updated_zetaris_installation_guide.md)
requires the platform archive, its matching environment file, registry credentials and a licence or evaluation
entitlement. Obtain these through the owner's account at the
[Run locally portal](https://cloud.enterprise.zetaris.com/dashboard/download). The guide describes Docker Compose,
with WSL2 integration on Windows; its machine guidance includes 8 GB available memory, four CPUs and 15 GB free
disk. Its evaluation terms are separate from the starter repository's Apache licence. An older Freemium
installation recipe is not evidence of entitlement to the current platform bundle.

The [managed AWS guide](https://github.com/zetaris/getting-started/blob/main/docs/install/managed-aws-cluster-guide.md)
uses the owner's AWS identity, a CloudFormation stack and a compute cluster configured through Zetaris Cloud.
It creates billable resources and IAM roles. No AWS credentials were inspected and no resources were provisioned
for this milestone. Existing authorized deployment access is preferable when available.

The [official HTTP helper](https://github.com/zetaris/getting-started/blob/main/scripts/query_zetaris.py) documents
the SQL execution route used by PartLens. The client records HTTP status, request correlation, server identifiers
when provided, result identifiers and a response digest. A client-generated request ID is labelled separately
from a server query ID. Pending/error/malformed responses do not qualify as successful executions.

Configure `ZETARIS_BASE_URL` to the **UI gateway origin**, `ZETARIS_ORG_ID`, `ZETARIS_API_KEY`, optionally
`ZETARIS_ENGINE_ID`, and `PARTLENS_ZETARIS_PARTS_TABLE` locally. The owner's local bundle exposes the working
gateway at `http://localhost:3000`; the initially supplied `http://localhost:8888/api/v1.0` returned 404.
The engine ID can remain empty on this local instance. The demo catalogue must be available through an
authorized data-source connection. A CSV prepared locally does not complete that operation.
`partlens smoke-zetaris` then executes a query restricted to supplier IDs from the approved demo BOM and records
whether matching rows actually came back. `--sql` supports a separate diagnostic query; `SELECT 1` alone does
not demonstrate the demo dataset integration.

Current result: **operational against the owner's local Zetaris 2.4.3.1 instance**. The approved BOM and
unchanged retained supplier fixture were copied only into that instance's configured shared filesystem root,
registered with Lightning SQL and queried through the documented gateway. The setup script checks export hashes,
server row counts (64 supplier records, 19 BOM rows) and a server-executed join (17 placed lines, 15 matches).
Two headers remain unresolved. No live supplier refresh or additional LCSC collection occurred.

Successful evidence: `.partlens/runs/20261022T060243Z-616750.jsonl`; normal PartLens smoke query:
`20261022T060306Z-c9f3aa`; all 64 returned records compare equal to the original fixture in
`20261022T060327Z-d4604a`. HTTP 200 responses, server execution timings, SQL, returned part IDs and response
digests are recorded. The gateway does **not** return server query/request IDs; those fields remain null,
and the UUID correlations are explicitly client generated. `SHOW SERVER VERSION` returned 2.4.3.1 / cb88df0b
in `20261022T055728Z-2156b4`.

Live Claude also used the working Zetaris catalogue (`20261022T060443Z-998b88`, 19 successful SQL operations)
and a separate live session recalled and rechecked its Meterless decision (`20261022T060513Z-b2c4b2`, 18 SQL
operations). These are real agent/query operations, not mocked or scripted planner results. See the
[milestone report](MILESTONE-2.md) for model, tool-use and memory evidence.

Earlier missing-access, 404, unsupported SQL, response-parser, restricted-path and partial JSON-import failures
remain preserved. In particular, importing JSON Lines returned only one row; count validation rejected those
runs (`20261022T060152Z-e46ba5`, `20261022T060214Z-2a139d`). Complete JSON arrays succeeded. Failed demo namespaces
were retained rather than silently deleted. The copied files remain in the local Docker data volume and local
`.partlens/zetaris/` artifacts; they are internal pending licensing review and are not Git artifacts.

The reproducible setup uses the [official Lightning file-table syntax](https://github.com/zetaris/getting-started/blob/main/docs/guides/zetaris-lightning-sql-commands.md).
See the [runbook](MILESTONE-2-RUNBOOK.md) for commands. No cloud resources were created or other credentials inspected.

## Mouser

Mouser offers an [official Search API](https://www.mouser.com/en/api-search/) for product information,
availability and pricing, with account-based API access. Its published access summary lists up to 1,000 calls
per day. Request access through the owner's account; keep its key in local secret configuration.

The [official V2 schema](https://api.mouser.com/api/docs/V2) describes manufacturer-filtered keyword and part-number
searches, price-break currencies, availability, minimum quantities, order multiples, product attributes and
datasheet links. Search results are supplier evidence and leads for manufacturer research, not compatibility
verdicts. Prices/availability must retain retrieval time, and assembly-service classifications cannot be
inferred from Mouser listings. Its API key is a query parameter, so URLs and errors must be redacted before
logging.

No Mouser key was available, no authenticated request was sent and no operational Mouser integration is
claimed. Terms for retention, redistribution and demo display still need review. LCSC fixtures remain internal;
their collector is disabled pending licensing review.

## Cursor (Milestone 2 historical investigation)

Milestone 3 owner instruction supersedes the historical task below: use Codex and do not use Cursor or claim
Cursor usage. No Cursor workflow was completed. Its hackathon eligibility implication remains unresolved.

Windows app and running-window inventories returned no Cursor match; the standard user installation path
was absent. No Cursor AI coding task was completed. Do not count Codex changes toward this requirement.

A concrete pending Cursor task: improve the qualifications view with status/scope filters while retaining every
failed check and its sources. Use Cursor's own AI workflow on the public project, keep excluded paths out of
context, validate the change, and record the prompt, Cursor model, changed files and test result. Mark this
complete only after that workflow actually occurs; the prepared task is not evidence of completion.

## Milestone 3 access recheck, 2026-10-22

Independent real Zetaris/H-MEM validation succeeded at 07:18 UTC in runs `20261022T071829Z-b3d4ae`
(18 SQL operations) and `20261022T071831Z-0e0173` (16 SQL operations and cold recall).
At 16:50 UTC the unchanged local Zetaris gateway refused connections. Live local-agent run
`20261022T165002Z-c0a945` retains five failed query attempts; Docker's daemon was unavailable. Earlier successful
operations remain valid historical evidence; current Zetaris availability is blocked until the owner-local
instance runs again. Local fixture execution does not count as a replacement sponsor query.

No configured DigiKey credentials were found (`20261022T071126Z-2a7484`); no authenticated production lookup
was attempted. Official access research: [DigiKey documentation](https://developer.digikey.com/documentation).
No Mouser access succeeded. No NVIDIA key or authorized Meterless inference runtime was available; an
unauthenticated loopback models probe failed (`20261022T071735Z-797f10`). Meterless H-MEM is a separate, working
memory operation, not evidence of Meterless-hosted inference or Nemotron use.

Anthropic credits were exhausted in `20261022T070859Z-365063` after eight actual Opus turns, 38 tool calls and
92 successful Zetaris queries. That run did not reach a final answer. The owner subsequently selected local
inference and Sonnet for future paid use. No new paid calls were made for this provider change. Official
Ollama was installed in ignored local state with its published archive digest verified; cloud inference is
disabled. Local model evaluations and their failures are in [Milestone 3](MILESTONE-3.md).

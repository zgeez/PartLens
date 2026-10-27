# Official component API integration

Implemented during the build window on **2026-10-22 America/New_York**. Run identifiers and source timestamps
use UTC (the successful runs below are dated 2026-10-23 UTC). This is an operational, read-only component
integration. A complete dollar-denominated procurement or assembled-board quotation is **not available**.

## Observed operation

- The official service returned all **15 explicit Easyduino BOM component codes**, plus **one alternative
  already present in the retained internal research fixture**. No catalogue enumeration was performed.
- Two genuine authenticated requests in [the direct validation record](../../.partlens/runs/20261023T021006Z-65e325.jsonl)
  returned HTTP 200 and business success. The first, at `2026-10-23T02:10:06Z`, returned 15 records and
  server `J-Trace-ID` `8d04ba1c3f5f4436ae9f1505d810d6c5`; the second returned the alternative.
- The final [corrected run](../../.partlens/runs/20261023T021115Z-5ee71b.jsonl) reused those timestamped responses
  within the five-minute cache and executed **18 fresh Zetaris SELECTs**, all HTTP 200/succeeded. Its BOM join
  returned 17 placed lines, 15 matched component codes and two unresolved headers. The join's client request
  ID is `e6fda303-7edb-4253-9ce2-739c8a68f2e4`; Zetaris reported 138 ms. Server query/request IDs were not
  exposed and are recorded as null. A client UUID is not presented as a server identifier.
- Deterministic checks qualified the capacitor alternative against the original recorded capacitance,
  voltage rating, dielectric, tolerance and package. All six equivalence checks passed with source evidence.
  **Application compatibility remains unverified**: circuit conditions and relevant operating evidence are
  still missing. Neither an LLM nor a supplier's assembly flag determines compatibility.
- The full [local report](../../.partlens/jlcpcb/datasets/20261023T021115Z-5ee71b/report.json) retains tool
  inputs/outputs, decision evidence, quantities, comparisons and SQL/result evidence. These are internal
  artifacts, excluded from Git and public demo material. This validation uses deterministic tools, **not a
  live LLM**; previous local-agent and Meterless results remain in the Milestone 4 report.

## Official contract reviewed

Primary references: [basic rules](https://api.jlcpcb.com/docs/start),
[request signing](https://api.jlcpcb.com/docs/api-request-signature),
[API list](https://api.jlcpcb.com/docs/api-list),
[key configuration](https://api.jlcpcb.com/docs/configure-api-key),
[Java SDK guide](https://api.jlcpcb.com/docs/sdk-usage-guide), and the four approved endpoint PDFs supplied
through the owner's developer account. Original PDFs and public guide responses are retained under
`.partlens/jlcpcb/docs/`; signed download query strings are not retained. The SDK guide was reviewed; no SDK
implementation was copied, reverse engineered or installed into PartLens.

| Approved path | Documented scope | Implementation/use |
|---|---|---|
| `/overseas/openapi/component/getComponentDetailByCode` | Public detail for explicit C codes; POST JSON `componentCodes`, maximum 1000 codes | Implemented; actual authenticated reads succeeded; client limits each batch to 25 |
| `/overseas/openapi/component/getComponentLibraryList` | Paginated public list; `pageSize` and optional `lastKey` | Reviewed, not called or implemented; no catalogue download |
| `/overseas/openapi/component/getComponentInfos` | Owner lists this permission; its supplied PDF instead describes a demo URL with multipart pagination | Documentation discrepancy retained; neither path was guessed or called |
| `/overseas/openapi/component/getPrivateComponentLibrary` | Authenticated customer's private inventory | Reviewed, not called or exposed |

Requests go only to `https://open.jlcpcb.com` and the allowlisted detail path. JSON is UTF-8. Authentication
uses `Authorization: JOP` with app ID, access key, a 32-character alphanumeric nonce, Unix-seconds timestamp
and Base64 HMAC-SHA256 signature. The signed bytes are five newline-terminated fields: uppercase method,
path, timestamp, nonce and the **exact transmitted JSON body**, including the final newline.

`JLC_APP_ID`, `JLC_ACCESS_KEY` and `JLC_SECRET_KEY` are required; `JLC_APP_NAME` is optional local metadata,
not a signing input. Presence of all four was checked without displaying values. Secrets remain in ignored
`.env.local`. No authorization header, signing string or signature is logged. Redirects are refused.

HTTP 200 alone does not mean business success. The PDF uses `successful: true`; the live service returns
`success: true`. The adapter accepts either with `code: 200`, rejecting missing, false, conflicting or
non-boolean success fields. It rejects unexpected component identities and malformed response shapes.

## Fields and provenance

| Observed field | Treatment |
|---|---|
| `componentCode`, `componentModel`, `componentBrandEn`, `componentSpecification` | Separate `jlcpcb:<C-code>` supplier identity, MPN, manufacturer label and package; never relabelled as an LCSC retail offer |
| `parameters[].parameterName/parameterValue` | Exact supplier evidence for supported deterministic parameters; all raw parameters retained locally; contradictory duplicates cannot pass |
| `stockCount` | Timestamped JLCPCB supply observation; not interchangeable with retained LCSC inventory or an allocation guarantee |
| `priceRanges[].startQuantity/endQuantity/unitPrice` | Decimal prices with inclusive interval bounds; `endQuantity=-1` is open-ended; no extrapolation across gaps; overlaps rejected |
| `libraryType` | Raw enum retained. `base→basic`, `expand→extended` is an **inference corroborated** by official product pages, not a documented exhaustive enum list; unknown values remain unknown |
| `assemblyComponentFlag` | Raw boolean retained; documented wording is ambiguous. It does **not** establish assembly eligibility or compatibility |
| `solderJointCount` | Supplier-reported part count retained with source; not silently equated with the complete board's chargeable joints |
| `datasheetUrl`, `dataManualUrl`, `dataManualOfficialLink` | Observed HTTPS references retained; numeric file IDs never become invented URLs; a link alone is not reviewed manufacturer evidence |
| Currency, MOQ, order multiple, lifecycle, service eligibility | Not provided/defined by the reviewed detail contract; remain unknown |

Enum corroboration: the official [demo capacitor page](https://jlcpcb.com/partdetail/C1525) labels Basic,
and [regulator page](https://jlcpcb.com/partdetail/XC6206P332MR/C347376) labels Extended. The mapping's evidence
and its inference status travel separately from engineering parameters. It grants no board-level eligibility.

Unqualified supply-voltage values are kept in raw supplier data, never promoted to recommended operating
limits. Manufacturer datasheet overlays still require exact manufacturer/MPN matching. The official regulator
listing's expanded manufacturer label is not silently aliased to the older fixture's abbreviation; prior
manufacturer review cannot transfer automatically. Recommended and absolute ratings remain separate.

## Registry, Zetaris and UI

`sources/jlcpcb.py` implements the signing client, normalized records and `JLCCatalog`. `--jlc` enables it
for the existing UI, agent, cost and replay commands. BOM matching uses an explicit supplier namespace, so
an official record remains `jlcpcb:` throughout. Searches cover only components already retrieved by code.

With `--jlc --zetaris`, `JLCZetarisCatalog` passes a bounded official snapshot through actual Zetaris SQL.
`ZetarisInlineCatalog` constructs a read-only `WITH … VALUES … SELECT` relation. The validation joins this
relation against the existing stored demo BOM. **No DDL, new tables, Docker copies or existing dataset changes
are needed.** It is not a persistent Zetaris ingestion pipeline. Each SQL, status, result identifiers,
response digest and reported execution time is logged. No local SQL/mock fallback is used.

Zetaris field provenance identifies both the executing query and original supplier request. Parameter and
classification evidence preserve their own supplier locators; reviewed manufacturer evidence keeps its
datasheet locator. JSON metadata, price interval bounds, classifications and commercial unknowns survive
the flat catalogue/Zetaris round trip. SQL literals use UTF-8 hex encoding, including untrusted search text.

The Evidence tab shows missing commercial terms and raw source metadata. Cost views explicitly label nominal
price arithmetic as incomplete, with unknown currency, and keep it outside the USD assembly total.

## Cost coverage and comparison

The owner's **one-board** requirement is restored from the original user message at
`user:20261022T043042Z-84edf9#seq13`. **60 boards are hypothetical** and never overwrite that requirement.

- Price tiers apply to the requested nominal component demand using Decimal arithmetic. Source-backed
  per-line calculations for both quantities are in `official_nominal_price_observations` in the local report.
- Currency is unknown, so these amounts are **not labelled USD, summed into a dollar BOM total or used to
  claim savings**. MOQ/multiples are unknown, so actual order quantity is null. An order minimum is not inferred
  from the first price tier. Availability remains unverified where purchase quantity cannot be established;
  stock below even nominal demand still fails.
- The existing sourced JLCPCB fee schedule remains separate. Loading calculations use the recorded library
  mapping and remain conditional. No fee schedule, PCB fabrication quote, attrition requirement or service
  eligibility was obtained from the Components endpoint.
- The API provides part-level joint counts for the 15 covered lines. Two headers remain unidentified, and
  billing applicability is unresolved; no complete board joint count or resulting labor total is invented.
- Engineering-qualified alternatives with incomplete sourcing terms stay excluded from cost optimisation.
  A qualified component is not automatically purchasable or cheaper.

The final comparison covers 16 official records and their existing fixture counterparts: no MPN differences,
six manufacturer-label differences and 15 stock differences. These concern distinct supplier offers and
timestamps, not proof of identity changes. Price tiers are retained side by side; a monetary price discrepancy
cannot be asserted without official currency. Common mapped engineering parameters show no semantic value
differences. The report separately labels 82 mapping/coverage differences; those are **not** evidence that
the suppliers disagree about 82 specifications. Unmapped fields remain available in raw parameters.

The LCSC fixture hash remains `f4e2460af70321b4631df63ec63dbf064b4ecd796d2df78d81eb90b22a48619c`.
No undocumented-endpoint LCSC collection was resumed.

## Bounds, usage and reproduction

The owner's permission screen reports all four APIs enabled and “No Limit” daily usage. The reviewed PDFs
document HTTP 429 but give no numeric per-second allowance or quota headers. Daily unlimited is not treated
as unlimited request frequency. The client batches explicit codes, caches successful responses for 300 seconds,
uses a 20-second timeout, bounds response size, retries at most three times for transient network/429/selected
5xx errors, and uses bounded exponential backoff/jitter or `Retry-After`. Waits above 60 seconds stop with an
explicit retry-later outcome. Authentication/permission/schema/business errors are not retried as successes.
TTL, timeout and attempt bounds are configurable in `JLCClient`; stale/corrupt cache entries cannot supply a pass.

The [developer agreement](https://api.jlcpcb.com/docs/agreement), effective June 15, 2025, restricts use to
authorized purposes and endpoints, credential sharing, bulk extraction and third-party data redistribution
without written permission. It also restricts branding and claims of endorsement. Approval is not treated
as an open-data licence. API responses, caches, comparisons and run records stay internal and ignored;
public tests use synthetic TEST-prefixed MPNs. No public API-data demo or redistribution permission is claimed.
No new agreement was accepted through a browser during this work.

```powershell
# Single approved-demo lookup; reports whether the original response came from cache.
.\.venv\Scripts\partlens.exe smoke-jlc --code C1525

# Official primary supplier, optionally queried through actual Zetaris.
.\.venv\Scripts\partlens.exe ui --jlc --zetaris --quantity-record .partlens/runs/20261022T043042Z-84edf9.jsonl

# Reproduce the deterministic decision, comparisons, quantity scenarios and read-only Zetaris join.
.\.venv\Scripts\python.exe -X utf8 scripts/validate_jlcpcb_demo.py --zetaris --quantity-record .partlens/runs/20261022T043042Z-84edf9.jsonl --fees .partlens/fees/jlcpcb-economic-m3-20261022T071230Z-b93cfd.json

# Full suite, with a new permanent test record.
.\.venv\Scripts\python.exe scripts/validate.py
```

These commands require the owner's local credentials; the validation also needs the retained internal
fixture. Omitting `--zetaris` tests the direct adapter without claiming a Zetaris operation. A normalized
snapshot can be supplied as `--catalog FILE` for an explicitly timestamped offline replay. No routing,
design uploads, private component-library access, PCB ordering, purchasing, Cursor or cloud inference is used.

## Verification and preserved negative results

The existing 183-test baseline stayed green during implementation. Protocol tests cover independent signing
verification, both success envelopes, malformed/business/auth errors, redirects, cache integrity/expiry,
429/retry exhaustion, exact prices/range gaps, unknown MOQ/currency, source separation, SQL escaping,
engineering pass/fail/unverified, registry configuration and quantity/UI provenance.

The 104-operation Milestone 4 reference still reproduces **104/104**; audit:
[replay record](../../.partlens/runs/replays/20261023T020902Z-2ca381.jsonl).

Preserved negatives/corrections:

- `20261023T015202Z-019443` and `20261023T015224Z-b0d493`: HTTP 200 failed strict validation because the
  live `success` field differed from the PDF's `successful`. The second record captures the observed envelope.
- `20261023T020320Z-07b3f7`: local runner argument-name collision, corrected without rewriting the failed run.
- `20261023T020343Z-dd0b6b` and `20261023T021006Z-65e325`: successful earlier validations, retained. Their
  comparison reported ten equivalent temperature strings as value differences; the final run corrects
  normalization while preserving the original source wording in evidence.
- Initial unauthenticated PDF downloads returned 403; owner-supplied signed documentation downloads succeeded.
  The initial shell network sandbox denial and unavailable browser were not API authentication failures.

SSH commit signing remains enabled (`gpg.format=ssh`, `commit.gpgsign=true`). The signing agent is stopped
and disabled; no commit was attempted and no signing/hook bypass or passphrase handling occurred. Work remains
uncommitted.

Final checks:

- **234 tests passed**: the original 183 plus 51 synthetic integration/regression cases; no failures or skips.
  [Permanent test log](../../.partlens/validation/tests-20261023T021732Z-830fdd.txt).
- The new CLI performed another genuine authenticated alternative lookup, HTTP 200 with a server trace:
  [CLI record](../../.partlens/runs/20261023T021551Z-18b41b.jsonl).
- After the final SQL literal change, a real Zetaris query returned the official component with its
  independent supplier/parameter/classification provenance intact (HTTP 200, 109 ms, one result):
  [round-trip record](../../.partlens/runs/20261023T021640Z-4f304a.jsonl).
- The desktop workflow loaded the official snapshot, matched 19 displayed BOM rows, rendered eight tabs,
  qualified the alternative, kept application status unverified, displayed unknown commercial terms, and
  retained owner quantity 1 alongside hypothetical 60. This was **programmatic acceptance, not visual review**:
  [UI record](../../.partlens/ui-validation/20261023T021637Z-4e0432/runs/20261023T021637Z-1932cf.jsonl).
- Public source and all 56 staged entries in the approved project scope contained no configured secret
  values. Official caches/datasets were also checked; local state remains ignored, fixture hash unchanged,
  documentation links valid and `git diff --check` passed. Signing stays enabled; no commit attempt:
  [security/document-source audit](../../.partlens/runs/20261023T021830Z-b77f7e.jsonl).

Remaining limits: missing official currency/ordering/eligibility semantics; incomplete application and header
evidence; flash supply risk; incomplete PCBA/PCB/attrition/labor quotation; public data/branding permission;
manual visual acceptance; and owner-local signing-key availability. API access alone resolves none of these.

## Milestone 5 follow-up (historical observations above preserved)

The genuine local Qwen + official JLCPCB + actual Zetaris workflow and separate cold recall have now been
observed. A/C executed ten authenticated HTTP requests and 88 successful read-only Zetaris SELECTs; the
controller enforced all five recalled-item rechecks. The desktop also received actual native Windows
visual review. See the Milestone 5 record for run IDs, model/controller attribution, preserved
evaluator correction, 245-test result and replay counts.

The owner-supplied Business SDK archive contains compiled Java classes but no bundled field documentation.
It was inspected without execution or decompilation and remains ignored. Currency, MOQ, multiples and
assembly-flag meaning remain unresolved. Safe inspected response headers supplied Content-Type and Date,
not commercial semantics; no undocumented currency control was sent.
Support questions are prepared and have not been sent.

`--jlc-leads` optionally discovers explicit code leads from the retained internal fixture; all subsequent
qualifications use official records. `--jlc --zetaris` no longer implicitly adds the legacy supplier table.
Per-session limits are 12 HTTP attempts and 60 distinct codes by default, including retries, in addition
to the existing request/cache/timeout bounds. (2026-10-27: the code limit was 40 until a 16-line generated
breadboard-power BOM needed ~42 codes; desktop BOM checks now prefetch every line's leads in shared
25-code batches and refresh expired rows together, so that review used 3 requests instead of exhausting 12.) Recorded-source replay is offline and makes no new sponsor
operation. Data-usage/branding permission, commercial definitions, complete quotes and signing availability
remain unresolved despite operational API access.

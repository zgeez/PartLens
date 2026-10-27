# Presentation outline — PartLens

Historical Existing BOM outline. The owner subsequently authorized New Design; see
[DESIGN-GENERATION.md](DESIGN-GENERATION.md) for current measured capabilities and limitations. Adapt the
presentation only with accurate scope; the original measurements below remain historical evidence.

Draft outline, not a rendered slide deck or submitted entry. Target a short pitch followed by the
[three-minute demonstration](SUBMISSION-DEMO.md). Use text diagrams and synthetic examples for public
slides until supplier-data/branding permission is established. Do not paste internal API output as artwork.

| Slide | Main point | Evidence / speaker note |
|---|---|---|
| 1. The sourcing problem | A cheaper line item can fail electrically, be unavailable or add assembly costs. | A fictional synthetic capacitor example; no invented market savings statistic. |
| 2. PartLens | Investigate a BOM and explain verified, rejected and still-unknown choices. | Requirements, sourcing and deterministic qualification in one existing desktop workflow. |
| 3. Why an agent | Missing context and heterogeneous sources require iterative questions and investigations. | Qwen selects tools/candidates; the controller bounds work. Deterministic checks alone cannot choose every next investigation; the LLM cannot certify compatibility. |
| 4. Reasoning and control | Separate tool proposals from authority. | Reuse README Mermaid: Qwen → controller → tools → evidence/checks → factual renderer. Highlight provenance, budgets, failed checks and partial completion. |
| 5. Official supplier/data access | Approved JLCPCB detail reads and actual Zetaris SELECTs. | Explicit codes only, HMAC authentication, timestamps, traces and SQL audit; no bulk extraction or implicit old-data fallback. Zetaris returns data; Session relates it to BOM requirements. |
| 6. Memory with accountability | A historical decision is context that must be reverified. | Real Meterless write, separate Node process, five recalled items; controller-enforced current checks. Three unchanged, two cannot reverify. |
| 7. Engineering verification | Equivalence and application suitability are separate. | Synthetic/public-safe check matrix: value, voltage, dielectric, tolerance, package; missing IC/circuit evidence stays unverified. Absolute maximum is not a recommended operating limit. |
| 8. Live demonstration | Import → investigation → evidence → checks → cost → recall → recheck → explanation. | State the chosen demo mode. Distinguish autonomous evaluation, deterministic preview and offline/synthetic fallback. |
| 9. Measured results and limits | Show observations, not universal success claims. | 245 tests; one official-source A/C trial; 8 decisions (3 verified equivalences, 1 rejection, 4 unverified); 10 supplier HTTP requests, 88 Zetaris SELECTs. A's original evaluator false result and correction preserved. Unknown commercial terms prevent a full quote. |
| 10. Roadmap and ask | Resolve evidence and permission gaps before expanding capability. | Official currency/MOQ/eligibility definitions, authorized read-only quotation, reviewed IC/circuit evidence, broader bounded evaluations and public-data permission. Future work is not implemented. Ask for feedback, not an order. |

Closing disclosure: original code/synthetic fixtures are Apache-2.0; Easyduino BOM is CERN-OHL-P-2.0;
model/runtime/H-MEM retain their licences. Pre-existing references are in DISCLOSURE.md. Cursor was not
used and eligibility is unconfirmed. No endorsement, public release or HackOS submission is claimed.

# Milestone 2 engineering corrections

## XC6206 identity and ratings

The approved BOM identifies U1 by supplier code C347376 and value XC6206P332MR, without a manufacturer in the
BOM field. The retained supplier fixture identifies that listing as **UMW**. MPN text alone is insufficient
to transfer Torex ratings to that listing.

The [official UMW datasheet](https://www.umw-ic.com/static/pdf/db5d7ec139677efdcb3bf5b5558e8bbd.pdf), revision
Mar.2025, lists XC6206P332MR in its ordering table on page 12. Its electrical-characteristics table on page 4
gives an input range of 1.8-8 V, while the limit table on page 3 gives 9 V. The two rating tables were inspected
visually; the exact ordering code was checked in extracted text. Thus, the fixture's 8 V value is consistent
with this UMW document; it is not established as an erroneous Torex specification or as the absolute limit.
This does not qualify regulation, thermal dissipation or output-current capability at every operating point.

The [official Torex product page](https://product.torexsemi.com/en/series/xc6206) and
[Torex USA specifications](https://www.torex-usa.com/products/voltage-regulators/low-iq/xc6206/) confirm the distinct
1.8-6 V operating range. The linked official Torex PDF could not be fetched successfully (timeout/403); no
uninspected Torex absolute rating is asserted. The original designer's intended manufacturer and the actual
application conditions still need to be established before qualifying a cross-manufacturer substitution.

An operator-selected local evidence overlay records the UMW limits in separate fields and rating domains.
The supplier fixture stays unchanged. Deterministic checks reject using evidence labelled absolute maximum
to establish an operating limit. Non-passive identity qualification requires both a known manufacturer and
an exact MPN. Cross-manufacturer devices stay unverified until functional/pinout evidence exists.

## Equivalence and application

`check_substitute` reports original-specification equivalence. It also returns a distinct application result.
The optimiser continues to admit only deterministically verified equivalents with adequate sourcing evidence.

The targeted reference rejects C53109434 against C25905 because the recorded voltage ratings are 25 V and
50 V respectively. This establishes a failed
equivalence check, not an unsafe circuit. The actual circuit voltage is unknown in that reference.

Capacitor checks cover nominal capacitance, voltage, dielectric, tolerance and original temperature range
when stated. A lower-rated capacitor can pass an evidenced applied-voltage check while failing equivalence.
Full application qualification remains unverified without relevant DC-bias/effective-capacitance, ESR,
ripple and temperature evidence. No LLM tool can assign a verdict or override a failed check.

## Manufacturing evidence

The [current JLCPCB fee table](https://jlcpcb.com/help/article/pcb-assembly-price) was reviewed separately from
part classification. Its Economic PCBA figures informed a conditional local schedule: setup $8.18, stencil
$1.53, SMT labor $0.0016 per joint and extended-part loading $3.07. These are not a board quotation, and joint
counts cannot be replaced with component counts.

Official product pages classify [C1525 as Basic](https://jlcpcb.com/partdetail/C1525) and
[C347376 as Extended](https://jlcpcb.com/partdetail/XC6206P332MR/C347376). Separate local overlays retain their
service, source and retrieval time. A classification must match the fee schedule's service and pass a
freshness check. Remaining classifications, board eligibility, service component prices, attrition,
manual assembly, X-ray and other applicable charges remain unresolved. Costs remain conditional accordingly.

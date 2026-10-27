# Test fixtures

All records here are **synthetic test data** written for PartLens's tests. Supplier part numbers use the
`TEST-` prefix (supplier `fixture`) so they can never be mistaken for real catalogue entries, and prices/stock
are invented. They exercise specific behaviours:

These original synthetic fixtures are distributable under the repository's Apache-2.0 licence. They are
the offline sample used by `python scripts/sample_demo.py`, explicitly labelled deterministic synthetic
execution. They contain no real supplier snapshots or private design data and do not prove sponsor access.

| Fixture part | Exercises |
|---|---|
| `fixture:TEST-C100N-X7R-16V` | baseline 100 nF 0402 X7R 16 V capacitor (basic) |
| `fixture:TEST-C100N-Y5V-16V` | same nominal value, incompatible dielectric (Y5V) |
| `fixture:TEST-C100N-X5R-25V` | same nominal value, narrower temperature range (X5R) |
| `fixture:TEST-C100N-X7R-6V3` | same nominal value, lower voltage rating |
| `fixture:TEST-C100N-X7R-50V-EXT` | compatible and cheaper per unit, but an extended part (loading fee) |
| `fixture:TEST-C100N-X7R-0603` | package mismatch |
| `fixture:TEST-C100N-NODIEL` | dielectric not stated (unverified) |
| `fixture:TEST-C100N-X7R-STALE` | compatible, supplier data 60 days old (availability unverified) |
| `fixture:TEST-R10K-1-0402` / `-ALT` | resistor baseline and a cheaper verified alternative; quantity price breaks |
| `fixture:TEST-LDO-A` / `-B` | regulator; alternative with lower maximum input voltage (electrically incompatible) |

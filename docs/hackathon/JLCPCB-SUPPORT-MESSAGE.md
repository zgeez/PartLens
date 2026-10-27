# Draft message to JLCPCB support

Prepared for the owner to review and send. **Not sent.** Add account/application identifiers privately
through the authorized support channel; do not add credentials to this file.

**Subject: Official component API field definitions and permitted demo usage**

Hello JLCPCB Open Platform support,

We are testing an approved, read-only component integration using
`/overseas/openapi/component/getComponentDetailByCode`. Could you provide authoritative documentation for:

1. The ISO currency of `priceRanges.unitPrice` and any documented account/locale or request controls.
2. MOQ and order multiples, including whether `startQuantity` defines pricing only and how purchase rounding works.
3. The complete `libraryType` enum, `assemblyComponentFlag` boolean meanings and service-specific Basic/Extended
   classification versus actual PCBA eligibility.
4. Available read-only PCB/PCBA quotation permissions and required inputs, without creating an order;
   also how supplier `solderJointCount` maps to board-level billable joints.
5. Whether selected component data and UI captures may be shown in a public hackathon demo/open-source
   project, with permitted attribution/branding, retention and redistribution conditions.

Our Business SDK is `com.szjlc.overseas:overseas-openapi-sdk-java:1.0.6-SNAPSHOT`; field Javadocs or an
updated schema would help. We currently leave undocumented terms unknown and keep actual API records
internal. Please also clarify whether `stockCount` implies any allocation/procurement guarantee.

Thank you.

Detailed technical follow-up: [JLCPCB-SUPPORT-QUESTIONS.md](JLCPCB-SUPPORT-QUESTIONS.md).

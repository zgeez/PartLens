# JLCPCB component contract: questions for support

Prepared for the owner; **not sent**. No credentials, signed download URLs or supplier responses are included.
Context: approved public component-detail permission, `getComponentDetailByCode`; Business SDK Maven
artifact `com.szjlc.overseas:overseas-openapi-sdk-java:1.0.6-SNAPSHOT`. The approved PDF, public guides and
successful responses do not establish the following commercial meanings.

1. What ISO currency does `priceRanges.unitPrice` use? Is it fixed, account-dependent or locale-dependent?
   Please identify any documented request/header currency control and the authoritative response field.
2. Where are MOQ and order multiples supplied? Does `startQuantity` describe only a pricing interval?
   How should purchase rounding, minimum package quantities and attrition be determined?
3. Please supply the exhaustive `libraryType` enum and its meanings for Economic versus Standard PCBA,
   including effective dates. We observe `base` and `expand`; Basic/Extended mapping is only corroborated inference.
4. What exactly does `assemblyComponentFlag` mean for both boolean values? Which independent field or
   endpoint establishes assembly eligibility for a particular service and board?
5. What inventory does `stockCount` cover? Is it net of reserved stock, when was it measured, and does it
   imply procurement availability or any allocation guarantee?
6. How is `solderJointCount` defined for exposed pads, shields, mounting pins, through-hole/manual work and
   panels? What additional inputs determine board-level billable joints and service applicability?
7. Which read-only PCB/PCBA quotation API permissions are available to this application? What public-demo
   inputs are required, including whether Gerber upload is mandatory, to obtain currency, fabrication,
   assembly, attrition and surcharges without creating an order? Please also provide SDK field Javadocs and
   written guidance on publishing selected API-derived demo evidence and permissible branding.

Until answered, PartLens leaves currency, MOQ, order multiples, guaranteed procurement, assembly eligibility,
billable board joints and complete quotations unknown. No quote/order/private-library endpoint was called.

References: [basic rules](https://api.jlcpcb.com/docs/start),
[API list](https://api.jlcpcb.com/docs/api-list),
[SDK guide](https://api.jlcpcb.com/docs/sdk-usage-guide),
[API agreement](https://api.jlcpcb.com/docs/agreement).

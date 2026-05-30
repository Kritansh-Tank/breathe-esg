# TRADEOFFS.md — What We Deliberately Did Not Build

## Breathe ESG Emissions Ingestion Platform

Three deliberate tradeoffs and why each was made.

---

## 1. No Real-Time API Integration for Any Source

**What we built**: CSV file upload for all three sources.

**What we did not build**: Live API integrations (SAP OData, Green Button OAuth, Concur REST).

**Why**:

Real-time API integration sounds better on paper. In practice, for an enterprise onboarding tool, it creates more problems than it solves:

- **Client IT cooperation**: Each live API requires the client's IT team to configure authentication, firewall rules, and credentials. This takes weeks per client. CSV upload requires nothing from IT — just a download and an email.
- **Maintenance surface**: Three separate API integrations, each with different auth mechanisms, rate limits, schema changes, and provider-specific quirks. A CSV parser for each source has a fraction of that complexity.
- **Data latency is fine**: Breathe's use case is monthly or quarterly emissions reporting — not real-time monitoring. A once-a-month CSV upload matches the actual reporting cadence.

**What breaks in production**: If clients want automated, zero-touch ingestion (e.g., SAP automatically pushing to Breathe on month-end), CSV upload requires a manual step. This is the primary limitation. The mitigation is SFTP drop or email ingestion as a next step — clients email the CSV to a managed address, and Breathe processes it automatically. This is still simpler than live API integration.

---

## 2. Static Emission Factors (Not a Dynamic Factor API)

**What we built**: A hardcoded Python dict of UK DEFRA 2024 factors, versioned in source code.

**What we did not build**: Integration with a live emission factor API (Climatiq, electricityMap, ecoinvent).

**Why**:

Dynamic factor APIs have real appeal — country-specific grid intensity updates daily, and DEFRA factors change annually. But:

- **Reliability**: A third-party API in the ingestion path means if the factor API goes down, uploads fail. For a prototype that evaluators will click through, this is unacceptable.
- **Cost**: Climatiq charges per API call. Bulk CSV processing with 1000 rows would generate 1000 API calls per upload — expensive and slow.
- **Auditability**: When a client asks "why does this record show 0.204 kgCO₂e/kWh?", the answer must be traceable to a specific published source. A static, code-versioned table is trivially auditable. A dynamic API response is not.
- **Factor stability**: For fuel emission factors (the bulk of Scope 1), DEFRA factors change by <1% year-on-year. The precision gain from dynamic lookup is negligible versus the complexity added.

**What breaks in production**: Electricity grid emission factors genuinely change significantly year-on-year (e.g. UK grid went from 0.233 to 0.205 kgCO₂e/kWh between 2022 and 2024). A production system should either: (a) re-run the emission calculation annually when DEFRA updates, or (b) integrate a factor library like `climatiq-python` as a background update process — not in the hot path of CSV upload.

---

## 3. No Market-Based Electricity Accounting

**What we built**: Location-based electricity accounting only (grid average emission factor per country).

**What we did not build**: Market-based accounting (where clients can claim zero-emission electricity via renewable energy certificates / Power Purchase Agreements).

**Why**:

GHG Protocol allows both location-based and market-based Scope 2 reporting, and companies with PPAs or RECs frequently want to show near-zero Scope 2. But:

- **Data complexity**: Market-based accounting requires knowing which specific electricity products the client purchased, the associated residual mix factors, and whether their RECs are certified. This data doesn't come from the utility bill — it requires a separate contract management workflow.
- **Verification risk**: RECs are frequently double-counted in the industry. A prototype that blindly accepts "we have a PPA, make our Scope 2 zero" without verification would be misleading.
- **Analytical value**: For an analyst review dashboard, location-based Scope 2 is the more conservative and consistently comparable baseline. Market-based can be added as a reporting toggle once the underlying contract data pipeline is built.

**What breaks in production**: Clients with significant renewable energy commitments (e.g., RE100 members) will find their Scope 2 looks worse than they'd like using location-based factors alone. The PM conversation needed is: "We report both figures per GHG Protocol dual reporting guidance — location-based for comparability, market-based for your sustainability targets."

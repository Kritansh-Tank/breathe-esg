# DECISIONS.md — Engineering Decisions

## Breathe ESG Emissions Ingestion Platform

This document records every significant ambiguity, what we chose, why, and what we'd ask the PM if we could.

---

## Source 1 — SAP Fuel & Procurement

### Decision: Flat-file CSV upload (not IDoc, OData, or BAPI)

**Chosen**: SAP MM flat-file CSV export from transaction `ME80FN` or direct table joins (`EKKO + EKPO + EKBE`).

**Why not IDoc**: IDoc requires a configured EDI endpoint and middleware (e.g. SAP PI/PO or BTP Integration Suite) on the client's SAP system. This is a multi-month IT project, not a realistic onboarding path for Breathe.

**Why not OData**: OData services require live, authenticated access to the client's SAP S/4HANA system. Enterprise clients are extremely reluctant to give external vendors API-level access to their core ERP. Even where it's technically possible, security reviews take months.

**Why not BAPI**: BAPIs are synchronous function calls requiring SAP RFC connectivity — same problem as OData, plus they're not designed for bulk data export.

**Why CSV**: The SAP transaction `ME80FN` lets any user with purchasing evaluation access export a list of purchase orders to CSV in under 5 minutes. This is what actually happens at enterprise clients — a sustainability lead emails a CSV from IT. It's realistic, zero-infrastructure, and already widely used.

### What subset of SAP we handle

**Included**: MM Purchase Orders (EKKO/EKPO) for direct fuel materials — diesel, natural gas, LPG, gas oil, fuel oil, kerosene.

**Excluded**:
- GR/IR reconciliation (whether fuel was actually delivered vs. ordered) — we use PO date as the activity date; in production you'd join EKBE for goods receipt confirmation
- Plant cost hierarchy — we use the plant code as-is; in production a plant-to-legal-entity mapping would be needed for consolidated reporting
- Service POs (item category D) — fuel-as-a-service contracts are structurally different and would need a separate parser
- CO module (actual consumption postings) — more accurate but requires direct SAP CO access
- Currency conversion — costs are stored but not converted; not needed for emission calculation which is quantity-based
- Material master lookup — we identify fuel type from the free-text Description field; in production you'd use a material group → fuel type mapping table

**What we'd ask the PM**: "Can the client's SAP admin run a custom ABAP report that joins EKKO+EKPO+EKBE for us, filtered to material group 'FUEL', and schedule it as a monthly CSV extract? That would solve the GR reconciliation gap and remove the need for free-text description matching."

---

## Source 2 — Utility Bills (Electricity)

### Decision: Portal CSV upload (not Green Button API, not PDF parsing)

**Chosen**: CSV export from the utility provider's online portal, downloaded by the facilities team.

**Why not Green Button / API**: The Green Button Connect My Data (CMD) OAuth flow is provider-specific. National Grid, EDF, British Gas, and Scottish Power each have different API implementations. Some don't offer it at all. Integrating even 3 providers would require separate OAuth app registrations and maintenance for each. Not feasible for a prototype.

**Why not PDF parsing**: PDF bills are visually formatted documents with no consistent structure. Even OCR-based extraction has 5–10% error rates on meter readings and amounts — unacceptable for audit-grade data.

**Why CSV**: UK utility portals (and most EU equivalents) all provide a "Download billing history as CSV" or "Download meter data as CSV" button. This is standard practice. The Green Button Alliance's CSV format is widely supported. Facilities managers already download these files monthly for their spreadsheet tracking.

### What we handle

**Included**: Monthly billing-period consumption in kWh, meter ID, site address, billing start/end dates. Estimated readings are flagged in `analyst_note` for human review.

**Excluded**:
- Demand charges (kW peak) — not needed for Scope 2 emission calculation
- Power factor / reactive power (kVAR) — utility billing concept, not emissions-relevant
- Renewable energy certificates (RECs) — market-based accounting vs. location-based is a design choice; we use location-based (simpler, defensible for first version)
- Sub-metering — we treat each meter as a separate row; sub-meter aggregation is a client-specific hierarchy

**Billing period misalignment**: Utility billing periods frequently cross calendar month boundaries (e.g. 20 Dec – 22 Jan). We store `period_start` and `period_end` exactly as received — we do not force alignment to calendar months. This preserves accuracy at the cost of making month-on-month comparison harder. The PM could later add a proration feature.

**What we'd ask the PM**: "Should we implement market-based electricity accounting (where clients can claim zero-emission electricity via RECs)? This changes the emission factor from grid-average to zero, which is a significant reporting difference."

---

## Source 3 — Corporate Travel (Concur)

### Decision: Concur Intelligence CSV export (not live Concur API)

**Chosen**: CSV export from SAP Concur Intelligence / Analysis pre-built reports.

**Why not live Concur API**: The Concur REST API uses OAuth 2.0, which requires:
1. A registered Concur App Center application (takes weeks and Concur partner approval)
2. Enterprise admin enabling the app for their Concur tenant
3. Ongoing credential management

This is a multi-week setup. Even for Breathe's own integration, the carbon data Concur exposes natively is minimal — the actual calculation is done by third-party integrations like Thrust Carbon, which add another dependency.

**Why Concur Intelligence**: Concur Intelligence (the reporting module) has pre-built travel reports that export cleanly as CSV, including all the fields we need: trip date, travel type, origin/destination (IATA codes), service class, distance (sometimes), employee, cost center. Any Concur admin can schedule this as a monthly export in under 10 minutes.

### What we handle

**Included**: Air travel (with short/long-haul detection at 3700km per DEFRA), rail, car rental. Service class (Economy/Business/First) is factored into the emission factor. Missing distances are derived via Haversine great-circle from IATA airport coordinates.

**Excluded**:
- Hotel stays — Scope 3 Category 6 includes accommodation, but Concur hotel data rarely includes star rating or certification data needed for DEFRA factors; this would require a separate hotel emissions dataset
- Employee commuting — Scope 3 Category 7, separate data collection process entirely
- Spend-based fallback — we require distance data (given or derivable from IATA codes); if neither is available, the row is rejected with a parse error rather than using an unreliable spend-based estimate

**Distance derivation**: For air trips where `DistanceKm` is blank (common in Concur exports), we use Haversine great-circle distance from our IATA coordinate lookup table (40+ major airports). This is marked in `analyst_note` so the analyst can verify. In production, a complete IATA dataset (7000+ airports) would replace our lookup table.

**What we'd ask the PM**: "For the hotel emissions gap — do clients want Scope 3 Category 6 to include accommodation, or is air/rail/car sufficient for the first version? The data quality for hotel emissions is significantly lower."

---

## Auth and Multi-tenancy

### Decision: Shared schema multi-tenancy with row-level `organization` FK

**Why**: Shared schema is the right default for a SaaS ESG platform at this stage. It's simpler to maintain (single migration set), cost-effective (single DB), and sufficient for the isolation needs here — client data is separated by application-layer filtering, not database-layer schemas.

**Why not schema-per-tenant**: Schema-per-tenant (using PostgreSQL schemas) requires running migrations across all schemas on every deploy, complicates cross-tenant analytics, and adds significant operational overhead. Justified only when enterprise clients have GDPR physical separation requirements — not the default.

**Isolation enforcement**: Every view explicitly filters by `request.user.organization`. This is intentional — it's more auditable than a magic manager that silently filters.

### Decision: JWT (not session cookies)

JWT was chosen because the frontend (Vercel) and backend (Render) are on different domains. Cookie-based sessions require `SameSite=None; Secure` and careful CORS configuration. JWT with `Authorization: Bearer` header is simpler for a cross-origin SPA + API setup and is stateless (no server-side session store needed).

---

## Emission Factors

### Decision: Static lookup table (not dynamic API)

**Chosen**: Static Python dict of UK DEFRA 2024 factors, versioned in code.

**Why not a dynamic factor API** (e.g. Climatiq, electricityMap): 
1. External API dependency in a data path means outages block ingestion
2. Factor APIs charge per call — not appropriate for bulk CSV processing
3. For a first prototype, the complexity is unjustified

**Why DEFRA 2024**: DEFRA (UK Government GHG Conversion Factors) is the most widely used factor set for UK/EU corporate reporting. It covers all three source types (fuel, electricity, travel) in a single authoritative dataset. The US EPA eGRID is available as a country-specific override for US electricity.

**Factor versioning**: The factor used is stored on each `NormalizedRecord` at ingest time (`emission_factor_source = 'UK_DEFRA_2024'`). If factors update, old records are not automatically re-calculated — this is correct for audit purposes. A `recalculate_factors` management command would be the right upgrade path.

---

## Review Workflow

### Decision: Three-state approval (pending → approved → locked)

**Why not two-state** (pending → approved): Locking is essential for audit readiness. Once an auditor signs off on a dataset, analysts should not be able to change approved values. The `locked` state enforces this — locked records reject all write operations at the view layer.

**Why not more states**: A "submitted for review" intermediate state was considered but rejected — it adds workflow complexity without clear benefit at this scale. The `analyst_note` field and `flagged` status handle the need for human communication about uncertain records.

### Decision: Approvals are per-record, not per-batch

Batch-level approval was considered but rejected. In practice, a single SAP CSV might contain 50 records across multiple plant codes, fuel types, and time periods. An analyst needs to review each row individually, not rubber-stamp an entire file. The bulk-approve endpoint exists for efficiency but is still row-level.

---

## Role-Based Access Control (RBAC)

### Decision: Three roles — analyst, admin, auditor

**Why three roles, not two or one**:

In real ESG workflows, three actors interact with the data at different stages:

- **Analyst**: The person who processes incoming data — uploads CSVs, spots anomalies, flags or approves rows. This is the primary day-to-day user.
- **Admin**: The sustainability manager or team lead who has final authority over the dataset — can lock records once approved, preventing retroactive changes before audit submission.
- **Auditor**: An external (or internal) auditor who must be able to verify the data without any risk of accidentally changing it. Read-only access is not a courtesy — it's a requirement for audit independence.

**Permission matrix rationale**:

| Action | analyst | admin | auditor |
|--------|:-------:|:-----:|:-------:|
| Upload CSV | ✅ | ✅ | ❌ |
| Approve / Flag / Edit | ✅ | ✅ | ❌ |
| Lock for audit | ❌ | ✅ | ❌ |
| View all records + audit log | ✅ | ✅ | ✅ |

Lock is admin-only because once a record is locked, it cannot be changed by anyone. This action has permanent consequences and should require a deliberate, privileged decision — not something an analyst can accidentally trigger.

**Enforcement**: Permissions are enforced at both the API layer (HTTP 403 if role is insufficient) and the UI layer (buttons hidden for unauthorized roles). API enforcement is the security guarantee; UI enforcement is the UX improvement.

**What we'd ask the PM**: "Should auditors be able to leave comments on records (without changing status), similar to a 'review note' without write access? This is a common auditor requirement in regulated industries."

---

## Deployment Stack

### Decision: Render (backend) + Vercel (frontend) + Supabase (database)

**Backend — Render over Railway/Fly**:
- Render has a persistent free tier with always-on web services (no cold starts on paid tier), native support for `Procfile`-based deploys (same as Heroku), and automatic deploys from GitHub. Railway and Fly.io are both viable alternatives, but Render's Django deployment documentation is more mature and the `dj-database-url` + `gunicorn` + `whitenoise` stack is well-established there.

**Frontend — Vercel over Netlify/Render**:
- Vercel is purpose-built for frontend SPA deployments. It auto-detects Vite, handles SPA routing rewrites natively via `vercel.json`, and provides edge CDN globally. Netlify is equally capable; Vercel was chosen because its zero-config Vite support requires less setup.

**Database — Supabase over Neon/ElephantSQL**:
- Supabase provides a managed PostgreSQL instance with a generous free tier (500MB), a web-based table editor for quick data verification, and connection pooling via PgBouncer (Transaction mode on port 6543) — essential for Django + gunicorn where multiple workers share the connection pool. Neon is a strong alternative but Supabase's dashboard makes it easier to verify that migrations ran correctly during the post-submission review.

**Why not a monolithic deployment** (e.g., Django serving the React build):
- Keeping frontend and backend separate allows independent deployments, separate scaling, and clean separation of concerns. Vercel's CDN for static assets will always outperform Django/WhiteNoise for frontend delivery. The CORS configuration cost is small compared to the operational benefits.


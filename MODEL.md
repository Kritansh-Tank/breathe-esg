# MODEL.md — Data Model Documentation
## Breathe ESG Emissions Ingestion Platform

---

## Overview

The data model is built around three concerns:
1. **Multi-tenancy** — every object is scoped to an `Organization`
2. **Source-of-truth preservation** — raw inbound data is never mutated
3. **Audit trail** — every state change is logged immutably

---

## Entity Relationship Diagram

```
Organization (tenant)
    │
    ├── User (role: admin | analyst | auditor)
    │
    ├── AuditLog (immutable, append-only)
    │
    └── IngestionBatch (one per CSV upload)
            │
            └── RawRecord (immutable verbatim row)
                    │
                    └── NormalizedRecord (analyst-editable, versioned)
```

---

## Models

### `Organization` — Tenant

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | Primary key |
| `name` | CharField(255) | Display name |
| `slug` | SlugField(100) | Unique identifier, used for URL routing |
| `created_at` | DateTimeField | Auto-set on creation |

**Multi-tenancy decision**: Shared schema with row-level isolation. Every model that holds client data has an `organization` FK. This is the standard SaaS approach — simpler migrations than schema-per-tenant, lower cost, and sufficient for Breathe's onboarding use case. Only moved to schema-per-tenant if a client's data isolation requirements demand it (e.g., GDPR physical separation).

---

### `User` — Extends AbstractUser

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | Primary key |
| `organization` | FK(Organization) | The tenant this user belongs to |
| `role` | CharField | `admin` \| `analyst` \| `auditor` |
| `email`, `username` | (inherited) | Standard Django auth fields |

**Roles**:
- `analyst` — can upload CSVs, view, edit, approve, and flag records
- `admin` — all analyst permissions + can lock approved records for audit
- `auditor` — read-only; can view all records and the audit log, cannot modify anything

**Role Permission Matrix**:

| Action | analyst | admin | auditor |
|--------|:-------:|:-----:|:-------:|
| Login / view dashboard | ✅ | ✅ | ✅ |
| View normalized records | ✅ | ✅ | ✅ |
| View audit log | ✅ | ✅ | ✅ |
| Upload CSV (ingest data) | ✅ | ✅ | ❌ |
| Edit a normalized record | ✅ | ✅ | ❌ |
| Approve a record | ✅ | ✅ | ❌ |
| Flag a record (with note) | ✅ | ✅ | ❌ |
| Bulk approve records | ✅ | ✅ | ❌ |
| Lock an approved record | ❌ | ✅ | ❌ |
| Access Django admin panel | ❌ | ✅ | ❌ |

> Permissions are enforced at **both** the API layer (returns HTTP 403 if role is insufficient) and the UI layer (buttons are hidden for unauthorised roles).


---

### `IngestionBatch` — One per file upload

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | Primary key |
| `organization` | FK(Organization) | Tenant scope |
| `source_type` | CharField | `sap` \| `utility` \| `travel` |
| `ingested_by` | FK(User) | Who uploaded the file |
| `ingested_at` | DateTimeField | Auto-set |
| `file_name` | CharField(255) | Original filename |
| `row_count` | IntegerField | Successfully parsed rows |
| `error_count` | IntegerField | Rows that failed parsing |
| `status` | CharField | `pending` → `processing` → `processed` / `failed` |
| `error_log` | JSONField | `[{row: "PO-1234-10", error: "..."}]` |

**Why batch matters**: Groups all records from a single file upload. Enables re-ingestion auditing, allows analysts to filter by upload event, and provides a natural unit for rollback if needed.

---

### `RawRecord` — Immutable verbatim copy

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | Primary key |
| `batch` | FK(IngestionBatch) | Parent batch |
| `organization` | FK(Organization) | Denormalized for fast per-tenant queries |
| `raw_payload` | JSONField | **Verbatim CSV row as received — never mutated** |
| `source_row_id` | CharField(255) | e.g. `PO-4500012301-10` for SAP |
| `parse_error` | TextField | Non-empty if normalization failed |
| `created_at` | DateTimeField | Auto-set |

**Why immutable**: This is the audit anchor. If an analyst later disputes a normalized value, we can always prove what the original file said. The `raw_payload` field stores the exact dict from the CSV row, keys included, before any transformation.

---

### `NormalizedRecord` — The central emission record

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | Primary key |
| `organization` | FK(Organization) | Tenant scope |
| `raw_record` | OneToOne(RawRecord) | Source-of-truth link |
| `batch` | FK(IngestionBatch) | For batch-level filtering |
| **Source provenance** | | |
| `source_type` | CharField | `sap` \| `utility` \| `travel` |
| `source_id` | CharField | e.g. `PO-4500012301-10`, `UTIL-METER-LDN-001-1` |
| `supplier_or_site` | CharField | Vendor code / meter address / employee name |
| **GHG Classification** | | |
| `scope` | IntegerField | 1, 2, or 3 (GHG Protocol) |
| `category` | CharField | e.g. `stationary_combustion`, `purchased_electricity` |
| `description` | CharField | Human-readable description of the activity |
| **Normalized activity** | | |
| `activity_quantity` | DecimalField(18,4) | The normalized amount |
| `activity_unit` | CharField | `L`, `kWh`, `km`, `passenger_km` |
| `activity_unit_original` | CharField | As-received UOM (e.g. `MT`, `M3`, `Nm3`) |
| **Emission calculation** | | |
| `emission_factor` | DecimalField(18,8) | kgCO₂e per unit |
| `emission_factor_source` | CharField | `UK_DEFRA_2024` |
| `co2e_kg` | DecimalField(18,4) | `activity_quantity × emission_factor` |
| **Period + location** | | |
| `period_start` | DateField | Start of activity period |
| `period_end` | DateField | End of activity period |
| `facility_code` | CharField | SAP plant code / meter ID / cost center |
| `country` | CharField | ISO 3166-1 alpha-2 |
| **Review state** | | |
| `status` | CharField | `pending_review` → `approved` → `locked` (or `flagged`) |
| `is_edited` | BooleanField | True if analyst changed any field |
| `last_edited_by` | FK(User, null) | |
| `last_edited_at` | DateTimeField(null) | |
| `analyst_note` | TextField | Free text annotation |
| `locked_at` | DateTimeField(null) | Set when record is locked |
| `locked_by` | FK(User, null) | Admin who locked |

**State machine**:
```
pending_review → approved → locked
pending_review → flagged → approved (after fixing) → locked
locked records cannot be edited, approved, or flagged
```

---

### `AuditLog` — Immutable event log

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | Primary key |
| `organization` | FK(Organization) | Tenant scope |
| `user` | FK(User, null) | Who performed the action |
| `action` | CharField | `ingest` \| `edit` \| `approve` \| `flag` \| `lock` |
| `target_type` | CharField | e.g. `NormalizedRecord`, `IngestionBatch` |
| `target_id` | CharField | UUID of the affected object |
| `diff` | JSONField | `{before: {...}, after: {...}}` for edits |
| `note` | TextField | Optional human note |
| `timestamp` | DateTimeField | Auto-set, immutable |

**Immutability enforcement**: The Django admin for `AuditLog` overrides `has_add_permission`, `has_change_permission`, and `has_delete_permission` to return `False`. Entries are only ever created by application code via `AuditLog.objects.create()` — never updated. The `timestamp` is `auto_now_add=True` so it cannot be set externally.

---

## Multi-tenancy Query Pattern

All views enforce tenant isolation via:
```python
NormalizedRecord.objects.filter(organization=request.user.organization)
```

This is checked at the view layer, not in a shared manager, to keep the implementation explicit and auditable. A custom manager was considered but rejected — explicit filtering is easier to verify in code review for a security-sensitive context.

---

## Unit Normalization Rules

| Source | Original Units | Normalized To | Method |
|--------|---------------|---------------|--------|
| SAP diesel | L, Ltr, Litre, GAL | L | Conversion factors |
| SAP diesel | MT, Tonne | L | Density (kg/L) |
| SAP natural gas | M3, Nm3 | kWh | Calorific value (10.55 kWh/m³) |
| SAP LPG | MT | L | Density (0.51 kg/L) |
| Utility | kWh, MWh | kWh | ×1000 for MWh |
| Travel air/rail/car | km (given or derived) | km | Haversine if IATA codes given |

---

## Emission Factor Source

All factors: **UK Government GHG Conversion Factors for Company Reporting 2024** (DEFRA).

- Fuel: kgCO₂e per litre (or kWh for gas)
- Electricity: kgCO₂e per kWh (location-based, market average per country)
- Travel: kgCO₂e per passenger-km (includes radiative forcing for air)

The factor is stored on each `NormalizedRecord` at the time of ingestion. If DEFRA updates factors in 2025, existing records are unaffected — they retain the 2024 factor used when ingested, which is correct for auditability. A re-normalization command would be needed to update existing records.

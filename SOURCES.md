# SOURCES.md — Real-World Data Source Research

## Breathe ESG Emissions Ingestion Platform

For each of the three sources: what the real-world format looks like, what we learned, what our sample data reflects, and what would break in a real deployment.

---

## Source 1 — SAP Fuel & Procurement

### Real-World Format

SAP MM procurement data lives across three primary database tables:
- **EKKO** — Purchase order header (PO number, vendor, date, purchasing org, currency)
- **EKPO** — Purchase order line items (material number, description, quantity, unit of measure, price, plant)
- **EKBE** — Purchase order history (goods receipts, invoices, linking PO to actual delivery)

Real exports from `ME80FN` (General Purchasing Evaluations) produce a flat file that merges these tables. The actual column names in the CSV depend on the display variant configured by the SAP admin — they are not standardized across companies.

**What we learned from research:**
- Column headers are often in the display language of the SAP system. German companies will have `Buchungsdatum` instead of `DocumentDate`, `Menge` instead of `Quantity`, `Werk` instead of `Plant`. We handle the most common German variants.
- UOM (unit of measure) is stored as the SAP internal code: `L` (litre), `Ltr` (also litre), `ST` (piece), `M3` (cubic metre), `KG` (kilogram), `MT` (metric tonne), `Nm3` (normal cubic metre for gas). These are not always the same as ISO units.
- Natural gas can be in `M3`, `Nm3`, or `kWh` depending on whether the supplier invoices by volume or energy content. Different countries use different norms.
- Dates in SAP are stored in YYYYMMDD internally but exported to CSV in the system's display format — typically DD.MM.YYYY in European systems (German format) or MM/DD/YYYY in US systems.
- Purchase orders capture the commitment to buy — not necessarily delivery. The goods receipt date (`EKBE.BUDAT`) is the actual delivery date and is more accurate for emission period assignment.

**What our sample data looks like:**
- 15 rows across 5 plant codes (`1010` through `1050`)
- Mix of diesel (L and Ltr), natural gas (M3 and Nm3), LPG (MT), gas oil (Ltr), fuel oil (MT), kerosene (L)
- German date format (DD.MM.YYYY) throughout
- 2 intentional error rows: one with an invalid quantity string, one with an impossible date (32.13.2024)
- One row with a missing `GoodsReceiptDate` (falls back to DocumentDate + 7 days)
- Vendor numbers in SAP format (V-10045 etc.)

**What would break in a real deployment:**
1. **Column name variability**: Different clients will have different column headers depending on their SAP display variant. A production system needs a configurable column mapping per client, not a hardcoded list.
2. **Material group vs. description**: We identify fuel type from the free-text `Description` field (substring matching). In production, the client's material master includes a material group (e.g. `FUEL-DIESEL`, `UTIL-GAS`) that should be used instead — it's structured and doesn't require NLP.
3. **Plant-to-facility mapping**: SAP plant codes (`1010`, `2001`) mean nothing without a plant master lookup table that maps them to legal entities, addresses, and countries. We default to country `GB` — wrong for any client with international plants.
4. **GR/IR reconciliation**: We use the PO order date as the activity date. In reality, fuel is consumed when delivered (goods receipt date). If a PO is raised in December but fuel arrives in January, the emission belongs to January — our approach would misattribute it.
5. **Character encoding**: SAP exports can be in SAP codepage 1100 (essentially Latin-1) or UTF-8 depending on system version. We handle both, but edge cases with special characters in vendor names (accents, umlauts) may corrupt.

---

## Source 2 — Utility Bills (Electricity)

### Real-World Format

Utility billing data is accessed via:
- **Portal CSV download**: Most UK and EU utility providers offer "Billing History" or "Usage History" downloads from their online portal. Format varies by provider.
- **Green Button (US/Canada)**: A standardized XML or CSV format for meter data, mandated by some US states. Available from providers like PG&E, ConEdison, Xcel Energy.
- **EDI (Electronic Data Interchange)**: Large commercial accounts sometimes receive machine-readable bills via EDI 810 (Invoice) format. Requires EDI infrastructure.

**What we learned from research:**
- There is no universal CSV schema. National Grid, EDF, British Gas, and Scottish Power all export different column names and date formats.
- Billing periods are almost never aligned to calendar months. A large commercial meter billed on a 28-day cycle will drift — January's bill might cover Dec 20 – Jan 17. This complicates month-on-month comparison.
- Estimated reads are extremely common — utility providers estimate consumption between actual meter reads (typically quarterly for smaller meters). Estimated rows must be flagged for analyst review because they'll be corrected in the next bill.
- Half-hourly (HH) metered accounts (large commercial) produce 48 data points per day. Our model aggregates to billing period totals for simplicity; interval data would require a different schema.
- Some portals export cumulative meter readings (previous/current) and expect the consumer to subtract to get consumption. Others export consumption directly.

**What our sample data looks like:**
- 8 rows across 3 UK sites (London, Manchester, Edinburgh)
- 3 different meter IDs under 2 account numbers
- One billing period crossing a month boundary (Dec 20 – Jan 22)
- One estimated reading (flagged with `Estimated: Yes`)
- Mix of HH tariff (`BUSI-HALF-HH`) and SME tariff (`BUSI-SME`)
- All UK locations → UK DEFRA 2024 grid factor (0.20493 kgCO₂e/kWh)

**What would break in a real deployment:**
1. **No universal schema**: Every utility provider uses different column names. A production system needs either a provider-specific parser library or a configurable column mapping UI.
2. **Estimated reads correction**: When an estimated read is subsequently corrected in the next bill, the corrected bill shows a credit adjustment. Our model would double-count unless the analyst manually flags and offsets the estimate.
3. **HH data volume**: A single large site with half-hourly metering generates 17,520 rows per year. Our model handles this (each row becomes a `NormalizedRecord`) but the dashboard aggregations become slow without database indexing on `period_start` + `organization`.
4. **Tariff structure**: We store tariff name in `analyst_note` but don't parse it. Time-of-use tariffs, export tarrifs (for on-site generation), and demand charges are all lost. Not needed for Scope 2 emission calculation but useful for energy cost analysis.
5. **Renewable generation export**: Sites with solar PV will have export readings (negative consumption). Our parser would generate a negative `activity_quantity` which breaks the emission calculation. Production needs a sign check.

---

## Source 3 — Corporate Travel (Concur)

### Real-World Format

SAP Concur travel data is accessible via:
- **Concur Intelligence / Analysis Reports**: Built-in reporting module that produces trip-level CSV exports. Available to any Concur admin.
- **Concur REST API**: Expense Report API and TripIt integration API provide JSON. Requires OAuth app registration.
- **Thrust Carbon / Climatiq integration**: Carbon-specific partners that pull Concur data and return calculated emissions. Bypasses the need for in-house calculation.

**What we learned from research:**
- Concur does not natively expose a carbon footprint field. Emission data comes from partner integrations (Thrust Carbon is the most common).
- The Concur Intelligence CSV includes: expense report ID, trip date, travel mode, origin/destination (IATA codes for air, city names for rail), service class, cost, employee, cost center. Distance is often blank — Concur doesn't always calculate it.
- IATA airport codes are universal for air travel but Concur sometimes uses city codes (e.g. LON for London instead of LHR/LGW) which are ambiguous. Rail segments often use station names rather than codes.
- Service class is inconsistently coded: "Economy", "Y Class", "Coach", "Standard" all mean the same thing. "Business", "J Class", "Club" are equivalent. Normalization requires a fuzzy matcher in production.
- Concur exports don't distinguish between short-haul and long-haul flights — distance must be calculated from IATA coordinates.

**What our sample data looks like:**
- 12 rows mixing Air, Rail, Car Rental travel types
- Air trips without DistanceKm (demonstrating Haversine fallback from IATA codes)
- Rail with explicit distance
- Car rental with fuel type (Diesel vs. Unknown)
- Row 10: DistanceKm = 0 (parse error — rejected)
- Row 12: Invalid IATA codes "FAKE"→"FAKE" (parse error — rejected)
- Mix of Economy and Business service class for air (different emission factors)
- Long-haul (LHR→JFK: ~5540km) and short-haul (LHR→CDG: ~340km) correctly differentiated

**What would break in a real deployment:**
1. **IATA coordinate coverage**: Our lookup table covers ~45 major airports. The real IATA database has 9,000+ airports. Any trip involving a regional airport (e.g. BRS for Bristol, ABZ for Aberdeen) would fail distance derivation. Production needs the full IATA dataset.
2. **Hotel emissions**: Scope 3 Category 6 (Business Travel) includes accommodation. Concur hotel data doesn't include star rating or certification, which is what DEFRA needs for hotel factors. This entire sub-category is missing from our implementation.
3. **Duplicate detection**: If a travel coordinator uploads the same Concur report twice (e.g., re-exporting after an expense correction), we'd double-count. Production needs deduplication on `ExpenseReportID` + source row key.
4. **International rail**: We use DEFRA UK rail factor (0.03549 kgCO₂e/km) for all rail. International rail (Eurostar, ICE, TGV) has a different — often much lower — factor because European electricity grids are cleaner than UK. DEFRA provides separate international rail factors.
5. **Car ownership vs. rental**: DEFRA has different factors for employee-owned vehicles (where fuel type is known) vs. rental vehicles (where it's often unknown). Our current approach uses "car rental unknown" as default, which over-estimates for electric rental cars.

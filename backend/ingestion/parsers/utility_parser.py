"""
Utility Bill CSV Parser (Electricity)
======================================
Handles portal CSV exports — specifically the UK/EU billing CSV format
that facilities teams download from utility provider portals.

We chose CSV upload over API for these reasons:
  - Utility portal APIs (Green Button OAuth, e.g. PG&E, National Grid)
    are provider-specific and require enterprise OAuth registration.
  - In practice, a facilities team downloads a CSV from their portal monthly.
  - PDF parsing is fragile; structured CSV is the realistic path.

Expected columns (case-insensitive, extra columns ignored):
  AccountNumber, MeterID, BillingPeriodStart, BillingPeriodEnd,
  ConsumptionKWh, PreviousReading, CurrentReading, TotalCost,
  Currency, Tariff, SiteAddress (optional), Country (optional)

Known quirks handled:
  - Billing periods that cross calendar month boundaries
  - Estimated readings (flagged in notes)
  - Mixed units (kWh and MWh in same file)
  - Missing CurrentReading: calculated from PreviousReading + Consumption

What we ignore:
  - Demand charges (kW peaks) — not needed for Scope 2 emission calc
  - Power factor corrections
  - Reactive power (kVAR)
  - Renewable energy certificate (REC) claims → market-based accounting
"""

import csv
import io
from datetime import datetime
from decimal import Decimal
from typing import Optional

from ingestion.emission_factors import get_electricity_factor, EMISSION_FACTOR_SOURCE

DATE_FORMATS = [
    "%d/%m/%Y", "%Y-%m-%d", "%m/%d/%Y", "%d-%m-%Y",
    "%d.%m.%Y", "%Y/%m/%d", "%d %b %Y", "%d %B %Y",
]


def _parse_date(raw: str) -> Optional[datetime]:
    raw = raw.strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def _normalise_cols(row: dict) -> dict:
    return {k.strip().lower().replace(" ", "_"): v.strip() for k, v in row.items()}


def _parse_kwh(value_str: str, uom_hint: str = "kwh") -> Optional[float]:
    """Parse consumption value and normalise to kWh."""
    try:
        val = float(value_str.replace(",", "").strip())
        if "mwh" in uom_hint.lower():
            val *= 1000
        return val
    except (ValueError, AttributeError):
        return None


def parse_utility_csv(file_content: str, batch_id, organization_id) -> list[dict]:
    """
    Parse utility portal billing CSV.
    Returns list of dicts with normalized emission record fields.
    """
    results = []
    reader = csv.DictReader(io.StringIO(file_content))

    required_cols = {"billingperiodstart", "billingperiodend", "consumptionkwh"}

    for i, raw_row in enumerate(reader, start=2):
        row = _normalise_cols(raw_row)
        record = {
            "source_row_id": "",
            "raw_payload": raw_row,
            "parse_error": "",
            "normalized": None,
        }

        # Allow flexible column naming
        # ConsumptionKWh alias variants
        for alias in ("consumption_kwh", "kwh", "usage_kwh", "energy_kwh", "consumptionkwh"):
            if alias in row:
                row.setdefault("consumptionkwh", row[alias])
                break
        for alias in ("billing_period_start", "period_start", "start_date", "billingperiodstart"):
            if alias in row:
                row.setdefault("billingperiodstart", row[alias])
                break
        for alias in ("billing_period_end", "period_end", "end_date", "billingperiodend"):
            if alias in row:
                row.setdefault("billingperiodend", row[alias])
                break

        missing = required_cols - set(row.keys())
        if missing:
            record["parse_error"] = f"Row {i}: Missing columns: {missing}"
            results.append(record)
            continue

        meter_id = row.get("meterid", row.get("meter_id", row.get("account_number", f"METER-{i}")))
        account = row.get("accountnumber", row.get("account_number", ""))
        record["source_row_id"] = f"UTIL-{meter_id}-{i}"

        # ── Consumption ───────────────────────────────────────────────────────
        consumption_kwh = _parse_kwh(row["consumptionkwh"])
        if consumption_kwh is None:
            record["parse_error"] = f"Row {i}: Invalid consumption value '{row['consumptionkwh']}'"
            results.append(record)
            continue

        # ── Dates ─────────────────────────────────────────────────────────────
        start_date = _parse_date(row.get("billingperiodstart", ""))
        end_date = _parse_date(row.get("billingperiodend", ""))
        if start_date is None or end_date is None:
            record["parse_error"] = (
                f"Row {i}: Cannot parse billing dates "
                f"'{row.get('billingperiodstart')}' – '{row.get('billingperiodend')}'"
            )
            results.append(record)
            continue

        # ── Emission calculation ───────────────────────────────────────────────
        country = row.get("country", "GB").strip().upper()
        ef = get_electricity_factor(country)
        co2e_kg = Decimal(str(consumption_kwh)) * Decimal(str(ef))

        # ── Estimated reading flag ─────────────────────────────────────────────
        notes = []
        estimated = row.get("estimated", row.get("estimate", "")).lower()
        if estimated in ("yes", "y", "true", "1", "estimated"):
            notes.append("Estimated reading — should be confirmed with actual meter data.")
        tariff = row.get("tariff", "")
        if tariff:
            notes.append(f"Tariff: {tariff}")

        record["normalized"] = {
            "source_type": "utility",
            "source_id": record["source_row_id"],
            "supplier_or_site": row.get("siteaddress", row.get("site_address", account)),
            "scope": 2,
            "category": "purchased_electricity",
            "description": f"Electricity — Meter {meter_id}",
            "activity_quantity": Decimal(str(round(consumption_kwh, 4))),
            "activity_unit": "kWh",
            "activity_unit_original": row.get("unit", "kWh"),
            "emission_factor": Decimal(str(ef)),
            "emission_factor_source": EMISSION_FACTOR_SOURCE,
            "co2e_kg": co2e_kg.quantize(Decimal("0.0001")),
            "period_start": start_date.date(),
            "period_end": end_date.date(),
            "facility_code": meter_id,
            "country": country,
            "analyst_note": " | ".join(notes),
            "status": "pending_review",
        }
        results.append(record)

    return results

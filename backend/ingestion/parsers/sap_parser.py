"""
SAP MM Flat-File CSV Parser
===========================
Handles exports from SAP transaction ME80FN / SE16 table joins (EKKO+EKPO+EKBE).

Expected columns (case-insensitive, extra columns ignored):
  PO_Number, Item, DocumentDate, Plant, MaterialNumber, Description,
  Quantity, UOM, NetPrice, Currency, GoodsReceiptDate (optional)

Known real-world quirks handled:
  - German date formats: TT.MM.JJJJ (DD.MM.YYYY)
  - UOM values: L, Ltr, Litre, GAL, Gallon, MT, M3, Nm3, KG, STD
  - German UOM: Ltr, KG (same), M3 (cubic metres)
  - Missing GoodsReceiptDate: falls back to DocumentDate + 7 days
  - Fuel type identified by free-text Description field

What we handle: MM Purchase Orders for fuel materials only.
What we ignore: GR/IR reconciliation, plant cost hierarchy, service POs,
                indirect materials (MRO), currency conversion.
"""

import csv
import io
import math
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

from ingestion.emission_factors import get_fuel_factor, EMISSION_FACTOR_SOURCE

# ── Unit conversion to litres ─────────────────────────────────────────────────
UOM_TO_LITRES = {
    "l": 1.0,
    "ltr": 1.0,
    "litre": 1.0,
    "litres": 1.0,
    "liter": 1.0,
    "liters": 1.0,
    "gal": 3.78541,       # US gallon
    "gallon": 3.78541,
    "gallons": 3.78541,
    "igl": 4.54609,       # Imperial gallon
    "kg": None,           # fuel-type dependent — handled via density
    "mt": None,           # metric tonne
    "ton": None,
}

# M3 → litres (1 m³ = 1000 L) but for natural gas m³ we convert to kWh first
M3_GAS_KWH_PER_M3 = 10.55    # UK avg calorific value, DEFRA 2024
NM3_GAS_KWH_PER_NM3 = 10.35  # Normal cubic metre

# Fuel densities (kg/L) for converting mass UOMs
FUEL_DENSITY_KG_L = {
    "diesel": 0.835,
    "gas oil": 0.835,
    "petrol": 0.745,
    "gasoline": 0.745,
    "kerosene": 0.800,
    "lpg": 0.510,
    "propane": 0.510,
    "fuel oil": 0.950,
    "heavy fuel oil": 0.950,
}

DATE_FORMATS = [
    "%d.%m.%Y",    # SAP default: 30.05.2024
    "%d/%m/%Y",    # Alternative: 30/05/2024
    "%Y-%m-%d",    # ISO
    "%m/%d/%Y",    # US format
    "%d-%m-%Y",    # Dash-separated
    "%d.%m.%y",    # Two-digit year
]


def _parse_date(raw: str) -> Optional[datetime]:
    raw = raw.strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def _normalise_uom(uom: str) -> str:
    return uom.strip().lower().replace(".", "")


def _convert_to_litres(quantity: float, uom: str, fuel_name: str) -> Optional[float]:
    """Convert any fuel quantity to litres. Returns None if conversion impossible."""
    u = _normalise_uom(uom)

    # Direct litre mappings
    if u in UOM_TO_LITRES and UOM_TO_LITRES[u] is not None:
        return quantity * UOM_TO_LITRES[u]

    # Mass to litres via density
    if u in ("kg", "kilogram", "kilograms"):
        density = FUEL_DENSITY_KG_L.get(fuel_name, 0.835)  # default diesel
        return quantity / density

    if u in ("mt", "ton", "tonne", "tonnes", "t"):
        density = FUEL_DENSITY_KG_L.get(fuel_name, 0.835)
        return (quantity * 1000) / density

    # M3 / Nm3 for gas → kWh handled in caller
    return None


def _convert_gas_m3_to_kwh(quantity: float, uom: str) -> float:
    u = _normalise_uom(uom)
    if u in ("nm3", "nbm", "ncm"):
        return quantity * NM3_GAS_KWH_PER_NM3
    return quantity * M3_GAS_KWH_PER_M3  # standard m3


def normalise_columns(row: dict) -> dict:
    """Make column names lowercase + strip spaces for consistent access."""
    return {k.strip().lower().replace(" ", "_"): v.strip() for k, v in row.items()}


def parse_sap_csv(file_content: str, batch_id, organization_id) -> list[dict]:
    """
    Parse SAP MM flat-file CSV.

    Returns list of dicts, each with keys matching NormalizedRecord fields
    plus 'parse_error' (empty string if OK).
    """
    results = []
    reader = csv.DictReader(io.StringIO(file_content))

    required_cols = {"po_number", "quantity", "uom", "description", "documentdate"}

    for i, raw_row in enumerate(reader, start=2):  # row 2 = first data row (row 1 = header)
        row = normalise_columns(raw_row)
        record = {
            "source_row_id": "",
            "raw_payload": raw_row,
            "parse_error": "",
            "normalized": None,
        }

        # ── Column presence check ─────────────────────────────────────────────
        missing = required_cols - set(row.keys())
        if missing:
            record["parse_error"] = f"Row {i}: Missing columns: {missing}"
            results.append(record)
            continue

        po_num = row.get("po_number", "")
        item = row.get("item", row.get("item_number", "0"))
        record["source_row_id"] = f"PO-{po_num}-{item}"

        # ── Parse description → fuel type ─────────────────────────────────────
        description = row.get("description", "")
        fuel_info = get_fuel_factor(description)
        fuel_name = fuel_info["name"]

        # ── Quantity ──────────────────────────────────────────────────────────
        try:
            qty_str = row["quantity"].replace(",", ".")
            quantity = float(qty_str)
        except (ValueError, KeyError):
            record["parse_error"] = f"Row {i}: Invalid quantity '{row.get('quantity')}'"
            results.append(record)
            continue

        uom = row.get("uom", row.get("unit_of_measure", "L"))

        # ── Convert quantity to factor-compatible unit ─────────────────────────
        factor = fuel_info["factor"]
        factor_unit = fuel_info["unit"]
        unit_original = uom

        if fuel_name in ("natural gas", "gas", "erdgas") or "gas" in description.lower():
            # Gas: convert m³/Nm³ → kWh, then apply kgCO2e/kWh factor
            u = _normalise_uom(uom)
            if u in ("m3", "m³", "cbm", "nm3"):
                activity_qty = _convert_gas_m3_to_kwh(quantity, uom)
                activity_unit = "kWh"
            elif u in ("kwh", "mwh"):
                activity_qty = quantity * (1000 if u == "mwh" else 1)
                activity_unit = "kWh"
            else:
                activity_qty = quantity
                activity_unit = uom
        else:
            # Liquid fuel: convert to litres
            litres = _convert_to_litres(quantity, uom, fuel_name)
            if litres is None:
                record["parse_error"] = (
                    f"Row {i}: Cannot convert UOM '{uom}' to litres for fuel '{fuel_name}'"
                )
                results.append(record)
                continue
            activity_qty = litres
            activity_unit = "L"

        co2e_kg = Decimal(str(activity_qty)) * Decimal(str(factor))

        # ── Dates ─────────────────────────────────────────────────────────────
        doc_date_raw = row.get("documentdate", row.get("document_date", ""))
        doc_date = _parse_date(doc_date_raw)
        if doc_date is None:
            record["parse_error"] = f"Row {i}: Cannot parse date '{doc_date_raw}'"
            results.append(record)
            continue

        gr_date_raw = row.get("goodsreceiptdate", row.get("goods_receipt_date", ""))
        gr_date = _parse_date(gr_date_raw) if gr_date_raw else None
        period_end = gr_date or (doc_date + timedelta(days=7))

        record["normalized"] = {
            "source_type": "sap",
            "source_id": record["source_row_id"],
            "supplier_or_site": row.get("vendor_number", row.get("vendornumber", "")),
            "scope": fuel_info["scope"],
            "category": fuel_info["category"],
            "description": f"{description} ({fuel_name})",
            "activity_quantity": Decimal(str(round(activity_qty, 4))),
            "activity_unit": activity_unit,
            "activity_unit_original": unit_original,
            "emission_factor": Decimal(str(factor)),
            "emission_factor_source": EMISSION_FACTOR_SOURCE,
            "co2e_kg": co2e_kg.quantize(Decimal("0.0001")),
            "period_start": doc_date.date(),
            "period_end": period_end.date(),
            "facility_code": row.get("plant", ""),
            "country": row.get("country", "GB"),
            "status": "pending_review",
        }
        results.append(record)

    return results

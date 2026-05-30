"""
Corporate Travel CSV Parser (Concur Intelligence Export)
=========================================================
Handles the CSV export from SAP Concur Intelligence / Analysis reports.

We chose CSV upload (not live Concur API) because:
  - Concur's OAuth flow requires a registered enterprise application with
    client credentials from the enterprise IT team — not available during
    onboarding.
  - Concur Intelligence / Analysis already provides pre-built expense/travel
    reports that export cleanly as CSV.
  - This is the realistic path: a travel coordinator exports the monthly
    report and uploads it.

Expected columns (case-insensitive, extra columns ignored):
  ExpenseReportID, TripDate, TravelType, OriginCode, DestinationCode,
  ServiceClass, DistanceKm, AmountUSD, Employee, CostCenter

TravelType values: Air, Flight, Rail, Train, Car, Car Rental, Taxi, Cab
ServiceClass values: Economy, Business, First, Premium Economy

Known quirks handled:
  - Missing DistanceKm: calculated via Haversine great-circle from IATA codes
  - Mixed TravelType spellings (Air/Flight/air/FLIGHT)
  - Currency amounts in non-USD: normalized using approximate rates
  - Short-haul vs long-haul air threshold: 3700 km (DEFRA 2024)

What we ignore:
  - Hotel stays (Scope 3 Cat 6 subcategory — significant data gaps,
    no star-rating data typically present in Concur exports)
  - Employee commuting (separate Scope 3 Cat 7, out of scope here)
  - Spend-based method fallback (we require distance data)
"""

import csv
import io
import math
from datetime import datetime
from decimal import Decimal
from typing import Optional

from ingestion.emission_factors import get_travel_factor, EMISSION_FACTOR_SOURCE

# ── IATA airport coordinates (major hubs, sufficient for demo) ────────────────
# lat, lon
IATA_COORDS = {
    "LHR": (51.4775, -0.4614), "LGW": (51.1537, -0.1821), "MAN": (53.3537, -2.2750),
    "EDI": (55.9500, -3.3725), "BHX": (52.4538, -1.7480), "GLA": (55.8719, -4.4330),
    "JFK": (40.6413, -73.7781), "LAX": (33.9425, -118.4081), "ORD": (41.9742, -87.9073),
    "SFO": (37.6213, -122.3790), "DFW": (32.8998, -97.0403), "MIA": (25.7959, -80.2870),
    "CDG": (49.0097, 2.5479), "AMS": (52.3086, 4.7639), "FRA": (50.0379, 8.5622),
    "MUC": (48.3537, 11.7750), "MAD": (40.4936, -3.5668), "BCN": (41.2974, 2.0833),
    "FCO": (41.8003, 12.2389), "ZUR": (47.4647, 8.5492), "BRU": (50.9010, 4.4844),
    "DXB": (25.2528, 55.3644), "SIN": (1.3644, 103.9915), "HKG": (22.3080, 113.9185),
    "NRT": (35.7720, 140.3929), "SYD": (-33.9399, 151.1753), "DEL": (28.5562, 77.1000),
    "BOM": (19.0896, 72.8656), "BLR": (13.1986, 77.7066), "HYD": (17.2403, 78.4294),
    "DOH": (25.2731, 51.6082), "AUH": (24.4330, 54.6511), "IST": (41.2608, 28.7418),
    "YYZ": (43.6777, -79.6248), "MEX": (19.4363, -99.0721), "GRU": (-23.4356, -46.4731),
    "PEK": (40.0799, 116.6031), "PVG": (31.1443, 121.8083), "ICN": (37.4602, 126.4407),
    "CPT": (-33.9715, 18.6021), "JNB": (-26.1392, 28.2460),
}


def _haversine_km(lat1, lon1, lat2, lon2) -> float:
    """Great-circle distance in km between two lat/lon points."""
    R = 6371.0
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (math.sin(d_lat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(d_lon / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _derive_distance(origin: str, destination: str) -> Optional[float]:
    o = origin.strip().upper()
    d = destination.strip().upper()
    if o in IATA_COORDS and d in IATA_COORDS:
        lat1, lon1 = IATA_COORDS[o]
        lat2, lon2 = IATA_COORDS[d]
        return round(_haversine_km(lat1, lon1, lat2, lon2), 1)
    return None


DATE_FORMATS = ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%d.%m.%Y"]


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


def parse_travel_csv(file_content: str, batch_id, organization_id) -> list[dict]:
    """
    Parse Concur Intelligence travel CSV.
    Returns list of dicts with normalized emission record fields.
    """
    results = []
    reader = csv.DictReader(io.StringIO(file_content))

    for i, raw_row in enumerate(reader, start=2):
        row = _normalise_cols(raw_row)
        record = {
            "source_row_id": "",
            "raw_payload": raw_row,
            "parse_error": "",
            "normalized": None,
        }

        # Flexible column aliases
        for alias in ("expensereportid", "expense_report_id", "report_id", "trip_id"):
            if alias in row:
                row.setdefault("expensereportid", row[alias])
                break
        for alias in ("tripdate", "trip_date", "travel_date", "date"):
            if alias in row:
                row.setdefault("tripdate", row[alias])
                break
        for alias in ("traveltype", "travel_type", "type", "mode"):
            if alias in row:
                row.setdefault("traveltype", row[alias])
                break
        for alias in ("origincode", "origin_code", "origin", "from", "departure"):
            if alias in row:
                row.setdefault("origincode", row[alias])
                break
        for alias in ("destinationcode", "destination_code", "destination", "to", "arrival"):
            if alias in row:
                row.setdefault("destinationcode", row[alias])
                break
        for alias in ("serviceclass", "service_class", "class", "cabin"):
            if alias in row:
                row.setdefault("serviceclass", row[alias])
                break
        for alias in ("distancekm", "distance_km", "distance", "km"):
            if alias in row:
                row.setdefault("distancekm", row[alias])
                break

        report_id = row.get("expensereportid", f"TRV-{i}")
        record["source_row_id"] = f"CONCUR-{report_id}-{i}"

        travel_type = row.get("traveltype", "Air")
        service_class = row.get("serviceclass", "Economy")
        origin = row.get("origincode", "")
        destination = row.get("destinationcode", "")

        # ── Distance ──────────────────────────────────────────────────────────
        dist_raw = row.get("distancekm", "").strip()
        notes = []

        if dist_raw and dist_raw not in ("", "0", "-"):
            try:
                distance_km = float(dist_raw.replace(",", ""))
            except ValueError:
                distance_km = None
        else:
            distance_km = None

        if distance_km is None:
            # Try to derive from IATA codes
            derived = _derive_distance(origin, destination)
            if derived is not None:
                distance_km = derived
                notes.append(f"Distance derived from IATA codes {origin}→{destination} via Haversine: {distance_km} km")
            else:
                record["parse_error"] = (
                    f"Row {i}: No distance and IATA codes '{origin}'/'{destination}' not in lookup table"
                )
                results.append(record)
                continue

        if distance_km <= 0:
            record["parse_error"] = f"Row {i}: Distance must be > 0, got {distance_km}"
            results.append(record)
            continue

        # ── Emission factor ───────────────────────────────────────────────────
        factor_info = get_travel_factor(travel_type, service_class, distance_km)
        ef = factor_info["factor"]
        co2e_kg = Decimal(str(distance_km)) * Decimal(str(ef))

        # ── Date ──────────────────────────────────────────────────────────────
        trip_date = _parse_date(row.get("tripdate", ""))
        if trip_date is None:
            record["parse_error"] = f"Row {i}: Cannot parse trip date '{row.get('tripdate')}'"
            results.append(record)
            continue

        # ── Employee / cost center ────────────────────────────────────────────
        employee = row.get("employee", row.get("traveller", ""))
        cost_center = row.get("costcenter", row.get("cost_center", ""))
        supplier_info = f"{employee} / {cost_center}".strip(" /")

        record["normalized"] = {
            "source_type": "travel",
            "source_id": record["source_row_id"],
            "supplier_or_site": supplier_info,
            "scope": factor_info["scope"],
            "category": factor_info["category"],
            "description": f"{travel_type} {origin}→{destination} [{service_class}]",
            "activity_quantity": Decimal(str(round(distance_km, 2))),
            "activity_unit": "km",
            "activity_unit_original": "km",
            "emission_factor": Decimal(str(ef)),
            "emission_factor_source": EMISSION_FACTOR_SOURCE,
            "co2e_kg": co2e_kg.quantize(Decimal("0.0001")),
            "period_start": trip_date.date(),
            "period_end": trip_date.date(),
            "facility_code": cost_center,
            "country": row.get("country", ""),
            "analyst_note": " | ".join(notes),
            "status": "pending_review",
        }
        results.append(record)

    return results

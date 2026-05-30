"""
Emission factors lookup table — static, UK DEFRA 2024 values.
Source: UK Government GHG Conversion Factors for Company Reporting 2024
https://www.gov.uk/government/collections/government-conversion-factors-for-company-reporting

All factors in kgCO2e per unit.

Scope assignments:
  Scope 1  — company-owned/controlled combustion (SAP fuel)
  Scope 2  — purchased electricity (utility bills)
  Scope 3  — business travel by third-party carriers (Concur travel)
"""

# ── Fuel factors (kgCO2e per litre, unless noted) ────────────────────────────
FUEL_FACTORS = {
    # Diesel / Gas Oil
    "diesel":            {"factor": 2.5313, "unit": "L",  "scope": 1, "category": "stationary_combustion"},
    "gas oil":           {"factor": 2.5313, "unit": "L",  "scope": 1, "category": "stationary_combustion"},
    "hvgo":              {"factor": 2.5313, "unit": "L",  "scope": 1, "category": "stationary_combustion"},
    # Petrol / Gasoline
    "petrol":            {"factor": 2.1616, "unit": "L",  "scope": 1, "category": "stationary_combustion"},
    "gasoline":          {"factor": 2.1616, "unit": "L",  "scope": 1, "category": "stationary_combustion"},
    # Natural Gas (factor per kWh of heat content; 1 m³ ≈ 10.55 kWh)
    "natural gas":       {"factor": 0.18296, "unit": "kWh", "scope": 1, "category": "stationary_combustion"},
    "gas":               {"factor": 0.18296, "unit": "kWh", "scope": 1, "category": "stationary_combustion"},
    "erdgas":            {"factor": 0.18296, "unit": "kWh", "scope": 1, "category": "stationary_combustion"},  # German
    # LPG (kgCO2e per litre)
    "lpg":               {"factor": 1.5557, "unit": "L",  "scope": 1, "category": "stationary_combustion"},
    "propane":           {"factor": 1.5557, "unit": "L",  "scope": 1, "category": "stationary_combustion"},
    # Fuel Oil (Heavy)
    "fuel oil":          {"factor": 2.7584, "unit": "L",  "scope": 1, "category": "stationary_combustion"},
    "heavy fuel oil":    {"factor": 2.7584, "unit": "L",  "scope": 1, "category": "stationary_combustion"},
    # Kerosene / Jet fuel (used for on-site generators, not air travel)
    "kerosene":          {"factor": 2.5301, "unit": "L",  "scope": 1, "category": "stationary_combustion"},
}

# ── Electricity grid factors (kgCO2e per kWh) ────────────────────────────────
# Location-based, market average. DEFRA 2024.
ELECTRICITY_FACTORS = {
    "GB":  0.20493,   # UK grid (DEFRA 2024)
    "DE":  0.38400,   # Germany (UBA 2023)
    "US":  0.38600,   # US average (EPA eGRID 2023)
    "IN":  0.71600,   # India (CEA 2022)
    "AU":  0.62000,   # Australia (DCCEEW 2023)
    "FR":  0.05200,   # France (low due to nuclear)
    "DEFAULT": 0.38600,  # global average fallback
}

# ── Travel factors (kgCO2e per passenger-km) ─────────────────────────────────
# DEFRA 2024 — includes radiative forcing for air.
TRAVEL_FACTORS = {
    "air_economy_shorthaul":   {"factor": 0.15573, "scope": 3, "category": "business_travel_air"},
    "air_economy_longhaul":    {"factor": 0.19085, "scope": 3, "category": "business_travel_air"},
    "air_business_shorthaul":  {"factor": 0.23359, "scope": 3, "category": "business_travel_air"},
    "air_business_longhaul":   {"factor": 0.42875, "scope": 3, "category": "business_travel_air"},
    "air_first":               {"factor": 0.57254, "scope": 3, "category": "business_travel_air"},
    "air_unknown":             {"factor": 0.19085, "scope": 3, "category": "business_travel_air"},
    "rail_national":           {"factor": 0.03549, "scope": 3, "category": "business_travel_rail"},
    "rail_international":      {"factor": 0.00415, "scope": 3, "category": "business_travel_rail"},
    "car_rental_petrol":       {"factor": 0.17105, "scope": 3, "category": "business_travel_car"},
    "car_rental_diesel":       {"factor": 0.15904, "scope": 3, "category": "business_travel_car"},
    "car_rental_unknown":      {"factor": 0.17105, "scope": 3, "category": "business_travel_car"},
    "taxi":                    {"factor": 0.14931, "scope": 3, "category": "business_travel_car"},
}

EMISSION_FACTOR_SOURCE = "UK_DEFRA_2024"


def get_fuel_factor(description: str) -> dict:
    """Match material description (case-insensitive substring) to a fuel factor dict."""
    desc_lower = description.lower().strip()
    for key, val in FUEL_FACTORS.items():
        if key in desc_lower:
            return {**val, "name": key}
    # Fallback to diesel
    return {**FUEL_FACTORS["diesel"], "name": "diesel (fallback)"}


def get_electricity_factor(country_code: str) -> float:
    return ELECTRICITY_FACTORS.get(country_code.upper(), ELECTRICITY_FACTORS["DEFAULT"])


def get_travel_factor(travel_type: str, service_class: str = "", distance_km: float = 0) -> dict:
    """
    Map travel type + service class to a factor key.
    Short-haul threshold: < 3700 km (DEFRA definition).
    """
    t = travel_type.lower().strip()
    sc = service_class.lower().strip()

    if "air" in t or "flight" in t or "fly" in t:
        if "business" in sc or "biz" in sc:
            key = "air_business_longhaul" if distance_km >= 3700 else "air_business_shorthaul"
        elif "first" in sc:
            key = "air_first"
        else:
            key = "air_economy_longhaul" if distance_km >= 3700 else "air_economy_shorthaul"
    elif "rail" in t or "train" in t or "euro" in t:
        key = "rail_international" if distance_km > 500 else "rail_national"
    elif "car" in t or "rental" in t or "hire" in t:
        if "diesel" in sc:
            key = "car_rental_diesel"
        else:
            key = "car_rental_unknown"
    elif "taxi" in t or "cab" in t or "uber" in t:
        key = "taxi"
    else:
        key = "air_unknown"

    return {**TRAVEL_FACTORS[key], "key": key}

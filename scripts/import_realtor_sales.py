"""Convert Realtor Api Data sold-property responses into engine sales batches.

Safe default: write a review JSON file. Add --push only after checking output.
Secrets are loaded from .env and never printed.
"""
import argparse
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx


SALE_BATCH_LIMIT = 500
DEFAULT_HOST = "realtor-api-data.p.rapidapi.com"
DEFAULT_ENDPOINT = "/properties/sold"
WATER_STREET_HINTS = (
    " BAY ",
    "BAY DR",
    "BROADVIEW",
    "KEYSTONE",
    "HIBISCUS",
    "PALM",
    "STAR ISLAND",
    "SUNSET ISLAND",
    "DI LIDO",
    "RIVO ALTO",
    "SAN MARINO",
    "LA GORCE",
    "ALLISON",
    "N SHORE DR",
    "ATLANTIC WAY",
    "STILLWATER",
    "NOREMAC",
    "S SHORE DR",
    "SUNSET DR",
)


def load_dotenv(path=".env") -> None:
    env_path = Path(path)
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def clean_text(value: Any) -> str:
    if value in (None, [], {}):
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def clean_int(value: Any) -> int | None:
    if value in (None, "", [], {}):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    text = clean_text(value)
    return int(re.sub(r"[^\d]", "", text)) if re.search(r"\d", text) else None


def clean_float(value: Any) -> float | None:
    if value in (None, "", [], {}):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        text = re.sub(r"[^0-9.]", "", str(value))
        return float(text) if text else None


def date_iso(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ", "%m/%d/%Y"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            pass
    return None


def address_slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:80] or "unknown-address"


def infer_micro_market(address: dict[str, Any]) -> str:
    city = clean_text(address.get("city")).upper()
    zip_code = clean_text(address.get("postal_code"))
    line = clean_text(address.get("line")).upper()
    text = f"{line} {city} {zip_code}"
    if city == "BAY HARBOR ISLANDS":
        return "bay_harbor_islands"
    if city in {"BAL HARBOUR", "BAL HARBOR"}:
        return "bal_harbour"
    if city == "SURFSIDE":
        return "surfside"
    if city == "NORTH MIAMI" or zip_code == "33181" or "KEYSTONE" in text:
        return "keystone"
    if city == "NORTH MIAMI BEACH":
        return "north_miami_beach"
    if city == "MIAMI BEACH":
        return "miami_beach"
    return city.lower().replace(" ", "_") or "unknown"


def infer_water_type(address: dict[str, Any]) -> str:
    text = f" {clean_text(address.get('line')).upper()} {clean_text(address.get('city')).upper()} "
    if any(hint in text for hint in WATER_STREET_HINTS):
        return "Verify"
    return "None"


def condition_class(prop: dict[str, Any]) -> str:
    flags = prop.get("flags") or {}
    if flags.get("is_new_construction") is True:
        return "new"
    return "unknown"


def property_records(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict) and isinstance(payload.get("properties"), list):
        return payload["properties"]
    if isinstance(payload, dict) and isinstance(payload.get("data"), dict):
        return property_records(payload["data"])
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    return []


def normalize_property(prop: dict[str, Any], args: argparse.Namespace) -> tuple[dict[str, Any] | None, str]:
    status = clean_text(prop.get("status")).lower()
    desc = prop.get("description") or {}
    prop_type = clean_text(desc.get("type")).lower()
    if args.sold_only and status != "sold":
        return None, f"not sold: {status or 'unknown'}"
    if args.sfr_only and prop_type != "single_family":
        return None, f"not single_family: {prop_type or 'unknown'}"

    sold_date = date_iso(desc.get("sold_date"))
    price = clean_int(desc.get("sold_price"))
    living_sf = clean_int(desc.get("sqft"))
    if not sold_date or not price:
        return None, "missing sold date or sold price"
    if price < args.min_price:
        return None, f"below min price: {price}"
    if not living_sf:
        return None, "missing living sqft"

    location = prop.get("location") or {}
    address = location.get("address") or {}
    line = clean_text(address.get("line"))
    city = clean_text(address.get("city"))
    state_code = clean_text(address.get("state_code")) or "FL"
    zip_code = clean_text(address.get("postal_code"))
    full_address = ", ".join(x for x in (line, city, state_code, zip_code) if x)
    if not full_address:
        return None, "missing address"

    sale_id_base = clean_text(prop.get("property_id") or prop.get("listing_id")) or address_slug(full_address)
    sale_id = f"realtor:{sale_id_base}:{sold_date.replace('-', '')}:{price}"
    water_type = args.water_type or infer_water_type(address)

    return {
        "saleId": sale_id,
        "address": line,
        "zip": zip_code,
        "price": price,
        "soldDate": sold_date,
        "livingSF": living_sf,
        "lotSF": clean_int(desc.get("lot_sqft")),
        "beds": clean_int(desc.get("beds")),
        "baths": clean_float(desc.get("baths_consolidated")),
        "propertyClass": "sfr",
        "waterType": water_type,
        "waterfront": water_type != "None",
        "conditionClass": args.condition_class or condition_class(prop),
        "market": args.micro_market or infer_micro_market(address),
        "verified": False,
        "source": args.source,
    }, ""


def fetch_sold(args: argparse.Namespace) -> Any:
    load_dotenv()
    host = os.environ.get("SALES_RAPIDAPI_HOST", DEFAULT_HOST)
    key = os.environ.get("SALES_RAPIDAPI_KEY")
    if not key:
        raise SystemExit("Missing SALES_RAPIDAPI_KEY. Run scripts/set_sales_rapidapi_secret.ps1 first.")
    params = {
        "query": args.query,
        "limit": str(args.limit),
        "offset": str(args.offset),
        "lot_size_min": str(args.lot_size_min),
        "lot_size_max": str(args.lot_size_max),
        "home_size_min": str(args.home_size_min),
        "home_size_max": str(args.home_size_max),
        "home_age_min": str(args.home_age_min),
        "home_age_max": str(args.home_age_max),
        "price_min": str(args.min_price),
        "price_max": str(args.price_max),
        "property_type": "single_family",
        "expand_area": str(args.expand_area),
    }
    headers = {
        "Content-Type": "application/json",
        "x-rapidapi-host": host,
        "x-rapidapi-key": key,
    }
    with httpx.Client(timeout=45) as client:
        response = client.get(f"https://{host}{args.endpoint}", headers=headers, params=params)
    if response.status_code >= 400:
        print(response.text.replace(key, "[REDACTED]")[:1000])
        response.raise_for_status()
    return response.json()


def write_json(path: str | Path, payload: Any) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def push_batches(rows: list[dict[str, Any]]) -> list[Any]:
    from engine_client import engine_request

    results = []
    for idx in range(0, len(rows), SALE_BATCH_LIMIT):
        batch = rows[idx:idx + SALE_BATCH_LIMIT]
        print(f"Pushing batch {idx // SALE_BATCH_LIMIT + 1}: {len(batch)} rows", flush=True)
        results.append(engine_request("/api/import-sales", {"sales": batch}))
    return results


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", help="Saved Realtor API JSON response to normalize.")
    parser.add_argument("--query", default="Miami Beach, FL")
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--lot-size-min", type=int, default=1000)
    parser.add_argument("--lot-size-max", type=int, default=9999999)
    parser.add_argument("--home-size-min", type=int, default=500)
    parser.add_argument("--home-size-max", type=int, default=999999)
    parser.add_argument("--home-age-min", type=int, default=1920)
    parser.add_argument("--home-age-max", type=int, default=2026)
    parser.add_argument("--min-price", type=int, default=100000)
    parser.add_argument("--price-max", type=int, default=99999999999)
    parser.add_argument("--expand-area", type=int, default=1)
    parser.add_argument("--out", default="realtor_sales_import.json")
    parser.add_argument("--skipped-out", default="realtor_sales_import.skipped.json")
    parser.add_argument("--push", action="store_true")
    parser.add_argument("--sold-only", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--sfr-only", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--source", default="realtor_api_data_sold")
    parser.add_argument("--water-type", choices=("Canal", "Open Bay", "Canal/Bay", "None", "Verify"))
    parser.add_argument("--condition-class", choices=("new", "renovated", "original", "teardown", "unknown"))
    parser.add_argument("--micro-market")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    payload = json.loads(Path(args.json).read_text(encoding="utf-8")) if args.json else fetch_sold(args)
    rows = []
    skipped = []
    for idx, prop in enumerate(property_records(payload), start=1):
        row, reason = normalize_property(prop, args)
        if row:
            rows.append(row)
        else:
            skipped.append({"index": idx, "reason": reason})

    rows = list({row["saleId"]: row for row in rows}.values())
    write_json(args.out, rows)
    write_json(args.skipped_out, skipped)
    print(f"Normalized {len(rows)} sales; skipped {len(skipped)}.")
    print(f"Wrote {args.out}")
    print(f"Wrote {args.skipped_out}")

    if args.push:
        print(json.dumps(push_batches(rows), indent=2))


if __name__ == "__main__":
    main()

"""Smoke-test Realtor sales-data RapidAPI access without printing secrets.

The script loads SALES_RAPIDAPI_HOST and SALES_RAPIDAPI_KEY from .env, calls a
Realtor API endpoint, prints only safe response structure/counts, and saves the
full JSON response under work/ for local inspection. work/ is ignored by Git.
"""
import argparse
import json
import os
from collections import Counter
from pathlib import Path
from typing import Any

import httpx


DEFAULT_HOST = "realtor-api-data.p.rapidapi.com"


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


def collect_records(node: Any) -> list[dict[str, Any]]:
    """Find likely listing-like dicts in an unknown response shape."""
    found: list[dict[str, Any]] = []
    if isinstance(node, dict):
        keys = {str(k).lower() for k in node.keys()}
        if (
            "property_id" in keys
            or "listing_id" in keys
            or {"list_price", "price", "sold_price"} & keys
        ):
            found.append(node)
        for value in node.values():
            found.extend(collect_records(value))
    elif isinstance(node, list):
        for item in node:
            found.extend(collect_records(item))
    return found


def find_status(record: dict[str, Any]) -> str:
    for key in ("status", "prop_status", "listing_status", "type"):
        value = record.get(key)
        if value:
            return str(value)
    return "unknown"


def summarize(data: Any) -> dict[str, Any]:
    records = collect_records(data)
    statuses = Counter(find_status(r) for r in records)
    sample_keys = sorted(records[0].keys())[:40] if records else []
    top_level_keys = sorted(data.keys()) if isinstance(data, dict) else []
    return {
        "top_level_type": type(data).__name__,
        "top_level_keys": top_level_keys[:40],
        "listing_like_records_found": len(records),
        "status_counts": dict(statuses.most_common()),
        "first_record_keys": sample_keys,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--endpoint", required=True, help="Endpoint path from RapidAPI, e.g. /sold")
    parser.add_argument("--method", choices=["GET", "POST"], default="GET")
    parser.add_argument("--postal-code", default="33181")
    parser.add_argument("--status", default="sold")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--out", default="work/realtor_sales_api_test_response.json")
    args = parser.parse_args()

    load_dotenv()
    host = os.environ.get("SALES_RAPIDAPI_HOST", DEFAULT_HOST)
    key = os.environ.get("SALES_RAPIDAPI_KEY")
    if not key:
        raise SystemExit("Missing SALES_RAPIDAPI_KEY. Run scripts/set_sales_rapidapi_secret.ps1 first.")

    url = f"https://{host}{args.endpoint}"
    headers = {
        "Content-Type": "application/json",
        "x-rapidapi-host": host,
        "x-rapidapi-key": key,
    }
    params = {
        "postal_code": args.postal_code,
        "status": args.status,
        "limit": str(args.limit),
    }
    payload = {
        "limit": args.limit,
        "offset": 0,
        "postal_code": args.postal_code,
        "status": [args.status],
        "sort": {"direction": "desc", "field": "sold_date" if args.status == "sold" else "list_date"},
    }

    with httpx.Client(timeout=30) as client:
        if args.method == "POST":
            response = client.post(url, headers=headers, json=payload)
        else:
            response = client.get(url, headers=headers, params=params)

    content_type = response.headers.get("content-type", "")
    print(f"HTTP {response.status_code}")
    print(f"Content-Type: {content_type}")

    if response.status_code >= 400:
        print("Request failed. Body preview follows with secrets redacted if present:")
        print(response.text.replace(key, "[REDACTED]")[:1000])
        response.raise_for_status()

    data = response.json()
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    print(json.dumps(summarize(data), indent=2))
    print(f"Saved full response locally to {out_path}")


if __name__ == "__main__":
    main()

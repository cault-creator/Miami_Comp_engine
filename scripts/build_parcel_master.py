"""Build a checkpointed Miami-Dade parcel master JSONL from PA records.

Feed this output into import_pa_sales.py:

    python scripts/import_pa_sales.py --pa-json parcel_master.jsonl --out pa_sales_import.json
"""
import argparse
import asyncio
import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from browser_util import get_browser
from county_pa import fetch_county_with_browser


DEFAULT_PROFILE = "mdc-pa"


def clean_text(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def normalize_address(value):
    text = clean_text(value).upper()
    text = re.sub(r"\b(MIAMI BEACH|MIAMI|NORTH MIAMI|BAL HARBOUR|BAY HARBOR ISLANDS),?\s+FL\b", "", text)
    text = re.sub(r"\bFL\b", "", text)
    text = re.sub(r"\b33\d{3}(?:-\d{4})?\b", "", text)
    text = re.sub(r"[,;]+", " ", text)
    return clean_text(text)


def read_json_or_jsonl(path):
    text = Path(path).read_text()
    stripped = text.lstrip()
    if not stripped:
        return []
    if stripped[0] in "[{":
        data = json.loads(text)
        return data if isinstance(data, list) else [data]
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def read_addresses_file(path, field):
    source = Path(path)
    if source.suffix.lower() == ".csv":
        with source.open(newline="") as fh:
            reader = csv.DictReader(fh)
            rows = []
            for row in reader:
                value = row.get(field) or row.get(field.lower()) or row.get(field.upper())
                if value:
                    rows.append(value)
            return rows
    return source.read_text().splitlines()


def addresses_from_auction_json(path):
    rows = read_json_or_jsonl(path)
    out = []
    for row in rows:
        address = row.get("address") or row.get("Property Address")
        if address:
            out.append(address)
    return out


def dedupe_preserve_order(values):
    seen = set()
    out = []
    for value in values:
        normalized = normalize_address(value)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        out.append(normalized)
    return out


def load_done_keys(path):
    output = Path(path)
    done = set()
    if not output.exists():
        return done
    for line in output.read_text().splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        key = row.get("_query_address") or row.get("address")
        if key:
            done.add(normalize_address(key))
    return done


def append_jsonl(path, row):
    with Path(path).open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, sort_keys=True) + "\n")


async def open_browser(profile, headless):
    return await get_browser(profile, timeout_seconds=300, headless=headless)


async def fetch_many(addresses, args):
    done = load_done_keys(args.out) if args.resume else set()
    todo = [address for address in addresses if normalize_address(address) not in done]
    if args.limit:
        todo = todo[:args.limit]

    print(f"Input addresses: {len(addresses)}")
    print(f"Already done: {len(done)}")
    print(f"To fetch: {len(todo)}")

    browser = await open_browser(args.profile, args.headless)
    fetched_since_restart = 0
    try:
        for idx, address in enumerate(todo, start=1):
            try:
                print(f"[{idx}/{len(todo)}] {address}", flush=True)
                parcel = await fetch_county_with_browser(browser, address)
                parcel["_query_address"] = address
                parcel["_fetched_at"] = datetime.now(timezone.utc).isoformat()
                parcel["_source"] = "miami_dade_property_appraiser"
                append_jsonl(args.out, parcel)
                fetched_since_restart += 1
            except Exception as exc:
                error_row = {
                    "_query_address": address,
                    "_fetched_at": datetime.now(timezone.utc).isoformat(),
                    "_source": "miami_dade_property_appraiser",
                    "error": repr(exc)[:500],
                }
                append_jsonl(args.out, error_row)
                print(f"ERROR {address}: {error_row['error']}", flush=True)

            if args.delay:
                await asyncio.sleep(args.delay)

            if args.restart_every and fetched_since_restart >= args.restart_every:
                await browser.close()
                await asyncio.sleep(args.restart_delay)
                browser = await open_browser(args.profile, args.headless)
                fetched_since_restart = 0
    finally:
        await browser.close()


def build_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument("--address", action="append", help="Address to fetch. Repeatable.")
    parser.add_argument("--addresses-file", help="Text or CSV file of addresses.")
    parser.add_argument("--address-field", default="address", help="CSV address column name.")
    parser.add_argument("--auction-json", help="Auction scraper JSON/JSONL output with address fields.")
    parser.add_argument("--out", default="parcel_master.jsonl", help="Checkpointed parcel master output.")
    parser.add_argument("--resume", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--limit", type=int, help="Fetch only the first N pending addresses.")
    parser.add_argument("--delay", type=float, default=1.5, help="Seconds between searches.")
    parser.add_argument("--restart-every", type=int, default=75, help="Restart browser after N successful fetches.")
    parser.add_argument("--restart-delay", type=float, default=5.0)
    parser.add_argument("--profile", default=DEFAULT_PROFILE)
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="Print deduped inputs without fetching PA.")
    parser.add_argument("--preview", type=int, default=25, help="Number of dry-run addresses to print.")
    return parser


async def async_main(args):
    addresses = []
    if args.address:
        addresses.extend(args.address)
    if args.addresses_file:
        addresses.extend(read_addresses_file(args.addresses_file, args.address_field))
    if args.auction_json:
        addresses.extend(addresses_from_auction_json(args.auction_json))

    addresses = dedupe_preserve_order(addresses)
    if not addresses:
        raise SystemExit("No addresses supplied. Use --address, --addresses-file, or --auction-json.")

    if args.dry_run:
        print(f"Input addresses after dedupe: {len(addresses)}")
        for address in addresses[:args.preview]:
            print(address)
        if len(addresses) > args.preview:
            print(f"... {len(addresses) - args.preview} more")
        return

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    await fetch_many(addresses, args)
    print(f"Wrote parcel master: {args.out}")


def main():
    args = build_parser().parse_args()
    asyncio.run(async_main(args))


if __name__ == "__main__":
    main()

"""Small CLI client for the Miami Comp Engine.

Set ENGINE_API_KEY in your shell or a local .env file before calling protected
routes. Do not paste the key into chat or commit it into source control.
"""
import argparse
import json
import os
from pathlib import Path

import httpx


DEFAULT_ENGINE_BASE = "https://judicious-cassowary-306.convex.site"


def load_dotenv(path=".env"):
    env_path = Path(path)
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def engine_request(endpoint, payload=None):
    load_dotenv()
    base = os.environ.get("ENGINE_BASE", DEFAULT_ENGINE_BASE).rstrip("/")
    key = os.environ.get("ENGINE_API_KEY")
    if not key:
        raise SystemExit("Missing ENGINE_API_KEY. Put it in .env or set it in your shell.")

    url = f"{base}{endpoint}"
    headers = {"x-engine-key": key, "content-type": "application/json"}
    with httpx.Client(timeout=60) as client:
        response = client.post(url, headers=headers, json=payload or {})
        response.raise_for_status()
        return response.json()


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    comp = sub.add_parser("comp", help="Run comparable-sales search for an address.")
    comp.add_argument("address")

    value = sub.add_parser("value", help="Run full valuation for an address.")
    value.add_argument("address")

    import_sales = sub.add_parser("import-sales", help="Bulk import sale rows from JSON.")
    import_sales.add_argument("json_file")

    args = parser.parse_args()
    if args.cmd == "comp":
        result = engine_request("/api/comp", {"address": args.address})
    elif args.cmd == "value":
        result = engine_request("/api/value", {"address": args.address})
    else:
        rows = json.loads(Path(args.json_file).read_text())
        result = engine_request("/api/import-sales", {"rows": rows})

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

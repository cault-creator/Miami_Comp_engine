"""Miami-Dade Property Appraiser fetch + parse.

fetch_county(address) -> dict with property facts, or {"error": ...}.
Uses the persistent "mdc-pa" browser profile. Address WITHOUT city (e.g. "590 Lakeview Dr").
"""
import re

from browser_util import get_browser


def _money(s):
    return int(re.sub(r"[^\d]", "", s)) if re.search(r"\d", s or "") else None


def _num(s):
    return int(re.sub(r"[^\d]", "", s)) if re.search(r"\d", s or "") else None


def parse_pa_text(txt):
    p = {"raw_len": len(txt)}
    m = re.search(r"Folio:\s*([\d-]+)", txt)
    p["folio"] = m.group(1) if m else None
    m = re.search(r"Sub-Division:\s*\n([^\n]+)", txt)
    p["subdivision"] = m.group(1).strip() if m else None
    m = re.search(r"Property Address\s*\n([^\n]+)", txt)
    p["address"] = m.group(1).strip() if m else None
    m = re.search(r"\nOwner\s*\n([^\n]+)", txt)
    p["owner"] = m.group(1).strip() if m else None
    m = re.search(r"Mailing Address\s*\n([^\n]+)\n([^\n]+)", txt)
    p["mailing"] = (m.group(1).strip() + " " + m.group(2).strip()) if m else None
    m = re.search(r"Beds / Baths /Half\s*([\d]+)\s*/\s*([\d]+)\s*/\s*([\d]+)", txt)
    if m:
        p["beds"], p["baths"], p["half_baths"] = int(m.group(1)), int(m.group(2)), int(m.group(3))
    for key, label in [("living_sf", "Living Area"), ("adjusted_sf", "Adjusted Area"),
                       ("actual_sf", "Actual Area"), ("lot_sf", "Lot Size")]:
        m = re.search(label + r"\s*\t?([\d,]+)\s*Sq\.Ft", txt)
        p[key] = _num(m.group(1)) if m else None
    m = re.search(r"Year Built\s*\t?([^\n]+)", txt)
    p["year_built_raw"] = m.group(1).strip() if m else None
    m = re.search(r"Year Built\s*\t?(\d{4})", txt)
    p["year_built"] = int(m.group(1)) if m else None
    if not p["year_built"]:
        m = re.search(r"Building Number\s*Sub Area\s*Year Built.*?\n\d+\t\d+\t(\d{4})", txt, re.S)
        p["year_built"] = int(m.group(1)) if m else None
        if p["year_built"]:
            p["year_built_raw"] = "Multiple (first %d)" % p["year_built"]

    # Assessment table: 2026 is first column; parse each row independently
    def _row(label):
        m = re.search(label + r"\s*\n?\$?([\d,]+)\s*\n?\t?\n?\$?([\d,]+)\s*\n?\t?\n?\$?([\d,]+)", txt)
        return (_num(m.group(1)), _num(m.group(2)), _num(m.group(3))) if m else (None, None, None)
    p["land_value_2026"], p["land_value_2025"], p["land_value_2024"] = _row("Land Value")
    p["building_value_2026"], _, _ = _row("Building Value")
    p["market_value_2026"], p["market_value_2025"], p["market_value_2024"] = _row("Market Value")
    p["assessed_2026"], _, _ = _row("Assessed Value")
    # Sales history
    p["sales_history"] = [
        {"date": d, "price": _num(pr), "qual": q.strip()}
        for d, pr, q in re.findall(r"(\d{2}/\d{2}/\d{4})\t\$([\d,]+)\t[\d-]+\t([^\n]+)", txt)
    ]
    # Extra features
    p["extra_features"] = re.findall(
        r"(Dock[^\n\t]*|Pool[^\n\t]*|Fence[^\n\t]*|Patio[^\n\t]*|Wall[^\n\t]*)\t(\d{4})", txt)
    p["has_dock"] = any("dock" in f[0].lower() for f in p["extra_features"])
    p["has_pool"] = any("pool" in f[0].lower() for f in p["extra_features"])
    m = re.search(r"Full Legal Description\s*\n([^\n]+(?:\n[^\n]+){1,4})", txt)
    p["legal"] = m.group(1).replace("\n", " | ") if m else None
    p["riparian"] = bool(p["legal"] and "RIP" in p["legal"].upper())
    m = re.search(r"Benefits Information[^\n]*\n(.*?)\nNote:", txt, re.S)
    p["benefits"] = (m.group(1)[:300] if m else "")
    p["homestead"] = "Homestead" in (p["benefits"] or "") or "Save Our Homes" in (p["benefits"] or "")
    p["soh_capped"] = "Save Our Homes" in (p["benefits"] or "")
    m = re.search(r"Zoning Code:\s*([^\t\n]+)", txt)
    p["zoning"] = m.group(1).strip() if m else None
    return p


async def fetch_county_with_browser(b, address_no_city):
    await b.goto("https://apps.miamidadepa.gov/propertysearch/")
    await b.page.wait_for_timeout(4000)
    inp = b.page.locator("input:visible").first
    await inp.fill(address_no_city)
    await inp.press("Enter")
    await b.page.wait_for_timeout(7000)
    txt = await b.page.inner_text("body")
    if "Back to Search Results" not in txt:
        return {"error": "no single result / property page not reached", "raw": txt[:1500]}
    return parse_pa_text(txt)


async def fetch_county(address_no_city):
    b = await get_browser("mdc-pa", timeout_seconds=300)
    try:
        return await fetch_county_with_browser(b, address_no_city)
    finally:
        await b.close()

import re, json, asyncio, datetime
import httpx

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"}
BASE = "https://www.miamidade.realforeclose.com/index.cfm"

ITEM_SPLIT = re.compile(r'<div id="AITEM_\d+"')

def parse_items(html):
    items = []
    for b in ITEM_SPLIT.split(html)[1:]:
        it = {}
        m = re.search(r'Auction Type:@[A-Z]+@?[^>]*>\s*([A-Z ]+)', b)
        it["type"] = m.group(1).strip() if m else None
        m = re.search(r'Case #:\s*@[A-Z]+@?[^>]*>\s*([0-9A-Za-z-]+)', b)
        it["case"] = m.group(1).strip() if m else None
        m = re.search(r'Final Judgment Amount:@[A-Z]+@?[^>]*>\s*(\$[\d,.]+)', b)
        it["judgment"] = m.group(1) if m else None
        m = re.search(r'folio=(\d{13,})', b)
        it["parcel"] = m.group(1) if m else None
        m = re.search(r'Opening Bid:@[A-Z]+@?[^>]*>\s*(\$[\d,.]+)', b)
        it["opening_bid"] = m.group(1) if m else None
        m = re.search(r'Certificate #:@[A-Z]+@?[^>]*>\s*(\d+)', b)
        it["certificate"] = m.group(1) if m else None
        m = re.search(r'Property Address:@[A-Z]+@?[^>]*>\s*(.*?)@[A-Z]@', b)
        street = m.group(1).strip() if m else None
        city = None
        if m:
            rest = b[m.end():]
            m2 = re.search(r'@[A-Z]+@?[^>]*>\s*([A-Z][A-Z .]+, FL[^@<]*)', rest)
            city = m2.group(1).strip() if m2 else None
        it["address"] = ((street or "") + " " + (city or "")).strip() or None
        m = re.search(r'Assessed Value:@[A-Z]+@?[^>]*>\s*(\$[\d,.]+)', b)
        it["assessed"] = m.group(1) if m else None
        items.append(it)
    return items

async def load(client, area, **params):
    base = {"zaction": "AUCTION", "Zmethod": "UPDATE", "FNC": "LOAD", "AREA": area,
            "PageDir": 0, "doR": 1, "tx": 1, "bypassPage": 1, "test": 1, "_": 1}
    base.update(params)
    r = await client.get(BASE, params=base, timeout=60)
    d = r.json()
    return d.get("rlist", ""), parse_items(d.get("retHTML", ""))

async def scrape_area(client, area):
    out = []
    seen = set()
    rlist, items = await load(client, area)
    seen.add(rlist)
    for it in items:
        it["area"] = area
    out += items
    for n in range(20):
        rlist, items = await load(client, area, PageDir=1, bypassPage=0, _=n + 2)
        if not items or rlist in seen:
            break
        seen.add(rlist)
        for it in items:
            it["area"] = area
        out += items
    return out

async def main():
    start = datetime.date(2026, 8, 31)
    dates = [(start + datetime.timedelta(days=i)) for i in range(45)]
    dates = [d for d in dates if d.weekday() < 5]
    all_items = []
    for d in dates:
        ds = d.strftime("%m/%d/%Y")
        try:
            async with httpx.AsyncClient(headers=UA, follow_redirects=True) as client:
                await client.get(BASE, params={"zaction": "AUCTION", "Zmethod": "PREVIEW", "AUCTIONDATE": ds}, timeout=60)
                day = []
                for area in ("W", "C"):
                    items = await scrape_area(client, area)
                    for it in items:
                        it["date"] = ds
                    day += items
                w = [i for i in day if i["area"] == "W"]
                print(ds, "waiting:", len(w), "closed/cxld:", len(day) - len(w), flush=True)
                all_items += day
        except Exception as e:
            print(ds, "ERR", repr(e)[:100], flush=True)
    json.dump(all_items, open("fc_items_raw.json", "w"), indent=1)
    uniq = {}
    for it in all_items:
        k = (it.get("case"), it.get("parcel"))
        if k not in uniq or it["area"] == "W":
            uniq[k] = it
    json.dump(list(uniq.values()), open("fc_items.json", "w"), indent=1)
    good = [i for i in uniq.values() if i.get("case") and i.get("address")]
    print("raw:", len(all_items), "unique:", len(uniq), "fully parsed:", len(good))

import sys
if __name__ == '__main__' and '--test' not in sys.argv:
    asyncio.run(main())

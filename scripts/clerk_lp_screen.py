"""Batch lis pendens / lien screen for FUB owner names via clerk official records SPA."""
import asyncio, json, re, os

from browser_util import get_browser

HOME = "https://onlineservices.miamidadeclerk.gov/officialrecords/"
DISTRESS_DOCS = ("LIS PENDENS", "FEDERAL TAX LIEN", "NOTICE OF TAX LIEN", "JUDGMENT", "LIEN", "BANKRUPTCY")

def parse_cards(txt):
    recs = []
    blocks = re.split(r"Clerk's File Number:\s*", txt)
    for b in blocks[1:]:
        m = re.match(r"(\d{4}\s*R\s*\d+)", b)
        cfn = m.group(1) if m else None
        party = re.search(r"Party Name\s*\n\s*([^\n]+)", b)
        doc = re.search(r"Document Type\s*\n\s*([^\n]+)", b)
        rd = re.search(r"Rec Date\s*\n\s*([^\n]+)", b)
        legal = re.search(r"Legal Description\s*\n\s*([^\n]+)", b)
        recs.append({
            "cfn": cfn,
            "party": party.group(1).strip() if party else None,
            "doc_type": doc.group(1).strip() if doc else None,
            "rec_date": rd.group(1).strip() if rd else None,
            "legal": legal.group(1).strip() if legal else None,
        })
    return recs

async def search_name(b, first, last):
    await b.goto(HOME)
    await b.page.wait_for_timeout(4000)
    try:
        await b.page.click("text=Name/Document", timeout=10000)
    except Exception:
        pass
    await b.page.wait_for_timeout(2500)
    await b.page.fill('input[name="lastName"]', last, timeout=10000)
    await b.page.fill('input[name="firstName"]', first, timeout=5000)
    try:
        await b.page.fill('input[name="dateRangeFrom"]', "01/01/2023", timeout=4000)
        await b.page.fill('input[name="dateRangeTo"]', "08/28/2026", timeout=4000)
    except Exception:
        pass
    await b.page.click('button[type="submit"]', timeout=8000)
    for _ in range(20):
        await b.page.wait_for_timeout(1500)
        if "SearchResults" in b.page.url:
            break
    await b.page.wait_for_timeout(2500)
    return {"url": b.page.url, "text": await b.page.inner_text("body")}

async def main():
    farm = json.load(open("fub_farm.json"))
    by_name = {}
    for r in farm:
        n = (r.get("name") or "").strip()
        if not n or n.lower() in ("no name", "unknown"):
            continue
        by_name.setdefault(n, []).append(r)
    done = {}
    if os.path.exists("lp_results.json"):
        done = json.load(open("lp_results.json"))
    print("unique farm names:", len(by_name), "already done:", len(done), flush=True)
    b = await get_browser("mdc-clerk", timeout_seconds=3600)
    out = dict(done)
    for idx, (name, leads) in enumerate(by_name.items()):
        if name in out and "hits" in out[name]:
            continue
        parts = name.replace("&", " ").split()
        if len(parts) < 2:
            continue
        first, last = parts[0], parts[-1]
        try:
            res = await search_name(b, first, last)
            recs = parse_cards(res["text"])
            hits = []
            for r in recs:
                if not r.get("doc_type"):
                    continue
                if not any(d in r["doc_type"].upper() for d in DISTRESS_DOCS):
                    continue
                rd = r.get("rec_date") or ""
                if rd and rd[-4:] < "2023":
                    continue
                p = (r.get("party") or "").upper()
                if last.upper() not in p:
                    continue
                hits.append(r)
            out[name] = {"hits": hits, "n_results": len(recs),
                         "leads": [{"id": l["id"], "street": l["street"], "city": l["city"], "stage": l["stage"], "tags": l.get("tags")} for l in leads]}
            flag = f"HITS={len(hits)}" if hits else "clean"
            print(idx, last.upper() + " " + first.upper(), flag, f"({len(recs)} res)", flush=True)
        except Exception as e:
            print(idx, name, "EXC", repr(e)[:140], flush=True)
            out[name] = {"error": repr(e)[:200], "leads": [l["id"] for l in leads]}
        json.dump(out, open("lp_results.json", "w"), indent=1)
    print("DONE", flush=True)

asyncio.run(main())

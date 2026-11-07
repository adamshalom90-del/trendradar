"""Daily product-catalog observations. Catalog presence is not proof of sales or demand."""
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

OUTPUT = Path("data/signals.json")
# Curated Shopify storefront candidates. Some may block the public catalog endpoint.
STORES = [
    {"url":"https://www.petlibro.com","category":"pets","market":"global"},
    {"url":"https://www.grovemade.com","category":"gadgets","market":"global"},
    {"url":"https://www.blendjet.com","category":"home_kitchen","market":"global"},
    {"url":"https://www.ugmonk.com","category":"gadgets","market":"global"},
    {"url":"https://www.bokksu.com","category":"home_kitchen","market":"global"},
]
def fetch_products(base):
    request = urllib.request.Request(base + "/products.json?limit=100&page=1", headers={"User-Agent":"TrendRadarResearch/0.2 (catalog monitoring; contact repository owner)" ,"Accept":"application/json"})
    with urllib.request.urlopen(request, timeout=20) as response:
        if "json" not in response.headers.get("Content-Type","").lower():
            raise ValueError("Store did not return JSON")
        payload = json.load(response)
    if not isinstance(payload,dict) or not isinstance(payload.get("products"),list):
        raise ValueError("Not a Shopify product catalog")
    return payload["products"]

def main():
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    try:
        data = json.loads(OUTPUT.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    data.setdefault("observations", [])
    data.setdefault("runs", [])
    # Do not mix Google Trends news observations with product listings.
    data["observations"] = [x for x in data["observations"] if x.get("source_type")=="shopify_catalog"]
    existing = {(x.get("observed_at","")[:10],x.get("store"),str(x.get("product_id"))): x for x in data["observations"]}
    statuses = {}
    new = 0
    for store in STORES:
        base = store["url"]
        try:
            products = fetch_products(base)
            added = 0
            for product in products:
                title = str(product.get("title") or "").strip()
                handle = str(product.get("handle") or "").strip()
                pid = product.get("id")
                if not title or not handle or not pid or any(w in title.casefold() for w in ("gift card","checkout+","package protection","free gift","100% off","subscription")):
                    continue
                key = (now[:10],base,str(pid))
                if key in existing:
                    old = existing[key]
                    images = product.get("images") or []
                    image_url = (product.get("image") or {}).get("src") or (images[0].get("src") if images else None)
                    if image_url and not old.get("image_url"):
                        old["image_url"] = image_url
                    continue
                variants = product.get("variants") or []
                prices = [v.get("price") for v in variants if v.get("price") is not None]
                available = any(v.get("available") is True for v in variants) if variants else None
                images = product.get("images") or []
                image_url = (product.get("image") or {}).get("src") or (images[0].get("src") if images else None)
                data["observations"].append({"image_url":image_url,"observed_at":now,"source_type":"shopify_catalog","store":base,"market":store["market"],"product_category":store["category"],"product_id":pid,"term":title,"vendor":product.get("vendor"),"price":prices[0] if prices else None,"currency":"unknown (storefront currency; verify)","available":available,"source_url":base+"/products/"+handle,"published_at":product.get("published_at"),"evidence":"Public storefront catalog listing; not verified sales or trend"})
                existing[key] = data["observations"][-1]
                added += 1
            statuses[base]={"ok":True,"catalog_count":len(products),"added":added}
            new += added
        except Exception as exc:
            statuses[base]={"ok":False,"error":str(exc)[:180]}
    data["schema"]=2
    data["source"]="Public Shopify storefront product catalogs"
    data["source_type"]="shopify_catalog"
    data["last_run"]=now
    data["runs"].append({"at":now,"status":statuses,"new_observations":new})
    data["runs"]=data["runs"][-100:]
    data["observations"]=data["observations"][-15000:]
    OUTPUT.parent.mkdir(exist_ok=True)
    OUTPUT.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(statuses))
    if not any(v["ok"] for v in statuses.values()):
        raise RuntimeError("No product catalog was accessible. See run logs; no data invented.")

if __name__=="__main__":
    main()

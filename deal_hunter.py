"""
Quick Commerce Deal Hunter — 3 Tier Alert
==========================================
Location  : Patiala, Punjab (147004)
Platforms : Blinkit, Zepto, BigBasket, Instamart
Tiers     : 50%+ | 40-49% | 30-39%
Alert     : Telegram only
Runs      : Every 30 minutes
"""

import os
import json
import hashlib
import requests
from datetime import datetime
import pytz
import time

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID", "")

PINCODE      = "147004"
CITY         = "Patiala"
LAT          = "30.3398"
LON          = "76.3869"

MIN_DISCOUNT = 30        # Fetch all 30%+ deals
MAX_PER_TIER = 8         # Max deals shown per tier
SEEN_FILE    = "seen_deals.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept":          "application/json, text/plain, */*",
    "Accept-Language": "en-IN,en;q=0.9",
}

# ─────────────────────────────────────────────────────────────────────────────
# SEEN DEALS (Anti-spam)
# ─────────────────────────────────────────────────────────────────────────────

def load_seen():
    try:
        with open(SEEN_FILE) as f:
            return set(json.load(f))
    except Exception:
        return set()


def save_seen(seen):
    with open(SEEN_FILE, "w") as f:
        json.dump(list(seen)[-500:], f)


def deal_id(platform, name, price):
    return hashlib.md5(f"{platform}_{name}_{price}".encode()).hexdigest()[:12]


# ─────────────────────────────────────────────────────────────────────────────
# SCRAPERS
# ─────────────────────────────────────────────────────────────────────────────

def scrape_bigbasket():
    deals = []
    try:
        s = requests.Session()
        s.headers.update(HEADERS)
        resp = s.get(
            "https://www.bigbasket.com/listing-svc/v2/listing",
            params={
                "type": "pc", "slug": "offers",
                "pincode": PINCODE, "sort": "disc_p_desc",
                "page": 1, "listingPageType": "offers",
            },
            timeout=20
        )
        if resp.status_code == 200:
            tabs = resp.json().get("tabs", [{}])
            for p in tabs[0].get("product_info", {}).get("products", []):
                try:
                    name  = p.get("desc", "")
                    mrp   = float(p.get("w", {}).get("mrp", 0))
                    price = float(p.get("w", {}).get("sp", mrp))
                    disc  = round((mrp - price) / mrp * 100) if mrp > 0 else 0
                    unit  = p.get("w", {}).get("desc", "")
                    cat   = p.get("category", {}).get("tlc_name", "")
                    slug  = p.get("absolute_url", "")
                    link  = f"https://www.bigbasket.com{slug}" if slug else ""
                    if disc >= MIN_DISCOUNT and price > 0:
                        deals.append({
                            "platform": "BigBasket",
                            "emoji":    "🛒",
                            "name":     f"{name} {unit}".strip(),
                            "mrp":      mrp,
                            "price":    price,
                            "discount": disc,
                            "category": cat,
                            "link":     link,
                        })
                except Exception:
                    continue
        print(f"  BigBasket: {len(deals)} deals")
    except Exception as e:
        print(f"  BigBasket error: {e}")
    return deals


def scrape_blinkit():
    deals = []
    try:
        s = requests.Session()
        s.headers.update({
            **HEADERS,
            "lat": LAT, "lon": LON,
            "app_client": "consumer",
            "device_type": "web",
        })
        s.get("https://blinkit.com", timeout=15)
        time.sleep(1)
        resp = s.get(
            "https://blinkit.com/v2/listing/listing/",
            params={
                "sort_attribute": "percent_discount",
                "sort_order": "desc",
                "start": 0, "size": 50,
            },
            timeout=20
        )
        if resp.status_code == 200:
            for p in resp.json().get("objects", []):
                try:
                    name  = p.get("name", "")
                    mrp   = float(p.get("mrp", 0))
                    price = float(p.get("price", mrp))
                    disc  = int(p.get("percent_discount", 0))
                    unit  = p.get("unit", "")
                    cat   = p.get("category", {}).get("name", "")
                    pid   = p.get("id", "")
                    link  = f"https://blinkit.com/prn/{name.lower().replace(' ','-')}/{pid}/"
                    if disc >= MIN_DISCOUNT and price > 0:
                        deals.append({
                            "platform": "Blinkit",
                            "emoji":    "⚡",
                            "name":     f"{name} {unit}".strip(),
                            "mrp":      mrp,
                            "price":    price,
                            "discount": disc,
                            "category": cat,
                            "link":     link,
                        })
                except Exception:
                    continue
        print(f"  Blinkit: {len(deals)} deals")
    except Exception as e:
        print(f"  Blinkit error: {e}")
    return deals


def scrape_zepto():
    deals = []
    try:
        s = requests.Session()
        s.headers.update({**HEADERS, "Origin": "https://zeptonow.com"})
        s_resp = s.get(
            f"https://api.zeptonow.com/api/v1/store/pincode/{PINCODE}",
            timeout=15
        )
        if s_resp.status_code == 200:
            store_id = s_resp.json().get("store", {}).get("id")
            if store_id:
                d_resp = s.get(
                    "https://api.zeptonow.com/api/v3/deals",
                    params={"storeId": store_id, "pageNumber": 1, "pageSize": 50},
                    timeout=20
                )
                if d_resp.status_code == 200:
                    sections = d_resp.json().get("sections", [{}])
                    for item in sections[0].get("items", []):
                        try:
                            name  = item.get("productName", "")
                            mrp   = float(item.get("mrp", 0)) / 100
                            price = float(item.get("discountedSellingPrice", mrp*100)) / 100
                            disc  = int(item.get("discountPercent", 0))
                            unit  = item.get("unitOfMeasure", "")
                            cat   = item.get("categoryName", "")
                            if disc >= MIN_DISCOUNT and price > 0:
                                deals.append({
                                    "platform": "Zepto",
                                    "emoji":    "🟡",
                                    "name":     f"{name} {unit}".strip(),
                                    "mrp":      mrp,
                                    "price":    price,
                                    "discount": disc,
                                    "category": cat,
                                    "link":     "https://zeptonow.com",
                                })
                        except Exception:
                            continue
        print(f"  Zepto: {len(deals)} deals")
    except Exception as e:
        print(f"  Zepto error: {e}")
    return deals


def scrape_instamart():
    deals = []
    try:
        s = requests.Session()
        s.headers.update({**HEADERS, "Origin": "https://www.swiggy.com"})
        resp = s.get(
            "https://www.swiggy.com/api/instamart/home",
            params={"lat": LAT, "lng": LON, "pincode": PINCODE},
            timeout=20
        )
        if resp.status_code == 200:
            cards = resp.json().get("data", {}).get("cards", [])
            for card in cards:
                items = card.get("gridElements", {}).get(
                    "infoWithStyle", {}).get("info", [])
                for item in items:
                    try:
                        offers = item.get("offers", [{}])
                        disc   = int(offers[0].get("discountPercent", 0))
                        if disc < MIN_DISCOUNT:
                            continue
                        name  = item.get("name", "")
                        mrp   = float(item.get("price", {}).get("mrp", 0)) / 100
                        price = float(item.get("price", {}).get("value", mrp*100)) / 100
                        cat   = item.get("category", "")
                        deals.append({
                            "platform": "Instamart",
                            "emoji":    "🟠",
                            "name":     name,
                            "mrp":      mrp,
                            "price":    price,
                            "discount": disc,
                            "category": cat,
                            "link":     "https://www.swiggy.com/instamart",
                        })
                    except Exception:
                        continue
        print(f"  Instamart: {len(deals)} deals")
    except Exception as e:
        print(f"  Instamart error: {e}")
    return deals


# ─────────────────────────────────────────────────────────────────────────────
# COMBINE & SORT
# ─────────────────────────────────────────────────────────────────────────────

def get_all_deals():
    print("  Scanning all platforms...")
    all_deals = []
    all_deals.extend(scrape_blinkit())
    all_deals.extend(scrape_zepto())
    all_deals.extend(scrape_bigbasket())
    all_deals.extend(scrape_instamart())
    all_deals.sort(key=lambda x: x["discount"], reverse=True)
    print(f"  Total {MIN_DISCOUNT}%+ deals: {len(all_deals)}")
    return all_deals


def filter_new(deals, seen):
    new = []
    for d in deals:
        did = deal_id(d["platform"], d["name"], d["price"])
        if did not in seen:
            d["_id"] = did
            new.append(d)
    return new


def split_tiers(deals):
    """Split deals into 3 tiers."""
    t1 = [d for d in deals if d["discount"] >= 50]   # 🔴 50%+
    t2 = [d for d in deals if 40 <= d["discount"] < 50]  # 🟠 40-49%
    t3 = [d for d in deals if 30 <= d["discount"] < 40]  # 🟡 30-39%
    return t1, t2, t3


# ─────────────────────────────────────────────────────────────────────────────
# TELEGRAM
# ─────────────────────────────────────────────────────────────────────────────

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        r = requests.post(url, json={
            "chat_id":    TELEGRAM_CHAT_ID,
            "text":       message,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }, timeout=15)
        return r.status_code == 200
    except Exception as e:
        print(f"  Telegram error: {e}")
        return False


def deal_line(d):
    """Format single deal line."""
    line  = f"  {d['emoji']} <b>{d['platform']}</b> — {d['name']}\n"
    line += f"  💰 ₹{d['price']} <s>₹{d['mrp']}</s> <b>{d['discount']}% OFF</b>\n"
    if d.get("category"):
        line += f"  🏷️ {d['category']}\n"
    if d.get("link") and "zeptonow" not in d["link"] and "swiggy" not in d["link"]:
        line += f"  🔗 <a href='{d['link']}'>Buy Now</a>\n"
    return line + "\n"


def build_and_send(t1, t2, t3):
    """Build 3-tier message and send."""
    ist = pytz.timezone("Asia/Kolkata")
    ts  = datetime.now(ist).strftime("%d-%b-%Y | %I:%M %p IST")
    total = len(t1) + len(t2) + len(t3)

    msg  = f"🔔 <b>DEAL ALERT — {CITY} ({PINCODE})</b>\n"
    msg += f"⏰ {ts}\n"
    msg += f"📦 {total} new deals found!\n"
    msg += "━" * 28 + "\n\n"

    if t1:
        msg += f"🔴 <b>50%+ OFF — HOT DEALS! ({len(t1)})</b>\n\n"
        for d in t1[:MAX_PER_TIER]:
            msg += deal_line(d)

    if t2:
        msg += f"🟠 <b>40-49% OFF — GREAT DEALS! ({len(t2)})</b>\n\n"
        for d in t2[:MAX_PER_TIER]:
            msg += deal_line(d)

    if t3:
        msg += f"🟡 <b>30-39% OFF — GOOD DEALS! ({len(t3)})</b>\n\n"
        for d in t3[:MAX_PER_TIER]:
            msg += deal_line(d)

    # Split if message too long (Telegram limit 4096 chars)
    if len(msg) <= 4000:
        ok = send_telegram(msg)
        print(f"  Telegram: {'✅ sent' if ok else '❌ failed'}")
    else:
        # Send in parts
        parts = []
        if t1:
            p  = f"🔴 <b>50%+ HOT DEALS — {ts}</b>\n\n"
            p += "".join(deal_line(d) for d in t1[:MAX_PER_TIER])
            parts.append(p)
        if t2:
            p  = f"🟠 <b>40-49% GREAT DEALS</b>\n\n"
            p += "".join(deal_line(d) for d in t2[:MAX_PER_TIER])
            parts.append(p)
        if t3:
            p  = f"🟡 <b>30-39% GOOD DEALS</b>\n\n"
            p += "".join(deal_line(d) for d in t3[:MAX_PER_TIER])
            parts.append(p)

        for i, part in enumerate(parts):
            ok = send_telegram(part)
            print(f"  Part {i+1}: {'✅' if ok else '❌'}")
            time.sleep(2)


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    ist = pytz.timezone("Asia/Kolkata")
    print("=" * 50)
    print(f"  DEAL HUNTER 3-TIER")
    print(f"  {CITY} ({PINCODE})")
    print(f"  {datetime.now(ist).strftime('%d-%b %I:%M %p')}")
    print("=" * 50)

    seen = load_seen()
    print(f"\n  Seen deals: {len(seen)}")

    all_deals = get_all_deals()

    if not all_deals:
        print("  No deals found — silent run")
        return

    new_deals = filter_new(all_deals, seen)
    print(f"  New deals: {len(new_deals)}")

    if not new_deals:
        print("  All deals already sent before — silent")
        return

    t1, t2, t3 = split_tiers(new_deals)
    print(f"\n  🔴 50%+   : {len(t1)} deals")
    print(f"  🟠 40-49% : {len(t2)} deals")
    print(f"  🟡 30-39% : {len(t3)} deals")

    print("\n  Sending Telegram alert...")
    build_and_send(t1, t2, t3)

    for d in new_deals:
        seen.add(d["_id"])
    save_seen(seen)

    print(f"\n  Seen updated: {len(seen)} total")
    print("  DONE! ✅")


if __name__ == "__main__":
    main()

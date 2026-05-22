"""
Quick Commerce Deal Hunter
===========================
Location  : Patiala, Punjab (147004)
Platforms : Blinkit, Zepto, BigBasket, Instamart
Filter    : 50%+ discount only
Alert     : Telegram only
Runs      : Every 30 minutes (Mon-Sun)
"""

import os
import json
import hashlib
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import pytz
import time

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID", "")

PINCODE   = "147004"
CITY      = "Patiala"
LAT       = "30.3398"
LON       = "76.3869"

MIN_DISCOUNT   = 50       # Alert only for 50%+ off
MAX_DEALS_MSG  = 15       # Max deals per Telegram message
SEEN_FILE      = "seen_deals.json"  # Tracks sent deals (anti-spam)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-IN,en;q=0.9",
}

# ─────────────────────────────────────────────────────────────────────────────
# SEEN DEALS TRACKER (Anti-spam)
# ─────────────────────────────────────────────────────────────────────────────

def load_seen_deals():
    try:
        with open(SEEN_FILE, "r") as f:
            return set(json.load(f))
    except Exception:
        return set()


def save_seen_deals(seen):
    with open(SEEN_FILE, "w") as f:
        json.dump(list(seen), f)


def deal_id(platform, name, price):
    """Unique ID for a deal — platform + product + price."""
    raw = f"{platform}_{name}_{price}"
    return hashlib.md5(raw.encode()).hexdigest()[:12]


# ─────────────────────────────────────────────────────────────────────────────
# PLATFORM SCRAPERS
# ─────────────────────────────────────────────────────────────────────────────

def scrape_bigbasket():
    """Scrape BigBasket deals for Patiala."""
    deals = []
    try:
        session = requests.Session()
        session.headers.update(HEADERS)

        # BigBasket listing API — sorted by discount
        url = "https://www.bigbasket.com/listing-svc/v2/listing"
        params = {
            "type":           "pc",
            "slug":           "offers",
            "pincode":        PINCODE,
            "sort":           "disc_p_desc",
            "page":           1,
            "tab_type":       ["pc"],
            "listingPageType":"offers",
        }
        resp = session.get(url, params=params, timeout=20)

        if resp.status_code == 200:
            data = resp.json()
            tabs = data.get("tabs", [{}])
            products = tabs[0].get("product_info", {}).get("products", [])

            for p in products:
                try:
                    name     = p.get("desc", "")
                    mrp      = float(p.get("w", {}).get("mrp", 0))
                    price    = float(p.get("w", {}).get("sp", mrp))
                    discount = round((mrp - price) / mrp * 100) if mrp > 0 else 0
                    unit     = p.get("w", {}).get("desc", "")
                    category = p.get("category", {}).get("tlc_name", "")
                    slug     = p.get("absolute_url", "")
                    link     = f"https://www.bigbasket.com{slug}" if slug else ""

                    if discount >= MIN_DISCOUNT and price > 0:
                        deals.append({
                            "platform":   "BigBasket 🛒",
                            "name":       f"{name} {unit}".strip(),
                            "mrp":        mrp,
                            "price":      price,
                            "discount":   discount,
                            "category":   category,
                            "link":       link,
                        })
                except Exception:
                    continue

        print(f"  BigBasket: {len(deals)} deals found")

    except Exception as e:
        print(f"  BigBasket error: {e}")

    return deals


def scrape_blinkit():
    """Scrape Blinkit deals for Patiala coordinates."""
    deals = []
    try:
        session = requests.Session()
        session.headers.update({
            **HEADERS,
            "lat":         LAT,
            "lon":         LON,
            "app_client":  "consumer",
            "device_type": "web",
        })

        # Get homepage cookies first
        session.get("https://blinkit.com", timeout=15)
        time.sleep(1)

        # Search for deals sorted by discount
        url = "https://blinkit.com/v2/listing/listing/"
        params = {
            "sort_attribute": "percent_discount",
            "sort_order":     "desc",
            "start":          0,
            "size":           50,
        }
        resp = session.get(url, params=params, timeout=20)

        if resp.status_code == 200:
            data = resp.json()
            products = data.get("objects", [])

            for p in products:
                try:
                    name     = p.get("name", "")
                    mrp      = float(p.get("mrp", 0))
                    price    = float(p.get("price", mrp))
                    discount = int(p.get("percent_discount", 0))
                    unit     = p.get("unit", "")
                    category = p.get("category", {}).get("name", "")
                    pid      = p.get("id", "")
                    link     = f"https://blinkit.com/prn/{name.lower().replace(' ','-')}/{pid}/"

                    if discount >= MIN_DISCOUNT and price > 0:
                        deals.append({
                            "platform": "Blinkit ⚡",
                            "name":     f"{name} {unit}".strip(),
                            "mrp":      mrp,
                            "price":    price,
                            "discount": discount,
                            "category": category,
                            "link":     link,
                        })
                except Exception:
                    continue

        print(f"  Blinkit: {len(deals)} deals found")

    except Exception as e:
        print(f"  Blinkit error: {e}")

    return deals


def scrape_zepto():
    """Scrape Zepto deals for Patiala."""
    deals = []
    try:
        session = requests.Session()
        session.headers.update({
            **HEADERS,
            "Origin":  "https://zeptonow.com",
            "Referer": "https://zeptonow.com/",
        })

        # Zepto store finder by pincode
        store_url = f"https://api.zeptonow.com/api/v1/store/pincode/{PINCODE}"
        s_resp = session.get(store_url, timeout=15)

        store_id = None
        if s_resp.status_code == 200:
            sdata    = s_resp.json()
            store_id = sdata.get("store", {}).get("id")

        if store_id:
            # Fetch deals for this store
            deals_url = f"https://api.zeptonow.com/api/v3/deals"
            params    = {"storeId": store_id, "pageNumber": 1, "pageSize": 50}
            d_resp    = session.get(deals_url, params=params, timeout=20)

            if d_resp.status_code == 200:
                data     = d_resp.json()
                products = data.get("sections", [{}])[0].get("items", [])

                for p in products:
                    try:
                        name      = p.get("productName", "")
                        mrp       = float(p.get("mrp", 0)) / 100
                        price     = float(p.get("discountedSellingPrice", mrp*100)) / 100
                        discount  = int(p.get("discountPercent", 0))
                        unit      = p.get("unitOfMeasure", "")
                        category  = p.get("categoryName", "")

                        if discount >= MIN_DISCOUNT and price > 0:
                            deals.append({
                                "platform": "Zepto 🟡",
                                "name":     f"{name} {unit}".strip(),
                                "mrp":      mrp,
                                "price":    price,
                                "discount": discount,
                                "category": category,
                                "link":     "https://zeptonow.com",
                            })
                    except Exception:
                        continue

        print(f"  Zepto: {len(deals)} deals found")

    except Exception as e:
        print(f"  Zepto error: {e}")

    return deals


def scrape_instamart():
    """Scrape Swiggy Instamart deals for Patiala."""
    deals = []
    try:
        session = requests.Session()
        session.headers.update({
            **HEADERS,
            "Origin":  "https://www.swiggy.com",
            "Referer": "https://www.swiggy.com/instamart",
        })

        # Instamart deals API
        url    = "https://www.swiggy.com/api/instamart/home"
        params = {
            "lat":        LAT,
            "lng":        LON,
            "pincode":    PINCODE,
            "page_type":  "INSTAMART_DEALS",
        }
        resp = session.get(url, params=params, timeout=20)

        if resp.status_code == 200:
            data  = resp.json()
            cards = data.get("data", {}).get("cards", [])

            for card in cards:
                items = card.get("gridElements", {}).get("infoWithStyle", {}).get("info", [])
                for item in items:
                    try:
                        offer  = item.get("offers", [{}])[0]
                        disc   = int(offer.get("discountPercent", 0))
                        if disc < MIN_DISCOUNT:
                            continue
                        name   = item.get("name", "")
                        mrp    = float(item.get("price", {}).get("mrp", 0)) / 100
                        price  = float(item.get("price", {}).get("value", mrp*100)) / 100
                        cat    = item.get("category", "")

                        deals.append({
                            "platform": "Instamart 🟠",
                            "name":     name,
                            "mrp":      mrp,
                            "price":    price,
                            "discount": disc,
                            "category": cat,
                            "link":     "https://www.swiggy.com/instamart",
                        })
                    except Exception:
                        continue

        print(f"  Instamart: {len(deals)} deals found")

    except Exception as e:
        print(f"  Instamart error: {e}")

    return deals


# ─────────────────────────────────────────────────────────────────────────────
# COMBINE & FILTER
# ─────────────────────────────────────────────────────────────────────────────

def get_all_deals():
    """Scrape all platforms and return combined deals list."""
    print("  Scanning all platforms...")
    all_deals = []
    all_deals.extend(scrape_blinkit())
    all_deals.extend(scrape_zepto())
    all_deals.extend(scrape_bigbasket())
    all_deals.extend(scrape_instamart())

    # Sort by discount % descending
    all_deals.sort(key=lambda x: x["discount"], reverse=True)
    print(f"  Total {MIN_DISCOUNT}%+ deals: {len(all_deals)}")
    return all_deals


def filter_new_deals(all_deals, seen):
    """Return only deals not seen before."""
    new = []
    for d in all_deals:
        did = deal_id(d["platform"], d["name"], d["price"])
        if did not in seen:
            d["_id"] = did
            new.append(d)
    return new


# ─────────────────────────────────────────────────────────────────────────────
# TELEGRAM
# ─────────────────────────────────────────────────────────────────────────────

def send_telegram(message):
    """Send message via Telegram bot."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        resp = requests.post(url, json={
            "chat_id":    TELEGRAM_CHAT_ID,
            "text":       message,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }, timeout=15)
        return resp.status_code == 200
    except Exception as e:
        print(f"  Telegram error: {e}")
        return False


def build_message(new_deals):
    """Build formatted Telegram message."""
    ist = pytz.timezone("Asia/Kolkata")
    ts  = datetime.now(ist).strftime("%d-%b-%Y | %I:%M %p IST")

    msg = (
        f"🔥 <b>DEAL ALERT — {MIN_DISCOUNT}%+ OFF!</b>\n"
        f"📍 {CITY} ({PINCODE})\n"
        f"⏰ {ts}\n"
        f"{'─'*30}\n\n"
    )

    shown = 0
    for d in new_deals[:MAX_DEALS_MSG]:
        msg += (
            f"<b>{d['platform']}</b>\n"
            f"📦 {d['name']}\n"
            f"💰 ₹{d['price']} "
            f"<s>₹{d['mrp']}</s> "
            f"🔴 <b>{d['discount']}% OFF</b>\n"
        )
        if d.get("category"):
            msg += f"🏷️ {d['category']}\n"
        if d.get("link") and d["link"] != "https://zeptonow.com":
            msg += f"🛒 <a href='{d['link']}'>Buy Now</a>\n"
        msg += "\n"
        shown += 1

    if len(new_deals) > MAX_DEALS_MSG:
        msg += f"<i>...and {len(new_deals) - MAX_DEALS_MSG} more deals!</i>\n"

    msg += f"\n✅ <b>{len(new_deals)} new deals found</b>"
    return msg


def send_in_chunks(new_deals):
    """Send deals in chunks if too many."""
    chunk_size = MAX_DEALS_MSG
    chunks = [new_deals[i:i+chunk_size]
              for i in range(0, len(new_deals), chunk_size)]

    for i, chunk in enumerate(chunks):
        msg = build_message(chunk)
        if i > 0:
            ist = pytz.timezone("Asia/Kolkata")
            ts  = datetime.now(ist).strftime("%I:%M %p")
            msg = f"🔥 <b>DEALS (Part {i+1}) — {ts}</b>\n\n" + \
                  "\n".join(msg.split("\n")[3:])
        ok = send_telegram(msg)
        print(f"  Telegram chunk {i+1}: {'✅ sent' if ok else '❌ failed'}")
        time.sleep(2)


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    ist = pytz.timezone("Asia/Kolkata")
    print("=" * 50)
    print(f"  DEAL HUNTER — {datetime.now(ist).strftime('%d-%b %I:%M %p')}")
    print(f"  Location: {CITY} ({PINCODE})")
    print(f"  Filter: {MIN_DISCOUNT}%+ discount")
    print("=" * 50)

    # Load previously seen deals
    seen = load_seen_deals()
    print(f"\n  Previously seen deals: {len(seen)}")

    # Scan all platforms
    print("\n  Scanning platforms...")
    all_deals = get_all_deals()

    if not all_deals:
        print("\n  No deals found this run — staying silent")
        return

    # Filter new deals only
    new_deals = filter_new_deals(all_deals, seen)
    print(f"  New deals: {len(new_deals)}")

    if not new_deals:
        print("  No NEW deals — already sent these before")
        return

    # Send Telegram alert
    print("\n  Sending Telegram alert...")
    send_in_chunks(new_deals)

    # Update seen deals
    for d in new_deals:
        seen.add(d["_id"])

    # Keep seen list manageable (last 500 deals)
    if len(seen) > 500:
        seen = set(list(seen)[-500:])

    save_seen_deals(seen)
    print(f"\n  Seen deals updated: {len(seen)} total")
    print("\n  DONE! ✅")


if __name__ == "__main__":
    main()

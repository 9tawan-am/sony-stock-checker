import os
import sys
import json
import time
import requests
from datetime import datetime

# ================= ตั้งค่าการใช้งาน =================
WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "ใส่_DISCORD_WEBHOOK_URL_ของคุณที่นี่")
COLLECTION_URL = "https://store.sony.co.th/collections/console/products.json?limit=250"
STATE_FILE = "stock_state.json"
CHECK_INTERVAL = 60  # ความถี่ในการเช็ก (วินาที) กรณีรันแบบเปิดทิ้งไว้ 24 ชม.

# หากต้องการกรองเฉพาะบางรุ่น ให้ใส่คำค้นหา เช่น ["PS5", "Pro"] (ปล่อยว่าง [] เพื่อเช็กทุกชิ้นในหน้านี้)
KEYWORDS = []
# ====================================================


def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except Exception:
            return set()
    return set()


def save_state(in_stock_ids):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(list(in_stock_ids), f, ensure_ascii=False, indent=2)


def send_discord_alert(product_name, price, product_url, image_url):
    if not WEBHOOK_URL or "ใส่_DISCORD_WEBHOOK" in WEBHOOK_URL:
        print("⚠️ ยังไม่ได้ตั้งค่า DISCORD_WEBHOOK_URL")
        return

    embed = {
        "title": f"🛒 สินค้าพร้อมสั่งซื้อแล้ว: {product_name}",
        "url": product_url,
        "color": 3066993,  # สีเขียว
        "fields": [
            {"name": "ราคา", "value": f"{float(price):,.0f} บาท", "inline": True},
            {"name": "สถานะ", "value": "✅ มีสินค้า (In Stock)", "inline": True},
            {"name": "ลิงก์สั่งซื้อ", "value": f"[คลิกเพื่อไปหน้าสินค้า]({product_url})", "inline": False},
        ],
        "footer": {"text": "Sony Store Thailand Stock Monitor"},
        "timestamp": datetime.utcnow().isoformat(),
    }

    if image_url:
        embed["thumbnail"] = {"url": image_url}

    payload = {
        "content": "@everyone พบสินค้าใน Sony Store สามารถสั่งซื้อได้แล้ว!",
        "embeds": [embed],
    }

    try:
        res = requests.post(WEBHOOK_URL, json=payload, timeout=10)
        res.raise_for_status()
        print(f"[แจ้งเตือนสำเร็จ] {product_name}")
    except Exception as e:
        print(f"[แจ้งเตือนล้มเหลว] {e}")


def check_stock():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    }

    try:
        response = requests.get(COLLECTION_URL, headers=headers, timeout=15)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ดึงข้อมูลไม่สำเร็จ: {e}")
        return

    previous_in_stock = load_state()
    current_in_stock = set()

    for product in data.get("products", []):
        title = product.get("title", "")
        handle = product.get("handle", "")
        product_url = f"https://store.sony.co.th/products/{handle}"
        images = product.get("images", [])
        image_url = images[0].get("src") if images else None

        # กรองคำค้นหา (ถ้ามีการกำหนดไว้)
        if KEYWORDS and not any(kw.lower() in title.lower() for kw in KEYWORDS):
            continue

        for variant in product.get("variants", []):
            variant_id = str(variant.get("id"))
            variant_title = variant.get("title", "")
            full_name = title if variant_title == "Default Title" else f"{title} ({variant_title})"
            available = variant.get("available", False)
            price = variant.get("price", "0")

            if available:
                current_in_stock.add(variant_id)
                # แจ้งเตือนเฉพาะรายการที่เพิ่งมีของ (รอบก่อนหน้ายังไม่มี)
                if variant_id not in previous_in_stock:
                    send_discord_alert(full_name, price, product_url, image_url)
                    time.sleep(1)  # หน่วงเวลาเล็กน้อยป้องกัน Discord Rate Limit

    save_state(current_in_stock)
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] เช็กเรียบร้อย | สินค้าพร้อมขาย {len(current_in_stock)} รายการ")


if __name__ == "__main__":
    # ถ้ารันด้วยคำสั่ง python check_sony.py --once จะเช็ก 1 ครั้งแล้วจบ (เหมาะกับ Cron / GitHub Actions)
    if "--once" in sys.argv:
        check_stock()
    else:
        print("เริ่มต้นระบบตรวจสอบสินค้า Sony Store (กด Ctrl+C เพื่อหยุด)...")
        while True:
            check_stock()
            time.sleep(CHECK_INTERVAL)

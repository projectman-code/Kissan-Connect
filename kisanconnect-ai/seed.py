"""Demo data so every page has something to show on first run.

Demo logins (change these before any real use):
    admin     / admin123
    ramesh    / farmer123   (Nashik)
    lakshmi   / farmer123   (Guntur)
    gurpreet  / farmer123   (Ludhiana)
    suresh    / farmer123   (waiting for admin approval)
    priya     / buyer123
    spicehub  / buyer123
"""
import random
from datetime import datetime, timedelta

from werkzeug.security import generate_password_hash

from ai.catalog import CROPS


def _ts(days_ago, hour=10):
    d = datetime.now() - timedelta(days=days_ago)
    return d.replace(hour=hour, minute=random.randint(0, 59), second=0).strftime("%Y-%m-%d %H:%M:%S")


def seed(db):
    random.seed(11)
    users = [
        ("admin", "admin123", "Platform Admin", "admin", "9876500000", "Hyderabad, Telangana", "active"),
        ("ramesh", "farmer123", "Ramesh Patil", "farmer", "9876500001", "Nashik, Maharashtra", "active"),
        ("lakshmi", "farmer123", "Lakshmi Devi", "farmer", "9876500002", "Guntur, Andhra Pradesh", "active"),
        ("gurpreet", "farmer123", "Gurpreet Singh", "farmer", "9876500003", "Ludhiana, Punjab", "active"),
        ("suresh", "farmer123", "Suresh Naik", "farmer", "9876500004", "Belagavi, Karnataka", "pending"),
        ("priya", "buyer123", "Priya Sharma", "buyer", "9876500005", "Flat 302, Green Park Apartments, Madhapur, Hyderabad 500081", "active"),
        ("spicehub", "buyer123", "Spice Hub Restaurant", "buyer", "9876500006", "12 MG Road, Indiranagar, Bengaluru 560038", "active"),
    ]
    ids = {}
    for i, (u, pw, name, role, phone, addr, status) in enumerate(users):
        village = addr.split(",")[0] if role == "farmer" else addr
        village = addr if role == "farmer" else addr.split(",")[-1].strip().rsplit(" ", 1)[0]
        cur = db.execute(
            """INSERT INTO users(username,password_hash,name,role,phone,village,address,language,status,created_at)
               VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (u, generate_password_hash(pw), name, role, phone, village, addr,
             {"lakshmi": "te", "priya": "en"}.get(u, "en"), status, _ts(30 - i)))
        ids[u] = cur.lastrowid

    # seller, crop, price, qty, grade, organic, score, description
    catalog = [
        ("ramesh", "Onion", 26, 800, "A", 0, 88, "Red onions from Nashik, sun-cured for 10 days. Firm, dry skin and a long shelf life."),
        ("ramesh", "Tomato", 28, 300, "B", 0, 74, "Vine-ripened hybrid tomatoes picked this morning. Good for curries and sauces."),
        ("ramesh", "Grapes", 85, 150, "A", 0, 91, "Seedless Thompson grapes, sweet and crisp. Packed in ventilated crates."),
        ("ramesh", "Pomegranate", 130, 120, "A", 1, 86, "Bhagwa pomegranates grown without synthetic pesticides. Deep red arils."),
        ("lakshmi", "Red Chilli", 235, 200, "A", 0, 90, "Guntur sannam dried red chillies. Bright colour and strong heat."),
        ("lakshmi", "Rice", 48, 1200, "B", 0, 70, "Sona Masuri rice, aged 8 months. Light, fluffy and easy to digest."),
        ("lakshmi", "Turmeric", 135, 180, "A", 1, 89, "Cured and polished organic turmeric fingers with high curcumin."),
        ("lakshmi", "Banana", 42, 400, "B", 0, 72, "Yelakki bananas from our own orchard. Small, sweet and fragrant."),
        ("lakshmi", "Green Chilli", 66, 90, "B", 0, 69, "Fresh green chillies, medium hot, picked twice a week."),
        ("gurpreet", "Wheat", 31, 2000, "A", 0, 85, "Sharbati wheat, double cleaned. Makes soft rotis with a natural sweetness."),
        ("gurpreet", "Milk", 62, 120, "A", 1, 92, "A2 desi cow milk, delivered chilled within 12 hours of milking."),
        ("gurpreet", "Ghee", 640, 60, "A", 1, 93, "Bilona ghee made from curd of desi cow milk. Slow churned and golden."),
        ("gurpreet", "Potato", 20, 900, "B", 0, 71, "Punjab table potatoes, washed and graded. Good for frying and curries."),
        ("gurpreet", "Maize", 25, 600, "C", 0, 55, "Dried maize kernels for flour or feed. Clean and sorted."),
        ("ramesh", "Mango", 95, 250, "A", 0, 90, "Kesar mangoes ripened naturally. No carbide, no wax."),
        ("lakshmi", "Groundnut", 88, 300, "B", 0, 68, "Shelled groundnuts, cold-pressed oil quality. Sun dried."),
        ("gurpreet", "Carrot", 38, 150, "B", 0, 73, "Sweet red carrots from sandy soil. Crunchy and juicy."),
    ]
    pids = {}
    for i, (seller, crop, price, qty, grade, organic, score, desc) in enumerate(catalog):
        info = CROPS[crop]
        village = [u for u in users if u[0] == seller][0][5]
        cur = db.execute(
            """INSERT INTO products(seller_id,name,category,description,price,unit,quantity,grade,quality_score,
               ai_verified,organic,location,emoji,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (ids[seller], crop, info["cat"], desc, price, info["unit"], qty, grade, score, 1, organic,
             village, info["emoji"], _ts(20 - i)))
        pids[crop] = (cur.lastrowid, ids[seller], price, info["unit"], info["emoji"])

    # buyer, [(crop, qty)], status, days ago
    orders = [
        ("priya", [("Tomato", 5), ("Onion", 4)], "Delivered", 12),
        ("priya", [("Milk", 6), ("Ghee", 1)], "Delivered", 10),
        ("spicehub", [("Red Chilli", 10), ("Turmeric", 5)], "Delivered", 9),
        ("spicehub", [("Onion", 40), ("Tomato", 25)], "Delivered", 7),
        ("priya", [("Mango", 4)], "Delivered", 5),
        ("spicehub", [("Rice", 50)], "Out for delivery", 2),
        ("priya", [("Grapes", 3), ("Pomegranate", 2)], "Packed", 2),
        ("spicehub", [("Wheat", 60), ("Potato", 30)], "Confirmed", 1),
        ("priya", [("Banana", 6)], "Placed", 0),
        ("spicehub", [("Carrot", 10)], "Cancelled", 4),
    ]
    delivered = []
    for buyer, lines, status, ago in orders:
        by_seller = {}
        for crop, qty in lines:
            by_seller.setdefault(pids[crop][1], []).append((crop, qty))
        for seller_id, group in by_seller.items():
            total = sum(pids[c][2] * n for c, n in group)
            buyer_row = [u for u in users if u[0] == buyer][0]
            pay = "Collected" if status == "Delivered" else ("Not required" if status == "Cancelled" else "Pending")
            oid = db.execute(
                """INSERT INTO orders(buyer_id,seller_id,total,status,payment_status,address,phone,created_at)
                   VALUES(?,?,?,?,?,?,?,?)""",
                (ids[buyer], seller_id, total, status, pay, buyer_row[5], buyer_row[4], _ts(ago))).lastrowid
            for crop, n in group:
                pid, _, price, unit, emoji = pids[crop]
                db.execute("""INSERT INTO order_items(order_id,product_id,name,emoji,price,qty,unit)
                              VALUES(?,?,?,?,?,?,?)""", (oid, pid, crop, emoji, price, n, unit))
                if status == "Delivered":
                    delivered.append((pid, ids[buyer]))

    comments = ["Fresh and exactly as graded.", "Good quality and quick delivery.",
                "Packed well. Will order again.", "Very sweet and fresh."]
    seen = set()
    for i, (pid, buyer_id) in enumerate(delivered):
        if (pid, buyer_id) in seen:
            continue
        seen.add((pid, buyer_id))
        db.execute("INSERT INTO reviews(product_id,buyer_id,rating,comment,created_at) VALUES(?,?,?,?,?)",
                   (pid, buyer_id, 5 if i % 3 else 4, comments[i % len(comments)], _ts(3)))

    msgs = [
        ("priya", "ramesh", "Namaste! Are the grapes available for delivery to Hyderabad this week?", 2),
        ("ramesh", "priya", "Yes, we dispatch every Tuesday. Order by Monday evening and it arrives Wednesday.", 2),
    ]
    for s, r, body, ago in msgs:
        db.execute("INSERT INTO messages(sender_id,receiver_id,body,is_read,created_at) VALUES(?,?,?,?,?)",
                   (ids[s], ids[r], body, 0 if r == "priya" else 1, _ts(ago)))
    db.commit()

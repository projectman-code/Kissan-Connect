"""KisanConnect AI - farmer-to-buyer agriculture marketplace.

Run:  pip install -r requirements.txt   then   python app.py
Open: http://127.0.0.1:5000
"""
import os
import secrets
import sqlite3
import time
import uuid
from datetime import datetime, timedelta
from functools import wraps

from flask import (Flask, abort, flash, g, jsonify, redirect, render_template,
                   request, send_from_directory, session, url_for)
from PIL import Image
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from ai import chatbot, disease, forecast, price, quality
from ai.catalog import CATEGORIES, CROPS, GRADES, UNITS, emoji_for
from i18n import LANG_NAMES, TRANSLATIONS

APP_DIR = os.path.dirname(os.path.abspath(__file__))
# DATA_DIR: where the database and uploaded photos live. Point it at a Render
# persistent disk (for example /var/data) to keep data between deploys.
INSTANCE_DIR = os.environ.get("DATA_DIR") or os.path.join(APP_DIR, "instance")
DB_PATH = os.path.join(INSTANCE_DIR, "kisan.db")
UPLOAD_DIR = os.path.join(INSTANCE_DIR, "uploads")
os.makedirs(INSTANCE_DIR, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)

ORDER_FLOW = ["Placed", "Confirmed", "Packed", "Out for delivery", "Delivered"]
ALLOWED_IMG = {"png", "jpg", "jpeg", "webp"}


def _secret():
    path = os.path.join(INSTANCE_DIR, "secret.key")
    if os.environ.get("SECRET_KEY"):
        return os.environ["SECRET_KEY"]
    if not os.path.exists(path):
        with open(path, "w") as f:
            f.write(secrets.token_hex(32))
    return open(path).read().strip()


app = Flask(__name__)
app.config.update(SECRET_KEY=_secret(), MAX_CONTENT_LENGTH=6 * 1024 * 1024,
                  SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax")

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL,
  name TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('admin','farmer','buyer')),
  phone TEXT, village TEXT, address TEXT, language TEXT DEFAULT 'en',
  status TEXT NOT NULL DEFAULT 'active', cod_blocked INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS products(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  seller_id INTEGER NOT NULL REFERENCES users(id),
  name TEXT NOT NULL, category TEXT NOT NULL, description TEXT,
  price REAL NOT NULL, unit TEXT NOT NULL, quantity INTEGER NOT NULL,
  grade TEXT NOT NULL DEFAULT 'B', quality_score INTEGER, ai_verified INTEGER NOT NULL DEFAULT 0,
  organic INTEGER NOT NULL DEFAULT 0, location TEXT, image TEXT, emoji TEXT,
  status TEXT NOT NULL DEFAULT 'active', created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS orders(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  buyer_id INTEGER NOT NULL REFERENCES users(id), seller_id INTEGER NOT NULL REFERENCES users(id),
  total REAL NOT NULL, status TEXT NOT NULL DEFAULT 'Placed',
  payment_method TEXT NOT NULL DEFAULT 'COD', payment_status TEXT NOT NULL DEFAULT 'Pending',
  address TEXT NOT NULL, phone TEXT NOT NULL, note TEXT, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS order_items(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  order_id INTEGER NOT NULL REFERENCES orders(id), product_id INTEGER NOT NULL REFERENCES products(id),
  name TEXT NOT NULL, emoji TEXT, price REAL NOT NULL, qty INTEGER NOT NULL, unit TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS messages(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  sender_id INTEGER NOT NULL REFERENCES users(id), receiver_id INTEGER NOT NULL REFERENCES users(id),
  product_id INTEGER, body TEXT NOT NULL, is_read INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS reviews(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  product_id INTEGER NOT NULL REFERENCES products(id), buyer_id INTEGER NOT NULL REFERENCES users(id),
  rating INTEGER NOT NULL, comment TEXT, created_at TEXT NOT NULL, UNIQUE(product_id, buyer_id));
"""


# ----------------------------------------------------------------- database
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys=ON")
    return g.db


@app.teardown_appcontext
def close_db(_):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def q(sql, args=(), one=False):
    cur = get_db().execute(sql, args)
    rows = cur.fetchall()
    cur.close()
    if one:
        return rows[0] if rows else None
    return rows


def x(sql, args=()):
    db = get_db()
    cur = db.execute(sql, args)
    db.commit()
    return cur.lastrowid


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# --------------------------------------------------------------------- auth
def home_for(role):
    return {"admin": "/admin", "farmer": "/farmer", "buyer": "/shop"}.get(role, "/")


def safe_next(target):
    if target and target.startswith("/") and not target.startswith("//"):
        return target
    return None


def role_required(*roles):
    """Admin passes every check, so admin can do all that buyers and farmers do."""
    def deco(fn):
        @wraps(fn)
        def wrapper(*a, **k):
            if not g.user:
                flash("Log in to continue.", "info")
                return redirect(url_for("login", next=request.path))
            if roles and g.user["role"] != "admin" and g.user["role"] not in roles:
                abort(403)
            return fn(*a, **k)
        return wrapper
    return deco


def csrf_token():
    if "_csrf" not in session:
        session["_csrf"] = secrets.token_hex(16)
    return session["_csrf"]


@app.before_request
def load_user():
    g.user = None
    uid = session.get("uid")
    if uid:
        user = q("SELECT * FROM users WHERE id=?", (uid,), one=True)
        if user and user["status"] != "blocked":
            g.user = user
        else:
            session.pop("uid", None)
    if request.method == "POST":
        token = request.form.get("_csrf") or request.headers.get("X-CSRF-Token", "")
        if not token or not secrets.compare_digest(token, session.get("_csrf", "")):
            abort(400)


@app.context_processor
def inject():
    lang = session.get("lang") or (g.user["language"] if g.user else "en")
    if lang not in LANG_NAMES:
        lang = "en"

    def t(key):
        row = TRANSLATIONS.get(key, {})
        return row.get(lang) or row.get("en") or key

    cart = session.get("cart", {})
    unread = 0
    if g.user:
        unread = q("SELECT COUNT(*) c FROM messages WHERE receiver_id=? AND is_read=0", (g.user["id"],), one=True)["c"]
    return dict(t=t, lang=lang, lang_names=LANG_NAMES, csrf_token=csrf_token, me=g.user,
                cart_count=sum(cart.values()), unread_count=unread, categories=CATEGORIES,
                order_flow=ORDER_FLOW, year=datetime.now().year,
                show_demo=os.environ.get("SHOW_DEMO", "0") == "1")


@app.template_filter("inr")
def inr(value):
    try:
        value = float(value or 0)
    except (TypeError, ValueError):
        return "₹0"
    return "₹{:,.0f}".format(value) if value == int(value) or value >= 1000 else "₹{:,.1f}".format(value)


@app.template_filter("when")
def when(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S").strftime("%d %b, %I:%M %p")
    except (TypeError, ValueError):
        return value or ""


@app.template_filter("day")
def day(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S").strftime("%d %b %Y")
    except (TypeError, ValueError):
        return value or ""


_fails = {}


def _too_many(key):
    hits = [t for t in _fails.get(key, []) if time.time() - t < 300]
    _fails[key] = hits
    return len(hits) >= 6


@app.route("/media/<path:filename>")
def media(filename):
    return send_from_directory(UPLOAD_DIR, filename, max_age=3600)


@app.route("/lang/<code>")
def set_lang(code):
    if code in LANG_NAMES:
        session["lang"] = code
        if g.user:
            x("UPDATE users SET language=? WHERE id=?", (code, g.user["id"]))
    return redirect(safe_next(request.args.get("next")) or request.referrer or "/")


@app.route("/login", methods=["GET", "POST"])
def login():
    if g.user:
        return redirect(home_for(g.user["role"]))
    if request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")
        key = f"{request.remote_addr}:{username}"
        if _too_many(key):
            flash("Too many wrong attempts. Wait 5 minutes and try again.", "error")
            return render_template("login.html"), 429
        user = q("SELECT * FROM users WHERE username=?", (username,), one=True)
        if not user or not check_password_hash(user["password_hash"], password):
            _fails.setdefault(key, []).append(time.time())
            flash("Wrong username or password. Check both and try again.", "error")
            return render_template("login.html", username=username), 401
        if user["status"] == "blocked":
            flash("This account is blocked. Contact the admin.", "error")
            return render_template("login.html", username=username), 403
        session.clear()
        session["uid"] = user["id"]
        session["lang"] = user["language"] or "en"
        csrf_token()
        flash(f"Welcome, {user['name']}.", "success")
        return redirect(safe_next(request.args.get("next")) or home_for(user["role"]))
    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if g.user:
        return redirect(home_for(g.user["role"]))
    if request.method == "POST":
        f = request.form
        username = f.get("username", "").strip().lower()
        role = f.get("role", "buyer")
        errors = []
        if role not in ("farmer", "buyer"):
            role = "buyer"
        if not f.get("name", "").strip():
            errors.append("Enter your full name.")
        if len(username) < 3 or not username.replace("_", "").replace(".", "").isalnum():
            errors.append("Username needs 3 or more letters or numbers (underscore and dot allowed).")
        if len(f.get("password", "")) < 6:
            errors.append("Password needs at least 6 characters.")
        phone = "".join(c for c in f.get("phone", "") if c.isdigit())
        if len(phone) != 10:
            errors.append("Enter a 10 digit phone number.")
        if q("SELECT 1 FROM users WHERE username=?", (username,), one=True):
            errors.append("That username is taken. Pick another.")
        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("register.html", form=f), 400
        status = "pending" if role == "farmer" else "active"
        x("""INSERT INTO users(username,password_hash,name,role,phone,village,address,language,status,created_at)
             VALUES(?,?,?,?,?,?,?,?,?,?)""",
          (username, generate_password_hash(f["password"]), f["name"].strip(), role, phone,
           f.get("village", "").strip(), f.get("village", "").strip(),
           f.get("language", "en") if f.get("language") in LANG_NAMES else "en", status, now()))
        flash("Account created. Log in to continue." if role == "buyer"
              else "Account created. An admin will approve your farmer account soon. You can log in meanwhile.", "success")
        return redirect(url_for("login"))
    return render_template("register.html", form={})


@app.route("/logout", methods=["POST", "GET"])
def logout():
    session.clear()
    flash("You are logged out.", "info")
    return redirect(url_for("landing"))


# -------------------------------------------------------------------- public
PRODUCT_SELECT = """
SELECT p.*, u.name AS seller_name, u.village AS seller_village, u.status AS seller_status,
  COALESCE((SELECT AVG(rating) FROM reviews r WHERE r.product_id=p.id),0) AS rating,
  (SELECT COUNT(*) FROM reviews r WHERE r.product_id=p.id) AS review_count
FROM products p JOIN users u ON u.id=p.seller_id
"""
VISIBLE = " WHERE p.status='active' AND p.quantity>0 AND u.status='active' "


@app.route("/")
def landing():
    featured = q(PRODUCT_SELECT + VISIBLE + " ORDER BY p.created_at DESC LIMIT 8")
    stats = {
        "farmers": q("SELECT COUNT(*) c FROM users WHERE role='farmer' AND status='active'", one=True)["c"],
        "products": q("SELECT COUNT(*) c FROM products WHERE status='active'", one=True)["c"],
        "orders": q("SELECT COUNT(*) c FROM orders", one=True)["c"],
    }
    board = []
    for crop in ("Tomato", "Mango", "Rice", "Onion", "Milk"):
        s = price.suggest_price(crop, "B", False)
        board.append(s | {"emoji": CROPS[crop]["emoji"]})
    return render_template("landing.html", featured=featured, stats=stats, board=board)


@app.route("/shop")
def shop():
    where, args = [VISIBLE.strip()[len("WHERE"):].strip()], []
    qs = request.args.get("q", "").strip()
    cat = request.args.get("category", "")
    grade = request.args.get("grade", "")
    if qs:
        where.append("(p.name LIKE ? OR p.description LIKE ? OR u.village LIKE ? OR u.name LIKE ?)")
        args += [f"%{qs}%"] * 4
    if cat in CATEGORIES:
        where.append("p.category=?")
        args.append(cat)
    if grade in GRADES:
        where.append("p.grade=?")
        args.append(grade)
    if request.args.get("organic"):
        where.append("p.organic=1")
    order = {"price_asc": "p.price ASC", "price_desc": "p.price DESC", "rating": "rating DESC",
             "grade": "p.grade ASC"}.get(request.args.get("sort"), "p.created_at DESC")
    items = q(PRODUCT_SELECT + " WHERE " + " AND ".join(where) + f" ORDER BY {order}", args)
    return render_template("shop.html", items=items, qs=qs, cat=cat, grade=grade,
                           organic=bool(request.args.get("organic")), sort=request.args.get("sort", ""),
                           grades=GRADES)


@app.route("/product/<int:pid>")
def product(pid):
    p = q(PRODUCT_SELECT + " WHERE p.id=?", (pid,), one=True)
    if not p or (p["status"] != "active" and not (g.user and (g.user["role"] == "admin" or g.user["id"] == p["seller_id"]))):
        abort(404)
    reviews = q("""SELECT r.*, u.name FROM reviews r JOIN users u ON u.id=r.buyer_id
                   WHERE r.product_id=? ORDER BY r.created_at DESC""", (pid,))
    can_review = False
    if g.user:
        can_review = bool(q("""SELECT 1 FROM orders o JOIN order_items i ON i.order_id=o.id
                               WHERE o.buyer_id=? AND i.product_id=? AND o.status='Delivered'""",
                            (g.user["id"], pid), one=True))
    insight = None
    if p["name"] in CROPS:
        fair = price.suggest_price(p["name"], p["grade"], bool(p["organic"]))
        if fair["suggested"]:
            diff = (p["price"] - fair["suggested"]) / fair["suggested"] * 100
            tag = "fair" if abs(diff) <= 8 else ("below" if diff < 0 else "above")
            insight = dict(fair=fair["suggested"], low=fair["low"], high=fair["high"], diff=round(diff), tag=tag)
    related = q(PRODUCT_SELECT + VISIBLE + " AND p.category=? AND p.id!=? LIMIT 4", (p["category"], pid))
    return render_template("product.html", p=p, reviews=reviews, can_review=can_review,
                           insight=insight, related=related)


@app.route("/review/<int:pid>", methods=["POST"])
@role_required("buyer")
def review(pid):
    ok = q("""SELECT 1 FROM orders o JOIN order_items i ON i.order_id=o.id
              WHERE o.buyer_id=? AND i.product_id=? AND o.status='Delivered'""", (g.user["id"], pid), one=True)
    if not ok:
        flash("You can review a product after it is delivered.", "error")
        return redirect(url_for("product", pid=pid))
    rating = max(1, min(5, int(request.form.get("rating", 5) or 5)))
    comment = request.form.get("comment", "").strip()[:400]
    x("""INSERT INTO reviews(product_id,buyer_id,rating,comment,created_at) VALUES(?,?,?,?,?)
         ON CONFLICT(product_id,buyer_id) DO UPDATE SET rating=excluded.rating, comment=excluded.comment""",
      (pid, g.user["id"], rating, comment, now()))
    flash("Thanks for your review.", "success")
    return redirect(url_for("product", pid=pid))


# ---------------------------------------------------------------------- cart
def cart_lines():
    cart, lines, total = session.get("cart", {}), [], 0
    for pid, qty in cart.items():
        p = q(PRODUCT_SELECT + " WHERE p.id=?", (int(pid),), one=True)
        if not p or p["status"] != "active":
            continue
        sub = p["price"] * qty
        total += sub
        lines.append(dict(p=p, qty=qty, sub=sub))
    return lines, total


@app.route("/cart")
@role_required()
def cart():
    lines, total = cart_lines()
    return render_template("cart.html", lines=lines, total=total)


@app.route("/cart/add/<int:pid>", methods=["POST"])
@role_required()
def cart_add(pid):
    p = q("SELECT * FROM products WHERE id=? AND status='active'", (pid,), one=True)
    if not p:
        abort(404)
    if p["seller_id"] == g.user["id"]:
        flash("You cannot buy your own produce.", "error")
        return redirect(url_for("product", pid=pid))
    try:
        qty = max(1, int(request.form.get("qty", 1)))
    except ValueError:
        qty = 1
    cart = session.get("cart", {})
    new_qty = cart.get(str(pid), 0) + qty
    if new_qty > p["quantity"]:
        new_qty = p["quantity"]
        flash(f"Only {p['quantity']} {p['unit']} available. Cart updated to the maximum.", "info")
    else:
        flash(f"{p['name']} added to cart.", "success")
    cart[str(pid)] = new_qty
    session["cart"] = cart
    if request.form.get("buy_now"):
        return redirect(url_for("cart"))
    return redirect(request.referrer or url_for("shop"))


@app.route("/cart/update/<int:pid>", methods=["POST"])
@role_required()
def cart_update(pid):
    cart = session.get("cart", {})
    p = q("SELECT quantity FROM products WHERE id=?", (pid,), one=True)
    try:
        qty = int(request.form.get("qty", 1))
    except ValueError:
        qty = 1
    if qty <= 0 or not p:
        cart.pop(str(pid), None)
    else:
        cart[str(pid)] = min(qty, p["quantity"])
    session["cart"] = cart
    return redirect(url_for("cart"))


@app.route("/cart/remove/<int:pid>", methods=["POST"])
@role_required()
def cart_remove(pid):
    cart = session.get("cart", {})
    cart.pop(str(pid), None)
    session["cart"] = cart
    return redirect(url_for("cart"))


@app.route("/checkout", methods=["GET", "POST"])
@role_required()
def checkout():
    lines, total = cart_lines()
    if not lines:
        flash("Your cart is empty. Add something from the market first.", "info")
        return redirect(url_for("shop"))
    if g.user["cod_blocked"]:
        flash("Cash on delivery is switched off for your account. Contact the admin.", "error")
        return redirect(url_for("cart"))
    if request.method == "POST":
        address = request.form.get("address", "").strip()
        phone = "".join(c for c in request.form.get("phone", "") if c.isdigit())
        note = request.form.get("note", "").strip()[:300]
        if len(address) < 10 or len(phone) != 10:
            flash("Enter a full delivery address and a 10 digit phone number.", "error")
            return render_template("checkout.html", lines=lines, total=total, form=request.form), 400
        db = get_db()
        by_seller = {}
        for ln in lines:
            if ln["p"]["seller_id"] == g.user["id"]:
                flash("Remove your own produce from the cart.", "error")
                return redirect(url_for("cart"))
            by_seller.setdefault(ln["p"]["seller_id"], []).append(ln)
        try:
            db.execute("BEGIN")
            placed = []
            for seller_id, group in by_seller.items():
                sub_total = 0
                for ln in group:
                    cur = db.execute("UPDATE products SET quantity=quantity-? WHERE id=? AND quantity>=?",
                                     (ln["qty"], ln["p"]["id"], ln["qty"]))
                    if cur.rowcount == 0:
                        raise ValueError(f"{ln['p']['name']} just ran low on stock. Update your cart.")
                    sub_total += ln["sub"]
                oid = db.execute("""INSERT INTO orders(buyer_id,seller_id,total,address,phone,note,created_at)
                                    VALUES(?,?,?,?,?,?,?)""",
                                 (g.user["id"], seller_id, sub_total, address, phone, note, now())).lastrowid
                for ln in group:
                    db.execute("""INSERT INTO order_items(order_id,product_id,name,emoji,price,qty,unit)
                                  VALUES(?,?,?,?,?,?,?)""",
                               (oid, ln["p"]["id"], ln["p"]["name"], ln["p"]["emoji"], ln["p"]["price"],
                                ln["qty"], ln["p"]["unit"]))
                placed.append(oid)
            db.commit()
        except ValueError as e:
            db.rollback()
            flash(str(e), "error")
            return redirect(url_for("cart"))
        session["cart"] = {}
        flash("Order placed. Pay cash to the farmer when it arrives.", "success")
        return redirect(url_for("order_detail", oid=placed[0]) if len(placed) == 1 else url_for("orders"))
    return render_template("checkout.html", lines=lines, total=total,
                           form={"address": g.user["address"] or "", "phone": g.user["phone"] or ""})


# -------------------------------------------------------------------- orders
def order_items_for(oid):
    return q("SELECT * FROM order_items WHERE order_id=?", (oid,))


@app.route("/orders")
@role_required()
def orders():
    rows = q("""SELECT o.*, s.name AS seller_name FROM orders o JOIN users s ON s.id=o.seller_id
                WHERE o.buyer_id=? ORDER BY o.created_at DESC""", (g.user["id"],))
    data = [dict(o=o, lines=order_items_for(o["id"])) for o in rows]
    return render_template("orders.html", data=data)


@app.route("/orders/<int:oid>")
@role_required()
def order_detail(oid):
    o = q("""SELECT o.*, s.name AS seller_name, s.phone AS seller_phone, b.name AS buyer_name
             FROM orders o JOIN users s ON s.id=o.seller_id JOIN users b ON b.id=o.buyer_id WHERE o.id=?""",
          (oid,), one=True)
    if not o:
        abort(404)
    if g.user["role"] != "admin" and g.user["id"] not in (o["buyer_id"], o["seller_id"]):
        abort(403)
    return render_template("order_detail.html", o=o, items=order_items_for(oid),
                           can_manage=g.user["role"] == "admin" or g.user["id"] == o["seller_id"],
                           can_cancel=g.user["id"] == o["buyer_id"] and o["status"] in ("Placed", "Confirmed"))


def _set_status(oid, new):
    o = q("SELECT * FROM orders WHERE id=?", (oid,), one=True)
    if o["status"] in ("Delivered", "Cancelled"):
        return False
    if new == "Cancelled":
        for it in order_items_for(oid):
            x("UPDATE products SET quantity=quantity+? WHERE id=?", (it["qty"], it["product_id"]))
        x("UPDATE orders SET status='Cancelled', payment_status='Not required' WHERE id=?", (oid,))
    elif new in ORDER_FLOW:
        pay = "Collected" if new == "Delivered" else "Pending"
        x("UPDATE orders SET status=?, payment_status=? WHERE id=?", (new, pay, oid))
    else:
        return False
    return True


@app.route("/orders/<int:oid>/status", methods=["POST"])
@role_required()
def order_status(oid):
    o = q("SELECT * FROM orders WHERE id=?", (oid,), one=True)
    if not o:
        abort(404)
    new = request.form.get("status", "")
    is_seller = g.user["role"] == "admin" or g.user["id"] == o["seller_id"]
    is_buyer_cancel = g.user["id"] == o["buyer_id"] and new == "Cancelled" and o["status"] in ("Placed", "Confirmed")
    if not (is_seller or is_buyer_cancel):
        abort(403)
    if _set_status(oid, new):
        flash(f"Order #{oid} is now {new}.", "success")
    else:
        flash("That order can no longer change.", "error")
    return redirect(safe_next(request.form.get("next")) or url_for("order_detail", oid=oid))


# ---------------------------------------------------------------------- chat
@app.route("/chat")
@app.route("/chat/<int:uid>")
@role_required()
def chat(uid=None):
    threads = q("""
      SELECT u.id, u.name, u.role, u.village,
        (SELECT body FROM messages m WHERE (m.sender_id=u.id AND m.receiver_id=:me) OR (m.sender_id=:me AND m.receiver_id=u.id) ORDER BY m.id DESC LIMIT 1) AS last_body,
        (SELECT created_at FROM messages m WHERE (m.sender_id=u.id AND m.receiver_id=:me) OR (m.sender_id=:me AND m.receiver_id=u.id) ORDER BY m.id DESC LIMIT 1) AS last_at,
        (SELECT COUNT(*) FROM messages m WHERE m.sender_id=u.id AND m.receiver_id=:me AND m.is_read=0) AS unread
      FROM users u WHERE u.id IN (
        SELECT receiver_id FROM messages WHERE sender_id=:me UNION SELECT sender_id FROM messages WHERE receiver_id=:me)
      ORDER BY last_at DESC""", {"me": g.user["id"]})
    other = None
    product_ctx = None
    if uid:
        other = q("SELECT id,name,role,village FROM users WHERE id=? AND status!='blocked'", (uid,), one=True)
        if not other or other["id"] == g.user["id"]:
            abort(404)
        pid = request.args.get("product", type=int)
        if pid:
            product_ctx = q("SELECT id,name,emoji,price,unit FROM products WHERE id=?", (pid,), one=True)
    return render_template("chat.html", threads=threads, other=other, product_ctx=product_ctx)


@app.route("/api/chat/<int:uid>", methods=["GET", "POST"])
@role_required()
def chat_api(uid):
    me = g.user["id"]
    other = q("SELECT id FROM users WHERE id=? AND status!='blocked'", (uid,), one=True)
    if not other or uid == me:
        abort(404)
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        body = str(data.get("body", "")).strip()[:500]
        if not body:
            return jsonify(error="Type a message first."), 400
        x("INSERT INTO messages(sender_id,receiver_id,product_id,body,created_at) VALUES(?,?,?,?,?)",
          (me, uid, data.get("product_id") or None, body, now()))
    after = request.args.get("after", 0, type=int)
    rows = q("""SELECT id, sender_id, body, created_at, product_id FROM messages
                WHERE id>? AND ((sender_id=? AND receiver_id=?) OR (sender_id=? AND receiver_id=?)) ORDER BY id""",
             (after, me, uid, uid, me))
    x("UPDATE messages SET is_read=1 WHERE sender_id=? AND receiver_id=?", (uid, me))
    return jsonify(me=me, messages=[dict(r) | {"mine": r["sender_id"] == me} for r in rows])


# -------------------------------------------------------------------- farmer
def image_ok(file):
    if not file or not file.filename:
        return False
    ext = file.filename.rsplit(".", 1)[-1].lower()
    if ext not in ALLOWED_IMG:
        return False
    try:
        Image.open(file.stream).verify()
        file.stream.seek(0)
        return True
    except Exception:
        file.stream.seek(0)
        return False


def save_image(file):
    ext = file.filename.rsplit(".", 1)[-1].lower()
    name = f"{uuid.uuid4().hex}.{ext}"
    img = Image.open(file.stream).convert("RGB")
    img.thumbnail((1200, 1200))
    img.save(os.path.join(UPLOAD_DIR, secure_filename(name)), quality=88)
    return name


@app.route("/farmer")
@role_required("farmer")
def farmer_dashboard():
    me = g.user["id"]
    stats = q("""SELECT COUNT(*) orders,
        COALESCE(SUM(CASE WHEN status='Placed' THEN 1 ELSE 0 END),0) new_orders,
        COALESCE(SUM(CASE WHEN payment_status='Collected' THEN total ELSE 0 END),0) collected,
        COALESCE(SUM(CASE WHEN status NOT IN ('Delivered','Cancelled') THEN total ELSE 0 END),0) pending_cod
        FROM orders WHERE seller_id=?""", (me,), one=True)
    products = q("SELECT * FROM products WHERE seller_id=? ORDER BY created_at DESC", (me,))
    recent = q("""SELECT o.*, b.name AS buyer_name FROM orders o JOIN users b ON b.id=o.buyer_id
                  WHERE o.seller_id=? ORDER BY o.created_at DESC LIMIT 6""", (me,))
    days = []
    for i in range(6, -1, -1):
        d = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
        total = q("SELECT COALESCE(SUM(total),0) t FROM orders WHERE seller_id=? AND status!='Cancelled' AND substr(created_at,1,10)=?",
                  (me, d), one=True)["t"]
        days.append(dict(label=datetime.strptime(d, "%Y-%m-%d").strftime("%a"), value=total))
    return render_template("farmer/dashboard.html", stats=stats, products=products, recent=recent,
                           days=days, low=[p for p in products if p["quantity"] <= 10 and p["status"] == "active"])


@app.route("/farmer/products")
@role_required("farmer")
def farmer_products():
    items = q("SELECT * FROM products WHERE seller_id=? ORDER BY created_at DESC", (g.user["id"],))
    return render_template("farmer/products.html", items=items)


def _product_form(existing=None):
    f = request.form
    errors = []
    crop = f.get("crop", "")
    if crop == "__other":
        name = f.get("custom_name", "").strip()[:60]
        category = f.get("category") if f.get("category") in CATEGORIES else "Vegetables"
        unit = f.get("unit") if f.get("unit") in UNITS else "kg"
    elif crop in CROPS:
        name, category, unit = crop, CROPS[crop]["cat"], f.get("unit") if f.get("unit") in UNITS else CROPS[crop]["unit"]
    else:
        name = category = unit = ""
    if not name:
        errors.append("Choose a crop or type its name.")
    try:
        price_v = float(f.get("price", 0))
        qty = int(float(f.get("quantity", 0)))
        if price_v <= 0 or qty < 1:
            raise ValueError
    except ValueError:
        errors.append("Price must be above 0 and quantity at least 1.")
        price_v, qty = 0, 0
    grade = f.get("grade") if f.get("grade") in GRADES else "B"
    image = existing["image"] if existing else None
    score = existing["quality_score"] if existing else None
    verified = existing["ai_verified"] if existing else 0
    file = request.files.get("image")
    if file and file.filename:
        if not image_ok(file):
            errors.append("Upload a real photo in JPG, PNG or WEBP format (max 6 MB).")
        else:
            res = quality.analyze_quality(file.stream)
            file.stream.seek(0)
            grade, score, verified = res["grade"], res["score"], 1
            image = save_image(file)
    data = dict(name=name, category=category, unit=unit, price=price_v, quantity=qty, grade=grade,
                quality_score=score, ai_verified=verified, image=image,
                description=f.get("description", "").strip()[:600], organic=1 if f.get("organic") else 0,
                location=f.get("location", "").strip()[:80] or (g.user["village"] or ""),
                emoji=emoji_for(name, category))
    return data, errors


@app.route("/farmer/products/new", methods=["GET", "POST"])
@role_required("farmer")
def product_new():
    if g.user["status"] != "active":
        flash("Your farmer account is waiting for admin approval. You can list produce once approved.", "info")
        return redirect(url_for("farmer_dashboard"))
    if request.method == "POST":
        data, errors = _product_form()
        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("farmer/product_form.html", p=None, form=request.form,
                                   crops=CROPS, units=UNITS, grades=GRADES), 400
        x("""INSERT INTO products(seller_id,name,category,description,price,unit,quantity,grade,quality_score,
             ai_verified,organic,location,image,emoji,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
          (g.user["id"], data["name"], data["category"], data["description"], data["price"], data["unit"],
           data["quantity"], data["grade"], data["quality_score"], data["ai_verified"], data["organic"],
           data["location"], data["image"], data["emoji"], now()))
        flash(f"{data['name']} is now listed on the market.", "success")
        return redirect(url_for("farmer_products"))
    return render_template("farmer/product_form.html", p=None, form={}, crops=CROPS, units=UNITS, grades=GRADES)


@app.route("/farmer/products/<int:pid>/edit", methods=["GET", "POST"])
@role_required("farmer")
def product_edit(pid):
    p = q("SELECT * FROM products WHERE id=?", (pid,), one=True)
    if not p:
        abort(404)
    if g.user["role"] != "admin" and p["seller_id"] != g.user["id"]:
        abort(403)
    if request.method == "POST":
        data, errors = _product_form(p)
        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("farmer/product_form.html", p=p, form=request.form,
                                   crops=CROPS, units=UNITS, grades=GRADES), 400
        x("""UPDATE products SET name=?,category=?,description=?,price=?,unit=?,quantity=?,grade=?,quality_score=?,
             ai_verified=?,organic=?,location=?,image=?,emoji=? WHERE id=?""",
          (data["name"], data["category"], data["description"], data["price"], data["unit"], data["quantity"],
           data["grade"], data["quality_score"], data["ai_verified"], data["organic"], data["location"],
           data["image"], data["emoji"], pid))
        flash("Listing updated.", "success")
        return redirect(safe_next(request.form.get("next")) or url_for("farmer_products"))
    form = dict(p) | {"crop": p["name"] if p["name"] in CROPS else "__other", "custom_name": p["name"]}
    return render_template("farmer/product_form.html", p=p, form=form, crops=CROPS, units=UNITS, grades=GRADES)


@app.route("/farmer/products/<int:pid>/toggle", methods=["POST"])
@role_required("farmer")
def product_toggle(pid):
    p = q("SELECT * FROM products WHERE id=?", (pid,), one=True)
    if not p:
        abort(404)
    if g.user["role"] != "admin" and p["seller_id"] != g.user["id"]:
        abort(403)
    new = "hidden" if p["status"] == "active" else "active"
    x("UPDATE products SET status=? WHERE id=?", (new, pid))
    flash(f"{p['name']} is now {'hidden from' if new == 'hidden' else 'visible on'} the market.", "success")
    return redirect(safe_next(request.form.get("next")) or url_for("farmer_products"))


@app.route("/farmer/products/<int:pid>/delete", methods=["POST"])
@role_required("farmer")
def product_delete(pid):
    p = q("SELECT * FROM products WHERE id=?", (pid,), one=True)
    if not p:
        abort(404)
    if g.user["role"] != "admin" and p["seller_id"] != g.user["id"]:
        abort(403)
    has_orders = q("SELECT 1 FROM order_items WHERE product_id=?", (pid,), one=True)
    if has_orders:
        x("UPDATE products SET status='removed', quantity=0 WHERE id=?", (pid,))
    else:
        x("DELETE FROM reviews WHERE product_id=?", (pid,))
        x("DELETE FROM products WHERE id=?", (pid,))
    flash(f"{p['name']} was removed.", "success")
    return redirect(safe_next(request.form.get("next")) or url_for("farmer_products"))


@app.route("/farmer/orders")
@role_required("farmer")
def farmer_orders():
    status = request.args.get("status", "")
    sql = """SELECT o.*, b.name AS buyer_name, b.phone AS buyer_phone FROM orders o
             JOIN users b ON b.id=o.buyer_id WHERE o.seller_id=?"""
    args = [g.user["id"]]
    if status in ORDER_FLOW + ["Cancelled"]:
        sql += " AND o.status=?"
        args.append(status)
    rows = q(sql + " ORDER BY o.created_at DESC", args)
    data = [dict(o=o, lines=order_items_for(o["id"])) for o in rows]
    return render_template("farmer/orders.html", data=data, status=status)


# ------------------------------------------------------------------------ AI
@app.route("/api/ai/price", methods=["POST"])
@role_required("farmer")
def api_price():
    d = request.get_json(silent=True) or {}
    res = price.suggest_price(d.get("crop", ""), d.get("grade", "B"), bool(d.get("organic")))
    if not res:
        return jsonify(error="Price suggestions are available for the listed crops. Enter your own price for other items."), 404
    return jsonify(res)


@app.route("/api/ai/grade", methods=["POST"])
@role_required("farmer")
def api_grade():
    file = request.files.get("image")
    if not image_ok(file):
        return jsonify(error="Upload a real photo in JPG, PNG or WEBP format."), 400
    return jsonify(quality.analyze_quality(file.stream))


@app.route("/api/ai/chat", methods=["POST"])
def api_chat():
    d = request.get_json(silent=True) or {}
    lang = session.get("lang") or (g.user["language"] if g.user else "en")
    return jsonify(chatbot.reply(d.get("message", ""), lang))


@app.route("/ai/crop-doctor", methods=["GET", "POST"])
def crop_doctor():
    result, preview = None, None
    if request.method == "POST":
        file = request.files.get("image")
        if not image_ok(file):
            flash("Upload a clear photo of a leaf in JPG, PNG or WEBP format.", "error")
        else:
            lang = session.get("lang") or (g.user["language"] if g.user else "en")
            result = disease.diagnose(file.stream, request.form.get("crop") or None, lang)
            file.stream.seek(0)
            import base64
            from io import BytesIO
            img = Image.open(file.stream).convert("RGB")
            img.thumbnail((480, 480))
            buf = BytesIO()
            img.save(buf, "JPEG", quality=80)
            preview = "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
    return render_template("crop_doctor.html", result=result, preview=preview, crops=sorted(CROPS))


@app.route("/ai/forecast")
@role_required("farmer")
def demand_forecast():
    since = (datetime.now() - timedelta(days=60)).strftime("%Y-%m-%d")
    rows = q("""SELECT i.name, i.qty FROM order_items i JOIN orders o ON o.id=i.order_id
                WHERE o.status!='Cancelled' AND substr(o.created_at,1,10)>=?""", (since,))
    data = forecast.forecast([(r["name"], r["qty"]) for r in rows])
    return render_template("forecast.html", fc=data)


# --------------------------------------------------------------------- admin
@app.route("/admin")
@role_required("admin")
def admin_dashboard():
    users = {r["role"]: r["c"] for r in q("SELECT role, COUNT(*) c FROM users GROUP BY role")}
    stats = q("""SELECT COUNT(*) orders,
        COALESCE(SUM(CASE WHEN status!='Cancelled' THEN total ELSE 0 END),0) gmv,
        COALESCE(SUM(CASE WHEN payment_status='Collected' THEN total ELSE 0 END),0) collected,
        COALESCE(SUM(CASE WHEN status NOT IN ('Delivered','Cancelled') THEN total ELSE 0 END),0) pending
        FROM orders""", one=True)
    pending_farmers = q("SELECT * FROM users WHERE role='farmer' AND status='pending' ORDER BY created_at")
    by_status = {r["status"]: r["c"] for r in q("SELECT status, COUNT(*) c FROM orders GROUP BY status")}
    top = q("""SELECT i.name, i.emoji, SUM(i.qty*i.price) revenue, SUM(i.qty) qty FROM order_items i
               JOIN orders o ON o.id=i.order_id WHERE o.status!='Cancelled' GROUP BY i.name ORDER BY revenue DESC LIMIT 5""")
    days = []
    for i in range(13, -1, -1):
        d = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
        c = q("SELECT COUNT(*) c FROM orders WHERE substr(created_at,1,10)=?", (d,), one=True)["c"]
        days.append(dict(label=datetime.strptime(d, "%Y-%m-%d").strftime("%d"), value=c))
    cats = q("SELECT category, COUNT(*) c FROM products WHERE status='active' GROUP BY category ORDER BY c DESC")
    products = q("SELECT COUNT(*) c FROM products WHERE status='active'", one=True)["c"]
    recent = q("""SELECT o.*, b.name AS buyer_name, s.name AS seller_name FROM orders o
                  JOIN users b ON b.id=o.buyer_id JOIN users s ON s.id=o.seller_id ORDER BY o.created_at DESC LIMIT 6""")
    return render_template("admin/dashboard.html", users=users, stats=stats, pending_farmers=pending_farmers,
                           by_status=by_status, top=top, days=days, cats=cats, products=products, recent=recent)


@app.route("/admin/users")
@role_required("admin")
def admin_users():
    role = request.args.get("role", "")
    status = request.args.get("status", "")
    sql, args = "SELECT * FROM users WHERE 1=1", []
    if role in ("admin", "farmer", "buyer"):
        sql += " AND role=?"
        args.append(role)
    if status in ("active", "pending", "blocked"):
        sql += " AND status=?"
        args.append(status)
    rows = q(sql + " ORDER BY created_at DESC", args)
    return render_template("admin/users.html", rows=rows, role=role, status=status)


@app.route("/admin/users/new", methods=["GET", "POST"])
@role_required("admin")
def admin_user_new():
    if request.method == "POST":
        f = request.form
        username = f.get("username", "").strip().lower()
        role = f.get("role") if f.get("role") in ("admin", "farmer", "buyer") else "buyer"
        phone = "".join(c for c in f.get("phone", "") if c.isdigit())
        if len(username) < 3 or len(f.get("password", "")) < 6 or not f.get("name", "").strip():
            flash("Name, a username of 3+ characters and a password of 6+ characters are required.", "error")
        elif q("SELECT 1 FROM users WHERE username=?", (username,), one=True):
            flash("That username is taken.", "error")
        else:
            x("""INSERT INTO users(username,password_hash,name,role,phone,village,address,language,status,created_at)
                 VALUES(?,?,?,?,?,?,?,?,?,?)""",
              (username, generate_password_hash(f["password"]), f["name"].strip(), role, phone,
               f.get("village", "").strip(), f.get("village", "").strip(), "en", "active", now()))
            flash(f"{role.title()} account '{username}' created.", "success")
            return redirect(url_for("admin_users"))
        return render_template("admin/user_form.html", form=f), 400
    return render_template("admin/user_form.html", form={})


@app.route("/admin/users/<int:uid>/<action>", methods=["POST"])
@role_required("admin")
def admin_user_action(uid, action):
    u = q("SELECT * FROM users WHERE id=?", (uid,), one=True)
    if not u:
        abort(404)
    if u["id"] == g.user["id"] and action in ("block", "cod_block"):
        flash("You cannot block your own account.", "error")
        return redirect(request.referrer or url_for("admin_users"))
    updates = {"approve": ("status", "active", f"{u['name']} approved."),
               "block": ("status", "blocked", f"{u['name']} is blocked."),
               "unblock": ("status", "active", f"{u['name']} is active again."),
               "cod_block": ("cod_blocked", 1, f"Cash on delivery is off for {u['name']}."),
               "cod_unblock": ("cod_blocked", 0, f"Cash on delivery is on for {u['name']}.")}
    if action not in updates:
        abort(404)
    col, val, msg = updates[action]
    x(f"UPDATE users SET {col}=? WHERE id=?", (val, uid))
    flash(msg, "success")
    return redirect(request.referrer or url_for("admin_users"))


@app.route("/admin/products")
@role_required("admin")
def admin_products():
    rows = q(PRODUCT_SELECT + " ORDER BY p.created_at DESC")
    return render_template("admin/products.html", rows=rows)


@app.route("/admin/orders")
@role_required("admin")
def admin_orders():
    status = request.args.get("status", "")
    sql = """SELECT o.*, b.name AS buyer_name, s.name AS seller_name FROM orders o
             JOIN users b ON b.id=o.buyer_id JOIN users s ON s.id=o.seller_id"""
    args = []
    if status in ORDER_FLOW + ["Cancelled"]:
        sql += " WHERE o.status=?"
        args.append(status)
    rows = q(sql + " ORDER BY o.created_at DESC", args)
    data = [dict(o=o, lines=order_items_for(o["id"])) for o in rows]
    return render_template("admin/orders.html", data=data, status=status)


# ------------------------------------------------------------------- errors
@app.errorhandler(400)
def bad(_):
    return render_template("error.html", code=400, title="That request did not go through",
                           msg="Your session expired or the form was incomplete. Go back, refresh the page and try again."), 400


@app.errorhandler(403)
def forbidden(_):
    return render_template("error.html", code=403, title="This area is not for your account",
                           msg="Your role does not include this page. Use the menu to go back to your own area."), 403


@app.errorhandler(404)
def missing(_):
    return render_template("error.html", code=404, title="We could not find that page",
                           msg="The link may be old or the item was removed."), 404


@app.errorhandler(413)
def too_big(_):
    return render_template("error.html", code=413, title="That file is too large",
                           msg="Upload a photo smaller than 6 MB."), 413


# --------------------------------------------------------------------- seed
def init_db():
    # RESET_DB=1 wipes the database and uploaded photos on every start,
    # so each redeploy begins with fresh demo data.
    if os.environ.get("RESET_DB") == "1":
        if os.path.exists(DB_PATH):
            os.remove(DB_PATH)
        for name in os.listdir(UPLOAD_DIR):
            if name != ".gitkeep":
                try:
                    os.remove(os.path.join(UPLOAD_DIR, name))
                except OSError:
                    pass
    db = sqlite3.connect(DB_PATH)
    db.executescript(SCHEMA)
    db.commit()
    if db.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
        from seed import seed
        seed(db)
    db.close()


init_db()
price.ensure_model()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"\n  KisanConnect AI is running at http://127.0.0.1:{port}\n")
    app.run(host="127.0.0.1", port=port, debug=bool(os.environ.get("FLASK_DEBUG")))

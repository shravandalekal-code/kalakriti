import os
import sqlite3
import uuid
import csv
import io
import math
from datetime import datetime
from functools import wraps
from flask import Flask, request, jsonify, send_from_directory, Response
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
cors_origins = [origin.strip() for origin in os.environ.get("CORS_ORIGINS", "*").split(",") if origin.strip()]
CORS(app, origins=cors_origins)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("DATABASE_PATH", os.path.join(BASE_DIR, "artisan_marketplace.db"))
UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER", os.path.join(BASE_DIR, "static", "uploads"))
BACKEND_PUBLIC_URL = os.environ.get("BACKEND_PUBLIC_URL", "http://127.0.0.1:5000").rstrip("/")
os.makedirs(os.path.dirname(DB_PATH) or BASE_DIR, exist_ok=True)
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif"}
ACTIVE_TOKENS = {}  # token -> {"user_id": int, "role": str}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def uploaded_image_url(filename):
    return f"{BACKEND_PUBLIC_URL}/uploads/{filename}"


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    cur = conn.cursor()

    # Users table: roles -> 'admin', 'artisan', 'customer'
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('admin', 'artisan', 'customer')),
            bio TEXT DEFAULT '',
            location TEXT DEFAULT '',
            craft_specialty TEXT DEFAULT '',
            phone TEXT DEFAULT '',
            is_active INTEGER DEFAULT 1,
            created_at TEXT NOT NULL
        )
    """)

    # Products table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            artisan_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            category TEXT NOT NULL,
            description TEXT NOT NULL,
            price REAL NOT NULL,
            stock INTEGER NOT NULL DEFAULT 1,
            is_available INTEGER NOT NULL DEFAULT 1,
            image_url TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            FOREIGN KEY (artisan_id) REFERENCES users(id)
        )
    """)

    # Orders table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            total_amount REAL NOT NULL,
            shipping_address TEXT NOT NULL,
            payment_method TEXT DEFAULT 'Cash on Delivery',
            status TEXT NOT NULL DEFAULT 'Pending',
            created_at TEXT NOT NULL,
            FOREIGN KEY (customer_id) REFERENCES users(id)
        )
    """)

    # Order Items table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            artisan_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            unit_price REAL NOT NULL,
            FOREIGN KEY (order_id) REFERENCES orders(id),
            FOREIGN KEY (product_id) REFERENCES products(id)
        )
    """)

    # Seed only the platform admin in a new database; public users register themselves.
    cur.execute("SELECT COUNT(*) FROM users")
    if cur.fetchone()[0] == 0:
        admin_password = os.environ.get("KALAKRITI_ADMIN_PASSWORD")
        if not admin_password:
            conn.close()
            raise RuntimeError("Set KALAKRITI_ADMIN_PASSWORD before initializing a new database.")

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cur.execute("""
            INSERT INTO users (name, email, password_hash, role, bio, location, craft_specialty, phone, is_active, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, ("Platform Admin", "admin@kalakriti.in", generate_password_hash(admin_password),
              "admin", "System Administrator for Local Artisan & Handcraft Marketplace",
              "Bengaluru, Karnataka", "Administration", "9876543210", 1, now))

    conn.commit()
    conn.close()


def auth_required(roles=None):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            auth_header = request.headers.get("Authorization", "")
            token = auth_header.replace("Bearer ", "").strip()
            if not token or token not in ACTIVE_TOKENS:
                return jsonify({"error": "Unauthorized. Please log in."}), 401
            session_info = ACTIVE_TOKENS[token]
            if roles and session_info["role"] not in roles:
                return jsonify({"error": "Forbidden. Insufficient role permissions."}), 403
            request.user_id = session_info["user_id"]
            request.user_role = session_info["role"]
            return fn(*args, **kwargs)
        return wrapper
    return decorator


# Serve uploaded product images
@app.route("/uploads/<path:filename>")
def serve_upload(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)


# -------------------- AUTHENTICATION FLOW (Admin, Artisan, Customer) --------------------
@app.route("/api/auth/register", methods=["POST"])
def register():
    data = request.get_json() or {}
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    role = (data.get("role") or "customer").strip().lower()
    location = (data.get("location") or "").strip()
    craft_specialty = (data.get("craft_specialty") or "").strip()
    bio = (data.get("bio") or "").strip()
    phone = (data.get("phone") or "").strip()

    if role not in ("artisan", "customer"):
        return jsonify({"error": "Public registration is only available for Customer or Artisan roles."}), 400
    if not name or not email or len(password) < 4:
        return jsonify({"error": "Name, valid email, and password (min 4 chars) are required."}), 400

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id FROM users WHERE email = ?", (email,))
    if cur.fetchone():
        conn.close()
        return jsonify({"error": "Email is already registered."}), 409

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cur.execute("""
        INSERT INTO users (name, email, password_hash, role, bio, location, craft_specialty, phone, is_active, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
    """, (name, email, generate_password_hash(password), role, bio, location, craft_specialty, phone, now))
    user_id = cur.lastrowid
    conn.commit()
    conn.close()

    token = str(uuid.uuid4())
    ACTIVE_TOKENS[token] = {"user_id": user_id, "role": role}
    return jsonify({
        "message": "Registration successful",
        "token": token,
        "user": {"id": user_id, "name": name, "email": email, "role": role, "location": location, "craft_specialty": craft_specialty}
    }), 201


@app.route("/api/auth/login", methods=["POST"])
def login():
    data = request.get_json() or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    expected_portal = (data.get("portal") or "").strip().lower()  # 'admin' or 'public'

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE email = ?", (email,))
    user = cur.fetchone()
    conn.close()

    if not user or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "Invalid credentials. Please check email and password."}), 401

    if user["is_active"] == 0:
        return jsonify({"error": "Your account has been deactivated by the Administrator."}), 403

    if expected_portal == "admin" and user["role"] != "admin":
        return jsonify({"error": "Access Denied. Only Administrators can sign in via the Admin Portal."}), 403

    if expected_portal == "artisan" and user["role"] != "artisan":
        return jsonify({"error": "Access Denied. Only Artisans can sign in via the Artisan Portal."}), 403

    if expected_portal == "public" and user["role"] != "customer":
        return jsonify({"error": "Access Denied. Only Customers can sign in through the Public Login Portal."}), 403

    token = str(uuid.uuid4())
    ACTIVE_TOKENS[token] = {"user_id": user["id"], "role": user["role"]}

    return jsonify({
        "message": "Login successful",
        "token": token,
        "user": {
            "id": user["id"],
            "name": user["name"],
            "email": user["email"],
            "role": user["role"],
            "bio": user["bio"],
            "location": user["location"],
            "craft_specialty": user["craft_specialty"],
            "phone": user["phone"]
        }
    })


@app.route("/api/auth/logout", methods=["POST"])
def logout():
    token = request.headers.get("Authorization", "").replace("Bearer ", "").strip()
    ACTIVE_TOKENS.pop(token, None)
    return jsonify({"message": "Logged out successfully"})


# -------------------- PUBLIC PRODUCT BROWSING & SEARCH / FILTER --------------------
@app.route("/api/products", methods=["GET"])
def get_products():
    search = (request.args.get("search") or "").strip().lower()
    category = (request.args.get("category") or "").strip()
    min_price = request.args.get("min_price", type=float)
    max_price = request.args.get("max_price", type=float)
    include_unavailable = request.args.get("all", "0") == "1"

    conn = get_db()
    cur = conn.cursor()
    query = """
        SELECT p.*, u.name AS artisan_name, u.location AS artisan_location, u.craft_specialty
        FROM products p
        JOIN users u ON p.artisan_id = u.id
        WHERE u.is_active = 1
    """
    params = []
    if not include_unavailable:
        query += " AND p.is_available = 1 AND p.stock > 0"
    if category and category.lower() != "all":
        query += " AND LOWER(p.category) = ?"
        params.append(category.lower())
    if search:
        query += " AND (LOWER(p.title) LIKE ? OR LOWER(p.description) LIKE ? OR LOWER(u.name) LIKE ? OR LOWER(u.location) LIKE ?)"
        like_term = f"%{search}%"
        params.extend([like_term, like_term, like_term, like_term])
    if min_price is not None:
        query += " AND p.price >= ?"
        params.append(min_price)
    if max_price is not None:
        query += " AND p.price <= ?"
        params.append(max_price)

    query += " ORDER BY p.created_at DESC"
    cur.execute(query, params)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return jsonify(rows)


@app.route("/api/products/<int:product_id>", methods=["GET"])
def get_product_detail(product_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT p.*, u.name AS artisan_name, u.location AS artisan_location,
               u.craft_specialty, u.bio AS artisan_bio
        FROM products p
        JOIN users u ON p.artisan_id = u.id
        WHERE p.id = ?
    """, (product_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return jsonify({"error": "Product not found"}), 404
    return jsonify(dict(row))


# -------------------- ARTISAN FLOW: PROFILE & PRODUCT MANAGEMENT --------------------
@app.route("/api/artisan/profile", methods=["GET", "PUT"])
@auth_required(roles=["artisan"])
def artisan_profile():
    conn = get_db()
    cur = conn.cursor()
    if request.method == "GET":
        cur.execute("SELECT id, name, email, role, bio, location, craft_specialty, phone FROM users WHERE id = ?", (request.user_id,))
        user = cur.fetchone()
        conn.close()
        return jsonify(dict(user))

    data = request.get_json() or {}
    name = (data.get("name") or "").strip()
    bio = (data.get("bio") or "").strip()
    location = (data.get("location") or "").strip()
    craft_specialty = (data.get("craft_specialty") or "").strip()
    phone = (data.get("phone") or "").strip()

    cur.execute("""
        UPDATE users
        SET name = COALESCE(NULLIF(?, ''), name),
            bio = ?,
            location = ?,
            craft_specialty = ?,
            phone = ?
        WHERE id = ?
    """, (name, bio, location, craft_specialty, phone, request.user_id))
    conn.commit()
    cur.execute("SELECT id, name, email, role, bio, location, craft_specialty, phone FROM users WHERE id = ?", (request.user_id,))
    updated = dict(cur.fetchone())
    conn.close()
    return jsonify({"message": "Artisan profile updated", "user": updated})


@app.route("/api/artisan/products", methods=["GET", "POST"])
@auth_required(roles=["artisan"])
def artisan_products():
    conn = get_db()
    cur = conn.cursor()
    if request.method == "GET":
        cur.execute("SELECT * FROM products WHERE artisan_id = ? ORDER BY created_at DESC", (request.user_id,))
        items = [dict(r) for r in cur.fetchall()]
        conn.close()
        return jsonify(items)

    # Supports multipart/form-data (with image upload) or JSON
    if request.content_type and "multipart/form-data" in request.content_type:
        title = (request.form.get("title") or "").strip()
        category = (request.form.get("category") or "Handcraft").strip()
        description = (request.form.get("description") or "").strip()
        price = float(request.form.get("price") or 0)
        stock = int(request.form.get("stock") or 1)
        is_available = 1 if str(request.form.get("is_available", "1")) in ("1", "true", "True") else 0
        image_url = (request.form.get("image_url") or "").strip()

        if "image" in request.files:
            file = request.files["image"]
            if file and file.filename and allowed_file(file.filename):
                ext = file.filename.rsplit(".", 1)[1].lower()
                fname = f"{uuid.uuid4().hex}.{ext}"
                file.save(os.path.join(UPLOAD_FOLDER, fname))
                image_url = uploaded_image_url(fname)
    else:
        data = request.get_json() or {}
        title = (data.get("title") or "").strip()
        category = (data.get("category") or "Handcraft").strip()
        description = (data.get("description") or "").strip()
        price = float(data.get("price") or 0)
        stock = int(data.get("stock") or 1)
        is_available = 1 if data.get("is_available", True) else 0
        image_url = (data.get("image_url") or "").strip()

    if not title or price <= 0:
        conn.close()
        return jsonify({"error": "Product title and positive price are required."}), 400

    if not image_url:
        image_url = "https://images.unsplash.com/photo-1513519245088-0e12902e5a38?auto=format&fit=crop&w=600&q=80"

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cur.execute("""
        INSERT INTO products (artisan_id, title, category, description, price, stock, is_available, image_url, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (request.user_id, title, category, description, price, stock, is_available, image_url, now))
    prod_id = cur.lastrowid
    conn.commit()
    conn.close()
    return jsonify({"message": "Product added successfully", "id": prod_id}), 201


@app.route("/api/artisan/products/<int:product_id>", methods=["PUT", "DELETE"])
@auth_required(roles=["artisan", "admin"])
def manage_single_product(product_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM products WHERE id = ?", (product_id,))
    product = cur.fetchone()
    if not product:
        conn.close()
        return jsonify({"error": "Product not found"}), 404

    if request.user_role == "artisan" and product["artisan_id"] != request.user_id:
        conn.close()
        return jsonify({"error": "You can only edit your own products."}), 403

    if request.method == "DELETE":
        cur.execute("DELETE FROM products WHERE id = ?", (product_id,))
        conn.commit()
        conn.close()
        return jsonify({"message": "Product deleted"})

    is_multipart = request.content_type and "multipart/form-data" in request.content_type
    data = request.form if is_multipart else request.get_json() or {}
    title = (data.get("title", product["title"]) or "").strip()
    category = (data.get("category", product["category"]) or "").strip()
    description = (data.get("description", product["description"]) or "").strip()
    image_url = (data.get("image_url", product["image_url"]) or "").strip()
    try:
        price = float(data.get("price", product["price"]))
        stock = int(data.get("stock", product["stock"]))
        is_available = int(data.get("is_available", product["is_available"]))
        artisan_id = int(data.get("artisan_id", product["artisan_id"])) if request.user_role == "admin" else product["artisan_id"]
    except (TypeError, ValueError):
        conn.close()
        return jsonify({"error": "Artisan, price, stock, and availability must be valid values."}), 400

    if not title or not category:
        conn.close()
        return jsonify({"error": "Product title and category are required."}), 400
    if not math.isfinite(price) or price <= 0:
        conn.close()
        return jsonify({"error": "Product price must be greater than zero."}), 400
    if stock < 0 or is_available not in (0, 1):
        conn.close()
        return jsonify({"error": "Stock or availability value is invalid."}), 400

    if request.user_role == "admin":
        cur.execute("SELECT id FROM users WHERE id = ? AND role = 'artisan'", (artisan_id,))
        if not cur.fetchone():
            conn.close()
            return jsonify({"error": "Select a valid artisan for this product."}), 400

    image = request.files.get("image") if is_multipart else None
    if image and image.filename:
        if not allowed_file(image.filename):
            conn.close()
            return jsonify({"error": "Unsupported image format. Use PNG, JPG, JPEG, WEBP, or GIF."}), 400
        ext = image.filename.rsplit(".", 1)[1].lower()
        filename = f"{uuid.uuid4().hex}.{ext}"
        image.save(os.path.join(UPLOAD_FOLDER, filename))
        image_url = uploaded_image_url(filename)

    cur.execute("""
        UPDATE products
        SET artisan_id = ?, title = ?, category = ?, description = ?, price = ?, stock = ?, is_available = ?, image_url = ?
        WHERE id = ?
    """, (artisan_id, title, category, description, price, stock, is_available, image_url, product_id))
    conn.commit()
    conn.close()
    return jsonify({"message": "Product updated successfully"})


@app.route("/api/artisan/orders", methods=["GET"])
@auth_required(roles=["artisan"])
def artisan_orders():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT o.id AS order_id, o.status, o.created_at, o.shipping_address,
               u.name AS customer_name, p.title AS product_title,
               oi.quantity, oi.unit_price, (oi.quantity * oi.unit_price) AS subtotal
        FROM order_items oi
        JOIN orders o ON oi.order_id = o.id
        JOIN products p ON oi.product_id = p.id
        JOIN users u ON o.customer_id = u.id
        WHERE oi.artisan_id = ?
        ORDER BY o.created_at DESC
    """, (request.user_id,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return jsonify(rows)


# -------------------- CUSTOMER FLOW: PLACE ORDER & VIEW ORDERS --------------------
@app.route("/api/orders", methods=["POST"])
@auth_required(roles=["customer"])
def place_order():
    data = request.get_json() or {}
    items = data.get("items") or []
    shipping_address = (data.get("shipping_address") or "").strip()
    payment_method = (data.get("payment_method") or "Cash on Delivery").strip()

    if not items:
        return jsonify({"error": "Your cart is empty."}), 400
    if not shipping_address:
        return jsonify({"error": "Shipping address is required."}), 400
    if payment_method != "Cash on Delivery":
        return jsonify({"error": "Only Cash on Delivery is currently available."}), 400

    conn = get_db()
    cur = conn.cursor()
    total_amount = 0.0
    validated_items = []

    for item in items:
        pid = int(item.get("product_id"))
        qty = int(item.get("quantity", 1))
        cur.execute("SELECT * FROM products WHERE id = ?", (pid,))
        prod = cur.fetchone()
        if not prod or prod["is_available"] == 0 or prod["stock"] < qty:
            conn.close()
            return jsonify({"error": f"Insufficient stock for product ID {pid}"}), 400
        total_amount += prod["price"] * qty
        validated_items.append((prod, qty))

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cur.execute("""
        INSERT INTO orders (customer_id, total_amount, shipping_address, payment_method, status, created_at)
        VALUES (?, ?, ?, ?, 'Pending', ?)
    """, (request.user_id, total_amount, shipping_address, payment_method, now))
    order_id = cur.lastrowid

    for prod, qty in validated_items:
        cur.execute("""
            INSERT INTO order_items (order_id, product_id, artisan_id, quantity, unit_price)
            VALUES (?, ?, ?, ?, ?)
        """, (order_id, prod["id"], prod["artisan_id"], qty, prod["price"]))

        new_stock = prod["stock"] - qty
        avail = 1 if new_stock > 0 else 0
        cur.execute("UPDATE products SET stock = ?, is_available = ? WHERE id = ?", (new_stock, avail, prod["id"]))

    conn.commit()
    conn.close()
    return jsonify({"message": "Order placed successfully!", "order_id": order_id, "total_amount": total_amount}), 201


@app.route("/api/customer/orders", methods=["GET"])
@auth_required(roles=["customer"])
def customer_orders():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM orders WHERE customer_id = ? ORDER BY created_at DESC", (request.user_id,))
    orders = [dict(r) for r in cur.fetchall()]
    for order in orders:
        cur.execute("""
            SELECT oi.*, p.title, p.image_url
            FROM order_items oi
            JOIN products p ON oi.product_id = p.id
            WHERE oi.order_id = ?
        """, (order["id"],))
        order["items"] = [dict(i) for i in cur.fetchall()]
    conn.close()
    return jsonify(orders)


# -------------------- ADMIN FLOW: USERS, PRODUCTS, ORDERS, REPORTS --------------------
@app.route("/api/admin/products", methods=["GET", "POST"])
@auth_required(roles=["admin"])
def admin_products():
    conn = get_db()
    cur = conn.cursor()

    if request.method == "GET":
        cur.execute("""
            SELECT p.*, u.name AS artisan_name, u.location AS artisan_location, u.craft_specialty
            FROM products p
            JOIN users u ON p.artisan_id = u.id
            ORDER BY p.created_at DESC
        """)
        products = [dict(row) for row in cur.fetchall()]
        conn.close()
        return jsonify(products)

    is_multipart = request.content_type and "multipart/form-data" in request.content_type
    data = request.form if is_multipart else request.get_json() or {}
    title = (data.get("title") or "").strip()
    category = (data.get("category") or "").strip()
    description = (data.get("description") or "").strip()
    image_url = (data.get("image_url") or "").strip()
    try:
        artisan_id = int(data.get("artisan_id", 0))
        price = float(data.get("price", 0))
        stock = int(data.get("stock", 1))
        is_available = int(data.get("is_available", 1))
    except (TypeError, ValueError):
        conn.close()
        return jsonify({"error": "Artisan, price, stock, and availability must be valid values."}), 400

    if not title or not category:
        conn.close()
        return jsonify({"error": "Product title and category are required."}), 400
    if not math.isfinite(price) or price <= 0:
        conn.close()
        return jsonify({"error": "Product price must be greater than zero."}), 400
    if stock < 0 or is_available not in (0, 1):
        conn.close()
        return jsonify({"error": "Stock or availability value is invalid."}), 400

    cur.execute("SELECT id FROM users WHERE id = ? AND role = 'artisan' AND is_active = 1", (artisan_id,))
    if not cur.fetchone():
        conn.close()
        return jsonify({"error": "Select an active artisan for this product."}), 400

    image = request.files.get("image") if is_multipart else None
    if image and image.filename:
        if not allowed_file(image.filename):
            conn.close()
            return jsonify({"error": "Unsupported image format. Use PNG, JPG, JPEG, WEBP, or GIF."}), 400
        ext = image.filename.rsplit(".", 1)[1].lower()
        filename = f"{uuid.uuid4().hex}.{ext}"
        image.save(os.path.join(UPLOAD_FOLDER, filename))
        image_url = uploaded_image_url(filename)

    if not image_url:
        image_url = "https://images.unsplash.com/photo-1513519245088-0e12902e5a38?auto=format&fit=crop&w=600&q=80"

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cur.execute("""
        INSERT INTO products (artisan_id, title, category, description, price, stock, is_available, image_url, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (artisan_id, title, category, description, price, stock, is_available, image_url, now))
    product_id = cur.lastrowid
    conn.commit()
    conn.close()
    return jsonify({"message": "Product added successfully", "id": product_id}), 201


@app.route("/api/admin/users", methods=["GET"])
@auth_required(roles=["admin"])
def admin_list_users():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, name, email, role, location, craft_specialty, phone, is_active, created_at FROM users ORDER BY created_at DESC")
    users = [dict(r) for r in cur.fetchall()]
    conn.close()
    return jsonify(users)


@app.route("/api/admin/users/<int:user_id>/toggle", methods=["PUT"])
@auth_required(roles=["admin"])
def admin_toggle_user(user_id):
    if user_id == request.user_id:
        return jsonify({"error": "Cannot deactivate your own admin account."}), 400
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT is_active FROM users WHERE id = ?", (user_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "User not found"}), 404
    new_status = 0 if row["is_active"] == 1 else 1
    cur.execute("UPDATE users SET is_active = ? WHERE id = ?", (new_status, user_id))
    conn.commit()
    conn.close()
    return jsonify({"message": "User status updated", "is_active": new_status})


@app.route("/api/admin/orders", methods=["GET"])
@auth_required(roles=["admin"])
def admin_list_orders():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT o.*, u.name AS customer_name, u.email AS customer_email
        FROM orders o
        JOIN users u ON o.customer_id = u.id
        ORDER BY o.created_at DESC
    """)
    orders = [dict(r) for r in cur.fetchall()]
    for order in orders:
        cur.execute("""
            SELECT oi.*, p.title AS product_title
            FROM order_items oi
            JOIN products p ON oi.product_id = p.id
            WHERE oi.order_id = ?
        """, (order["id"],))
        order["items"] = [dict(i) for i in cur.fetchall()]
    conn.close()
    return jsonify(orders)


@app.route("/api/admin/orders/<int:order_id>/status", methods=["PUT"])
@auth_required(roles=["admin"])
def admin_update_order_status(order_id):
    data = request.get_json() or {}
    status = (data.get("status") or "").strip()
    valid_statuses = ["Pending", "Confirmed", "Shipped", "Delivered", "Cancelled"]
    if status not in valid_statuses:
        return jsonify({"error": f"Invalid status. Choose from {valid_statuses}"}), 400

    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE orders SET status = ? WHERE id = ?", (status, order_id))
    conn.commit()
    conn.close()
    return jsonify({"message": f"Order #{order_id} status updated to {status}"})


@app.route("/api/admin/reports", methods=["GET"])
@auth_required(roles=["admin"])
def admin_reports():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM users WHERE role = 'artisan'")
    total_artisans = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM users WHERE role = 'customer'")
    total_customers = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM products")
    total_products = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*), COALESCE(SUM(total_amount), 0) FROM orders WHERE status != 'Cancelled'")
    order_stats = cur.fetchone()
    total_orders = order_stats[0]
    total_revenue = order_stats[1]

    cur.execute("""
        SELECT category, COUNT(*) AS product_count, SUM(stock) AS total_stock
        FROM products GROUP BY category
    """)
    category_breakdown = [dict(r) for r in cur.fetchall()]

    cur.execute("""
        SELECT u.name AS artisan_name, u.location,
               COALESCE(SUM(oi.quantity * oi.unit_price), 0) AS total_sales,
               COALESCE(SUM(oi.quantity), 0) AS units_sold
        FROM users u
        LEFT JOIN order_items oi ON u.id = oi.artisan_id
        WHERE u.role = 'artisan'
        GROUP BY u.id
        ORDER BY total_sales DESC
    """)
    artisan_performance = [dict(r) for r in cur.fetchall()]
    conn.close()

    return jsonify({
        "summary": {
            "total_artisans": total_artisans,
            "total_customers": total_customers,
            "total_products": total_products,
            "total_orders": total_orders,
            "total_revenue": total_revenue
        },
        "category_breakdown": category_breakdown,
        "artisan_performance": artisan_performance
    })


@app.route("/api/admin/reports/export", methods=["GET"])
@auth_required(roles=["admin"])
def admin_export_csv():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT o.id AS Order_ID, o.created_at AS Date, u.name AS Customer,
               o.total_amount AS Amount_INR, o.payment_method AS Payment, o.status AS Status,
               o.shipping_address AS Shipping_Address
        FROM orders o
        JOIN users u ON o.customer_id = u.id
        ORDER BY o.created_at DESC
    """)
    rows = cur.fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Order ID", "Date", "Customer", "Amount (INR)", "Payment Method", "Status", "Shipping Address"])
    for r in rows:
        writer.writerow([r["Order_ID"], r["Date"], r["Customer"], r["Amount_INR"], r["Payment"], r["Status"], r["Shipping_Address"]])

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=kalakriti_sales_report.csv"}
    )


if __name__ == "__main__":
    init_db()
    print("Kalakriti Local Artisan & Handcraft Backend running on http://127.0.0.1:5000")
    app.run(host="127.0.0.1", port=5000, debug=True)

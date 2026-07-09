from pathlib import Path

from datetime import datetime

from flask import Flask, abort, redirect, render_template, render_template_string, request, session, url_for
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3

app = Flask(__name__)
app.secret_key = "supersecretkey"

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "liquor.db"


def get_db():
    return sqlite3.connect(DB_PATH)


def ensure_database():
    if DB_PATH.exists():
        try:
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute("SELECT name FROM sqlite_master LIMIT 1")
        except sqlite3.DatabaseError:
            DB_PATH.unlink()

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL,
                username TEXT NOT NULL,
                message TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (product_id) REFERENCES products(id)
            )
            """
        )

        user_count = cursor.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        if user_count == 0:
            cursor.executemany(
                "INSERT INTO users (username, password) VALUES (?, ?)",
                [
                    ("admin", generate_password_hash("password")),
                    ("sam", generate_password_hash("password123")),
                ],
            )

        product_count = cursor.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        if product_count == 0:
            cursor.executemany(
                "INSERT INTO products (name) VALUES (?)",
                [
                    ("Macallan 18",),
                    ("Dom Pérignon Vintage",),
                    ("Hennessy XO",),
                    ("Johnnie Walker Blue Label",),
                    ("Château Margaux 2015",),
                    ("Ardbeg Uigeadail",),
                ],
            )
        conn.commit()


ensure_database()


@app.context_processor
def inject_member_navigation():
    user = session.get("user")
    return {
        "member_label": "Your Account" if user else "Login",
        "member_url": "/dashboard" if user else "/login",
        "show_logout": bool(user),
    }


# -------------------------
# HOME PAGE
# -------------------------
@app.route("/")
def home():
    return render_template("index.html")


# -------------------------
# LOGIN (SQL INJECTION VULNERABLE)
# -------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = request.form["username"]
        pwd = request.form["password"]

        conn = get_db()
        cursor = conn.cursor()

        # SECURE: parameterized query, fetches by username only
        result = cursor.execute(
            "SELECT * FROM users WHERE username = ?", (user,)
        ).fetchone()

        # SECURE: check hashed password separately
        if result and check_password_hash(result[2], pwd):
            session["user"] = user
            return redirect("/dashboard")
        else:
            return "Login Failed"
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


# -------------------------
# DASHBOARD
# -------------------------
@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect("/login")

    cart = session.get("cart", [])
    conn = get_db()
    cursor = conn.cursor()
    cart_products = []
    if cart:
        placeholders = ",".join("?" for _ in cart)
        cart_products = cursor.execute(
            f"SELECT id, name FROM products WHERE id IN ({placeholders})",
            cart,
        ).fetchall()

    is_admin = session.get("user") == "admin"
    return render_template("dashboard.html", user=session["user"], cart=cart_products, is_admin=is_admin)


# -------------------------
# SEARCH (SQL INJECTION VULNERABLE)
# -------------------------
@app.route("/search", methods=["GET"])
def search():
    term = request.args.get("q", "")

    conn = get_db()
    cursor = conn.cursor()

    #VULNERABLE QUERY
    query = f"SELECT * FROM products WHERE name LIKE '%{term}%'"
    results = cursor.execute(query).fetchall()

    return render_template("search.html", results=results, query=term)


# -------------------------
# REVIEW (SSTI VULNERABLE)
# -------------------------
@app.route("/review", methods=["GET", "POST"])
def review():
    confirmation_html = None 
    conn = get_db()
    cursor = conn.cursor()
    products = cursor.execute("SELECT * FROM products ORDER BY name").fetchall()

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        message = request.form.get("message", "").strip()
        product_id = request.form.get("product_id", type=int)

        if not product_id:
            return render_template(
                "review.html",
                products=products,
                review_error="Choose a wine before submitting your review.",
            )

        product = cursor.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
        if product is None:
            abort(404)

        if not name or not message:
            reviews = cursor.execute(
                "SELECT username, message, created_at FROM reviews WHERE product_id = ? ORDER BY id DESC",
                (product_id,),
            ).fetchall()
            return render_template("product.html", product=product, reviews=reviews, review_error="Please write both your name and review before submitting.")

        cursor.execute(
            "INSERT INTO reviews (product_id, username, message, created_at) VALUES (?, ?, ?, ?)",
            (product_id, name, message, datetime.utcnow().isoformat(timespec="seconds")),
        )
        conn.commit()

        # Fixed Code: Use render_template_string to safely render the confirmation message without allowing template injection.
        confirmation_html = render_template_string( "<p>Thank you, <strong>{{ name }}</strong>! Your review has been submitted.</p>", name=name)
    
    return render_template("review.html", products=products, review_error=None, confirmation=confirmation_html)



@app.route("/cart")
def cart():
    if "user" not in session:
        return redirect("/login")

    cart_ids = session.get("cart", [])
    cart_products = []
    if cart_ids:
        conn = get_db()
        cursor = conn.cursor()
        placeholders = ",".join("?" for _ in cart_ids)
        cart_products = cursor.execute(
            f"SELECT id, name FROM products WHERE id IN ({placeholders})",
            cart_ids,
        ).fetchall()

    return render_template("cart.html", user=session["user"], cart_products=cart_products)


@app.route("/cart/add/<int:id>", methods=["POST"])
def add_to_cart(id):
    if "user" not in session:
        return redirect("/login")

    conn = get_db()
    cursor = conn.cursor()
    product = cursor.execute("SELECT id FROM products WHERE id = ?", (id,)).fetchone()
    if product is None:
        abort(404)

    cart = session.get("cart", [])
    cart.append(id)
    session["cart"] = cart

    return redirect(request.referrer or url_for("cart"))


@app.route("/admin", methods=["GET", "POST"])
def admin():
    if session.get("user") != "admin":
        return redirect("/dashboard" if "user" in session else "/login")

    conn = get_db()
    cursor = conn.cursor()
    admin_message = None
    admin_error = None

    if request.method == "POST":
        action = request.form.get("action")
        if action == "add":
            name = request.form.get("name", "").strip()
            if name:
                cursor.execute("INSERT INTO products (name) VALUES (?)", (name,))
                conn.commit()
                admin_message = "Wine added successfully."
        elif action == "remove":
            product_id = request.form.get("product_id", type=int)
            if product_id:
                cursor.execute("DELETE FROM products WHERE id = ?", (product_id,))
                cursor.execute("DELETE FROM reviews WHERE product_id = ?", (product_id,))
                conn.commit()
                admin_message = "Wine removed successfully."
        elif action == "add_member":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")

            if not username or not password:
                admin_error = "Username and password are required for new members."
            else:
                try:
                    cursor.execute(
                        "INSERT INTO users (username, password) VALUES (?, ?)",
                        (username, password),
                    )
                    conn.commit()
                    admin_message = f"Member '{username}' added successfully."
                except sqlite3.IntegrityError:
                    admin_error = "That username already exists."

    products = cursor.execute("SELECT * FROM products ORDER BY id DESC").fetchall()
    users = cursor.execute("SELECT id, username FROM users ORDER BY id DESC").fetchall()
    return render_template(
        "admin.html",
        products=products,
        users=users,
        admin_message=admin_message,
        admin_error=admin_error,
    )

@app.route("/shop")
def shop():
    conn = get_db()
    cursor = conn.cursor()

    products = cursor.execute("SELECT * FROM products").fetchall()

    return render_template("shop.html", products=products)

@app.route("/product/<int:id>")
def product(id):
    conn = get_db()
    cursor = conn.cursor()

    product = cursor.execute("SELECT * FROM products WHERE id = ?", (id,)).fetchone()

    if product is None:
        abort(404)

    reviews = cursor.execute(
        "SELECT username, message, created_at FROM reviews WHERE product_id = ? ORDER BY id DESC",
        (id,),
    ).fetchall()

    return render_template(
        "product.html",
        product=product,
        reviews=reviews,
        review_error=None,
    )

if __name__ == "__main__":
    app.run(debug=False)
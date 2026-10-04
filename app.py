from flask import Flask, render_template, request, redirect
import sqlite3
from datetime import datetime

app = Flask(__name__)

DATABASE = "inventory.db"


# Database connection
def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


# Create table
def create_table():
    conn = get_db()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            category TEXT,
            quantity INTEGER NOT NULL,
            price REAL NOT NULL,
            supplier TEXT
        )
    """)

    conn.commit()
    conn.close()


# Home page
@app.route("/")
def index():
    conn = get_db()

    products = conn.execute(
        "SELECT * FROM products ORDER BY id"
    ).fetchall()

    conn.close()

    return render_template("index.html", products=products)


# Add product
@app.route("/add", methods=["POST"])
def add_product():

    product_id = request.form["id"]
    name = request.form["name"]
    category = request.form["category"]
    quantity = request.form["quantity"]
    price = request.form["price"]
    supplier = request.form["supplier"]

    quantity = int(quantity)
    price = float(price)

    conn = get_db()

    try:
        conn.execute("""
            INSERT INTO products
            (id, name, category, quantity, price, supplier)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            product_id,
            name,
            category,
            quantity,
            price,
            supplier
        ))

        conn.commit()

    except sqlite3.IntegrityError:
        conn.close()
        return "Product ID already exists"

    conn.close()

    return redirect("/")


# Delete product
@app.route("/delete/<product_id>")
def delete_product(product_id):

    conn = get_db()

    conn.execute(
        "DELETE FROM products WHERE id = ?",
        (product_id,)
    )

    conn.commit()
    conn.close()

    return redirect("/")


# Edit product page
@app.route("/edit/<product_id>")
def edit_product(product_id):

    conn = get_db()

    product = conn.execute(
        "SELECT * FROM products WHERE id = ?",
        (product_id,)
    ).fetchone()

    conn.close()

    if product is None:
        return "Product not found"

    return render_template(
        "edit_product.html",
        product=product
    )


# Update product
@app.route("/update", methods=["POST"])


# Update product
@app.route("/update", methods=["POST"])
def update_product():

    product_id = request.form["id"]
    name = request.form["name"]
    category = request.form["category"]
    quantity = request.form["quantity"]
    price = request.form["price"]
    supplier = request.form["supplier"]

    conn = get_db()

    conn.execute("""
        UPDATE products
        SET name = ?,
            category = ?,
            quantity = ?,
            price = ?,
            supplier = ?
        WHERE id = ?
    """, (
        name,
        category,
        quantity,
        price,
        supplier,
        product_id
    ))

    conn.commit()
    conn.close()

    return redirect("/")

# Stock Out page
@app.route("/stock-out/<product_id>")
def stock_out_page(product_id):

    conn = get_db()

    product = conn.execute(
        "SELECT * FROM products WHERE id = ?",
        (product_id,)
    ).fetchone()

    conn.close()

    if product is None:
        return "Product not found"

    return render_template(
        "stock_out.html",
        product=product
    )


# Stock Out
@app.route("/stock-out", methods=["POST"])
def stock_out():

    product_id = request.form["id"]
    quantity = int(request.form["quantity"])

    conn = get_db()

    product = conn.execute(
        "SELECT quantity FROM products WHERE id = ?",
        (product_id,)
    ).fetchone()

    if product is None:
        conn.close()
        return "Product not found"

    if quantity > product["quantity"]:
        conn.close()
        return "Not enough stock"

    new_quantity = product["quantity"] - quantity

    conn.execute(
        "UPDATE products SET quantity = ? WHERE id = ?",
        (new_quantity, product_id)
    )

    conn.commit()
    conn.close()

    return redirect("/")


# Search product
@app.route("/search")
def search():

    keyword = request.args.get("keyword", "")

    conn = get_db()

    products = conn.execute("""
        SELECT * FROM products
        WHERE id LIKE ?
        OR name LIKE ?
        OR category LIKE ?
        ORDER BY id
    """, (
        "%" + keyword + "%",
        "%" + keyword + "%",
        "%" + keyword + "%"
    )).fetchall()

    conn.close()

    return render_template(
        "index.html",
        products=products
    )


# Low stock
@app.route("/low-stock")
def low_stock():

    conn = get_db()

    products = conn.execute("""
        SELECT * FROM products
        WHERE quantity <= 5
        ORDER BY quantity
    """).fetchall()

    conn.close()

    return render_template(
        "index.html",
        products=products
    )


# Generate bill
@app.route("/bill/<product_id>")
def bill(product_id):

    conn = get_db()

    product = conn.execute(
        "SELECT * FROM products WHERE id = ?",
        (product_id,)
    ).fetchone()

    conn.close()

    if product is None:
        return "Product not found"

    return render_template(
        "bill.html",
        product=product,
        date=datetime.now().strftime("%d-%m-%Y %H:%M")
    )


# Start application
if __name__ == "__main__":

    create_table()

    app.run(
        debug=True,
        host="0.0.0.0",
        port=5000
    ) 
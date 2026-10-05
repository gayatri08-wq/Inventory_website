```python
from flask import Flask, render_template, request, redirect
import sqlite3
from datetime import datetime, timedelta
import math
import requests

app = Flask(__name__)

DATABASE = "inventory.db"


# =========================================================
# DATABASE CONNECTION
# =========================================================

def get_db():

    conn = sqlite3.connect(DATABASE)

    conn.row_factory = sqlite3.Row

    return conn


# =========================================================
# CREATE TABLE
# =========================================================

def create_table():

    conn = get_db()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS products (

            id TEXT PRIMARY KEY,

            name TEXT NOT NULL,

            category TEXT,

            quantity INTEGER NOT NULL,

            price REAL NOT NULL,

            supplier TEXT,

            supplier_location TEXT,

            delivery_location TEXT,

            delivery_date TEXT,

            delivery_time TEXT

        )
    """)

    # Existing columns check

    columns = [
        row["name"]
        for row in conn.execute(
            "PRAGMA table_info(products)"
        ).fetchall()
    ]


    # Supplier Location

    if "supplier_location" not in columns:

        conn.execute(
            "ALTER TABLE products ADD COLUMN supplier_location TEXT"
        )


    # Delivery Location

    if "delivery_location" not in columns:

        conn.execute(
            "ALTER TABLE products ADD COLUMN delivery_location TEXT"
        )


    # Delivery Date

    if "delivery_date" not in columns:

        conn.execute(
            "ALTER TABLE products ADD COLUMN delivery_date TEXT"
        )


    # Delivery Time

    if "delivery_time" not in columns:

        conn.execute(
            "ALTER TABLE products ADD COLUMN delivery_time TEXT"
        )


    conn.commit()

    conn.close()


# =========================================================
# LOCATION GEOCODING
# =========================================================

def get_coordinates(location):

    """
    Converts location name into latitude and longitude.

    Example:
    Mumbai -> latitude, longitude
    Pune   -> latitude, longitude
    """

    try:

        url = "https://nominatim.openstreetmap.org/search"

        params = {
            "q": location,
            "format": "json",
            "limit": 1
        }

        headers = {
            "User-Agent": "InventoryManagementSystem/1.0"
        }

        response = requests.get(
            url,
            params=params,
            headers=headers,
            timeout=10
        )

        if response.status_code != 200:

            return None


        data = response.json()


        if not data:

            return None


        latitude = float(data[0]["lat"])

        longitude = float(data[0]["lon"])


        return latitude, longitude


    except Exception:

        return None


# =========================================================
# CALCULATE DELIVERY ETA
# =========================================================

def calculate_delivery_eta(
    supplier_location,
    delivery_location
):

    """
    Calculates road distance and estimated travel time
    between supplier and delivery location.
    """

    if not supplier_location or not delivery_location:

        return None


    # Get supplier coordinates

    start = get_coordinates(
        supplier_location
    )


    # Get destination coordinates

    end = get_coordinates(
        delivery_location
    )


    # If locations cannot be found

    if not start or not end:

        return None


    start_lat, start_lon = start

    end_lat, end_lon = end


    try:

        # OSRM road routing

        route_url = (
            f"https://router.project-osrm.org/route/v1/driving/"
            f"{start_lon},{start_lat};"
            f"{end_lon},{end_lat}"
        )


        params = {
            "overview": "false"
        }


        response = requests.get(
            route_url,
            params=params,
            timeout=15
        )


        if response.status_code == 200:

            data = response.json()


            if data.get("routes"):

                route = data["routes"][0]


                distance_km = (
                    route["distance"] / 1000
                )


                duration_minutes = (
                    route["duration"] / 60
                )


                # Current time

                now = datetime.now()


                # Estimated arrival

                arrival = (
                    now +
                    timedelta(
                        minutes=duration_minutes
                    )
                )


                return {
                    "distance": round(
                        distance_km,
                        2
                    ),

                    "duration": round(
                        duration_minutes
                    ),

                    "arrival": arrival
                }


    except Exception:

        pass


    # =====================================================
    # FALLBACK CALCULATION
    # =====================================================

    try:

        distance_km = calculate_straight_distance(
            start_lat,
            start_lon,
            end_lat,
            end_lon
        )


        # Average speed assumption

        average_speed = 40


        duration_minutes = (
            distance_km / average_speed
        ) * 60


        now = datetime.now()


        arrival = (
            now +
            timedelta(
                minutes=duration_minutes
            )
        )


        return {
            "distance": round(
                distance_km,
                2
            ),

            "duration": round(
                duration_minutes
            ),

            "arrival": arrival
        }


    except Exception:

        return None


# =========================================================
# STRAIGHT DISTANCE
# =========================================================

def calculate_straight_distance(
    lat1,
    lon1,
    lat2,
    lon2
):

    """
    Haversine formula.
    Used as fallback if routing service fails.
    """

    radius = 6371


    lat1 = math.radians(lat1)

    lon1 = math.radians(lon1)

    lat2 = math.radians(lat2)

    lon2 = math.radians(lon2)


    dlat = lat2 - lat1

    dlon = lon2 - lon1


    a = (
        math.sin(dlat / 2) ** 2
        +
        math.cos(lat1)
        *
        math.cos(lat2)
        *
        math.sin(dlon / 2) ** 2
    )


    c = 2 * math.atan2(
        math.sqrt(a),
        math.sqrt(1 - a)
    )


    return radius * c


# =========================================================
# HOME PAGE
# =========================================================

@app.route("/")
def index():

    create_table()

    conn = get_db()


    products = conn.execute(
        "SELECT * FROM products ORDER BY id"
    ).fetchall()


    conn.close()


    return render_template(
        "index.html",
        products=products
    )


# =========================================================
# ADD PRODUCT
# =========================================================

@app.route("/add", methods=["POST"])
def add_product():

    product_id = request.form["product_id"]

    name = request.form["name"]

    category = request.form["category"]

    quantity = request.form["quantity"]

    price = request.form["price"]

    supplier = request.form["supplier"]

    supplier_location = request.form[
        "supplier_location"
    ]

    delivery_location = request.form[
        "delivery_location"
    ]


    quantity = int(quantity)

    price = float(price)


    # =====================================================
    # AUTOMATIC ETA
    # =====================================================

    eta = calculate_delivery_eta(
        supplier_location,
        delivery_location
    )


    if eta:

        delivery_date = (
            eta["arrival"]
            .strftime("%Y-%m-%d")
        )

        delivery_time = (
            eta["arrival"]
            .strftime("%H:%M")
        )

    else:

        # If location cannot be found

        delivery_date = ""

        delivery_time = ""


    conn = get_db()


    try:

        conn.execute("""
            INSERT INTO products
            (
                id,
                name,
                category,
                quantity,
                price,
                supplier,
                supplier_location,
                delivery_location,
                delivery_date,
                delivery_time
            )

            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (

            product_id,

            name,

            category,

            quantity,

            price,

            supplier,

            supplier_location,

            delivery_location,

            delivery_date,

            delivery_time

        ))


        conn.commit()


    except sqlite3.IntegrityError:

        conn.close()

        return "Product ID already exists"


    conn.close()


    return redirect("/")


# =========================================================
# DELETE PRODUCT
# =========================================================

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


# =========================================================
# EDIT PRODUCT
# =========================================================

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


# =========================================================
# UPDATE PRODUCT
# =========================================================

@app.route("/update", methods=["POST"])
def update_product():

    product_id = request.form["id"]

    name = request.form["name"]

    category = request.form["category"]

    quantity = request.form["quantity"]

    price = request.form["price"]

    supplier = request.form["supplier"]

    supplier_location = request.form[
        "supplier_location"
    ]

    delivery_location = request.form[
        "delivery_location"
    ]


    # =====================================================
    # AUTOMATIC ETA AFTER UPDATE
    # =====================================================

    eta = calculate_delivery_eta(
        supplier_location,
        delivery_location
    )


    if eta:

        delivery_date = (
            eta["arrival"]
            .strftime("%Y-%m-%d")
        )

        delivery_time = (
            eta["arrival"]
            .strftime("%H:%M")
        )

    else:

        delivery_date = ""

        delivery_time = ""


    conn = get_db()


    conn.execute("""
        UPDATE products

        SET

            name = ?,

            category = ?,

            quantity = ?,

            price = ?,

            supplier = ?,

            supplier_location = ?,

            delivery_location = ?,

            delivery_date = ?,

            delivery_time = ?

        WHERE id = ?
    """, (

        name,

        category,

        quantity,

        price,

        supplier,

        supplier_location,

        delivery_location,

        delivery_date,

        delivery_time,

        product_id

    ))


    conn.commit()

    conn.close()


    return redirect("/")


# =========================================================
# STOCK OUT PAGE
# =========================================================

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


# =========================================================
# STOCK OUT
# =========================================================

@app.route("/stock-out", methods=["POST"])
def stock_out():

    product_id = request.form["id"]

    quantity = int(
        request.form["quantity"]
    )


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


    new_quantity = (
        product["quantity"] - quantity
    )


    conn.execute(
        """
        UPDATE products
        SET quantity = ?
        WHERE id = ?
        """,

        (
            new_quantity,
            product_id
        )
    )


    conn.commit()

    conn.close()


    return redirect("/")


# =========================================================
# SEARCH
# =========================================================

@app.route("/search")
def search():

    keyword = request.args.get(
        "keyword",
        ""
    )


    conn = get_db()


    products = conn.execute("""
        SELECT * FROM products

        WHERE id LIKE ?

        OR name LIKE ?

        OR category LIKE ?

        OR supplier LIKE ?

        OR supplier_location LIKE ?

        OR delivery_location LIKE ?

        OR delivery_date LIKE ?

        OR delivery_time LIKE ?

        ORDER BY id
    """, (

        "%" + keyword + "%",

        "%" + keyword + "%",

        "%" + keyword + "%",

        "%" + keyword + "%",

        "%" + keyword + "%",

        "%" + keyword + "%",

        "%" + keyword + "%",

        "%" + keyword + "%"

    )).fetchall()


    conn.close()


    return render_template(
        "index.html",
        products=products
    )


# =========================================================
# LOW STOCK
# =========================================================

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


# =========================================================
# PRODUCT MAP
# =========================================================

@app.route("/map/<product_id>")
def product_map(product_id):

    conn = get_db()


    product = conn.execute(
        "SELECT * FROM products WHERE id = ?",
        (product_id,)
    ).fetchone()


    conn.close()


    if product is None:

        return "Product not found"


    return render_template(
        "map.html",
        product=product
    )


# =========================================================
# BILL
# =========================================================

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

        date=datetime.now().strftime(
            "%d-%m-%Y %H:%M"
        )
    )


# =========================================================
# START APPLICATION
# =========================================================

if __name__ == "__main__":

    create_table()


    app.run(
        debug=True,

        host="0.0.0.0",

        port=5000
    )
```

from flask import Flask, render_template, request, redirect
import sqlite3
from datetime import datetime, timedelta
import math
import requests

app = Flask(__name__)

DATABASE = "inventory.db"


# -----------------------------------------
# DATABASE CONNECTION
# -----------------------------------------

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


# -----------------------------------------
# CREATE TABLE
# -----------------------------------------

def create_table():

    conn = get_db()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT,
            quantity INTEGER,
            price REAL,
            supplier TEXT,
            supplier_location TEXT,
            delivery_location TEXT,
            delivery_date TEXT,
            delivery_time TEXT
        )
    """)

    conn.commit()

    # Add missing columns safely
    columns = [
        "supplier_location",
        "delivery_location",
        "delivery_date",
        "delivery_time"
    ]

    existing_columns = [
        row["name"]
        for row in conn.execute(
            "PRAGMA table_info(products)"
        ).fetchall()
    ]

    for column in columns:

        if column not in existing_columns:

            conn.execute(
                f"ALTER TABLE products ADD COLUMN {column} TEXT"
            )

    conn.commit()
    conn.close()


create_table()


# -----------------------------------------
# CLEAN LOCATION NAME
# -----------------------------------------

def clean_location(location):

    if not location:
        return ""

    location = location.strip()

    # Common spelling / short-name corrections
    corrections = {
        "kura": "Kurla, Mumbai, Maharashtra, India",
        "kurla": "Kurla, Mumbai, Maharashtra, India",
        "mumbai": "Mumbai, Maharashtra, India",
        "bombay": "Mumbai, Maharashtra, India",
        "pune": "Pune, Maharashtra, India",
        "surat": "Surat, Gujarat, India",
        "thane": "Thane, Maharashtra, India",
        "nashik": "Nashik, Maharashtra, India",
        "nagpur": "Nagpur, Maharashtra, India",
        "delhi": "Delhi, India",
        "new delhi": "New Delhi, India",
        "bangalore": "Bengaluru, Karnataka, India",
        "bengaluru": "Bengaluru, Karnataka, India",
        "hyderabad": "Hyderabad, Telangana, India",
        "chennai": "Chennai, Tamil Nadu, India",
        "ahmedabad": "Ahmedabad, Gujarat, India",
        "kolkata": "Kolkata, West Bengal, India",
        "jaipur": "Jaipur, Rajasthan, India",
        "indore": "Indore, Madhya Pradesh, India",
        "navi mumbai": "Navi Mumbai, Maharashtra, India"
    }

    key = location.lower()

    if key in corrections:
        return corrections[key]

    # If user already entered India,
    # don't add India again
    if "india" in key:
        return location

    return location + ", India"


# -----------------------------------------
# GET COORDINATES
# -----------------------------------------

def get_coordinates(location):

    location = clean_location(location)

    if not location:
        return None

    url = "https://nominatim.openstreetmap.org/search"

    params = {
        "q": location,
        "format": "json",
        "limit": 5,
        "countrycodes": "in",
        "addressdetails": 1
    }

    headers = {
        "User-Agent": "InventoryManagementSystem/1.0"
    }

    try:

        response = requests.get(
            url,
            params=params,
            headers=headers,
            timeout=10
        )

        response.raise_for_status()

        data = response.json()

        if not data:
            return None

        # Make sure result belongs to India
        for place in data:

            display_name = place.get(
                "display_name",
                ""
            ).lower()

            address = place.get(
                "address",
                {}
            )

            country = address.get(
                "country",
                ""
            ).lower()

            if (
                "india" in display_name
                or country == "india"
            ):

                return (
                    float(place["lat"]),
                    float(place["lon"])
                )

        return None

    except Exception as e:

        print("Geocoding error:", e)

        return None


# -----------------------------------------
# HAVERSINE DISTANCE
# -----------------------------------------

def haversine_distance(
    lat1,
    lon1,
    lat2,
    lon2
):

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
        * math.cos(lat2)
        * math.sin(dlon / 2) ** 2
    )

    c = 2 * math.atan2(
        math.sqrt(a),
        math.sqrt(1 - a)
    )

    return radius * c


# -----------------------------------------
# CALCULATE DELIVERY ETA
# -----------------------------------------

def calculate_delivery_eta(
    supplier_location,
    delivery_location
):

    supplier_coordinates = get_coordinates(
        supplier_location
    )

    delivery_coordinates = get_coordinates(
        delivery_location
    )

    if (
        not supplier_coordinates
        or not delivery_coordinates
    ):

        return None, None


    lat1, lon1 = supplier_coordinates
    lat2, lon2 = delivery_coordinates


    # -----------------------------------------
    # ROUTE USING OSRM
    # -----------------------------------------

    route_url = (
        "https://router.project-osrm.org/"
        "route/v1/driving/"
        f"{lon1},{lat1};{lon2},{lat2}"
    )

    params = {
        "overview": "false"
    }

    try:

        response = requests.get(
            route_url,
            params=params,
            timeout=15
        )

        response.raise_for_status()

        data = response.json()

        if (
            data.get("routes")
            and len(data["routes"]) > 0
        ):

            route = data["routes"][0]

            duration_seconds = route["duration"]

            duration_minutes = int(
                duration_seconds / 60
            )

        else:

            raise Exception(
                "Route not found"
            )

    except Exception as e:

        print("OSRM error:", e)

        # -----------------------------------------
        # FALLBACK CALCULATION
        # -----------------------------------------

        distance = haversine_distance(
            lat1,
            lon1,
            lat2,
            lon2
        )

        # Average speed for fallback
        average_speed = 40

        duration_minutes = int(
            (distance / average_speed) * 60
        )


    # -----------------------------------------
    # ETA
    # -----------------------------------------

    arrival_time = (
        datetime.now()
        +
        timedelta(
            minutes=duration_minutes
        )
    )

    delivery_date = arrival_time.strftime(
        "%Y-%m-%d"
    )

    delivery_time = arrival_time.strftime(
        "%I:%M %p"
    )

    return delivery_date, delivery_time


# -----------------------------------------
# HOME PAGE
# -----------------------------------------

@app.route("/")
def index():

    conn = get_db()

    products = conn.execute(
        "SELECT * FROM products ORDER BY id DESC"
    ).fetchall()

    conn.close()

    return render_template(
        "index.html",
        products=products
    )


# -----------------------------------------
# ADD PRODUCT
# -----------------------------------------

@app.route("/add", methods=["POST"])
def add_product():

    name = request.form.get(
        "name",
        ""
    )

    category = request.form.get(
        "category",
        ""
    )

    quantity = request.form.get(
        "quantity",
        0
    )

    price = request.form.get(
        "price",
        0
    )

    supplier = request.form.get(
        "supplier",
        ""
    )

    supplier_location = request.form.get(
        "supplier_location",
        ""
    )

    delivery_location = request.form.get(
        "delivery_location",
        ""
    )


    # -----------------------------------------
    # AUTOMATIC ETA
    # -----------------------------------------

    delivery_date, delivery_time = (
        calculate_delivery_eta(
            supplier_location,
            delivery_location
        )
    )


    conn = get_db()

    conn.execute("""
        INSERT INTO products (
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
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
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
    conn.close()

    return redirect("/")


# -----------------------------------------
# DELETE PRODUCT
# -----------------------------------------

@app.route("/delete/<int:id>")
def delete_product(id):

    conn = get_db()

    conn.execute(
        "DELETE FROM products WHERE id = ?",
        (id,)
    )

    conn.commit()
    conn.close()

    return redirect("/")


# -----------------------------------------
# EDIT PRODUCT
# -----------------------------------------

@app.route("/edit/<int:id>")
def edit_product(id):

    conn = get_db()

    product = conn.execute(
        "SELECT * FROM products WHERE id = ?",
        (id,)
    ).fetchone()

    conn.close()

    return render_template(
        "edit_product.html",
        product=product
    )


# -----------------------------------------
# UPDATE PRODUCT
# -----------------------------------------

@app.route("/update/<int:id>", methods=["POST"])
def update_product(id):

    name = request.form.get(
        "name",
        ""
    )

    category = request.form.get(
        "category",
        ""
    )

    quantity = request.form.get(
        "quantity",
        0
    )

    price = request.form.get(
        "price",
        0
    )

    supplier = request.form.get(
        "supplier",
        ""
    )

    supplier_location = request.form.get(
        "supplier_location",
        ""
    )

    delivery_location = request.form.get(
        "delivery_location",
        ""
    )


    # -----------------------------------------
    # RECALCULATE ETA
    # -----------------------------------------

    delivery_date, delivery_time = (
        calculate_delivery_eta(
            supplier_location,
            delivery_location
        )
    )


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
        id
    ))

    conn.commit()
    conn.close()

    return redirect("/")


# -----------------------------------------
# STOCK OUT
# -----------------------------------------

@app.route("/stock_out/<int:id>", methods=["GET", "POST"])
def stock_out(id):

    conn = get_db()

    product = conn.execute(
        "SELECT * FROM products WHERE id = ?",
        (id,)
    ).fetchone()

    if request.method == "POST":

        quantity_out = int(
            request.form.get(
                "quantity",
                0
            )
        )

        new_quantity = max(
            0,
            product["quantity"] - quantity_out
        )

        conn.execute("""
            UPDATE products
            SET quantity = ?
            WHERE id = ?
        """, (
            new_quantity,
            id
        ))

        conn.commit()

        conn.close()

        return redirect("/")

    conn.close()

    return render_template(
        "stock_out.html",
        product=product
    )


# -----------------------------------------
# SEARCH
# -----------------------------------------

@app.route("/search")
def search():

    query = request.args.get(
        "query",
        ""
    )

    conn = get_db()

    products = conn.execute("""
        SELECT * FROM products
        WHERE
            name LIKE ?
            OR category LIKE ?
            OR supplier LIKE ?
            OR supplier_location LIKE ?
            OR delivery_location LIKE ?
        ORDER BY id DESC
    """, (
        "%" + query + "%",
        "%" + query + "%",
        "%" + query + "%",
        "%" + query + "%",
        "%" + query + "%"
    )).fetchall()

    conn.close()

    return render_template(
        "index.html",
        products=products
    )


# -----------------------------------------
# LOW STOCK
# -----------------------------------------

@app.route("/low_stock")
def low_stock():

    conn = get_db()

    products = conn.execute("""
        SELECT * FROM products
        WHERE quantity <= 5
        ORDER BY quantity ASC
    """).fetchall()

    conn.close()

    return render_template(
        "index.html",
        products=products
    )


# -----------------------------------------
# MAP
# -----------------------------------------

@app.route("/map/<int:id>")
def product_map(id):

    conn = get_db()

    product = conn.execute(
        "SELECT * FROM products WHERE id = ?",
        (id,)
    ).fetchone()

    conn.close()

    return render_template(
        "map.html",
        product=product
    )


# -----------------------------------------
# BILL
# -----------------------------------------

@app.route("/bill/<int:id>")
def bill(id):

    conn = get_db()

    product = conn.execute(
        "SELECT * FROM products WHERE id = ?",
        (id,)
    ).fetchone()

    conn.close()

    return render_template(
        "bill.html",
        product=product
    )


# -----------------------------------------
# RUN APP
# -----------------------------------------

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )

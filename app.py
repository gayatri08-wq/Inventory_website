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
# CREATE / UPDATE DATABASE
# =========================================================

def create_table():

    conn = get_db()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id TEXT,
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

    existing_columns = [
        row["name"]
        for row in conn.execute(
            "PRAGMA table_info(products)"
        ).fetchall()
    ]

    required_columns = [
        ("product_id", "TEXT"),
        ("supplier_location", "TEXT"),
        ("delivery_location", "TEXT"),
        ("delivery_date", "TEXT"),
        ("delivery_time", "TEXT")
    ]

    for column_name, column_type in required_columns:

        if column_name not in existing_columns:

            conn.execute(
                f"ALTER TABLE products ADD COLUMN "
                f"{column_name} {column_type}"
            )

    conn.commit()
    conn.close()


# =========================================================
# CLEAN LOCATION
# =========================================================

def clean_location(location):

    if not location:
        return ""

    location = location.strip()

    location_lower = location.lower()

    location_map = {

        "mumbai":
            "Mumbai, Maharashtra, India",

        "bombay":
            "Mumbai, Maharashtra, India",

        "kurla":
            "Kurla, Mumbai, Maharashtra, India",

        "thane":
            "Thane, Maharashtra, India",

        "navi mumbai":
            "Navi Mumbai, Maharashtra, India",

        "pune":
            "Pune, Maharashtra, India",

        "nashik":
            "Nashik, Maharashtra, India",

        "nagpur":
            "Nagpur, Maharashtra, India",

        "aurangabad":
            "Chhatrapati Sambhajinagar, Maharashtra, India",

        "chhatrapati sambhajinagar":
            "Chhatrapati Sambhajinagar, Maharashtra, India",

        "kolhapur":
            "Kolhapur, Maharashtra, India",

        "solapur":
            "Solapur, Maharashtra, India",

        "surat":
            "Surat, Gujarat, India",

        "ahmedabad":
            "Ahmedabad, Gujarat, India",

        "vadodara":
            "Vadodara, Gujarat, India",

        "rajkot":
            "Rajkot, Gujarat, India",

        "delhi":
            "Delhi, India",

        "new delhi":
            "New Delhi, Delhi, India",

        "jaipur":
            "Jaipur, Rajasthan, India",

        "indore":
            "Indore, Madhya Pradesh, India",

        "bhopal":
            "Bhopal, Madhya Pradesh, India",

        "hyderabad":
            "Hyderabad, Telangana, India",

        "bangalore":
            "Bengaluru, Karnataka, India",

        "bengaluru":
            "Bengaluru, Karnataka, India",

        "chennai":
            "Chennai, Tamil Nadu, India",

        "kolkata":
            "Kolkata, West Bengal, India",

        "lucknow":
            "Lucknow, Uttar Pradesh, India",

        "patna":
            "Patna, Bihar, India",

        "goa":
            "Goa, India"
    }

    if location_lower in location_map:

        return location_map[location_lower]

    if "india" in location_lower:

        return location

    return location + ", India"


# =========================================================
# GET COORDINATES
# =========================================================

def get_coordinates(location):

    try:

        cleaned_location = clean_location(location)

        url = "https://nominatim.openstreetmap.org/search"

        params = {
            "q": cleaned_location,
            "format": "json",
            "limit": 5,
            "countrycodes": "in",
            "addressdetails": 1
        }

        headers = {
            "User-Agent":
                "InventoryManagementSystem/1.0"
        }

        response = requests.get(
            url,
            params=params,
            headers=headers,
            timeout=10
        )

        if response.status_code != 200:
            return None

        results = response.json()

        for result in results:

            address = result.get(
                "address",
                {}
            )

            country = address.get(
                "country",
                ""
            ).lower()

            if country == "india":

                return (
                    float(result["lat"]),
                    float(result["lon"])
                )

        if results:

            return (
                float(results[0]["lat"]),
                float(results[0]["lon"])
            )

    except Exception as error:

        print(
            "Geocoding error:",
            error
        )

    return None


# =========================================================
# HAVERSINE DISTANCE
# =========================================================

def haversine_distance(
    lat1,
    lon1,
    lat2,
    lon2
):

    earth_radius = 6371

    lat1 = math.radians(lat1)
    lat2 = math.radians(lat2)

    dlat = lat2 - lat1

    dlon = math.radians(lon2 - lon1)

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

    return earth_radius * c


# =========================================================
# CALCULATE DELIVERY ETA
# =========================================================

def calculate_delivery_eta(
    supplier_location,
    delivery_location
):

    # -----------------------------------------------------
    # Default fallback
    # -----------------------------------------------------

    fallback_arrival = (
        datetime.now()
        + timedelta(days=3)
    )

    origin = get_coordinates(
        supplier_location
    )

    destination = get_coordinates(
        delivery_location
    )

    # -----------------------------------------------------
    # Location not found
    # -----------------------------------------------------

    if not origin or not destination:

        return (
            fallback_arrival.strftime(
                "%Y-%m-%d"
            ),
            fallback_arrival.strftime(
                "%I:%M %p"
            )
        )

    origin_lat, origin_lon = origin

    destination_lat, destination_lon = destination

    # -----------------------------------------------------
    # OSRM ROAD ROUTE
    # -----------------------------------------------------

    try:

        route_url = (
            "https://router.project-osrm.org/"
            "route/v1/driving/"
            f"{origin_lon},{origin_lat};"
            f"{destination_lon},{destination_lat}"
        )

        params = {
            "overview": "false"
        }

        response = requests.get(
            route_url,
            params=params,
            timeout=10
        )

        if response.status_code == 200:

            data = response.json()

            routes = data.get(
                "routes",
                []
            )

            if routes:

                duration_seconds = (
                    routes[0]["duration"]
                )

                arrival = (
                    datetime.now()
                    + timedelta(
                        seconds=duration_seconds
                    )
                )

                return (
                    arrival.strftime(
                        "%Y-%m-%d"
                    ),
                    arrival.strftime(
                        "%I:%M %p"
                    )
                )

    except Exception as error:

        print(
            "OSRM error:",
            error
        )

    # -----------------------------------------------------
    # FALLBACK DISTANCE
    # -----------------------------------------------------

    try:

        distance_km = haversine_distance(
            origin_lat,
            origin_lon,
            destination_lat,
            destination_lon
        )

        # Average road speed
        average_speed = 40

        travel_hours = (
            distance_km / average_speed
        )

        arrival = (
            datetime.now()
            + timedelta(
                hours=travel_hours
            )
        )

        return (
            arrival.strftime(
                "%Y-%m-%d"
            ),
            arrival.strftime(
                "%I:%M %p"
            )
        )

    except Exception as error:

        print(
            "Fallback ETA error:",
            error
        )

        return (
            fallback_arrival.strftime(
                "%Y-%m-%d"
            ),
            fallback_arrival.strftime(
                "%I:%M %p"
            )
        )


# =========================================================
# HOME
# =========================================================

@app.route("/")
def index():

    conn = get_db()

    products = conn.execute(
        """
        SELECT *
        FROM products
        ORDER BY id DESC
        """
    ).fetchall()

    conn.close()

    return render_template(
        "index.html",
        products=products
    )


# =========================================================
# ADD PRODUCT
# =========================================================

@app.route(
    "/add",
    methods=["POST"]
)
def add_product():

    product_id = request.form.get(
        "product_id",
        ""
    ).strip()

    name = request.form.get(
        "name",
        ""
    ).strip()

    category = request.form.get(
        "category",
        ""
    ).strip()

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
    ).strip()

    supplier_location = request.form.get(
        "supplier_location",
        ""
    ).strip()

    delivery_location = request.form.get(
        "delivery_location",
        ""
    ).strip()

    # -----------------------------------------------------
    # DELIVERY ETA
    # -----------------------------------------------------

    delivery_date = None
    delivery_time = None

    if (
        supplier_location
        and delivery_location
    ):

        delivery_date, delivery_time = (
            calculate_delivery_eta(
                supplier_location,
                delivery_location
            )
        )

    conn = get_db()

    conn.execute(
        """
        INSERT INTO products
        (
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
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
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
        )
    )

    conn.commit()
    conn.close()

    return redirect("/")


# =========================================================
# DELETE
# =========================================================

@app.route(
    "/delete/<int:id>"
)
def delete_product(id):

    conn = get_db()

    conn.execute(
        """
        DELETE FROM products
        WHERE id = ?
        """,
        (id,)
    )

    conn.commit()
    conn.close()

    return redirect("/")


# =========================================================
# EDIT
# =========================================================

@app.route(
    "/edit/<int:id>"
)
def edit_product(id):

    conn = get_db()

    product = conn.execute(
        """
        SELECT *
        FROM products
        WHERE id = ?
        """,
        (id,)
    ).fetchone()

    conn.close()

    if product is None:

        return "Product not found", 404

    return render_template(
        "edit_product.html",
        product=product
    )


# =========================================================
# UPDATE
# =========================================================

@app.route(
    "/update/<int:id>",
    methods=["POST"]
)
def update_product(id):

    product_id = request.form.get(
        "product_id",
        ""
    ).strip()

    name = request.form.get(
        "name",
        ""
    ).strip()

    category = request.form.get(
        "category",
        ""
    ).strip()

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
    ).strip()

    supplier_location = request.form.get(
        "supplier_location",
        ""
    ).strip()

    delivery_location = request.form.get(
        "delivery_location",
        ""
    ).strip()

    delivery_date = None
    delivery_time = None

    if (
        supplier_location
        and delivery_location
    ):

        delivery_date, delivery_time = (
            calculate_delivery_eta(
                supplier_location,
                delivery_location
            )
        )

    conn = get_db()

    conn.execute(
        """
        UPDATE products

        SET
            product_id = ?,
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
        """,
        (
            product_id,
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
        )
    )

    conn.commit()
    conn.close()

    return redirect("/")


# =========================================================
# STOCK OUT
# =========================================================

@app.route(
    "/stock-out/<int:id>",
    methods=["GET", "POST"]
)
def stock_out(id):

    conn = get_db()

    product = conn.execute(
        """
        SELECT *
        FROM products
        WHERE id = ?
        """,
        (id,)
    ).fetchone()

    if product is None:

        conn.close()

        return "Product not found", 404

    if request.method == "POST":

        quantity = int(
            request.form.get(
                "quantity",
                0
            )
        )

        current_quantity = (
            product["quantity"] or 0
        )

        new_quantity = (
            current_quantity - quantity
        )

        if new_quantity < 0:
            new_quantity = 0

        conn.execute(
            """
            UPDATE products
            SET quantity = ?
            WHERE id = ?
            """,
            (
                new_quantity,
                id
            )
        )

        conn.commit()
        conn.close()

        return redirect("/")

    conn.close()

    return render_template(
        "stock_out.html",
        product=product
    )


# =========================================================
# SEARCH
# =========================================================

@app.route("/search")
def search():

    keyword = request.args.get(
        "keyword",
        ""
    ).strip()

    conn = get_db()

    products = conn.execute(
        """
        SELECT *
        FROM products

        WHERE
            product_id LIKE ?
            OR name LIKE ?
            OR category LIKE ?
            OR supplier LIKE ?

        ORDER BY id DESC
        """,
        (
            f"%{keyword}%",
            f"%{keyword}%",
            f"%{keyword}%",
            f"%{keyword}%"
        )
    ).fetchall()

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

    products = conn.execute(
        """
        SELECT *
        FROM products

        WHERE quantity <= 5

        ORDER BY quantity ASC
        """
    ).fetchall()

    conn.close()

    return render_template(
        "index.html",
        products=products
    )


# =========================================================
# MAP
# =========================================================

@app.route(
    "/map/<int:id>"
)
def product_map(id):

    conn = get_db()

    product = conn.execute(
        """
        SELECT *
        FROM products
        WHERE id = ?
        """,
        (id,)
    ).fetchone()

    conn.close()

    if product is None:

        return "Product not found", 404

    return render_template(
        "map.html",
        product=product
    )


# =========================================================
# BILL
# =========================================================

@app.route(
    "/bill/<int:id>"
)
def bill(id):

    conn = get_db()

    product = conn.execute(
        """
        SELECT *
        FROM products
        WHERE id = ?
        """,
        (id,)
    ).fetchone()

    conn.close()

    if product is None:

        return "Product not found", 404

    return render_template(
        "bill.html",
        product=product
    )


# =========================================================
# START
# =========================================================

create_table()


if __name__ == "__main__":

    app.run(
        debug=True
    )

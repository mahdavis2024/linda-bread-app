# Standard library imports
import os
import re
import secrets
import string
from pathlib import Path
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

# Third-party imports
from dotenv import load_dotenv
from flask import (
    Flask, 
    flash,
    redirect, 
    render_template, 
    request, 
    send_from_directory,
    url_for
)
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager,
    UserMixin,
    login_required,
    login_user,
    logout_user
)
from flask_wtf.csrf import CSRFProtect
from werkzeug.security import check_password_hash
from PIL import Image, UnidentifiedImageError


# Application configuration
load_dotenv()

app = Flask(__name__)

app.config["SECRET_KEY"] = os.environ["SECRET_KEY"]
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///linda_bread.db"
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024


# Flask extensions
db = SQLAlchemy(app)
csrf = CSRFProtect(app)

login_manager = LoginManager(app)
login_manager.login_view = "admin_login"


# File storage configuration
UPLOAD_FOLDER = Path(app.instance_path) / "uploads"

UPLOAD_FOLDER.mkdir(
    parents=True,
    exist_ok=True
)
UPLOAD_FOLDER = Path(app.instance_path) / "uploads"

UPLOAD_FOLDER.mkdir(
    parents=True,
    exist_ok=True
)


# Database models
class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    order_code = db.Column(
        db.String(7),
        unique=True,
        nullable=False
    )

    customer_name = db.Column(
        db.String(100),
        nullable=False
    )

    phone = db.Column(
        db.String(30),
        nullable=False
    )

    quantity = db.Column(
        db.Integer,
        nullable=False
    )

    amount_cents = db.Column(
        db.Integer,
        nullable=False
    )

    delivery_date = db.Column(
        db.Date,
        nullable=False
    )

    screenshot_path = db.Column(
        db.String(255),
        nullable=True
    )

    status = db.Column(
        db.String(30),
        nullable=False,
        default="AWAITING_PAYMENT"
    )

    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )

    approved_at = db.Column(
        db.DateTime,
        nullable=True
    )


class Admin(UserMixin, db.Model):
    id = db.Column(
        db.Integer,
        primary_key=True
    )

    username = db.Column(
        db.String(50),
        unique=True,
        nullable=False
    )

    password_hash = db.Column(
        db.String(255),
        nullable=False
    )


class BusinessSettings(db.Model):
    id = db.Column(
        db.Integer,
        primary_key=True
    )

    mbway_number = db.Column(
        db.String(30),
        nullable=False
    )

    whatsapp_number = db.Column(
        db.String(30),
        nullable=False
    )


class DayCapacity(db.Model):
    id = db.Column(
        db.Integer,
        primary_key=True
    )

    production_date = db.Column(
        db.Date,
        unique=True,
        nullable=False
    )

    capacity_total = db.Column(
        db.Integer,
        nullable=False,
        default=21
    )

    capacity_used = db.Column(
        db.Integer,
        nullable=False,
        default=0
    )


# Authentication helpers
@login_manager.user_loader
def load_admin(admin_id):
    return db.session.get(Admin, int(admin_id))


# Jinja template filters
@app.template_filter("portugal_datetime")
def format_portugal_datetime(value):
    if value is None:
        return ""

    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)

    portugal_time = value.astimezone(
        ZoneInfo("Europe/Lisbon")
    )

    return portugal_time.strftime("%d-%m-%Y %H:%M")


# Application helper functions

def get_booking_window():
    today = date.today()
    minimum_date = today + timedelta(days=1)
    maximum_date = today + timedelta(days=14)

    return minimum_date, maximum_date


def ensure_booking_window_capacities(
    minimum_date,
    maximum_date
):
    current_date = minimum_date

    while current_date <= maximum_date:
        existing_capacity = db.session.execute(
            db.select(DayCapacity).filter_by(
                production_date=current_date
            )
        ).scalar_one_or_none()

        if existing_capacity is None:
            day_capacity = DayCapacity(
                production_date=current_date,
                capacity_total=21,
                capacity_used=0
            )

            db.session.add(day_capacity)

        current_date += timedelta(days=1)

    db.session.commit()


def generate_order_code():
    characters = string.ascii_uppercase + string.digits

    while True:
        order_code = "".join(
            secrets.choice(characters)
            for _ in range(7)
        )

        existing_order = db.session.execute(
            db.select(Order).filter_by(order_code=order_code)
        ).scalar_one_or_none()

        if existing_order is None:
            return order_code


def calculate_price_cents(quantity):
    prices_up_to_six = {
        1: 200,
        2: 400,
        3: 500,
        4: 700,
        5: 900,
        6: 1000
    }

    if quantity <= 6:
        return prices_up_to_six[quantity]

    return 1000 + (quantity - 6) * 150


def get_business_settings():
    settings = db.session.get(
        BusinessSettings,
        1
    )

    if settings is None:
        settings = BusinessSettings(
            id=1,
            mbway_number="",
            whatsapp_number=""
        )

        db.session.add(settings)
        db.session.commit()

    return settings


def get_available_booking_days(
    minimum_date,
    maximum_date
):
    capacities = db.session.execute(
        db.select(DayCapacity)
        .where(
            DayCapacity.production_date >= minimum_date,
            DayCapacity.production_date <= maximum_date
        )
        .order_by(DayCapacity.production_date)
    ).scalars().all()

    pending_orders = db.session.execute(
        db.select(Order).where(
            Order.delivery_date >= minimum_date,
            Order.delivery_date <= maximum_date,
            Order.status == "PENDING_VERIFICATION"
        )
    ).scalars().all()

    pending_quantities = {}

    for order in pending_orders:
        pending_quantities[order.delivery_date] = (
            pending_quantities.get(
                order.delivery_date,
                0
            )
            + order.quantity
        )

    available_days = []

    for day in capacities:
        pending_quantity = pending_quantities.get(
            day.production_date,
            0
        )

        remaining_capacity = (
            day.capacity_total
            - day.capacity_used
            - pending_quantity
        )

        remaining_capacity = max(
            remaining_capacity,
            0
        )

        available_days.append({
            "date_value": day.production_date.isoformat(),
            "weekday": day.production_date.strftime("%A"),
            "date_display": day.production_date.strftime("%d-%m-%Y"),
            "capacity_total": day.capacity_total,
            "capacity_used": day.capacity_used,
            "pending_quantity": pending_quantity,
            "remaining_capacity": remaining_capacity,
            "sold_out": remaining_capacity == 0
        })

    return available_days



# Public customer routes
@app.route("/")
def home():
    return render_template(
        "index.html",
        title="Linda Bread"
    )


@app.route("/reserve", methods=["GET", "POST"])
def reserve():

    minimum_date, maximum_date = get_booking_window()

    ensure_booking_window_capacities( 
        minimum_date,
        maximum_date
    )

    available_days = get_available_booking_days(
        minimum_date,
        maximum_date
    )

    if request.method == "POST":
        customer_name = request.form.get("customer_name", "").strip()
        phone = request.form.get("phone", "").strip()
        delivery_date = request.form.get("delivery_date", "").strip()
        quantity = request.form.get("quantity", "").strip()

        if not customer_name or not phone or not delivery_date or not quantity:
            return render_template(
                "reserve.html",
                title="Reserve Bread",
                error="Please complete all fields.",
                customer_name=customer_name,
                phone=phone,
                delivery_date=delivery_date,
                quantity=quantity,
                available_days=available_days
            )

        if len(customer_name) < 2:
            return render_template(
                "reserve.html",
                title="Reserve Bread",
                error="Please enter a name with at least 2 characters.",
                customer_name=customer_name,
                phone=phone,
                delivery_date=delivery_date,
                quantity=quantity,
                available_days=available_days
            )

        if not re.fullmatch(r"[0-9+()\-\s]+", phone):
            return render_template(
                "reserve.html",
                title="Reserve Bread",
                error="Please enter a valid phone number.",
                customer_name=customer_name,
                phone=phone,
                delivery_date=delivery_date,
                quantity=quantity,
                available_days=available_days
            )

        phone_digits = re.sub(r"\D", "", phone)
        if len(phone_digits) < 7 or len(phone_digits) > 15:
            return render_template(
                "reserve.html",
                title="Reserve Bread",
                error="The phone number must contain between 7 and 15 digits.",
                customer_name=customer_name,
                phone=phone,
                delivery_date=delivery_date,
                quantity=quantity,
                available_days=available_days
            )

        try:
            delivery_date_value = date.fromisoformat(delivery_date)
        except ValueError:
            return render_template(
                "reserve.html",
                title="Reserve Bread",
                error="Please enter a valid production date.",
                customer_name=customer_name,
                phone=phone,
                delivery_date=delivery_date,
                quantity=quantity,
                available_days=available_days
            )

        if delivery_date_value < minimum_date or delivery_date_value > maximum_date:
            return render_template(
                "reserve.html",
                title="Reserve Bread",
                error="Please select a production date within the available booking period.",
                customer_name=customer_name,
                phone=phone,
                delivery_date=delivery_date,
                quantity=quantity,
                available_days=available_days
            )

        selected_day = next(
            (
                day
                for day in available_days
                if day["date_value"] == delivery_date
            ),
            None
        )

        if selected_day is None:
            return render_template(
                "reserve.html",
                title="Reserve Bread",
                error="Please select an available production date.",
                customer_name=customer_name,
                phone=phone,
                delivery_date=delivery_date,
                quantity=quantity,
                available_days=available_days
            )

        if selected_day["sold_out"]:
            return render_template(
                "reserve.html",
                title="Reserve Bread",
                error="The selected production date is sold out.",
                customer_name=customer_name,
                phone=phone,
                delivery_date="",
                quantity=quantity,
                available_days=available_days
            )

        try:
            quantity_number = int(quantity)
        except ValueError:
            return render_template(
                "reserve.html",
                title="Reserve Bread",
                error="Please enter a valid bread quantity.",
                customer_name=customer_name,
                phone=phone,
                delivery_date=delivery_date,
                quantity=quantity,
                available_days=available_days
            )

        if quantity_number < 1 or quantity_number > 21:
            return render_template(
                "reserve.html",
                title="Reserve Bread",
                error="Quantity must be between 1 and 21 breads.",
                customer_name=customer_name,
                phone=phone,
                delivery_date=delivery_date,
                quantity=quantity,
                available_days=available_days
            )

        if quantity_number > selected_day["remaining_capacity"]:
            return render_template(
                "reserve.html",
                title="Reserve Bread",
                error=(
                    "Only "
                    f"{selected_day['remaining_capacity']} "
                    "breads are available for the selected date."
                ),
                customer_name=customer_name,
                phone=phone,
                delivery_date=delivery_date,
                quantity=quantity,
                available_days=available_days
            )

        amount_cents = calculate_price_cents(quantity_number)
        order_code = generate_order_code()

        # Commit successful order to the database order table
        new_order = Order(
            order_code=order_code,
            customer_name=customer_name,
            phone=phone,
            quantity=quantity_number,
            amount_cents=amount_cents,
            delivery_date=delivery_date_value
        )

        db.session.add(new_order)
        db.session.commit()

        # Success: If all validations pass, redirect to the confirmation page
        return redirect(
            url_for(
                "payment",
                order_code=order_code
            )
        )

    # Request method is GET: render the empty reservation form
    return render_template(
        "reserve.html",
        title="Reserve Bread",
        available_days=available_days
    )


@app.route("/payment/<order_code>", methods=["GET", "POST"])
def payment(order_code):
    order = db.session.execute(
        db.select(Order).filter_by(
            order_code=order_code
        )
    ).scalar_one_or_none()

    if order is None:
        return "Order not found.", 404

    settings = get_business_settings()

    if not settings.mbway_number:
        return "Payment settings are not configured.", 503

    amount_text = (
        f"{order.amount_cents // 100}."
        f"{order.amount_cents % 100:02d}"
    )

    if request.method == "POST":
        screenshot = request.files.get(
            "payment_screenshot"
        )

        if screenshot is None or not screenshot.filename:
            amount_text = (
                f"{order.amount_cents // 100}."
                f"{order.amount_cents % 100:02d}"
            )

            return render_template(
                "payment.html",
                title="Complete Payment",
                order=order,
                settings=settings,
                amount=amount_text,
                error="Please select a payment screenshot."
            )

        try:
            image = Image.open(screenshot.stream)
            image.verify()

            screenshot.stream.seek(0)

            image = Image.open(screenshot.stream)
            image.load()

        except (UnidentifiedImageError, OSError):
            amount_text = (
                f"{order.amount_cents // 100}."
                f"{order.amount_cents % 100:02d}"
            )

            return render_template(
                "payment.html",
                title="Complete Payment",
                order=order,
                settings=settings,
                amount=amount_text,
                error="The selected file is not a valid image."
            )

        image.thumbnail((1600, 1600))

        if image.mode != "RGB":
            image = image.convert("RGB")

        screenshot_filename = (
            f"{order.order_code}.webp"
        )

        screenshot_path = (
            UPLOAD_FOLDER / screenshot_filename
        )

        image.save(
            screenshot_path,
            "WEBP",
            quality=85
        )

        order.screenshot_path = screenshot_filename
        order.status = "PENDING_VERIFICATION"

        db.session.commit()

        return redirect(
            url_for(
                "confirmation",
                order_code=order.order_code
            )
        )

    return render_template(
        "payment.html",
        title="Complete Payment",
        order=order,
        settings=settings,
        amount=amount_text
    )


@app.route("/confirmation/<order_code>")
def confirmation(order_code):
    order = db.session.execute(
        db.select(Order).filter_by(order_code=order_code)
    ).scalar_one_or_none()

    if order is None:
        return "Order not found.", 404

    amount_text = (
        f"{order.amount_cents // 100}."
        f"{order.amount_cents % 100:02d}"
    )

    return render_template(
        "confirmation.html",
        title="Reservation Received",
        customer_name=order.customer_name,
        phone=order.phone,
        delivery_date=order.delivery_date.isoformat(),
        quantity=order.quantity,
        amount=amount_text,
        order_code=order.order_code
    )


# Protected admin routes
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        admin = db.session.execute(
            db.select(Admin).filter_by(username=username)
        ).scalar_one_or_none()

        if admin is None or not check_password_hash(
            admin.password_hash,
            password
        ):
            return render_template(
                "admin_login.html",
                title="Admin Login",
                error="Invalid username or password.",
                username=username
            )

        login_user(admin)

        return redirect(
            url_for("admin_orders")
        )

    return render_template(
        "admin_login.html",
        title="Admin Login"
    )


@app.route("/admin/logout", methods=["POST"])
@login_required
def admin_logout():
    logout_user()

    return redirect(
        url_for("admin_login")
    )


@app.route("/admin/orders")
@login_required
def admin_orders():
    orders = db.session.execute(
        db.select(Order).order_by(Order.created_at.desc())
    ).scalars().all()

    minimum_date, maximum_date = get_booking_window()

    ensure_booking_window_capacities(
        minimum_date,
        maximum_date
    )

    capacity_days = get_available_booking_days(
        minimum_date,
        maximum_date
    )

    return render_template(
        "admin_orders.html",
        title="Orders",
        orders=orders,
        capacity_days=capacity_days
    )


@app.route("/admin/settings", methods=["GET", "POST"])
@login_required
def admin_settings():
    settings = get_business_settings()

    if request.method == "POST":
        mbway_number = request.form.get(
            "mbway_number",
            ""
        ).strip()

        whatsapp_number = request.form.get(
            "whatsapp_number",
            ""
        ).strip()

        if not mbway_number or not whatsapp_number:
            return render_template(
                "admin_settings.html",
                title="Payment Settings",
                settings=settings,
                error="Please complete both fields.",
                saved=False
            )

        settings.mbway_number = mbway_number
        settings.whatsapp_number = whatsapp_number

        db.session.commit()

        flash("Payment settings saved successfully.")

        return redirect(
            url_for("admin_settings")
        )

    return render_template(
        "admin_settings.html",
        title="Payment Settings",
        settings=settings,
    )


@app.route("/admin/orders/<order_code>/payment-proof")
@login_required
def admin_payment_proof(order_code):
    order = db.session.execute(
        db.select(Order).filter_by(
            order_code=order_code
        )
    ).scalar_one_or_none()

    if order is None:
        return "Order not found.", 404

    if not order.screenshot_path:
        return "Payment screenshot not found.", 404

    return send_from_directory(
        UPLOAD_FOLDER,
        order.screenshot_path
    )


@app.route(
    "/admin/orders/<order_code>/action",
    methods=["POST"]
)
@login_required
def admin_order_action(order_code):
    order = db.session.execute(
        db.select(Order).filter_by(
            order_code=order_code
        )
    ).scalar_one_or_none()

    if order is None:
        return "Order not found.", 404

    action = request.form.get(
        "action",
        ""
    ).strip()

    if action == "mark_payment_reported":
        if order.status != "AWAITING_PAYMENT":
            flash(
                "This order is not awaiting payment."
            )

            return redirect(
                url_for("admin_orders")
            )

        minimum_date, maximum_date = (
            get_booking_window()
        )

        available_days = (
            get_available_booking_days(
                minimum_date,
                maximum_date
            )
        )

        selected_day = next(
            (
                day
                for day in available_days
                if day["date_value"]
                == order.delivery_date.isoformat()
            ),
            None
        )

        if selected_day is None:
            flash(
                "Warning: this order date is outside "
                "the current booking window."
            )

        elif (
            order.quantity
            > selected_day["remaining_capacity"]
        ):
            shortage = (
                order.quantity
                - selected_day["remaining_capacity"]
            )

            flash(
                f"Warning: order {order.order_code} "
                f"exceeds remaining capacity by "
                f"{shortage} breads. Payment was "
                "still marked as reported."
            )

        order.status = "PENDING_VERIFICATION"

        db.session.commit()

        flash(
            f"Payment reported for order "
            f"{order.order_code}."
        )

    elif action == "undo_payment_reported":
        if order.status != "PENDING_VERIFICATION":
            flash(
                "Only orders pending verification "
                "can be returned to awaiting payment."
            )

            return redirect(
                url_for("admin_orders")
            )

        if order.screenshot_path:
            flash(
                "This action is unavailable because "
                "a payment screenshot was uploaded."
            )

            return redirect(
                url_for("admin_orders")
            )

        order.status = "AWAITING_PAYMENT"

        db.session.commit()

        flash(
            f"Payment report was undone for order "
            f"{order.order_code}."
        )

    else:
        flash(
            "Please select a valid order action."
        )

    return redirect(
        url_for("admin_orders")
    )

# Create missing database tables
with app.app_context():
    db.create_all()

# Start the development server
if __name__ == "__main__":
    app.run(debug=True)
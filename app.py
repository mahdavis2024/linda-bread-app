import re
import secrets
import string
from datetime import date, datetime, timedelta, timezone

from flask import Flask, render_template, request
from flask_sqlalchemy import SQLAlchemy


app = Flask(__name__)

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///linda_bread.db"

db = SQLAlchemy(app)

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
        db.String(20),
        nullable=False,
        default="PENDING"
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

@app.route("/")
def home():
    return render_template(
        "index.html",
        title="Linda Bread"
    )


@app.route("/reserve", methods=["GET", "POST"])
def reserve():

    today = date.today()
    minimum_date = today + timedelta(days=1)
    maximum_date = today + timedelta(days=14)
    minimum_date_text = minimum_date.isoformat()
    maximum_date_text = maximum_date.isoformat()

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
                minimum_date=minimum_date_text,
                maximum_date=maximum_date_text
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
                minimum_date=minimum_date_text,
                maximum_date=maximum_date_text
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
                minimum_date=minimum_date_text,
                maximum_date=maximum_date_text
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
                minimum_date=minimum_date_text,
                maximum_date=maximum_date_text
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
                minimum_date=minimum_date_text,
                maximum_date=maximum_date_text
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
                minimum_date=minimum_date_text,
                maximum_date=maximum_date_text
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
                minimum_date=minimum_date_text,
                maximum_date=maximum_date_text
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
                minimum_date=minimum_date_text,
                maximum_date=maximum_date_text
            )

        amount_cents = calculate_price_cents(quantity_number)

        amount_text = (
                f"{amount_cents // 100}."
                f"{amount_cents % 100:02d}"
            )

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


        # Success: If all validations pass, render the confirmation response
        return render_template(
            "confirmation.html",
            title="Reservation Received",
            customer_name=customer_name,
            phone=phone,
            delivery_date=delivery_date,
            quantity=quantity_number, 
            amount=amount_text,
            order_code=order_code
        )


    # Request method is GET: render the empty reservation form
    return render_template(
        "reserve.html",
        title="Reserve Bread",
        minimum_date=minimum_date_text,
        maximum_date=maximum_date_text
    )

with app.app_context():
    db.create_all()


if __name__ == "__main__":
    app.run(debug=True)
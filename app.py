import re
from datetime import date, timedelta
from flask import Flask, render_template, request

app = Flask(__name__)

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

        # Success: If all validations pass, render the confirmation response
        return render_template(
            "confirmation.html",
            title="Reservation Received",
            customer_name=customer_name,
            phone=phone,
            delivery_date=delivery_date,
            quantity=quantity_number, 
            amount=amount_text
        )



    return render_template(
        "reserve.html",
        title="Reserve Bread",
        minimum_date=minimum_date_text,
        maximum_date=maximum_date_text
    )

if __name__ == "__main__":
    app.run(debug=True)
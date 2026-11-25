from flask import Flask, render_template, request

app = Flask(__name__)


@app.route("/")
def home():
    return render_template(
        "index.html",
        title="Linda Bread"
    )


@app.route("/reserve", methods=["GET", "POST"])
def reserve():
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
                quantity=quantity
            )

        if len(customer_name) < 2:
            return render_template(
                "reserve.html",
                title="Reserve Bread",
                error="Please enter a name with at least 2 characters.",
                customer_name=customer_name,
                phone=phone,
                delivery_date=delivery_date,
                quantity=quantity
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
                quantity=quantity
            )

        if quantity_number < 1 or quantity_number > 21:
            return render_template(
                "reserve.html",
                title="Reserve Bread",
                error="Quantity must be between 1 and 21 breads.",
                customer_name=customer_name,
                phone=phone,
                delivery_date=delivery_date,
                quantity=quantity
            )

        # Success: If all validations pass, render the confirmation page
        return render_template(
            "confirmation.html",
            title="Reservation Received",
            customer_name=customer_name,
            phone=phone,
            delivery_date=delivery_date,
            quantity=quantity_number
        )

    return render_template(
        "reserve.html",
        title="Reserve Bread"
    )

if __name__ == "__main__":
    app.run(debug=True)
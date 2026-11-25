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
        customer_name = request.form["customer_name"]
        phone = request.form["phone"]
        delivery_date = request.form["delivery_date"]
        quantity = request.form["quantity"]

        return render_template(
            "confirmation.html",
            title="Reservation Received",
            customer_name=customer_name,
            phone=phone,
            delivery_date=delivery_date,
            quantity=quantity
        )

    return render_template(
        "reserve.html",
        title="Reserve Bread"
    )

if __name__ == "__main__":
    app.run(debug=True)
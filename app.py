from flask import Flask, render_template

app = Flask(__name__)


@app.route("/")
def home():
    return render_template(
        "index.html",
        title="Linda Bread"
    )


@app.route("/reserve")
def reserve():
    return render_template(
        "reserve.html",
        title="Reserve Bread"
    )

if __name__ == "__main__":
    app.run(debug=True)
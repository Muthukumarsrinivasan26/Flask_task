import os
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail, Message
import threading
from datetime import datetime

# ------------------------------------------------
# FLASK CONFIG
# ------------------------------------------------

app = Flask(__name__)
app.config['SECRET_KEY'] = "secret-key"

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///" + os.path.join(BASE_DIR, "billing.db")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Email server (Debug server prints emails)
app.config['MAIL_SERVER'] = "localhost"
app.config['MAIL_PORT'] = 1025
app.config['MAIL_DEFAULT_SENDER'] = "billing@example.com"

db = SQLAlchemy(app)
mail = Mail(app)

# ------------------------------------------------
# MODELS
# ------------------------------------------------

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120))
    product_id = db.Column(db.String(50), unique=True)
    stock = db.Column(db.Integer)
    price = db.Column(db.Float)
    tax = db.Column(db.Float)

class Purchase(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_email = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    paid_amount = db.Column(db.Float)

    items = db.relationship("PurchaseItem", backref="purchase", cascade="all,delete")

    def total(self):
        return sum(item.total_price() for item in self.items)

class PurchaseItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    purchase_id = db.Column(db.Integer, db.ForeignKey("purchase.id"))
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"))
    qty = db.Column(db.Integer)

    product = db.relationship("Product")

    def total_price(self):
        base = self.product.price * self.qty
        return base + (base * self.product.tax / 100)

class Denomination(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    value = db.Column(db.Integer)
    count = db.Column(db.Integer)

# ------------------------------------------------
# SEND EMAIL IN BACKGROUND
# ------------------------------------------------

def send_async(app, msg):
    with app.app_context():
        mail.send(msg)

# ------------------------------------------------
# UTILITY - CHANGE CALCULATION
# ------------------------------------------------

def calc_change(balance, denominations):
    change = {}
    remaining = int(balance)

    for d in sorted(denominations, key=lambda x: -x.value):
        use = min(remaining // d.value, d.count)
        if use > 0:
            change[d.value] = use
            remaining -= d.value * use
    return change

# ------------------------------------------------
# ROUTES
# ------------------------------------------------
'''
@app.before_first_request
def seed():
    db.create_all()

    if not Product.query.first():
        data = [
            ("Pen", "PEN001", 100, 10.0, 5),
            ("Notebook", "NOTE001", 50, 40.0, 12),
            ("Water Bottle", "BOTT001", 30, 120.0, 18),
        ]
        for name, pid, stock, price, tax in data:
            db.session.add(Product(name=name, product_id=pid, stock=stock, price=price, tax=tax))

    if not Denomination.query.first():
        for v in [2000, 500, 200, 100, 50, 20, 10, 5, 2, 1]:
            db.session.add(Denomination(value=v, count=10))

    db.session.commit()
'''
def seed():
    db.create_all()

    if not Product.query.first():
        data = [
            ("Pen", "PEN001", 100, 10.0, 5),
            ("Notebook", "NOTE001", 50, 40.0, 12),
            ("Water Bottle", "BOTT001", 30, 120.0, 18),
        ]
        for name, pid, stock, price, tax in data:
            db.session.add(Product(name=name, product_id=pid, stock=stock, price=price, tax=tax))

    if not Denomination.query.first():
        for v in [2000, 500, 200, 100, 50, 20, 10, 5, 2, 1]:
            db.session.add(Denomination(value=v, count=10))

    db.session.commit()


@app.route("/", methods=["GET", "POST"])
def bill_form():
    denoms = Denomination.query.all()

    if request.method == "POST":
        email = request.form["customer_email"]
        paid = float(request.form["paid_amount"])

        product_ids = request.form.getlist("product_id[]")
        qtys = request.form.getlist("qty[]")

        # Update denomination counts
        for d in denoms:
            d.count = int(request.form.get(f"den_{d.value}", d.count))
        db.session.commit()

        # Create purchase
        p = Purchase(customer_email=email, paid_amount=paid)
        db.session.add(p)
        db.session.flush()

        total = 0

        for pid, q in zip(product_ids, qtys):
            product = Product.query.filter_by(product_id=pid).first()
            q = int(q)

            if not product or q <= 0 or q > product.stock:
                flash("Invalid product or stock error", "danger")
                return redirect("/")

            db.session.add(PurchaseItem(purchase_id=p.id, product_id=product.id, qty=q))
            product.stock -= q
            total += (product.price * q) + ((product.price * q) * product.tax / 100)

        db.session.commit()

        balance = paid - total
        change = calc_change(balance, Denomination.query.all())

        # Email
        msg = Message(
            subject=f"Invoice #{p.id}",
            recipients=[email],
            body=f"Your bill total is {total}"
        )
        threading.Thread(target=send_async, args=(app, msg)).start()

        return render_template("bill_result.html",
                               p=p, items=p.items,
                               total=total, balance=balance,
                               change=change)

    return render_template("bill_form.html", denoms=denoms)

@app.route("/history")
def history():
    email = request.args.get("email", "")
    purchases = Purchase.query.filter_by(customer_email=email).all() if email else []
    return render_template("history.html", purchases=purchases, email=email)

@app.route("/purchase/<int:id>")
def purchase_detail(id):
    p = Purchase.query.get_or_404(id)
    return render_template("history_detail.html", p=p, items=p.items)

# ------------------------------------------------
# RUN APP
# ------------------------------------------------
'''
if __name__ == "__main__":
    print("Start email debug server:")
    print("python -m smtpd -n -c DebuggingServer localhost:1025")
    app.run(debug=True)
'''
if __name__ == "__main__":
    with app.app_context():
        seed()

    print("Start email debug server:")
    print("python -m smtpd -n -c DebuggingServer localhost:1025")
    app.run(debug=True)

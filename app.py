from flask import Flask, render_template, request, redirect, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os

app = Flask(__name__)
app.secret_key = "food_ordering_secret_key"

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///food_ordering.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["UPLOAD_FOLDER"] = "static/uploads"

db = SQLAlchemy(app)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), default="user")


class Food(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    price = db.Column(db.Float, nullable=False)
    description = db.Column(db.Text, nullable=False)
    image = db.Column(db.String(200))


class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), nullable=False)
    food_name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    payment_method = db.Column(db.String(50), default="Cash on Delivery")


@app.route("/")
def index():
    search = request.args.get("search", "")

    if search:
        foods = Food.query.filter(
            Food.name.contains(search),
            Food.category == "Food"
        ).all()

        drinks = Food.query.filter(
            Food.name.contains(search),
            Food.category == "Drinks"
        ).all()
    else:
        foods = Food.query.filter_by(category="Food").all()
        drinks = Food.query.filter_by(category="Drinks").all()

    return render_template("index.html", foods=foods, drinks=drinks, search=search)


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = generate_password_hash(request.form["password"])

        user = User(username=username, password=password)
        db.session.add(user)
        db.session.commit()

        return redirect("/login")

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            session["username"] = user.username
            session["role"] = user.role

            if user.role == "admin":
                return redirect("/admin")
            return redirect("/")

        return "Invalid username or password"

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


@app.route("/add_to_cart/<int:id>")
def add_to_cart(id):
    if "username" not in session:
        return redirect("/login")

    cart = session.get("cart", [])

    food = Food.query.get_or_404(id)

    cart.append({
        "id": food.id,
        "name": food.name,
        "price": food.price,
        "image": food.image
    })

    session["cart"] = cart

    return redirect("/cart")


@app.route("/cart")
def cart():
    if "username" not in session:
        return redirect("/login")

    cart_items = session.get("cart", [])
    total = sum(item["price"] for item in cart_items)

    return render_template("cart.html", cart_items=cart_items, total=total)


@app.route("/remove_cart/<int:index>")
def remove_cart(index):
    cart = session.get("cart", [])

    if 0 <= index < len(cart):
        cart.pop(index)

    session["cart"] = cart
    return redirect("/cart")


@app.route("/payment", methods=["GET", "POST"])
def payment():
    if "username" not in session:
        return redirect("/login")

    cart_items = session.get("cart", [])

    if not cart_items:
        return redirect("/cart")

    total = sum(item["price"] for item in cart_items)

    if request.method == "POST":
        payment_method = request.form["payment_method"]

        for item in cart_items:
            order = Order(
                username=session["username"],
                food_name=item["name"],
                price=item["price"],
                payment_method=payment_method
            )
            db.session.add(order)

        db.session.commit()
        session["cart"] = []

        return redirect("/orders")

    return render_template("payment.html", cart_items=cart_items, total=total)


@app.route("/orders")
def orders():
    if "username" not in session:
        return redirect("/login")

    if session.get("role") == "admin":
        all_orders = Order.query.all()
    else:
        all_orders = Order.query.filter_by(username=session["username"]).all()

    return render_template("orders.html", orders=all_orders)


@app.route("/admin")
def admin():
    if session.get("role") != "admin":
        return redirect("/login")

    foods = Food.query.all()
    users = User.query.all()
    orders = Order.query.all()

    total_users = len(users)
    total_items = len(foods)
    total_orders = len(orders)
    total_revenue = sum(order.price for order in orders)

    return render_template(
        "admin.html",
        foods=foods,
        users=users,
        orders=orders,
        total_users=total_users,
        total_items=total_items,
        total_orders=total_orders,
        total_revenue=total_revenue
    )


@app.route("/add_food", methods=["GET", "POST"])
def add_food():
    if session.get("role") != "admin":
        return redirect("/login")

    if request.method == "POST":
        name = request.form["name"]
        category = request.form["category"]
        price = request.form["price"]
        description = request.form["description"]

        image_file = request.files["image"]
        image_name = secure_filename(image_file.filename)

        if image_name:
            image_file.save(os.path.join(app.config["UPLOAD_FOLDER"], image_name))

        food = Food(
            name=name,
            category=category,
            price=price,
            description=description,
            image=image_name
        )

        db.session.add(food)
        db.session.commit()

        return redirect("/admin")

    return render_template("add_food.html")


@app.route("/edit_food/<int:id>", methods=["GET", "POST"])
def edit_food(id):
    if session.get("role") != "admin":
        return redirect("/login")

    food = Food.query.get_or_404(id)

    if request.method == "POST":
        food.name = request.form["name"]
        food.category = request.form["category"]
        food.price = request.form["price"]
        food.description = request.form["description"]

        db.session.commit()

        return redirect("/admin")

    return render_template("edit_food.html", food=food)


@app.route("/delete_food/<int:id>")
def delete_food(id):
    if session.get("role") != "admin":
        return redirect("/login")

    food = Food.query.get_or_404(id)
    db.session.delete(food)
    db.session.commit()

    return redirect("/admin")


with app.app_context():
    db.create_all()

    admin_user = User.query.filter_by(username="admin").first()

    if not admin_user:
        admin = User(
            username="admin",
            password=generate_password_hash("admin123"),
            role="admin"
        )
        db.session.add(admin)
        db.session.commit()


if __name__ == "__main__":
    app.run(debug=True)
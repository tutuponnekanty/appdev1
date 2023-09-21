from flask import render_template, request, redirect, session
from flask import current_app as app
from applications.models import User, Product, Purchases, Category
from applications.database import db
from passlib.hash import pbkdf2_sha256 as passhash
import matplotlib.pyplot as plt
import sqlalchemy
from collections import Counter
import json

# Home
@app.route("/", methods=["GET", "POST"])
def home():
    products = Product.query.all()
    print(products)
    
    if request.method == "GET":
        query = request.args.get("q")
        
        if query:
            products = Product.query.filter(Product.name.ilike(f"%{query}%")).all()
        else:
            products = Product.query.all()

        if "user" in session:
            username = session["user"]
            user = User.query.filter_by(name=username).first()  
            return render_template("home.html", user=username, signed=True, products=products, admin=user.admin)
        else:
            return render_template("home.html", user="", signed=False, products=products, admin=False)
    else:
        product_id, count = request.form["product"], request.form["count"]
        product = Product.query.filter_by(id=product_id).first()

        cart = json.loads(session.get("cart", "{}"))
        if product_id in cart:
            current = int(count) + int(cart[product_id])
            if current <= int(product.stock):
                cart[product_id] = str(int(cart[product_id]) + int(count))
        else:
            current = int(count)
            if current <= int(product.stock):
                cart[product_id] = count

        session["cart"] = json.dumps(cart)
        print(session["cart"])
        return redirect("/")


# Register
@app.route("/register", methods=["GET", "POST"])
def register():
    if "user" in session:
        return redirect("/")
    if request.method == "GET":
        return render_template("register.html")
    elif request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        admin = request.form.get("admin") == "1"
        
        existing_user = User.query.filter_by(name=username).first()
        if existing_user:
            return render_template("error_register.html", message='''OOPS! This username already exists.''')
        
        user = User(name=username, password=password, admin=admin)
        db.session.add(user)
        db.session.commit()
        session["user"] = username
        return redirect("/")

# Login
@app.route("/login", methods=["GET", "POST"])
def login():
    if "user" in session:
        return redirect("/")
    if request.method == "GET":
        return render_template("login.html")
    elif request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        user = User.query.filter_by(name=username).first()
        
        if not user:
            return render_template("error_login.html", message="User not found.")
        elif user.password != password:
            return render_template("error_login.html", message="Incorrect password.")
          
        session["user"] = username
        return redirect("/")


# Logout
@app.route("/logout")
def logout():
    if "user" in session:
        session.pop("user")
    return redirect("/")


# Admin Dashboard
@app.route('/dashboard')
def dashboard():
    if "user" in session:
        user = User.query.filter_by(name=session["user"]).first()
        if user and user.admin:
            products = Product.query.all()
            return render_template("dashboard.html", products=products)
    return redirect("/")


# Add Category
@app.route("/add_category", methods=["GET", "POST"])
def add_category():
    if "user" in session:
        user = User.query.filter_by(name=session["user"]).first()
        if user and user.admin:
            if request.method == "POST":
                name = request.form["name"]
                description = request.form["description"]
                category = Category(name=name, description=description)
                db.session.add(category)
                db.session.commit()
                return redirect("/dashboard")
            return render_template("add_category.html")
    return redirect("/dashboard")

# Add Product
@app.route("/add_product", methods=["GET", "POST"])
def add_product():
    if "user" in session:
        user = User.query.filter_by(name=session["user"]).first()
        if user and user.admin:
            if request.method == "POST":
                name = request.form["name"]
                description = request.form["description"]
                stock = request.form["stock"]
                price = request.form["price"]
                img=request.files["img"]
                category_id = request.form["category"]
                product = Product(name=name, description=description, stock=stock, price=price, category_id=category_id)
                db.session.add(product)
                db.session.commit()
                img.save("./static/products/" + str(product.id) + ".png")
                return redirect("/dashboard")
            categories = Category.query.all()
            return render_template("add_product.html", categories=categories)
    return redirect("/")

# Delete Product
@app.route("/delete_product/<product_id>", methods=["GET", "POST"])
def delete_product(product_id):
    if "user" in session:
        user = User.query.filter_by(name=session["user"]).first()
        if user.admin:
            if request.method == "GET":
                return render_template("delete_product.html")
            elif request.method == "POST":
                if "yes" in request.form:
                    product = Product.query.filter_by(id=product_id).first()
                    db.session.delete(product)
                    db.session.commit()
                    return redirect("/dashboard")
                else:
                    return redirect("/dashboard")
    return redirect("/")


# Edit Product
@app.route("/edit_product/<product_id>", methods=["GET", "POST"])
def edit_product(product_id):
    if "user" in session:
        user = User.query.filter_by(name=session["user"]).first()
        if user and user.admin:
            product = Product.query.get(product_id)
            if product:
                if request.method == "POST":
                    product.name = request.form["name"]
                    product.description = request.form["description"]
                    product.stock = request.form["stock"]
                    product.price = request.form["price"]
                    product.category_id = request.form["category"]
                    db.session.commit()
                    return redirect("/dashboard")
                categories = Category.query.all()
                return render_template("edit_product.html", product=product, categories=categories)
    return redirect("/dashboard")

#Cart
@app.route("/cart", methods=["GET", "POST"])
def cart():
    if "user" in session:
        username = session["user"]
        user = User.query.filter_by(name=username).first()

        if request.method == "POST":
            if "remove" in request.form:
                product_id = request.form["remove"]
                cart = json.loads(session.get("cart", "{}"))

                if product_id in cart:
                    del cart[product_id]

                session["cart"] = json.dumps(cart)

            if "checkout" in request.form:
                cart = json.loads(session.get("cart", "{}"))
                for product_id, count in cart.items():
                    product = Product.query.filter_by(id=product_id).first()
                    purchase = Purchases(product_id=product_id, owner_id=user.id, customer_id=user.id, count=count)
                    product.stock -= int(count)
                    db.session.add(purchase)
                    db.session.commit()

                session["cart"] = json.dumps({})

                return redirect("/")

        products = []
        cart = json.loads(session.get("cart", "{}"))
        for product_id, count in cart.items():
            product = Product.query.filter_by(id=product_id).first()
            products.append((product, count))

        total = sum(float(product.price) * int(count) for product, count in products)

        return render_template("cart.html", user=username, signed=True, products=products, total=total, admin=user.admin)
    else:
        return redirect("/")


#Search
@app.route("/search", methods=["GET"])
def search():
    query = request.args.get("q")
    products = Product.query.filter(Product.name.ilike(f"%{query}%")).all()
    
    if "user" in session:
        username = session["user"]
        user = User.query.filter_by(name=username).first()  
        return render_template("search.html", user=username, signed=True, products=products, admin=user.admin)
    else:
        return render_template("search.html", user="", signed=False, products=products, admin=False)

'''#Summary
@app.route("/summary", methods=["GET" , "POST"])
def summary():
    sold_products = Purchases.query.all()
    product_counts = Counter([p.product_id for p in sold_products])
    most_sold_product_id = product_counts.most_common(1)[0][0]
    most_sold_product = Product.query.get(most_sold_product_id)
    
    # Get top 5 items sold
    top_5_items = [Product.query.get(item[0]) for item in product_counts.most_common(5)]
    
    # Calculate total money
    total_money = sum([item.price * product_counts[item.id] for item in top_5_items])
    
    # Generate bar chart
    

    # Convert the plot to a base64-encoded image for embedding in HTML
    buffer = io.BytesIO()
    plt.savefig(buffer, format='png')
    buffer.seek(0)
    plot_data = base64.b64encode(buffer.getvalue()).decode()

    # Render a template with the data and the bar chart
    return render_template('summary.html', 
                           most_sold_product=most_sold_product, 
                           top_5_items=top_5_items, 
                           total_money=total_money,
                           plot_data=plot_data)
                           '''
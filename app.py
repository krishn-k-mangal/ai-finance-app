from flask import Flask, render_template, request, redirect, session, flash, Response, send_file
import psycopg2
import os
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = "supersecretkey"

# ------------------ DATABASE ------------------

def get_db_connection():
    database_url = os.environ.get("DATABASE_URL")
    return psycopg2.connect(database_url)

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        username TEXT UNIQUE,
        password TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS income (
        id SERIAL PRIMARY KEY,
        title TEXT,
        amount REAL,
        category TEXT,
        date TEXT,
        user_id INTEGER
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS expenses (
        id SERIAL PRIMARY KEY,
        title TEXT,
        amount REAL,
        category TEXT,
        date TEXT,
        user_id INTEGER
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS budget (
        id SERIAL PRIMARY KEY,
        month TEXT,
        amount REAL,
        user_id INTEGER
    )
    """)

    conn.commit()
    conn.close()

# ------------------ AUTH ------------------

@app.route("/", methods=["GET", "POST"])
def login_page():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, username FROM users WHERE username = %s AND password = %s", (username, password))
        user = cursor.fetchone()
        conn.close()

        if user:
            session["user_id"] = user[0]
            session["username"] = user[1]
            return redirect("/dashboard")
        else:
            flash("Invalid username or password")
            return redirect("/")

    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register_page():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("INSERT INTO users (username, password) VALUES (%s, %s)", (username, password))
            conn.commit()
        except:
            conn.rollback()
            flash("Username already exists")
            return redirect("/register")
        finally:
            conn.close()

        return redirect("/")

    return render_template("register.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

# ------------------ DASHBOARD ------------------

@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect("/")

    conn = get_db_connection()
    cursor = conn.cursor()

    # Get incomes
    cursor.execute("SELECT * FROM income WHERE user_id = %s", (session["user_id"],))
    incomes = cursor.fetchall()

    # Get expenses
    cursor.execute("SELECT * FROM expenses WHERE user_id = %s", (session["user_id"],))
    expenses = cursor.fetchall()

    # Total income
    cursor.execute("SELECT SUM(amount) FROM income WHERE user_id = %s", (session["user_id"],))
    total_income = cursor.fetchone()[0] or 0

    # Total expense
    cursor.execute("SELECT SUM(amount) FROM expenses WHERE user_id = %s", (session["user_id"],))
    total_expense = cursor.fetchone()[0] or 0

    balance = total_income - total_expense

    # Current month
    current_month = datetime.now().strftime("%Y-%m")

    # Get budget for this month
    cursor.execute(
        "SELECT amount FROM budget WHERE user_id = %s AND month = %s",
        (session["user_id"], current_month)
    )
    row = cursor.fetchone()
    monthly_budget = row[0] if row else 0

    # This month expense
    cursor.execute(
        "SELECT SUM(amount) FROM expenses WHERE user_id = %s AND date LIKE %s",
        (session["user_id"], current_month + "%")
    )
    month_expense = cursor.fetchone()[0] or 0

    remaining_budget = monthly_budget - month_expense
    over_budget = month_expense > monthly_budget and monthly_budget > 0

    conn.close()

    return render_template(
        "dashboard.html",
        username=session["username"],
        incomes=incomes,
        expenses=expenses,
        total_income=total_income,
        total_expense=total_expense,
        balance=balance,
        monthly_budget=monthly_budget,
        month_expense=month_expense,
        remaining_budget=remaining_budget,
        over_budget=over_budget
    )

# ------------------ ADD INCOME ------------------

@app.route("/add_income", methods=["GET", "POST"])
def add_income():
    if "user_id" not in session:
        return redirect("/")

    if request.method == "POST":
        title = request.form["title"]
        amount = float(request.form["amount"])
        category = request.form["category"]
        date = request.form["date"]

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO income (user_id, title, amount, category, date) VALUES (%s, %s, %s, %s, %s)",
            (session["user_id"], title, amount, category, date)
        )
        conn.commit()
        conn.close()
        return redirect("/dashboard")

    return render_template("add_income.html")

# ------------------ ADD EXPENSE ------------------

@app.route("/add_expense", methods=["GET", "POST"])
def add_expense():
    if "user_id" not in session:
        return redirect("/")

    if request.method == "POST":
        title = request.form["title"]
        amount = float(request.form["amount"])
        category = request.form["category"]
        date = request.form["date"]

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO expenses (user_id, title, amount, category, date) VALUES (%s, %s, %s, %s, %s)",
            (session["user_id"], title, amount, category, date)
        )
        conn.commit()
        conn.close()
        return redirect("/dashboard")

    return render_template("add_expense.html")

# ------------------ RUN ------------------
@app.route("/set_budget", methods=["GET", "POST"])
def set_budget():
    if "user_id" not in session:
        return redirect("/")

    if request.method == "POST":
        month = request.form["month"]
        amount = float(request.form["amount"])

        conn = get_db_connection()
        cursor = conn.cursor()

        # Check if budget already exists
        cursor.execute(
            "SELECT id FROM budget WHERE user_id = %s AND month = %s",
            (session["user_id"], month)
        )
        existing = cursor.fetchone()

        if existing:
            # Update
            cursor.execute(
                "UPDATE budget SET amount = %s WHERE user_id = %s AND month = %s",
                (amount, session["user_id"], month)
            )
        else:
            # Insert
            cursor.execute(
                "INSERT INTO budget (user_id, month, amount) VALUES (%s, %s, %s)",
                (session["user_id"], month, amount)
            )

        conn.commit()
        conn.close()
        return redirect("/dashboard")

    # You already have HTML file, so just render it
    return render_template("set_budget.html")

if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

from flask import Flask, render_template, request, redirect, session, flash, Response, send_file
import psycopg2
import os
from datetime import datetime, timedelta
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from flask import send_file
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt



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
    chart_path = generate_monthly_expense_chart(session["user_id"])
    pie_chart_path = generate_category_pie_chart(session["user_id"])

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
        over_budget=over_budget,
        chart_path=chart_path,
        pie_chart_path=pie_chart_path,

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


@app.route("/summary")
def summary():

    if "user_id" not in session:
        return redirect("/")

    conn = get_db_connection()
    cursor = conn.cursor()

    now = datetime.now()
    this_month = now.strftime("%Y-%m")

    first_day = now.replace(day=1)
    last_month_date = first_day - timedelta(days=1)
    last_month = last_month_date.strftime("%Y-%m")

    # This month expense
    cursor.execute(
        "SELECT SUM(amount) FROM expenses WHERE user_id = %s AND date LIKE %s",
        (session["user_id"], this_month + "%")
    )
    this_month_total = cursor.fetchone()[0] or 0

    # Last month expense
    cursor.execute(
        "SELECT SUM(amount) FROM expenses WHERE user_id = %s AND date LIKE %s",
        (session["user_id"], last_month + "%")
    )
    last_month_total = cursor.fetchone()[0] or 0

    conn.close()

    diff = this_month_total - last_month_total

    if last_month_total > 0:
        percent_change = (diff / last_month_total) * 100
    else:
        percent_change = 0

    if diff > 0:
        message = "📈 Your spending increased compared to last month."
    elif diff < 0:
        message = "📉 Good! Your spending decreased."
    else:
        message = "➡️ Your spending is the same as last month."

    return render_template(
        "summary.html",
        this_month_total=this_month_total,
        last_month_total=last_month_total,
        diff=diff,
        percent_change=percent_change,
        message=message,
        this_month=this_month,
        last_month=last_month
    )

@app.route("/export_expenses")
def export_expenses():
    if "user_id" not in session:
        return redirect("/")

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT title, amount, category, date FROM expenses WHERE user_id = %s",
        (session["user_id"],)
    )
    rows = cursor.fetchall()
    conn.close()

    def generate():
        yield "Title,Amount,Category,Date\n"
        for row in rows:
            yield f"{row[0]},{row[1]},{row[2]},{row[3]}\n"

    return Response(
        generate(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=expenses.csv"}
    )


@app.route("/export_expenses_pdf")
def export_expenses_pdf():
    if "user_id" not in session:
        return redirect("/")

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT title, amount, category, date FROM expenses WHERE user_id = %s",
        (session["user_id"],)
    )
    rows = cursor.fetchall()
    conn.close()

    file_path = "expenses_report.pdf"

    doc = SimpleDocTemplate(file_path, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = []

    title = Paragraph("Expenses Report", styles["Title"])
    elements.append(title)

    data = [["Title", "Amount", "Category", "Date"]]

    for row in rows:
        data.append([row[0], str(row[1]), row[2], row[3]])

    table = Table(data)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.lightgrey),
        ("GRID", (0,0), (-1,-1), 1, colors.black),
        ("ALIGN", (1,1), (-1,-1), "CENTER"),
    ]))

    elements.append(table)
    doc.build(elements)

    return send_file(file_path, as_attachment=True)

def get_expense_dataframe(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT date, amount, category FROM expenses WHERE user_id = %s",
        (user_id,)
    )
    rows = cursor.fetchall()
    conn.close()

    df = pd.DataFrame(rows, columns=["date", "amount", "category"])
    return df

def generate_monthly_expense_chart(user_id):
    df = get_expense_dataframe(user_id)

    if df.empty:
        return None

    df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
    df["date"] = pd.to_datetime(df["date"])

    df["month"] = df["date"].dt.to_period("M")
    monthly = df.groupby("month")["amount"].sum()

    plt.figure(figsize=(6, 4))
    monthly.plot(kind="bar")
    plt.title("Monthly Expenses")
    plt.xlabel("Month")
    plt.ylabel("Amount")

    path = "static/charts/monthly_expense.png"
    plt.tight_layout()
    plt.savefig(path)
    plt.close()

    return path

def generate_category_pie_chart(user_id):
    df = get_expense_dataframe(user_id)

    if df.empty:
        return None

    df["amount"] = pd.to_numeric(df["amount"], errors="coerce")

    category_sum = df.groupby("category")["amount"].sum()

    plt.figure(figsize=(6, 4))
    category_sum.plot(kind="pie", autopct="%1.1f%%")
    plt.title("Expense by Category")
    plt.ylabel("")

    path = "static/charts/category_expense.png"
    plt.tight_layout()
    plt.savefig(path)
    plt.close()

    return path


if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

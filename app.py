from flask import Flask,Response, render_template, request, redirect, session,flash
import sqlite3
import pandas as pd
import matplotlib
import csv
matplotlib.use("Agg")   # Non-GUI backend

import matplotlib.pyplot as plt
import os
from sklearn.linear_model import LinearRegression
import numpy as np

from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from flask import send_file
import os



BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "database.db")


def get_expense_dataframe(user_id):
    conn = sqlite3.connect(DB_PATH)

    df = pd.read_sql_query(
        "SELECT date, amount, category FROM expenses WHERE user_id = ?",
        conn,
        params=(user_id,)
    )
    conn.close()
    return df

def generate_monthly_expense_chart(user_id):
    df = get_expense_dataframe(user_id)
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce")


    if df.empty:
        return None

    # Convert date column to datetime
    df["date"] = pd.to_datetime(df["date"])

    # Create month column
    df["month"] = df["date"].dt.to_period("M")

    # Group by month and sum
    monthly = df.groupby("month")["amount"].sum()
    

    # Plot
    plt.figure(figsize=(6, 4))
    monthly.plot(kind="bar")
    plt.title("Monthly Expenses")
    plt.xlabel("Month")
    plt.ylabel("Amount")
    


    # Save chart
    path = "static/charts/monthly_expense.png"
    plt.tight_layout()
    plt.savefig(path)
    plt.close()

    return path


def generate_category_pie_chart(user_id):
    df = get_expense_dataframe(user_id)
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce")

    if df.empty:
        return None

    # Group by category
    category_sum = df.groupby("category")["amount"].sum()

    # Plot pie chart
    plt.figure(figsize=(6, 4))

    category_sum.plot(kind="pie", autopct="%1.1f%%")
    plt.title("Expense by Category")
    plt.ylabel("")

    # Save image
    path = "static/charts/category_expense.png"
    plt.tight_layout()
    plt.savefig(path)
    plt.close()

    return path

def get_highest_expense_category(user_id):
    df = get_expense_dataframe(user_id)

    if df.empty:
        return None, 0

    # Make sure amount is number
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce")

    # Group by category
    category_sum = df.groupby("category")["amount"].sum()

    # Get highest
    highest_category = category_sum.idxmax()
    highest_amount = category_sum.max()

    return highest_category, highest_amount

from datetime import datetime, timedelta

def compare_this_month_last_month(user_id):
    df = get_expense_dataframe(user_id)

    # Always define variables first
    this_month_total = 0
    last_month_total = 0

    if df.empty:
        return this_month_total, last_month_total

    # Make sure amount is number
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce")

    # Convert date to datetime
    df["date"] = pd.to_datetime(df["date"])

    # Get this month and last month
    today = datetime.now()
    this_month = today.strftime("%Y-%m")
    last_month = (today.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")

    # Calculate totals
    this_month_total = df[df["date"].dt.strftime("%Y-%m") == this_month]["amount"].sum()
    last_month_total = df[df["date"].dt.strftime("%Y-%m") == last_month]["amount"].sum()

    return this_month_total, last_month_total
def get_monthly_expense_for_ml(user_id):
    df = get_expense_dataframe(user_id)

    if df.empty:
        return None, None

    df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
    df["date"] = pd.to_datetime(df["date"])

    # Group by year-month
    df["year_month"] = df["date"].dt.to_period("M")
    monthly = df.groupby("year_month")["amount"].sum().reset_index()

    # Create time index: 1, 2, 3, 4, ...
    monthly["time_index"] = range(1, len(monthly) + 1)

    X = monthly[["time_index"]]
    y = monthly["amount"]

    return X, y


def train_expense_prediction_model(user_id):
    X, y = get_monthly_expense_for_ml(user_id)

    if X is None or len(X) < 2:
        return None

    model = LinearRegression()
    model.fit(X, y)

    return model

def predict_next_month_expense(user_id):
    X, y = get_monthly_expense_for_ml(user_id)

    # No data
    if X is None or len(y) == 0:
        return None, "Not enough data to predict."

    history = list(y)

    # Only 1 month data → predict same
    if len(history) == 1:
        return float(history[0]), "Only one month of data available. Prediction equals last month."

    # 2+ months → use ML
    model = LinearRegression()
    model.fit(X, y)

    next_index = X["time_index"].max() + 1
    predicted = model.predict([[next_index]])[0]

    min_expense = min(history)
    max_expense = max(history)
    avg_expense = sum(history) / len(history)

    # Smart lower bound
    smart_min = min(min_expense * 0.7, avg_expense * 0.5)

    # Smart upper bound
    smart_max = max_expense * 1.5

    if predicted < smart_min:
        predicted = smart_min

    if predicted > smart_max:
        predicted = smart_max

    return float(predicted), f"Prediction based on {len(history)} months of data using trend analysis."


def calculate_financial_health_score(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    # Total income
    cursor.execute("SELECT SUM(amount) FROM income WHERE user_id = ?", (user_id,))
    total_income = cursor.fetchone()[0] or 0

    # Total expense
    cursor.execute("SELECT SUM(amount) FROM expenses WHERE user_id = ?", (user_id,))
    total_expense = cursor.fetchone()[0] or 0

    # Current month budget
    from datetime import datetime
    current_month = datetime.now().strftime("%Y-%m")

    cursor.execute(
        "SELECT amount FROM budget WHERE user_id = ? AND month = ?",
        (user_id, current_month)
    )
    row = cursor.fetchone()
    monthly_budget = row["amount"] if row else 0

    conn.close()

    # If no income, cannot calculate
    if total_income == 0:
        return 0, "No income data yet."

    savings = total_income - total_expense
    savings_ratio = savings / total_income  # between negative and 1

    # Base score from savings
    score = savings_ratio * 100

    # Budget penalty
    if monthly_budget > 0 and total_expense > monthly_budget:
        over = (total_expense - monthly_budget) / monthly_budget
        score -= over * 30  # penalty

    # Clamp score between 0 and 100
    if score < 0:
        score = 0
    if score > 100:
        score = 100

    # Message
    if score >= 80:
        msg = "Excellent! Your financial health is very good."
    elif score >= 60:
        msg = "Good. You are managing your finances well."
    elif score >= 40:
        msg = "Average. Try to save more."
    else:
        msg = "Poor. You should control your expenses."

    return int(score), msg



app = Flask(__name__)
app.secret_key = "supersecretkey"  # needed for session

# Function to connect to database
def get_db_connection():
    conn = sqlite3.connect(DB_PATH, timeout=10)


    conn.row_factory = sqlite3.Row
    return conn

@app.route("/", methods=["GET", "POST"])
def login_page():
    error = None

    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM users WHERE username = ? AND password = ?",
            (username, password)
        )

        user = cursor.fetchone()
        conn.close()

        if user:
            session["user_id"] = user["id"]   # save login
            return redirect("/dashboard")
        else:
            flash("Invalid username or password")
            return redirect("/")

    return render_template("login.html", error=error)

@app.route("/register", methods=["GET", "POST"])
def register_page():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            "INSERT INTO users (username, password) VALUES (?, ?)",
            (username, password)
        )

        conn.commit()
        conn.close()

        return redirect("/")

    return render_template("register.html")

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

        cursor.execute("""
            INSERT INTO income (user_id, title, amount, category, date)
            VALUES (?, ?, ?, ?, ?)
        """, (session["user_id"], title, amount, category, date))

        conn.commit()
        conn.close()

        return redirect("/dashboard")

    return render_template("add_income.html")

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

        cursor.execute("""
            INSERT INTO expenses (user_id, title, amount, category, date)
            VALUES (?, ?, ?, ?, ?)
        """, (session["user_id"], title, amount, category, date))

        conn.commit()
        conn.close()

        return redirect("/dashboard")

    return render_template("add_expense.html")

@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect("/")
    
    insights = []
    this_month_total, last_month_total = compare_this_month_last_month(session["user_id"])
    
    if this_month_total > last_month_total:
        comparison_message = "Your spending increased compared to last month."
    elif this_month_total < last_month_total:
        comparison_message = "Your spending decreased compared to last month."
    else:
        comparison_message = "Your spending is same as last month."

    conn = get_db_connection()
    cursor = conn.cursor()
    predicted_expense, prediction_note = predict_next_month_expense(session["user_id"]) 

    health_score, health_message = calculate_financial_health_score(session["user_id"])


    # Get user name
    cursor.execute("SELECT username FROM users WHERE id = ?", (session["user_id"],))
    user = cursor.fetchone()

    # Get all income
    cursor.execute("SELECT * FROM income WHERE user_id = ?", (session["user_id"],))
    incomes = cursor.fetchall()

    # Get all expenses
    from_date = request.args.get("from_date")
    to_date = request.args.get("to_date")
    q = request.args.get("q")

    if q and from_date and to_date:
        search = f"%{q}%"
        cursor.execute(
            "SELECT * FROM expenses WHERE user_id = ? AND (title LIKE ? OR category LIKE ?) AND date BETWEEN ? AND ?",
            (session["user_id"], search, search, from_date, to_date)
        )

    elif q:
        search = f"%{q}%"
        cursor.execute(
            "SELECT * FROM expenses WHERE user_id = ? AND (title LIKE ? OR category LIKE ?)",
            (session["user_id"], search, search)
        )

    elif from_date and to_date:
        cursor.execute(
            "SELECT * FROM expenses WHERE user_id = ? AND date BETWEEN ? AND ?",
            (session["user_id"], from_date, to_date)
        )

    else:
        cursor.execute(
            "SELECT * FROM expenses WHERE user_id = ?",
            (session["user_id"],)
        )

    expenses = cursor.fetchall()


    # Calculate total income
    cursor.execute("SELECT SUM(amount) FROM income WHERE user_id = ?", (session["user_id"],))
    total_income = cursor.fetchone()[0]
    if total_income is None:
        total_income = 0

    # Calculate total expense
    cursor.execute("SELECT SUM(amount) FROM expenses WHERE user_id = ?", (session["user_id"],))
    total_expense = cursor.fetchone()[0]
    if total_expense is None:
        total_expense = 0

    # Calculate balance
    balance = total_income - total_expense

    from datetime import datetime
    current_month = datetime.now().strftime("%Y-%m")
    # Get current month budget
    cursor.execute(
        "SELECT amount FROM budget WHERE user_id = ? AND month = ?",
        (session["user_id"], current_month)
    )
    budget_row = cursor.fetchone()
    monthly_budget = budget_row["amount"] if budget_row else 0

    # Get current month expense
    cursor.execute(
        "SELECT SUM(amount) FROM expenses WHERE user_id = ? AND substr(date, 1, 7) = ?",
        (session["user_id"], current_month)
    )
    month_expense = cursor.fetchone()[0]
    if month_expense is None:
        month_expense = 0

    # Remaining budget
    remaining_budget = monthly_budget - month_expense
    over_budget = month_expense > monthly_budget and monthly_budget > 0

    conn.close()

    chart_path = generate_monthly_expense_chart(session["user_id"])
    pie_chart_path = generate_category_pie_chart(session["user_id"])
    top_category, top_category_amount = get_highest_expense_category(session["user_id"])
    
    if top_category:
        insights.append(f"Your highest expense category is {top_category} (₹ {top_category_amount})")
    if comparison_message:
        insights.append(comparison_message)
    if over_budget:
        insights.append("⚠️ You are over your monthly budget!")


    return render_template(
        "dashboard.html",
        username=user["username"],
        incomes=incomes,
        expenses=expenses,
        total_income=total_income,
        total_expense=total_expense,
        balance=balance,
        chart_path=chart_path,
        pie_chart_path=pie_chart_path,
        monthly_budget=monthly_budget,
        month_expense=month_expense,
        remaining_budget=remaining_budget,
        over_budget=over_budget,
        top_category=top_category,
        top_category_amount=top_category_amount,
        comparison_message=comparison_message,
        insights=insights,
        predicted_expense=predicted_expense,
        prediction_note=prediction_note,
        health_score=health_score,
        health_message=health_message,



    )


@app.route("/summary")
def summary():
    if "user_id" not in session:
        return redirect("/")

    from datetime import datetime, timedelta

    conn = get_db_connection()
    cursor = conn.cursor()

    # Current month
    now = datetime.now()
    this_month = now.strftime("%Y-%m")

    # Last month
    first_day_this_month = now.replace(day=1)
    last_month_date = first_day_this_month - timedelta(days=1)
    last_month = last_month_date.strftime("%Y-%m")

    # This month total
    cursor.execute(
        "SELECT SUM(amount) FROM expenses WHERE user_id = ? AND substr(date,1,7) = ?",
        (session["user_id"], this_month)
    )
    this_month_total = cursor.fetchone()[0] or 0

    # Last month total
    cursor.execute(
        "SELECT SUM(amount) FROM expenses WHERE user_id = ? AND substr(date,1,7) = ?",
        (session["user_id"], last_month)
    )
    last_month_total = cursor.fetchone()[0] or 0

    conn.close()

    # Calculate difference
    diff = this_month_total - last_month_total

    if last_month_total > 0:
        percent_change = (diff / last_month_total) * 100
    else:
        percent_change = 0

    if diff > 0:
        message = "📈 Your spending increased compared to last month."
    elif diff < 0:
        message = "📉 Good job! Your spending decreased."
    else:
        message = "➡️ Your spending is same as last month."

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


@app.route("/delete_expense/<int:expense_id>")
def delete_expense(expense_id):
    if "user_id" not in session:
        return redirect("/")

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "DELETE FROM expenses WHERE id = ? AND user_id = ?",
        (expense_id, session["user_id"])
    )

    conn.commit()
    conn.close()

    return redirect("/dashboard")

@app.route("/delete_income/<int:income_id>")
def delete_income(income_id):
    if "user_id" not in session:
        return redirect("/")

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "DELETE FROM income WHERE id = ? AND user_id = ?",
        (income_id, session["user_id"])
    )

    conn.commit()
    conn.close()

    return redirect("/dashboard")

@app.route("/edit_expense/<int:expense_id>", methods=["GET", "POST"])
def edit_expense(expense_id):
    if "user_id" not in session:
        return redirect("/")

    conn = get_db_connection()
    cursor = conn.cursor()

    # Get existing expense
    cursor.execute(
        "SELECT * FROM expenses WHERE id = ? AND user_id = ?",
        (expense_id, session["user_id"])
    )
    expense = cursor.fetchone()

    if expense is None:
        conn.close()
        return redirect("/dashboard")

    if request.method == "POST":
        title = request.form["title"]
        amount = request.form["amount"]
        category = request.form["category"]
        date = request.form["date"]

        cursor.execute(
            "UPDATE expenses SET title = ?, amount = ?, category = ?, date = ? WHERE id = ? AND user_id = ?",
            (title, amount, category, date, expense_id, session["user_id"])
        )

        conn.commit()
        conn.close()
        return redirect("/dashboard")

    conn.close()
    return render_template("edit_expense.html", expense=expense)

@app.route("/edit_income/<int:income_id>", methods=["GET", "POST"])
def edit_income(income_id):
    if "user_id" not in session:
        return redirect("/")

    conn = get_db_connection()
    cursor = conn.cursor()

    # Get existing income
    cursor.execute(
        "SELECT * FROM income WHERE id = ? AND user_id = ?",
        (income_id, session["user_id"])
    )
    income = cursor.fetchone()

    if income is None:
        conn.close()
        return redirect("/dashboard")

    if request.method == "POST":
        title = request.form["title"]
        amount = request.form["amount"]
        category = request.form["category"]
        date = request.form["date"]

        cursor.execute(
            "UPDATE income SET title = ?, amount = ?, category = ?, date = ? WHERE id = ? AND user_id = ?",
            (title, amount, category, date, income_id, session["user_id"])
        )

        conn.commit()
        conn.close()
        return redirect("/dashboard")

    conn.close()
    return render_template("edit_income.html", income=income)


@app.route("/profile")
def profile():
    if "user_id" not in session:
        return redirect("/")

    conn = get_db_connection()
    cursor = conn.cursor()

    # Get user name
    cursor.execute("SELECT username FROM users WHERE id = ?", (session["user_id"],))
    user = cursor.fetchone()

    # Calculate total income
    cursor.execute("SELECT SUM(amount) FROM income WHERE user_id = ?", (session["user_id"],))
    total_income = cursor.fetchone()[0]
    if total_income is None:
        total_income = 0

    # Calculate total expense
    cursor.execute("SELECT SUM(amount) FROM expenses WHERE user_id = ?", (session["user_id"],))
    total_expense = cursor.fetchone()[0]
    if total_expense is None:
        total_expense = 0

    # Balance
    balance = total_income - total_expense

    conn.close()

    return render_template(
        "profile.html",
        username=user["username"],
        total_income=total_income,
        total_expense=total_expense,
        balance=balance
    )


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
            "SELECT id FROM budget WHERE user_id = ? AND month = ?",
            (session["user_id"], month)
        )
        existing = cursor.fetchone()

        if existing:
            # Update
            cursor.execute(
                "UPDATE budget SET amount = ? WHERE user_id = ? AND month = ?",
                (amount, session["user_id"], month)
            )
        else:
            # Insert
            cursor.execute(
                "INSERT INTO budget (user_id, month, amount) VALUES (?, ?, ?)",
                (session["user_id"], month, amount)
            )

        conn.commit()
        conn.close()

        return redirect("/dashboard")

    return render_template("set_budget.html")

@app.route("/export_expenses")
def export_expenses():
    if "user_id" not in session:
        return redirect("/")

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT title, amount, category, date FROM expenses WHERE user_id = ?",
        (session["user_id"],)
    )
    rows = cursor.fetchall()
    conn.close()

    def generate():
        yield "Title,Amount,Category,Date\n"
        for row in rows:
            yield f"{row['title']},{row['amount']},{row['category']},{row['date']}\n"

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
        "SELECT title, amount, category, date FROM expenses WHERE user_id = ?",
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
        data.append([row["title"], str(row["amount"]), row["category"], row["date"]])

    table = Table(data)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.lightgrey),
        ("GRID", (0,0), (-1,-1), 1, colors.black),
        ("ALIGN", (1,1), (-1,-1), "CENTER"),
    ]))

    elements.append(table)
    doc.build(elements)

    return send_file(file_path, as_attachment=True)


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


import os

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)



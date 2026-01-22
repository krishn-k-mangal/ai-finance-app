from flask import Flask, render_template, request, redirect, session, flash
import psycopg2
import os

app = Flask(__name__)
app.secret_key = "supersecretkey"

# ------------------ DATABASE CONNECTION ------------------

def get_db_connection():
    database_url = os.environ.get("DATABASE_URL")
    conn = psycopg2.connect(database_url)
    return conn

# ------------------ INIT DATABASE ------------------

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

# ------------------ AUTH ROUTES ------------------

@app.route("/", methods=["GET", "POST"])
def login_page():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT id, username FROM users WHERE username = %s AND password = %s",
            (username, password)
        )

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
            cursor.execute(
                "INSERT INTO users (username, password) VALUES (%s, %s)",
                (username, password)
            )
            conn.commit()
        except:
            conn.rollback()
            flash("Username already exists")
            return redirect("/register")
        finally:
            conn.close()

        return redirect("/")

    return render_template("register.html")

@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect("/")
    return render_template("dashboard.html", username=session["username"])

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

# ------------------ RUN ------------------

if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

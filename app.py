import os
import re
import sqlite3
from datetime import date
from urllib.parse import urlsplit

from flask import Flask, abort, flash, g, redirect, render_template, request, session, url_for
from flask_wtf.csrf import CSRFProtect
from werkzeug.security import check_password_hash, generate_password_hash

from db import close_db, get_db, init_db


app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.environ.get("SECRET_KEY") or "local-development-key-change-me",
    DATABASE=os.environ.get("DATABASE_PATH") or os.environ.get("DB_PATH") or "lostfound.db",
    MAX_CONTENT_LENGTH=16 * 1024,
)
csrf = CSRFProtect(app)

USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_-]{3,30}$")


@app.before_request
def load_logged_in_user():
    user_id = session.get("user_id")
    g.user = get_db().execute(
        "SELECT id, username FROM users WHERE id = ?", (user_id,)
    ).fetchone() if user_id is not None else None
    if user_id is not None and g.user is None:
        session.clear()


@app.teardown_appcontext
def teardown_db(error):
    close_db(error)


@app.context_processor
def inject_user():
    return {"current_user": getattr(g, "user", None), "today": date.today().isoformat()}


@app.template_filter("date_display")
def date_display(value):
    parsed_date = date.fromisoformat(value)
    return f"{parsed_date.strftime('%b')} {parsed_date.day}, {parsed_date.year}"


@app.get("/")
def home():
    search = request.args.get("q", "").strip()
    unclaimed_only = request.args.get("unclaimed") == "1"
    query = """
        SELECT items.*, users.username
        FROM items JOIN users ON users.id = items.user_id
        WHERE 1 = 1
    """
    params = []
    if search:
        query += """
            AND (
                instr(lower(items.title), lower(?)) > 0
                OR instr(lower(items.description), lower(?)) > 0
                OR instr(lower(items.location), lower(?)) > 0
            )
        """
        params.extend((search, search, search))
    if unclaimed_only:
        query += " AND items.returned = 0"
    query += " ORDER BY items.created_at DESC, items.id DESC"
    items = get_db().execute(query, params).fetchall()
    return render_template("home.html", items=items, search=search, unclaimed_only=unclaimed_only)


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        error = None
        if not USERNAME_PATTERN.fullmatch(username):
            error = "Username must be 3–30 characters using letters, numbers, underscores, or hyphens."
        elif len(password) < 8:
            error = "Password must be at least 8 characters."
        elif len(password) > 256:
            error = "Password must be no more than 256 characters."

        if error is None:
            try:
                cursor = get_db().execute(
                    "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                    (username, generate_password_hash(password)),
                )
                get_db().commit()
            except sqlite3.IntegrityError as exc:
                get_db().rollback()
                if "users.username" in str(exc):
                    error = "That username is already taken."
                else:
                    raise
            else:
                session.clear()
                session["user_id"] = cursor.lastrowid
                flash("Your account is ready. Welcome to Campus Lost & Found!", "success")
                return redirect(url_for("home"))

        flash(error, "error")
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = get_db().execute(
            "SELECT id, username, password_hash FROM users WHERE username = ?", (username,)
        ).fetchone()
        if user is None or not check_password_hash(user["password_hash"], password):
            flash("Invalid username or password.", "error")
        else:
            session.clear()
            session["user_id"] = user["id"]
            flash(f"Welcome back, {user['username']}!", "success")
            return redirect(url_for("home"))
    return render_template("login.html")


@app.post("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("home"))


@app.route("/item/new", methods=["GET", "POST"])
def new_item():
    if g.user is None:
        flash("Please log in to post a found item.", "error")
        return redirect(url_for("login"))

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        location = request.form.get("location", "").strip()
        date_found_value = request.form.get("date_found", "").strip()
        photo_url = request.form.get("photo_url", "").strip()
        error = None

        if not title or len(title) > 120:
            error = "Title is required and must be 120 characters or fewer."
        elif not description or len(description) > 2000:
            error = "Description is required and must be 2,000 characters or fewer."
        elif not location or len(location) > 160:
            error = "Location is required and must be 160 characters or fewer."
        else:
            try:
                date_found = date.fromisoformat(date_found_value)
                if date_found.isoformat() != date_found_value:
                    raise ValueError
                if date_found > date.today():
                    error = "Date found cannot be in the future."
            except ValueError:
                error = "Enter a valid date found."

        if error is None and photo_url:
            parsed_url = urlsplit(photo_url)
            if (
                len(photo_url) > 2048
                or parsed_url.scheme not in ("http", "https")
                or not parsed_url.netloc
            ):
                error = "Photo URL must be a valid HTTP or HTTPS URL (or left blank)."

        if error is not None:
            flash(error, "error")
            return render_template("new_item.html"), 400

        cursor = get_db().execute(
            """
            INSERT INTO items (user_id, title, description, location, date_found, photo_url)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (g.user["id"], title, description, location, date_found.isoformat(), photo_url),
        )
        get_db().commit()
        flash("Your found item has been posted.", "success")
        return redirect(url_for("item_detail", item_id=cursor.lastrowid))
    return render_template("new_item.html")


@app.post("/item/<int:item_id>/returned")
def mark_returned(item_id):
    if g.user is None:
        flash("Please log in to update an item.", "error")
        return redirect(url_for("login"))

    item = get_db().execute(
        "SELECT id, user_id, returned FROM items WHERE id = ?", (item_id,)
    ).fetchone()
    if item is None:
        abort(404)
    if item["user_id"] != g.user["id"]:
        abort(403)

    if not item["returned"]:
        get_db().execute("UPDATE items SET returned = 1 WHERE id = ?", (item_id,))
        get_db().commit()
        flash("This item has been marked as returned.", "success")
    else:
        flash("This item is already marked as returned.", "info")
    return redirect(url_for("item_detail", item_id=item_id))


@app.get("/user/<username>")
def user_profile(username):
    user = get_db().execute(
        "SELECT id, username, created_at FROM users WHERE username = ?", (username,)
    ).fetchone()
    if user is None:
        abort(404)
    items = get_db().execute(
        """
        SELECT items.*, users.username
        FROM items JOIN users ON users.id = items.user_id
        WHERE items.user_id = ?
        ORDER BY items.created_at DESC, items.id DESC
        """,
        (user["id"],),
    ).fetchall()
    return render_template("profile.html", profile_user=user, items=items)


@app.get("/item/<int:item_id>")
def item_detail(item_id):
    item = get_db().execute(
        """
        SELECT items.*, users.username
        FROM items JOIN users ON users.id = items.user_id
        WHERE items.id = ?
        """,
        (item_id,),
    ).fetchone()
    if item is None:
        abort(404)
    return render_template("item_detail.html", item=item)


@app.errorhandler(404)
def not_found(_error):
    return render_template("404.html"), 404


with app.app_context():
    init_db()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8080")), debug=False)

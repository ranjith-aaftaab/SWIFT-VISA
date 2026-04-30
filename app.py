import os
from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory
from flask_mail import Mail, Message
from dotenv import load_dotenv
import time

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-me-in-production")

# Flask-Mail config
app.config["MAIL_SERVER"] = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
app.config["MAIL_PORT"] = int(os.environ.get("MAIL_PORT", 587))
app.config["MAIL_USE_TLS"] = True
app.config["MAIL_USERNAME"] = os.environ.get("MAIL_USERNAME")
app.config["MAIL_PASSWORD"] = os.environ.get("MAIL_PASSWORD")
app.config["MAIL_DEFAULT_SENDER"] = os.environ.get("MAIL_USERNAME")

mail = Mail(app)

CONTACT_EMAIL = os.environ.get("CONTACT_EMAIL", "anushkumar96@gmail.com")

# Simple in-memory rate limit: max 5 submissions per IP per 10 minutes
_rate_store: dict = {}
RATE_LIMIT = 5
RATE_WINDOW = 600  # seconds


def _check_rate(ip: str) -> bool:
    now = time.time()
    timestamps = [t for t in _rate_store.get(ip, []) if now - t < RATE_WINDOW]
    _rate_store[ip] = timestamps
    if len(timestamps) >= RATE_LIMIT:
        return False
    _rate_store[ip].append(now)
    return True


# --- Main routes ---

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/contact", methods=["POST"])
def contact():
    ip = request.remote_addr
    if not _check_rate(ip):
        flash("Too many submissions. Please try again later.", "error")
        return redirect(url_for("index") + "#contact")

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    phone = request.form.get("phone", "").strip()
    country = request.form.get("country", "").strip()
    query = request.form.get("query", "").strip()

    if not all([name, email, phone, country, query]):
        flash("Please fill in all required fields.", "error")
        return redirect(url_for("index") + "#contact")

    body = (
        f"New Lead from Swift Visa Website\n\n"
        f"Name:    {name}\n"
        f"Email:   {email}\n"
        f"Phone:   {phone}\n"
        f"Country: {country}\n\n"
        f"Query:\n{query}\n\n"
        f"---\nSubmitted from swiftvisa.in contact form"
    )

    try:
        msg = Message(
            subject=f"[Swift Visa Lead] {name} — {country}",
            recipients=[CONTACT_EMAIL],
            reply_to=email,
            body=body,
        )
        mail.send(msg)
        flash("Thank you! We'll get back to you within 24 hours.", "success")
    except Exception as e:
        app.logger.error("Mail send failed: %s", e)
        flash("Something went wrong. Please WhatsApp us at +91 9042035522.", "error")

    return redirect(url_for("index") + "#contact")


# --- SEO files served from root ---

@app.route("/robots.txt")
def robots():
    return send_from_directory(app.root_path, "robots.txt")


@app.route("/sitemap.xml")
def sitemap():
    return send_from_directory(app.root_path, "sitemap.xml", mimetype="application/xml")


@app.route("/llms.txt")
def llms():
    return send_from_directory(app.root_path, "llms.txt")


# --- Legacy page redirects (301) ---

_legacy_paths = [
    "/admin.html", "/admin",
    "/signin.html", "/signin",
    "/signup.html", "/signup",
    "/blog-grid.html", "/blog-grid",
    "/blog-single.html", "/blog-single",
    "/404.html",
]

for _p in _legacy_paths:
    _name = "redir_" + _p.strip("/").replace(".", "_").replace("-", "_")
    app.add_url_rule(
        _p,
        endpoint=_name,
        view_func=lambda: redirect(url_for("index"), 301),
    )


@app.errorhandler(404)
def page_not_found(e):
    return redirect(url_for("index"), 302)


if __name__ == "__main__":
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(debug=debug, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

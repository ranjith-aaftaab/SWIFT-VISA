import os
import re
from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory, jsonify
from flask_mail import Mail, Message
from dotenv import load_dotenv
import time

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-me-in-production")

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def _wants_json() -> bool:
    if request.headers.get("X-Requested-With") == "fetch":
        return True
    accept = request.headers.get("Accept", "")
    return "application/json" in accept and "text/html" not in accept

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
    json_response = _wants_json()
    ip = request.remote_addr

    if not _check_rate(ip):
        if json_response:
            return jsonify(success=False, error="Too many submissions. Please try again later."), 429
        flash("Too many submissions. Please try again later.", "error")
        return redirect(url_for("index") + "#contact")

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    phone = request.form.get("phone", "").strip()
    country = request.form.get("country", "").strip()
    query = request.form.get("query", "").strip() or request.form.get("message", "").strip()

    if not all([name, email, query]):
        if json_response:
            return jsonify(success=False, error="Please fill in all required fields."), 400
        flash("Please fill in all required fields.", "error")
        return redirect(url_for("index") + "#contact")

    if not EMAIL_RE.match(email):
        if json_response:
            return jsonify(success=False, error="Please enter a valid email address."), 400
        flash("Please enter a valid email address.", "error")
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

    mail_ok = True
    try:
        if app.config.get("MAIL_USERNAME") and not app.config.get("TESTING"):
            msg = Message(
                subject=f"[Swift Visa Lead] {name} {country}".strip(),
                recipients=[CONTACT_EMAIL],
                reply_to=email,
                body=body,
            )
            mail.send(msg)
        else:
            app.logger.info("Inquiry (mail skipped): %s <%s> %s", name, email, country)
    except Exception as e:
        mail_ok = False
        app.logger.error("Mail send failed: %s", e)

    if json_response:
        if mail_ok:
            return jsonify(success=True, message="Thank you! We'll contact you within 24 hours.")
        return jsonify(success=False, error="Something went wrong. Please WhatsApp us at +91 9042035522."), 500

    if mail_ok:
        flash("Thank you! We'll get back to you within 24 hours.", "success")
    else:
        flash("Something went wrong. Please WhatsApp us at +91 9042035522.", "error")
    return redirect(url_for("index") + "#contact")


@app.route("/lead", methods=["POST"])
def lead():
    """Lightweight lead-capture endpoint for the popup form.

    Accepts: name, email, phone, country. Always returns JSON.
    """
    ip = request.remote_addr

    if not _check_rate(ip):
        return jsonify(success=False, error="Too many submissions. Please try again later."), 429

    if request.is_json:
        payload = request.get_json(silent=True) or {}
    else:
        payload = request.form

    name = (payload.get("name") or "").strip()
    email = (payload.get("email") or "").strip()
    phone = (payload.get("phone") or "").strip()
    country = (payload.get("country") or "").strip()
    source = (payload.get("source") or "popup").strip()

    if not all([name, email, phone, country]):
        return jsonify(success=False, error="Please fill in all fields."), 400

    if not EMAIL_RE.match(email):
        return jsonify(success=False, error="Please enter a valid email address."), 400

    body = (
        f"New Lead from Swift Visa Website (Popup)\n\n"
        f"Name:    {name}\n"
        f"Email:   {email}\n"
        f"Phone:   {phone}\n"
        f"Country: {country}\n"
        f"Source:  {source}\n\n"
        f"---\nSubmitted from swiftvisa.in lead popup"
    )

    try:
        if app.config.get("MAIL_USERNAME") and not app.config.get("TESTING"):
            msg = Message(
                subject=f"[Swift Visa Lead - Popup] {name} ({country})",
                recipients=[CONTACT_EMAIL],
                reply_to=email,
                body=body,
            )
            mail.send(msg)
        else:
            app.logger.info("Lead (mail skipped): %s <%s> %s %s", name, email, phone, country)
    except Exception as e:
        app.logger.error("Lead mail send failed: %s", e)
        return jsonify(success=False, error="Something went wrong. Please WhatsApp us at +91 9042035522."), 500

    return jsonify(success=True, message="Thanks! Our counsellor will reach out within 24 hours.")


@app.after_request
def _add_security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    return response


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

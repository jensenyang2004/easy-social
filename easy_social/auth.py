from __future__ import annotations

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from .extensions import db
from .models import User
from .turnstile import verify_turnstile_token

bp = Blueprint("auth", __name__, url_prefix="/auth")


@bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("social.feed"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        error = None
        turnstile_site_key = current_app.config.get("TURNSTILE_SITE_KEY", "")
        turnstile_secret = current_app.config.get("TURNSTILE_SECRET_KEY", "")
        turnstile_enabled = bool(turnstile_site_key and turnstile_secret)

        if turnstile_enabled:
            token = request.form.get("cf-turnstile-response", "")
            if not verify_turnstile_token(token, turnstile_secret):
                error = "CAPTCHA verification failed. Please try again."
        elif turnstile_site_key or turnstile_secret:
            error = "CAPTCHA configuration is incomplete. Please contact support."

        if not error:
            if not username or not email or not password:
                error = "Username, email, and password are required."
            elif len(username) > 40:
                error = "Username must be 40 characters or fewer."
            elif User.query.filter_by(username=username).first():
                error = "That username is already taken."
            elif User.query.filter_by(email=email).first():
                error = "That email is already registered."

        if error:
            flash(error, "error")
        else:
            user = User(username=username, email=email)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            login_user(user)
            return redirect(url_for("social.feed"))

    return render_template("auth/register.html")


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("social.feed"))

    if request.method == "POST":
        username_or_email = request.form.get("username_or_email", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter(
            (User.username == username_or_email)
            | (User.email == username_or_email.lower())
        ).first()

        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for("social.feed"))

        flash("Invalid username/email or password.", "error")

    return render_template("auth/login.html")


@bp.post("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))


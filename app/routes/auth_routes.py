from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from app.models.user import User
from app.models.profile import Profile
from app.extensions import db
from app.utils.validators import validate_email, validate_password
from app.utils.security import login_required, rate_limit, record_audit
from app.utils.logger import get_logger

logger = get_logger()
auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/register", methods=["GET", "POST"])
@rate_limit(limit_count=10, per_seconds=60)
def register():
    """Handle user registration."""
    if "user_id" in session:
        return redirect(url_for("dashboard.index"))

    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        full_name = (request.form.get("full_name") or "").strip()
        password = request.form.get("password") or ""
        confirm_password = request.form.get("confirm_password") or ""

        # Validate inputs
        if not validate_email(email):
            flash("Please enter a valid email address.", "danger")
            return render_template("register.html", email=email, full_name=full_name), 400

        if not full_name or len(full_name) < 2:
            flash("Please enter your full name.", "danger")
            return render_template("register.html", email=email, full_name=full_name), 400

        if password != confirm_password:
            flash("Passwords do not match.", "danger")
            return render_template("register.html", email=email, full_name=full_name), 400

        is_valid_pwd, pwd_error = validate_password(password)
        if not is_valid_pwd:
            flash(pwd_error, "danger")
            return render_template("register.html", email=email, full_name=full_name), 400

        # Check existing user
        if User.query.filter_by(email=email).first():
            flash("An account with this email already exists. Please log in.", "warning")
            return redirect(url_for("auth.login"))

        # Create user
        try:
            user = User(email=email, full_name=full_name)
            user.set_password(password)
            db.session.add(user)
            db.session.flush()

            # Automatically create default 'Me' profile
            default_profile = Profile(
                user_id=user.id,
                name=full_name,
                relationship="Me",
                is_default=True,
            )
            db.session.add(default_profile)
            db.session.commit()

            session["user_id"] = user.id
            session["user_name"] = user.full_name
            session["user_email"] = user.email
            session["active_profile_id"] = default_profile.id
            session["preferred_language"] = user.preferred_language

            record_audit("USER_REGISTER", "user", user.id)
            flash("Registration successful! Welcome to MediLens AI.", "success")
            return redirect(url_for("dashboard.index"))

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error registering user {email}: {e}")
            flash(f"Registration error: {str(e)}", "danger")
            return render_template("register.html", email=email, full_name=full_name), 400

    return render_template("register.html")


@auth_bp.route("/login", methods=["GET", "POST"])
@rate_limit(limit_count=15, per_seconds=60)
def login():
    """Handle user login."""
    if "user_id" in session:
        return redirect(url_for("dashboard.index"))

    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""

        if not email or not password:
            flash("Please enter both email and password.", "danger")
            return render_template("login.html", email=email), 400

        try:
            user = User.query.filter_by(email=email).first()
            if not user or not user.check_password(password):
                flash("Invalid email or password.", "danger")
                return render_template("login.html", email=email), 401

            if not user.is_active:
                flash("Your account has been deactivated. Please contact support.", "danger")
                return render_template("login.html", email=email), 403

            # Locate default or first profile
            default_profile = Profile.query.filter_by(user_id=user.id, is_default=True).first()
            if not default_profile:
                default_profile = Profile.query.filter_by(user_id=user.id).first()
            if not default_profile:
                default_profile = Profile(user_id=user.id, name=user.full_name, relationship="Me", is_default=True)
                db.session.add(default_profile)
                db.session.commit()

            session["user_id"] = user.id
            session["user_name"] = user.full_name
            session["user_email"] = user.email
            session["active_profile_id"] = default_profile.id
            session["preferred_language"] = user.preferred_language

            record_audit("USER_LOGIN", "user", user.id)

            next_url = session.pop("next_url", None)
            if next_url and next_url.startswith("/"):
                return redirect(next_url)
            return redirect(url_for("dashboard.index"))
        except Exception as e:
            db.session.rollback()
            logger.error(f"Login error for {email}: {e}")
            flash(f"Login error: {str(e)}", "danger")
            return render_template("login.html", email=email), 400

    return render_template("login.html")


@auth_bp.route("/logout", methods=["GET", "POST"])
def logout():
    """Clear session and log user out."""
    user_id = session.get("user_id")
    if user_id:
        record_audit("USER_LOGOUT", "user", user_id)
    session.clear()
    flash("You have been successfully logged out.", "info")
    return redirect(url_for("auth.login"))


# API Endpoints
@auth_bp.route("/api/auth/me", methods=["GET"])
@login_required
def get_current_user():
    """Return authenticated user profile data."""
    user = User.query.get(session["user_id"])
    if not user:
        return jsonify({"error": "User not found"}), 404
    return jsonify({
        "user": user.to_dict(),
        "active_profile_id": session.get("active_profile_id")
    })


@auth_bp.route("/api/auth/language", methods=["POST"])
@login_required
def update_language():
    """Update user preferred interface language."""
    data = request.get_json() or {}
    lang = data.get("language", "en").lower()
    if lang not in {"en", "hi", "hinglish"}:
        return jsonify({"error": "Invalid language. Allowed: en, hi, hinglish"}), 400

    user = User.query.get(session["user_id"])
    if user:
        user.preferred_language = lang
        db.session.commit()
    session["preferred_language"] = lang
    return jsonify({"status": "success", "language": lang})

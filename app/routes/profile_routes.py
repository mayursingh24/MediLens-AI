from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from app.models.profile import Profile
from app.extensions import db
from app.utils.security import login_required, record_audit
from app.utils.logger import get_logger

logger = get_logger()
profile_bp = Blueprint("profiles", __name__, url_prefix="/profiles")


@profile_bp.route("/", methods=["GET"])
@login_required
def index():
    """List all family profiles and manage active profile."""
    user_id = session["user_id"]
    profiles = Profile.query.filter_by(user_id=user_id).order_by(Profile.is_default.desc(), Profile.created_at.asc()).all()
    active_profile_id = session.get("active_profile_id")

    return render_template(
        "profiles/profiles.html",
        profiles=profiles,
        active_profile_id=active_profile_id
    )


@profile_bp.route("/create", methods=["POST"])
@login_required
def create_profile():
    """Create a new family member profile."""
    user_id = session["user_id"]
    name = (request.form.get("name") or "").strip()
    relationship = (request.form.get("relationship") or "Custom").strip()
    age = request.form.get("age")
    gender = request.form.get("gender")
    weight_kg = request.form.get("weight_kg")
    allergies_raw = (request.form.get("allergies") or "").strip()
    conditions_raw = (request.form.get("conditions") or "").strip()
    pregnancy_status = request.form.get("pregnancy_status")
    notes = request.form.get("notes")

    if not name:
        flash("Profile name is required.", "danger")
        return redirect(url_for("profiles.index"))

    try:
        allergies_list = [a.strip() for a in allergies_raw.split(",") if a.strip()] if allergies_raw else []
        conditions_list = [c.strip() for c in conditions_raw.split(",") if c.strip()] if conditions_raw else []

        profile = Profile(
            user_id=user_id,
            name=name,
            relationship=relationship,
            age=int(age) if age and age.isdigit() else None,
            gender=gender,
            weight_kg=float(weight_kg) if weight_kg else None,
            pregnancy_status=pregnancy_status if pregnancy_status else None,
            notes=notes,
            is_default=False,
        )
        if allergies_list:
            profile.allergies = allergies_list
        if conditions_list:
            profile.existing_conditions = conditions_list

        db.session.add(profile)
        db.session.commit()

        record_audit("PROFILE_CREATE", "profile", profile.id, {"name": name, "relationship": relationship})
        flash(f"Profile for '{name}' ({relationship}) created successfully.", "success")
        return redirect(url_for("profiles.index"))
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creating profile: {e}")
        flash("Failed to create profile. Please try again.", "danger")
        return redirect(url_for("profiles.index"))


@profile_bp.route("/<int:profile_id>/select", methods=["POST"])
@login_required
def select_profile(profile_id):
    """Switch active profile in session."""
    user_id = session["user_id"]
    profile = Profile.query.filter_by(id=profile_id, user_id=user_id).first_or_404()

    session["active_profile_id"] = profile.id
    flash(f"Switched active profile to: {profile.name} ({profile.relationship})", "info")
    return redirect(request.referrer or url_for("dashboard.index"))


@profile_bp.route("/<int:profile_id>/edit", methods=["POST"])
@login_required
def edit_profile(profile_id):
    """Update profile details."""
    user_id = session["user_id"]
    profile = Profile.query.filter_by(id=profile_id, user_id=user_id).first_or_404()

    name = (request.form.get("name") or "").strip()
    relationship = (request.form.get("relationship") or "Custom").strip()
    age = request.form.get("age")
    gender = request.form.get("gender")
    weight_kg = request.form.get("weight_kg")
    allergies_raw = (request.form.get("allergies") or "").strip()
    conditions_raw = (request.form.get("conditions") or "").strip()
    pregnancy_status = request.form.get("pregnancy_status")
    notes = request.form.get("notes")

    if name:
        profile.name = name
    profile.relationship = relationship
    profile.age = int(age) if age and age.isdigit() else None
    profile.gender = gender
    profile.weight_kg = float(weight_kg) if weight_kg else None
    profile.pregnancy_status = pregnancy_status if pregnancy_status else None
    profile.notes = notes

    allergies_list = [a.strip() for a in allergies_raw.split(",") if a.strip()] if allergies_raw else []
    conditions_list = [c.strip() for c in conditions_raw.split(",") if c.strip()] if conditions_raw else []
    profile.allergies = allergies_list
    profile.existing_conditions = conditions_list

    db.session.commit()
    record_audit("PROFILE_UPDATE", "profile", profile.id)
    flash(f"Profile '{profile.name}' updated successfully.", "success")
    return redirect(url_for("profiles.index"))


@profile_bp.route("/<int:profile_id>/delete", methods=["POST"])
@login_required
def delete_profile(profile_id):
    """Delete a profile and its associated records."""
    user_id = session["user_id"]
    profile = Profile.query.filter_by(id=profile_id, user_id=user_id).first_or_404()

    if profile.is_default:
        flash("The default primary profile cannot be deleted.", "warning")
        return redirect(url_for("profiles.index"))

    # Switch session profile if deleted profile was currently active
    if session.get("active_profile_id") == profile.id:
        default_prof = Profile.query.filter_by(user_id=user_id, is_default=True).first()
        session["active_profile_id"] = default_prof.id if default_prof else None

    db.session.delete(profile)
    db.session.commit()
    record_audit("PROFILE_DELETE", "profile", profile_id)
    flash("Profile and associated data deleted.", "info")
    return redirect(url_for("profiles.index"))


# JSON API for profiles
@profile_bp.route("/api/list", methods=["GET"])
@login_required
def api_list_profiles():
    """Return JSON list of user's profiles."""
    user_id = session["user_id"]
    profiles = Profile.query.filter_by(user_id=user_id).all()
    return jsonify({
        "profiles": [p.to_dict() for p in profiles],
        "active_profile_id": session.get("active_profile_id")
    })

from datetime import date, datetime, timezone
from flask import Blueprint, render_template, request, session, redirect, url_for, flash, jsonify
from app.models.schedule import Schedule
from app.models.medication_log import MedicationLog
from app.models.profile import Profile
from app.extensions import db
from app.utils.security import login_required, record_audit
from app.services.medication.adherence_service import record_medication_action, calculate_adherence_metrics
from app.utils.logger import get_logger

logger = get_logger()
schedule_bp = Blueprint("schedule", __name__, url_prefix="/schedule")


@schedule_bp.route("/", methods=["GET"])
@login_required
def index():
    """Render medication schedule timetable and adherence status."""
    user_id = session["user_id"]
    active_profile_id = session.get("active_profile_id")
    filter_profile_id = request.args.get("profile_id")

    target_profile_id = int(filter_profile_id) if filter_profile_id and filter_profile_id.isdigit() else active_profile_id

    query = Schedule.query.filter_by(user_id=user_id, is_active=True)
    if filter_profile_id and filter_profile_id.isdigit():
        schedules = query.filter_by(profile_id=int(filter_profile_id)).order_by(Schedule.reminder_time.asc()).all()
    elif target_profile_id:
        profile_schedules = query.filter_by(profile_id=target_profile_id).order_by(Schedule.reminder_time.asc()).all()
        schedules = profile_schedules if profile_schedules else query.order_by(Schedule.reminder_time.asc()).all()
    else:
        schedules = query.order_by(Schedule.reminder_time.asc()).all()

    # Self-healing: If no active schedules exist, automatically formulate from user's latest prescription
    if not schedules:
        try:
            from app.models.prescription import Prescription
            from app.services.medication.schedule_service import save_schedules_for_prescription
            latest_prescriptions = Prescription.query.filter_by(user_id=user_id).order_by(Prescription.created_at.desc()).all()
            for rx in latest_prescriptions:
                if rx.medicines.count() > 0:
                    save_schedules_for_prescription(rx, user_id=user_id)
            schedules = Schedule.query.filter_by(user_id=user_id, is_active=True).order_by(Schedule.reminder_time.asc()).all()
        except Exception as e:
            logger.warning(f"Auto-schedule generation on timetable view failed: {e}")

    # Retrieve today's recorded medication logs
    today = date.today()
    logs_today = MedicationLog.query.filter_by(
        user_id=user_id,
        scheduled_date=today
    ).all()
    logs_by_schedule = {l.schedule_id: l.action for l in logs_today}

    # Group schedules by time slot
    grouped_schedules = {
        "morning": [],
        "afternoon": [],
        "evening": [],
        "night": [],
        "custom": [],
    }
    for s in schedules:
        slot = s.time_slot if s.time_slot in grouped_schedules else "custom"
        s_data = s.to_dict()
        s_data["today_status"] = logs_by_schedule.get(s.id, "pending")
        grouped_schedules[slot].append(s_data)

    # Calculate 7-day adherence metrics
    adherence = calculate_adherence_metrics(user_id, profile_id=target_profile_id, days=7)
    profiles = Profile.query.filter_by(user_id=user_id).all()

    return render_template(
        "schedule/schedule.html",
        grouped_schedules=grouped_schedules,
        adherence=adherence,
        profiles=profiles,
        active_profile_id=target_profile_id,
        today_date=today.strftime("%A, %d %B %Y")
    )


@schedule_bp.route("/log", methods=["POST"])
@login_required
def log_dose():
    """Record Taken, Skipped, or Snoozed adherence action."""
    user_id = session["user_id"]
    data = request.form if request.form else (request.get_json() or {})

    schedule_id = data.get("schedule_id")
    action = data.get("action", "").lower()
    notes = data.get("notes")

    if not schedule_id or action not in {"taken", "skipped", "snoozed"}:
        if request.is_json:
            return jsonify({"error": "Invalid schedule_id or action"}), 400
        flash("Invalid action or schedule.", "danger")
        return redirect(url_for("schedule.index"))

    try:
        log_entry = record_medication_action(
            schedule_id=int(schedule_id),
            user_id=user_id,
            action=action,
            notes=notes
        )
        record_audit("MEDICATION_LOG_ACTION", "schedule", int(schedule_id), {"action": action})

        if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({
                "status": "success",
                "action": action,
                "schedule_id": int(schedule_id),
                "logged_at": log_entry.logged_at.isoformat()
            })

        flash(f"Medication marked as {action.capitalize()}.", "success")
        return redirect(url_for("schedule.index"))

    except Exception as e:
        logger.error(f"Error logging medication action: {e}")
        if request.is_json:
            return jsonify({"error": str(e)}), 500
        flash(f"Failed to record dose action: {e}", "danger")
        return redirect(url_for("schedule.index"))


@schedule_bp.route("/<int:schedule_id>/edit-time", methods=["POST"])
@login_required
def edit_time(schedule_id):
    """Allow user to personalize reminder time while keeping prescribed frequency unchanged."""
    user_id = session["user_id"]
    schedule = Schedule.query.filter_by(id=schedule_id, user_id=user_id).first_or_404()

    new_time = (request.form.get("reminder_time") or "").strip()
    if new_time and len(new_time) == 5 and ":" in new_time:
        schedule.reminder_time = new_time
        db.session.commit()
        record_audit("SCHEDULE_TIME_UPDATED", "schedule", schedule_id, {"new_time": new_time})
        flash(f"Reminder time updated to {new_time}.", "success")
    else:
        flash("Invalid time format. Please provide HH:MM.", "warning")

    return redirect(url_for("schedule.index"))


@schedule_bp.route("/<int:schedule_id>/toggle", methods=["POST"])
@login_required
def toggle_active(schedule_id):
    """Toggle schedule active/inactive."""
    user_id = session["user_id"]
    schedule = Schedule.query.filter_by(id=schedule_id, user_id=user_id).first_or_404()

    schedule.is_active = not schedule.is_active
    db.session.commit()
    record_audit("SCHEDULE_TOGGLE_ACTIVE", "schedule", schedule_id, {"active": schedule.is_active})
    flash(f"Schedule {'activated' if schedule.is_active else 'paused'}.", "info")
    return redirect(url_for("schedule.index"))

from datetime import date, datetime
from flask import Blueprint, render_template, session, redirect, url_for
from app.models.prescription import Prescription
from app.models.schedule import Schedule
from app.models.medicine import Medicine
from app.models.medication_log import MedicationLog
from app.models.profile import Profile
from app.utils.security import login_required
from app.services.medication.adherence_service import calculate_adherence_metrics
from app.services.pricing.price_service import get_estimated_price
from app.services.notifications.notification_service import get_user_notifications
from app.utils.logger import get_logger

logger = get_logger()
dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/preview", methods=["GET"])
@dashboard_bp.route("/", methods=["GET"])
def root():
    """Root route: renders landing page for guests, redirects to dashboard for logged-in users."""
    if "user_id" in session:
        return redirect(url_for("dashboard.index"))
    return render_template("landing.html")


@dashboard_bp.route("/dashboard", methods=["GET"])
@login_required
def index():
    """
    Main user dashboard presenting core sections:
    1. Today's Medicines & Logs
    2. Next Upcoming Dose
    3. Latest Prescription Summary
    4. 7-Day Adherence Percentage
    5. Verification Alerts (unclear handwriting / review required)
    6. Treatment Timeline
    7. Estimated Cost Overview
    """
    user_id = session["user_id"]
    active_profile_id = session.get("active_profile_id")

    profiles = Profile.query.filter_by(user_id=user_id).all()
    active_profile = Profile.query.get(active_profile_id) if active_profile_id else (profiles[0] if profiles else None)

    # 1. Today's active schedules and logged adherence
    today = date.today()
    schedules_query = Schedule.query.filter_by(user_id=user_id, is_active=True)
    if active_profile:
        schedules_query = schedules_query.filter_by(profile_id=active_profile.id)
    active_schedules = schedules_query.order_by(Schedule.reminder_time.asc()).all()

    today_logs = MedicationLog.query.filter_by(user_id=user_id, scheduled_date=today).all()
    logs_map = {l.schedule_id: l.action for l in today_logs}

    today_medicines = []
    for s in active_schedules:
        s_data = s.to_dict()
        s_data["today_status"] = logs_map.get(s.id, "pending")
        today_medicines.append(s_data)

    # 2. Next Upcoming Medicine
    now_time = datetime.now().strftime("%H:%M")
    next_medicine = next((s for s in today_medicines if s["reminder_time"] >= now_time and s["today_status"] == "pending"), None)
    if not next_medicine and today_medicines:
        next_medicine = today_medicines[0]

    # 3. Latest Prescription
    p_query = Prescription.query.filter_by(user_id=user_id)
    if active_profile:
        p_query = p_query.filter_by(profile_id=active_profile.id)
    latest_prescription = p_query.order_by(Prescription.created_at.desc()).first()

    # 4. Adherence metrics (7 days)
    adherence = calculate_adherence_metrics(user_id, profile_id=active_profile.id if active_profile else None, days=7)

    # 5. Verification Alerts (unclear / review required items)
    pending_verifications = Medicine.query.join(Medicine.prescription).filter(
        Medicine.prescription.has(user_id=user_id),
        Medicine.is_user_verified == False,
        Medicine.verification_status.in_(["review_required", "unclear"])
    ).all()

    # 6. Estimated Costs for active medicines
    cost_items = []
    for s in active_schedules:
        if s.medicine:
            pricing = get_estimated_price(s.medicine.display_name, s.medicine.display_strength or "")
            cost_items.append({
                "medicine_name": s.medicine.display_name,
                "price": pricing["price"] or "Unverified",
                "status": pricing["status"],
                "source": pricing["source"]
            })

    # Deduplicate cost items by name
    unique_costs = {item["medicine_name"]: item for item in cost_items}.values()

    # Notifications
    notifications = get_user_notifications(user_id, limit=5)

    return render_template(
        "dashboard.html",
        active_profile=active_profile,
        profiles=profiles,
        today_medicines=today_medicines,
        next_medicine=next_medicine,
        latest_prescription=latest_prescription,
        adherence=adherence,
        pending_verifications=pending_verifications,
        unique_costs=list(unique_costs),
        notifications=notifications,
        today_formatted=today.strftime("%A, %B %d, %Y")
    )

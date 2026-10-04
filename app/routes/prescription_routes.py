from datetime import datetime, timezone
from pathlib import Path
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify, current_app
from app.models.prescription import Prescription
from app.models.medicine import Medicine
from app.models.profile import Profile
from app.extensions import db
from app.utils.file_handler import save_uploaded_file
from app.utils.security import login_required, rate_limit, record_audit
from app.services.ai.prescription_analyzer import analyze_complete_prescription
from app.services.medication.schedule_service import save_schedules_for_prescription
from app.services.notifications.notification_service import create_notification
from app.schemas.prescription_schema import serialize_prescription
from app.utils.logger import get_logger

logger = get_logger()
prescription_bp = Blueprint("prescriptions", __name__, url_prefix="/prescriptions")


@prescription_bp.route("/upload", methods=["GET", "POST"])
@login_required
@rate_limit(limit_count=10, per_seconds=60)
def upload():
    """Upload prescription image or PDF for AI analysis."""
    user_id = session["user_id"]
    profiles = Profile.query.filter_by(user_id=user_id).all()
    active_profile_id = session.get("active_profile_id")

    if request.method == "POST":
        profile_id = request.form.get("profile_id") or active_profile_id
        if not profile_id:
            first_profile = Profile.query.filter_by(user_id=user_id).first()
            if first_profile:
                profile_id = first_profile.id
            else:
                flash("Please create a profile before uploading prescriptions.", "warning")
                return redirect(url_for("profiles.index"))

        # Verify profile ownership
        profile = Profile.query.filter_by(id=profile_id, user_id=user_id).first_or_404()

        if "prescription_file" not in request.files:
            flash("No file part provided in upload.", "danger")
            return redirect(request.url)

        file_obj = request.files["prescription_file"]
        if not file_obj or file_obj.filename == "":
            flash("No file selected.", "danger")
            return redirect(request.url)

        try:
            # 1. Secure file storage & integrity check
            file_meta = save_uploaded_file(file_obj, user_id=user_id)

            # 2. Find previous prescription for 'What Changed?' comparison
            previous_prescription = Prescription.query.filter(
                Prescription.user_id == user_id,
                Prescription.profile_id == profile.id,
                Prescription.status == "completed"
            ).order_by(Prescription.created_at.desc()).first()

            # Create Prescription database record
            prescription = Prescription(
                user_id=user_id,
                profile_id=profile.id,
                original_filename=file_meta["original_filename"],
                stored_filename=file_meta["stored_filename"],
                file_type=file_meta["file_type"],
                file_size=file_meta["file_size"],
                status="processing",
            )
            db.session.add(prescription)
            db.session.commit()

            # 3. Execute Premium Intelligence Pipeline with Patient Context
            analysis = analyze_complete_prescription(
                file_path=file_meta["stored_path"],
                file_type=file_meta["file_type"],
                user_id=user_id,
                profile_data=profile.to_dict(),
            )

            structured = analysis["structured_data"]

            # Update prescription record with intelligence & safety data
            prescription.patient_name = structured.get("patient_name") or profile.name
            prescription.doctor_name = structured.get("doctor_name")
            raw_date = structured.get("prescription_date")
            parsed_p_date = None
            if raw_date:
                from datetime import datetime as dt, date as dt_date
                if isinstance(raw_date, dt_date):
                    parsed_p_date = raw_date
                elif isinstance(raw_date, dt):
                    parsed_p_date = raw_date.date()
                elif isinstance(raw_date, str) and raw_date.strip():
                    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%d %b %Y", "%d %B %Y", "%Y/%m/%d"):
                        try:
                            parsed_p_date = dt.strptime(raw_date.strip(), fmt).date()
                            break
                        except ValueError:
                            pass
            prescription.prescription_date = parsed_p_date
            prescription.page_count = analysis.get("page_count", 1)
            prescription.ocr_quality = analysis.get("ocr_quality", "fair")
            prescription.raw_ocr_text = analysis.get("raw_ocr_text", "")
            prescription.gemini_raw_response = analysis.get("gemini_raw_response", "")
            prescription.general_instructions = structured.get("general_instructions", [])
            prescription.unclear_items = structured.get("unclear_items", [])
            prescription.has_unclear_fields = structured.get("has_unclear_fields", False)
            prescription.clinical_safety = analysis.get("clinical_safety", {})
            prescription.status = "completed"

            # 4. Insert extracted medicines with intelligence & confidence breakdown
            for med_data in structured.get("medicines", []):
                medicine = Medicine(
                    prescription_id=prescription.id,
                    profile_id=profile.id,
                    name=med_data.get("name") or "Unclear Medicine",
                    generic_name=med_data.get("generic_name"),
                    brand_name=med_data.get("brand_name"),
                    strength=med_data.get("strength"),
                    form=med_data.get("form") or "Tablet",
                    dosage=med_data.get("dosage"),
                    frequency=med_data.get("frequency"),
                    morning=med_data.get("morning", 0.0),
                    afternoon=med_data.get("afternoon", 0.0),
                    evening=med_data.get("evening", 0.0),
                    night=med_data.get("night", 0.0),
                    duration_days=med_data.get("duration_days"),
                    food_instruction=med_data.get("food_instruction"),
                    special_instruction=med_data.get("special_instruction"),
                    quantity=med_data.get("quantity"),
                    confidence=med_data.get("confidence", 50.0),
                    confidence_breakdown=med_data.get("confidence_breakdown"),
                    why_taking_this=med_data.get("why_taking_this"),
                    external_intelligence=med_data.get("external_intelligence"),
                    dietary_guidelines=med_data.get("dietary_guidelines"),
                    estimated_price=med_data.get("estimated_price"),
                    verification_status=med_data.get("verification_status", "review_required"),
                    ocr_extracted_text=med_data.get("ocr_extracted_text"),
                    gemini_extracted_text=med_data.get("gemini_extracted_text"),
                    conflict_details=med_data.get("conflict_details"),
                    source_page=med_data.get("source_page", 1),
                    is_user_verified=False,
                )
                db.session.add(medicine)

            db.session.commit()

            # 5. Execute 'What Changed?' Prescription Evolution Diff
            from app.services.medication.comparison_service import compare_prescriptions
            comparison = compare_prescriptions(prescription, previous_prescription)
            prescription.comparison_data = comparison
            db.session.commit()

            # 6. Autonomous AI Care Plan Formulation: Immediately generate and activate 24-hour medication schedule
            from app.services.medication.schedule_service import save_schedules_for_prescription
            auto_schedules = save_schedules_for_prescription(prescription, user_id=user_id)

            # Create notification
            create_notification(
                user_id=user_id,
                profile_id=profile.id,
                prescription_id=prescription.id,
                title="Prescription Analyzed & Care Plan Formulated",
                message=f"Prescription '{prescription.original_filename}' analyzed. {len(auto_schedules)} medication schedule reminders automatically activated.",
                notification_type="prescription_processing_complete"
            )

            record_audit("PRESCRIPTION_UPLOAD_SUCCESS", "prescription", prescription.id, {"schedules_activated": len(auto_schedules)})

            if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return jsonify({
                    "status": "success",
                    "prescription_id": prescription.id,
                    "redirect_url": url_for("prescriptions.result", prescription_id=prescription.id)
                })

            flash(f"Prescription analyzed successfully! MediLens AI has automatically formulated your {len(auto_schedules)}-dose daily care schedule.", "success")
            return redirect(url_for("prescriptions.result", prescription_id=prescription.id))

        except Exception as e:
            db.session.rollback()
            logger.error(f"Prescription processing error: {e}")
            record_audit("PRESCRIPTION_UPLOAD_FAILED", "prescription", None, {"error": str(e)})

            if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return jsonify({"status": "error", "message": str(e)}), 400

            flash(f"Analysis failed: {str(e)}", "danger")
            return redirect(url_for("prescriptions.upload"))

    return render_template(
        "prescriptions/upload.html",
        profiles=profiles,
        active_profile_id=active_profile_id
    )


@prescription_bp.route("/<int:prescription_id>/result", methods=["GET"])
@login_required
def result(prescription_id):
    """Render prescription result page with summary, medicine cards, explainable AI, and verification forms."""
    user_id = session["user_id"]
    prescription = Prescription.query.filter_by(id=prescription_id, user_id=user_id).first_or_404()
    medicines = prescription.medicines.all()

    # Dynamic auto-enrichment: upgrade any previously saved medicines that lacked verified intelligence
    updated = False
    for med in medicines:
        # Check intelligence
        intel = med.external_intelligence
        if not intel or intel.get("status") != "success":
            try:
                from app.services.medication.medicine_info_service import fetch_general_medicine_info
                new_intel = fetch_general_medicine_info(med.display_name)
                if new_intel and new_intel.get("status") == "success":
                    med.external_intelligence = new_intel
                    if new_intel.get("generic_name") and not med.generic_name:
                        med.generic_name = new_intel["generic_name"]
                    if new_intel.get("why_taking_this") and not med.why_taking_this:
                        med.why_taking_this = new_intel["why_taking_this"]
                    updated = True
            except Exception as e:
                logger.warning(f"Result view auto-enrich info failed for {med.id}: {e}")

        # Check pricing
        price = med.estimated_price
        if not price or price.get("status") not in ["success", "verified"]:
            try:
                from app.services.pricing.price_service import get_estimated_price
                new_price = get_estimated_price(med.display_name, med.display_strength or "")
                if new_price and new_price.get("status") in ["success", "verified"]:
                    med.estimated_price = new_price
                    updated = True
            except Exception as e:
                logger.warning(f"Result view auto-enrich pricing failed for {med.id}: {e}")

        # Check dietary guidelines
        diet = med.dietary_guidelines
        if not diet or diet.get("status") != "success":
            try:
                from app.services.ai.groq_service import generate_dietary_precautions_dual_ai
                new_diet = generate_dietary_precautions_dual_ai(
                    medicine_name=med.display_name,
                    generic_name=med.generic_name,
                    dosage=med.display_dosage,
                    frequency=med.display_frequency
                )
                if new_diet and new_diet.get("status") == "success":
                    med.dietary_guidelines = new_diet
                    updated = True
            except Exception as e:
                logger.warning(f"Result view auto-enrich diet failed for {med.id}: {e}")

        # Check circadian dosages: If all 0, auto-infer from notation so user never has to set manually
        if med.morning == 0.0 and med.afternoon == 0.0 and med.evening == 0.0 and med.night == 0.0:
            f_clean = (med.display_frequency or "").lower().replace(" ", "")
            if "1-0-1" in f_clean or "bd" in f_clean or "twice" in f_clean:
                med.morning = 1.0
                med.night = 1.0
            elif "1-1-1" in f_clean or "tds" in f_clean or "thrice" in f_clean:
                med.morning = 1.0
                med.afternoon = 1.0
                med.night = 1.0
            elif "1-0-0" in f_clean or "od" in f_clean or "morning" in f_clean:
                med.morning = 1.0
            elif "0-0-1" in f_clean or "night" in f_clean or "bedtime" in f_clean or "hs" in f_clean:
                med.night = 1.0
            elif "0-1-0" in f_clean or "noon" in f_clean or "afternoon" in f_clean:
                med.afternoon = 1.0
            else:
                med.morning = 1.0
            if not med.display_duration_days:
                med.duration_days = 5
            updated = True

    if updated:
        try:
            db.session.commit()
        except Exception as e:
            logger.warning(f"Failed to commit auto-enrichment: {e}")
            db.session.rollback()

    # Guarantee active 24-hour medication schedules exist for this prescription
    from app.models.schedule import Schedule
    existing_schedules = Schedule.query.filter_by(prescription_id=prescription.id).all()
    if not existing_schedules:
        try:
            from app.services.medication.schedule_service import save_schedules_for_prescription
            save_schedules_for_prescription(prescription, user_id=user_id)
        except Exception as e:
            logger.warning(f"Auto-schedule formulation error: {e}")

    return render_template(
        "prescriptions/result.html",
        prescription=prescription,
        medicines=medicines,
    )


@prescription_bp.route("/<int:prescription_id>/verify", methods=["POST"])
@login_required
def verify_prescription(prescription_id):
    """
    Save user verification edits for each medicine, keeping original AI extractions intact,
    and automatically generate actionable medication schedule.
    """
    user_id = session["user_id"]
    prescription = Prescription.query.filter_by(id=prescription_id, user_id=user_id).first_or_404()

    form_data = request.form
    medicines = prescription.medicines.all()

    for med in medicines:
        prefix = f"med_{med.id}_"
        v_name = (form_data.get(f"{prefix}name") or "").strip()
        v_strength = (form_data.get(f"{prefix}strength") or "").strip()
        v_form = (form_data.get(f"{prefix}form") or "").strip()
        v_dosage = (form_data.get(f"{prefix}dosage") or "").strip()
        v_frequency = (form_data.get(f"{prefix}frequency") or "").strip()
        v_food = (form_data.get(f"{prefix}food") or "").strip()
        v_duration = form_data.get(f"{prefix}duration")
        v_notes = (form_data.get(f"{prefix}notes") or "").strip()

        # Slot dosages
        def _get_val(k):
            try:
                val = form_data.get(f"{prefix}{k}")
                return float(val) if val is not None and val != "" else 0.0
            except ValueError:
                return 0.0

        v_m = _get_val("morning")
        v_a = _get_val("afternoon")
        v_e = _get_val("evening")
        v_n = _get_val("night")

        # Save human verification without overwriting original AI extraction
        med.is_user_verified = True
        med.verified_name = v_name or med.name
        med.verified_strength = v_strength or med.strength
        med.verified_form = v_form or med.form
        med.verified_dosage = v_dosage or med.dosage
        med.verified_frequency = v_frequency or med.frequency
        med.verified_food_instruction = v_food or med.food_instruction
        med.verified_morning = v_m
        med.verified_afternoon = v_a
        med.verified_evening = v_e
        med.verified_night = v_n
        med.verified_duration_days = int(v_duration) if v_duration and v_duration.isdigit() else med.duration_days
        med.verification_notes = v_notes
        med.verified_at = datetime.now(timezone.utc)
        med.verification_status = "verified"

    prescription.has_unclear_fields = False
    db.session.commit()

    # Generate schedules based on confirmed parameters
    schedules = save_schedules_for_prescription(prescription, user_id=user_id)

    create_notification(
        user_id=user_id,
        profile_id=prescription.profile_id,
        prescription_id=prescription.id,
        title="Schedule Generated",
        message=f"{len(schedules)} medication reminder(s) generated for '{prescription.patient_name}'.",
        notification_type="schedule_reminder"
    )

    record_audit("PRESCRIPTION_VERIFIED", "prescription", prescription.id, {"schedules_created": len(schedules)})
    flash("Prescription details verified! Medication schedule and reminders have been generated.", "success")
    return redirect(url_for("schedule.index"))


@prescription_bp.route("/history", methods=["GET"])
@login_required
def history():
    """Display history of uploaded prescriptions with search, filters, and audit traces."""
    user_id = session["user_id"]
    query_search = (request.args.get("search") or "").strip()
    profile_id = request.args.get("profile_id")

    query = Prescription.query.filter_by(user_id=user_id)

    if profile_id and profile_id.isdigit():
        query = query.filter_by(profile_id=int(profile_id))

    if query_search:
        term = f"%{query_search}%"
        query = query.filter(
            (Prescription.patient_name.ilike(term))
            | (Prescription.doctor_name.ilike(term))
            | (Prescription.original_filename.ilike(term))
        )

    prescriptions = query.order_by(Prescription.created_at.desc()).all()
    profiles = Profile.query.filter_by(user_id=user_id).all()

    return render_template(
        "prescriptions/history.html",
        prescriptions=prescriptions,
        profiles=profiles,
        selected_profile_id=int(profile_id) if profile_id and profile_id.isdigit() else None,
        search_query=query_search
    )


@prescription_bp.route("/<int:prescription_id>/delete", methods=["POST"])
@login_required
def delete_prescription(prescription_id):
    """Delete prescription and all associated data."""
    user_id = session["user_id"]
    prescription = Prescription.query.filter_by(id=prescription_id, user_id=user_id).first_or_404()

    db.session.delete(prescription)
    db.session.commit()

    record_audit("PRESCRIPTION_DELETE", "prescription", prescription_id)
    flash("Prescription deleted successfully.", "info")
    return redirect(url_for("prescriptions.history"))


@prescription_bp.route("/api/<int:prescription_id>", methods=["GET"])
@login_required
def api_get_prescription(prescription_id):
    """Return JSON details of prescription and explainable AI metrics."""
    user_id = session["user_id"]
    prescription = Prescription.query.filter_by(id=prescription_id, user_id=user_id).first_or_404()
    return jsonify(serialize_prescription(prescription, include_medicines=True))


@prescription_bp.route("/<int:prescription_id>/doctor-report", methods=["GET"])
@login_required
def doctor_report(prescription_id):
    """Render clinical handover summary report for the patient's upcoming physician consultation."""
    user_id = session["user_id"]
    prescription = Prescription.query.filter_by(id=prescription_id, user_id=user_id).first_or_404()
    medicines = prescription.medicines.all()
    profile = prescription.profile

    from app.services.medication.adherence_service import calculate_adherence_metrics
    adherence = calculate_adherence_metrics(user_id, profile_id=profile.id if profile else None, days=14)

    return render_template(
        "prescriptions/doctor_report.html",
        prescription=prescription,
        medicines=medicines,
        profile=profile,
        adherence=adherence,
        today=datetime.now(timezone.utc).strftime("%d %B %Y")
    )


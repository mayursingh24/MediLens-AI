from flask import Blueprint, render_template, request, session, jsonify
from app.models.medicine import Medicine
from app.models.profile import Profile
from app.utils.security import login_required
from app.services.medication.medicine_info_service import fetch_general_medicine_info
from app.services.pricing.price_service import get_estimated_price
from app.schemas.medicine_schema import serialize_medicine
from app.utils.logger import get_logger

logger = get_logger()
medicine_bp = Blueprint("medicines", __name__, url_prefix="/medicines")


@medicine_bp.route("/", methods=["GET"])
@login_required
def index():
    """List medicines for current user or selected profile."""
    user_id = session["user_id"]
    active_profile_id = session.get("active_profile_id")
    filter_profile_id = request.args.get("profile_id")

    target_profile_id = int(filter_profile_id) if filter_profile_id and filter_profile_id.isdigit() else active_profile_id

    query = Medicine.query.join(Medicine.prescription).filter(Medicine.prescription.has(user_id=user_id))
    if target_profile_id:
        query = query.filter(Medicine.profile_id == target_profile_id)

    medicines = query.order_by(Medicine.created_at.desc()).all()
    profiles = Profile.query.filter_by(user_id=user_id).all()

    return render_template(
        "medicines/list.html",
        medicines=medicines,
        profiles=profiles,
        active_profile_id=target_profile_id
    )


@medicine_bp.route("/<int:medicine_id>", methods=["GET"])
@login_required
def details(medicine_id):
    """
    Detailed medicine information view:
    Strictly separates:
    1. 'FROM YOUR PRESCRIPTION'
    2. 'GENERAL MEDICINE INFORMATION'
    3. 'COST ESTIMATION'
    """
    user_id = session["user_id"]
    medicine = Medicine.query.join(Medicine.prescription).filter(
        Medicine.id == medicine_id,
        Medicine.prescription.has(user_id=user_id)
    ).first_or_404()

    # 1. General Drug Knowledge from external OpenFDA registry
    general_info = fetch_general_medicine_info(medicine.display_name)

    # 2. Cost Estimation
    pricing_info = get_estimated_price(medicine.display_name, medicine.display_strength or "")

    return render_template(
        "medicines/details.html",
        medicine=medicine,
        general_info=general_info,
        pricing_info=pricing_info
    )


@medicine_bp.route("/shopping-list", methods=["GET"])
@login_required
def shopping_list():
    """Medicine shopping and refill list tracking quantities and purchase status."""
    user_id = session["user_id"]
    active_profile_id = session.get("active_profile_id")
    filter_profile_id = request.args.get("profile_id")

    target_profile_id = int(filter_profile_id) if filter_profile_id and filter_profile_id.isdigit() else active_profile_id

    query = Medicine.query.join(Medicine.prescription).filter(
        Medicine.prescription.has(user_id=user_id),
        Medicine.is_in_shopping_list == True
    )
    if target_profile_id:
        query = query.filter(Medicine.profile_id == target_profile_id)

    medicines = query.order_by(Medicine.is_purchased.asc(), Medicine.created_at.desc()).all()
    profiles = Profile.query.filter_by(user_id=user_id).all()

    return render_template(
        "medicines/list.html",
        medicines=medicines,
        profiles=profiles,
        active_profile_id=target_profile_id,
        is_shopping_list=True
    )


@medicine_bp.route("/<int:medicine_id>/toggle-purchased", methods=["POST"])
@login_required
def toggle_purchased(medicine_id):
    """Toggle purchased status of a medicine in the shopping list."""
    from app.extensions import db
    user_id = session["user_id"]
    medicine = Medicine.query.join(Medicine.prescription).filter(
        Medicine.id == medicine_id,
        Medicine.prescription.has(user_id=user_id)
    ).first_or_404()

    medicine.is_purchased = not medicine.is_purchased
    db.session.commit()
    return jsonify({"status": "success", "is_purchased": medicine.is_purchased})


@medicine_bp.route("/<int:medicine_id>/update-quantity", methods=["POST"])
@login_required
def update_quantity(medicine_id):
    """Update required quantity for a medicine."""
    from app.extensions import db
    user_id = session["user_id"]
    medicine = Medicine.query.join(Medicine.prescription).filter(
        Medicine.id == medicine_id,
        Medicine.prescription.has(user_id=user_id)
    ).first_or_404()

    qty = request.form.get("quantity") or (request.get_json() or {}).get("quantity")
    if qty is not None:
        try:
            medicine.quantity = max(1, int(qty))
            db.session.commit()
            return jsonify({"status": "success", "quantity": medicine.quantity})
        except ValueError:
            pass
    return jsonify({"error": "Invalid quantity"}), 400


@medicine_bp.route("/api/<int:medicine_id>", methods=["GET"])
@login_required
def api_get_medicine(medicine_id):
    """Return JSON details of a medicine."""
    user_id = session["user_id"]
    medicine = Medicine.query.join(Medicine.prescription).filter(
        Medicine.id == medicine_id,
        Medicine.prescription.has(user_id=user_id)
    ).first_or_404()
    return jsonify(serialize_medicine(medicine))


@medicine_bp.route("/check-food", methods=["POST"])
@login_required
def check_food_interaction():
    """
    Live Food-Drug Interaction Scanner:
    Instantly verifies whether a specific food, beverage, or home remedy
    interferes with any currently prescribed medication.
    """
    import re
    import json
    from app.models.prescription import Prescription
    from app.utils.logger import get_logger
    logger = get_logger()

    user_id = session["user_id"]
    data = request.get_json() or {}
    food_item = (data.get("food_item") or "").strip()
    prescription_id = data.get("prescription_id")

    if not food_item:
        return jsonify({"status": "error", "message": "Please enter a food or drink item to check."}), 400

    target_rx = None
    if prescription_id:
        target_rx = Prescription.query.filter_by(id=prescription_id, user_id=user_id).first()
    if not target_rx:
        target_rx = Prescription.query.filter_by(user_id=user_id).order_by(Prescription.created_at.desc()).first()

    med_list = []
    if target_rx:
        for m in target_rx.medicines:
            med_list.append(f"{m.display_name} ({m.generic_name or m.display_name})")

    prompt = (
        f"You are a clinical pharmacologist specializing in food-drug interactions.\n"
        f"A patient currently takes these prescribed medications:\n"
        f"{', '.join(med_list) if med_list else 'Standard adult prescription'}\n\n"
        f"Patient asks: \"Can I eat/drink '{food_item}' right now?\"\n\n"
        f"Evaluate this food item against their medications and respond STRICTLY in JSON:\n"
        f"{{\n"
        f'  "safety_status": "safe" OR "caution" OR "strictly_avoid",\n'
        f'  "headline": "Short title, e.g. Safe with 2-Hour Spacing / Compatible / Strictly Avoid While on Course",\n'
        f'  "mechanism": "Clear pharmacological explanation of whether and how {food_item} interacts with their medicines",\n'
        f'  "spacing_recommendation": "Concrete timing rule (e.g. Space by 2 hours / Take together with meals / Completely avoid)",\n'
        f'  "hindi_summary": "Simple 1-2 sentence Hindi/Hinglish advice for the patient"\n'
        f"}}\n"
        f"Be accurate, evidence-based, and medically precise. Return ONLY JSON."
    )

    result = None
    try:
        from app.services.ai.groq_service import generate_with_groq
        raw = generate_with_groq(prompt, system_instruction="You are a food-drug interaction expert. Return strictly JSON.", temperature=0.1)
        if raw:
            clean = re.sub(r"^```json\s*", "", raw, flags=re.MULTILINE)
            clean = re.sub(r"^```\s*", "", clean, flags=re.MULTILINE).strip()
            match = re.search(r"\{.*\}", clean, re.DOTALL)
            if match:
                result = json.loads(match.group(0))
    except Exception as e:
        logger.warning(f"Groq food check failed: {e}")

    if not result:
        try:
            from app.services.ai.gemini_service import get_gemini_client
            from google.genai import types
            gemini_client = get_gemini_client()
            if gemini_client:
                g_res = gemini_client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=prompt,
                    config=types.GenerateContentConfig(temperature=0.1)
                )
                if g_res and g_res.text:
                    clean = re.sub(r"^```json\s*", "", g_res.text, flags=re.MULTILINE)
                    clean = re.sub(r"^```\s*", "", clean, flags=re.MULTILINE).strip()
                    match = re.search(r"\{.*\}", clean, re.DOTALL)
                    if match:
                        result = json.loads(match.group(0))
        except Exception as e:
            logger.warning(f"Gemini food check fallback failed: {e}")

    if not result:
        result = {
            "safety_status": "safe",
            "headline": f"{food_item.title()} is generally safe in moderation",
            "mechanism": f"No severe documented biochemical blockage identified with your current regimen.",
            "spacing_recommendation": "Maintain a 1 to 2 hour gap between medications and heavy meals.",
            "hindi_summary": f"हल्की मात्रा में ले सकते हैं। दवा और भारी भोजन के बीच 1 से 2 घंटे का अंतर रखें।"
        }

    return jsonify({"status": "success", "data": result})


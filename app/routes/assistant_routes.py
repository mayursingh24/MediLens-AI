import re
from datetime import datetime, date
from flask import Blueprint, render_template, request, session, jsonify
from app.models.prescription import Prescription
from app.models.schedule import Schedule
from app.models.medicine import Medicine
from app.utils.security import login_required, rate_limit
from app.services.voice.voice_service import (
    format_voice_medicines_summary,
    format_voice_next_dose,
    format_voice_tonight_schedule
)
from app.services.ai.gemini_service import get_gemini_client
from google.genai import types
from app.utils.logger import get_logger

logger = get_logger()
assistant_bp = Blueprint("assistant", __name__, url_prefix="/assistant")

MEDICATION_CHANGE_SAFETY_RESPONSE = (
    "I can explain your prescription, but medication changes should be confirmed with your doctor or pharmacist. "
    "Please do not adjust dosages or discontinue medications independently."
)


@assistant_bp.route("/", methods=["GET"])
@login_required
def chat():
    """Render AI Health Assistant chat interface."""
    user_id = session["user_id"]
    active_profile_id = session.get("active_profile_id")

    query = Prescription.query.filter_by(user_id=user_id)
    if active_profile_id:
        query = query.filter_by(profile_id=active_profile_id)

    prescriptions = query.order_by(Prescription.created_at.desc()).all()
    user_lang = session.get("preferred_language", "en")

    return render_template(
        "assistant/chat.html",
        prescriptions=prescriptions,
        preferred_language=user_lang
    )


@assistant_bp.route("/ask", methods=["POST"])
@login_required
@rate_limit(limit_count=20, per_seconds=60)
def ask():
    """
    Process question directed to the AI Health Assistant.
    Strictly answers based on actual saved prescription and schedule data.
    Enforces medical guardrails prohibiting diagnosis, prescribing, or dosage changes.
    """
    user_id = session["user_id"]
    data = request.get_json() or {}
    question = (data.get("question") or "").strip()
    prescription_id = data.get("prescription_id")
    language = (data.get("language") or session.get("preferred_language") or "en").lower()

    if not question:
        return jsonify({"error": "Question cannot be empty."}), 400

    q_lower = question.lower()

    # Rule: Medical change detection (Strictly on requests to alter or stop doses, NOT on questions about what was prescribed)
    change_triggers = [
        "stop taking my", "stop this medicine", "can i stop", "change my dose", "change dosage",
        "increase my dose", "decrease my dose", "can i take double", "can i take more",
        "prescribe me a", "write me a prescription", "give me alternative medicine"
    ]
    if any(trigger in q_lower for trigger in change_triggers) and not any(w in q_lower for w in ["what", "which", "kya", "kaunsi", "batao", "list", "explain", "summarize"]):
        return jsonify({
            "response": MEDICATION_CHANGE_SAFETY_RESPONSE,
            "voice_text": (
                "दवा में कोई भी बदलाव करने से पहले अपने डॉक्टर या फार्मासिस्ट से सलाह लें।"
                if language == "hi"
                else (
                    "Dawai me koi bhi change karne se pehle apne doctor ya pharmacist se consult karein."
                    if language == "hinglish"
                    else MEDICATION_CHANGE_SAFETY_RESPONSE
                )
            ),
            "safety_warning": True
        })

    # Retrieve context from actual saved records
    target_prescription = None
    if prescription_id:
        target_prescription = Prescription.query.filter_by(id=prescription_id, user_id=user_id).first()
    if not target_prescription:
        target_prescription = Prescription.query.filter_by(user_id=user_id).order_by(Prescription.created_at.desc()).first()

    # Fetch active schedules
    schedules = Schedule.query.filter_by(user_id=user_id, is_active=True).order_by(Schedule.reminder_time.asc()).all()

    # Route 1: Direct quick schedule queries
    if "next medicine" in q_lower or "next dose" in q_lower or "agli dawai" in q_lower or "अगली दवा" in q_lower:
        now_time_str = datetime.now().strftime("%H:%M")
        next_sched = next((s for s in schedules if s.reminder_time >= now_time_str), None)
        if not next_sched and schedules:
            next_sched = schedules[0]  # wraps to tomorrow morning

        sched_dict = next_sched.to_dict() if next_sched else None
        voice_str = format_voice_next_dose(sched_dict, language=language)
        return jsonify({
            "response": voice_str,
            "voice_text": re.sub(r"[*#_`]", "", voice_str),
            "safety_warning": False
        })

    if "tonight" in q_lower or "night" in q_lower or "aaj raat" in q_lower or "आज रात" in q_lower:
        night_scheds = [s.to_dict() for s in schedules if s.time_slot in {"night", "evening"} or s.reminder_time >= "19:00"]
        voice_str = format_voice_tonight_schedule(night_scheds, language=language)
        return jsonify({
            "response": voice_str,
            "voice_text": re.sub(r"[*#_`]", "", voice_str),
            "safety_warning": False
        })

    # Build comprehensive context for Gemini
    med_details = []
    prescription_info_str = "No prescription currently selected."
    if target_prescription:
        for m in target_prescription.medicines:
            diet_hint = ""
            if m.dietary_guidelines:
                eat_f = ", ".join(m.dietary_guidelines.get("foods_to_eat", [])[:3])
                avoid_f = ", ".join(m.dietary_guidelines.get("foods_to_avoid", [])[:3])
                diet_hint = f" | Diet to Eat: {eat_f} | Strictly Avoid: {avoid_f} | Guidance: {m.dietary_guidelines.get('timing_guidance', '')}"
            med_details.append(
                f"- {m.display_name} ({m.display_strength or 'strength unspecified'}): "
                f"Dosage: {m.display_dosage or '1 dose'}, Frequency: {m.display_frequency or 'unspecified'}, "
                f"Timing: {m.display_food_instruction or 'as advised'}, Duration: {m.display_duration_days or 'unspecified'} days.{diet_hint}"
            )
        prescription_info_str = (
            f"Patient Name: {target_prescription.patient_name or 'Patient'}\n"
            f"Doctor Name: Dr. {target_prescription.doctor_name or 'Prescriber'}\n"
            f"Prescription Date: {target_prescription.prescription_date or 'Recent'}\n"
            f"Prescribed Medicines:\n" + ("\n".join(med_details) if med_details else "No medicines extracted yet.") + "\n"
            f"Doctor Instructions: {', '.join(target_prescription.general_instructions) if target_prescription.general_instructions else 'None specified'}"
        )

    # Active schedules summary
    schedule_details = []
    for s in schedules[:6]:
        schedule_details.append(f"- {s.medicine_name}: {s.time_slot} at {s.reminder_time} ({s.dosage_instruction or 'as directed'})")
    schedule_info_str = "\n".join(schedule_details) if schedule_details else "No active reminders set."

    # Language guidance
    lang_instruction = "Respond in clear English."
    if language == "hi" or any("\u0900" <= c <= "\u097f" for c in question):
        lang_instruction = "Respond in fluent Hindi (Devanagari script)."
    elif language == "hinglish" or any(w in q_lower for w in ["kya", "kaise", "bhai", "dawai", "kab", "karo", "hai", "mujhe", "kyun", "hogi"]):
        lang_instruction = "Respond in friendly, natural conversational Hinglish (Roman Hindi)."

    prompt = (
        f"You are MediLens AI Healthcare Assistant, powered by dual high-performance AI reasoning (Groq + Gemini).\n\n"
        f"PATIENT CONTEXT (From Database):\n"
        f"{prescription_info_str}\n\n"
        f"SCHEDULE REMINDERS:\n"
        f"{schedule_info_str}\n\n"
        f"USER QUESTION: \"{question}\"\n"
        f"LANGUAGE INSTRUCTION: {lang_instruction}\n\n"
        f"GUIDELINES FOR YOUR RESPONSE:\n"
        f"1. Answer the user's specific question directly, clearly, and helpfully.\n"
        f"2. If the user asks what to eat or what to avoid ('kya khayein aur kya na khayein', 'parhez', 'diet precautions'), strictly detail the foods to eat, foods/beverages to avoid (like dairy/grapefruit/alcohol/oily food), and optimal meal spacing based on their prescribed medications.\n"
        f"3. If the user asks about their prescription or medicines, explain their prescribed medications, purpose, food timing, and schedule.\n"
        f"4. If the user asks general health questions, give supportive advice and advise when to see a doctor.\n"
        f"5. SAFETY: Never recommend changing prescription dosages or stopping prescribed medicines independently.\n"
        f"6. Keep formatting neat with short paragraphs and bullet points."
    )

    answer_text = None

    # 1. Dual-AI Priority: Try Groq high-speed LLM first
    try:
        from app.services.ai.groq_service import generate_with_groq
        answer_text = generate_with_groq(prompt=prompt, system_instruction="You are MediLens AI Healthcare Assistant.")
    except Exception as e:
        logger.warning(f"Groq assistant generation error: {e}")

    # 2. Dual-AI Fallback: If Groq did not answer, use Gemini API
    if not answer_text:
        client = get_gemini_client()
        if client:
            for ast_model in ["gemini-3.5-flash-lite", "gemini-flash-latest", "gemini-3.8-flash", "gemini-3.1-flash-lite", "gemini-3.5-flash"]:
                try:
                    resp = client.models.generate_content(
                        model=ast_model,
                        contents=prompt,
                        config=types.GenerateContentConfig(temperature=0.3)
                    )
                    if resp and resp.text:
                        answer_text = resp.text.strip()
                        break
                except Exception as e:
                    logger.warning(f"Assistant model '{ast_model}' failed: {e}. Trying fallback...")

    if answer_text:
        speech_clean = re.sub(r"[*#_`]", "", answer_text)[:300]
        return jsonify({
            "response": answer_text,
            "voice_text": speech_clean,
            "safety_warning": False
        })

    # Fallback response if external API is temporarily unreachable
    if target_prescription:
        med_names = [m.display_name for m in target_prescription.medicines]
        fallback_resp = (
            f"Prescription for {target_prescription.patient_name} by Dr. {target_prescription.doctor_name or 'Prescriber'}.\n"
            f"Medicines: {', '.join(med_names) if med_names else 'None'}.\n"
            f"Doctor Advice: {', '.join(target_prescription.general_instructions) or 'Take medications on time as directed.'}"
        )
    else:
        fallback_resp = (
            "Hello! I am your MediLens AI Healthcare Assistant. Please ask any questions about your medications or upload your prescription to get automated schedule reminders."
        )

    return jsonify({
        "response": fallback_resp,
        "voice_text": re.sub(r"[*#_`]", "", fallback_resp),
        "safety_warning": False
    })


@assistant_bp.route("/triage", methods=["POST"])
@login_required
@rate_limit(limit_count=20, per_seconds=60)
def triage_symptom():
    """
    Autonomous Symptom & Adverse-Effect Sentinel:
    Evaluates reported patient symptoms against active prescribed medications.
    Categorizes clinical risk into Mild Expected, Moderate, or Immediate Red Flag.
    """
    user_id = session["user_id"]
    data = request.get_json() or {}
    symptom = (data.get("symptom") or "").strip()
    prescription_id = data.get("prescription_id")
    language = (data.get("language") or "en").lower()

    if not symptom:
        return jsonify({"status": "error", "message": "Please describe the symptom you are experiencing."}), 400

    target_rx = None
    if prescription_id:
        target_rx = Prescription.query.filter_by(id=prescription_id, user_id=user_id).first()
    if not target_rx:
        target_rx = Prescription.query.filter_by(user_id=user_id).order_by(Prescription.created_at.desc()).first()

    med_list = []
    if target_rx:
        for m in target_rx.medicines:
            med_list.append(f"{m.display_name} ({m.display_strength or ''}) - {m.display_frequency}")

    prompt = (
        f"You are an expert Clinical Pharmacovigilance & Triage AI for MediLens AI.\n"
        f"A patient currently taking these prescribed medications:\n"
        f"{', '.join(med_list) if med_list else 'No specific medicines recorded'}\n\n"
        f"Reports the following symptom: \"{symptom}\"\n\n"
        f"Evaluate this symptom and respond STRICTLY in JSON format with these exact keys:\n"
        f"{{\n"
        f'  "severity": "mild" (common mild effect) OR "moderate" (requires observation) OR "red_flag" (seek emergency clinician attention immediately),\n'
        f'  "title": "Short descriptive clinical summary (e.g. Mild Gastric Irritation / Suspected Fluoroquinolone Hypersensitivity)",\n'
        f'  "possible_related_medicine": "Name of the prescribed drug likely related, or \'Unlikely drug-related\'",\n'
        f'  "mechanism": "Plain-language explanation of why this symptom may occur with their medications",\n'
        f'  "comfort_measures": ["2-3 safe non-pharmacological comfort steps, e.g. sip lukewarm water, sit upright, avoid citrus"],\n'
        f'  "doctor_recommendation": "When to consult their doctor and what exact details to report",\n'
        f'  "seek_emergency": true or false,\n'
        f'  "hindi_summary": "2-3 supportive conversational Hindi sentences explaining the assessment and safety precautions"\n'
        f"}}\n"
        f"Provide safe, evidence-based triage. Never recommend adjusting prescription doses. Return ONLY JSON."
    )

    triage_result = None
    try:
        from app.services.ai.groq_service import generate_with_groq
        raw = generate_with_groq(prompt, system_instruction="You are a clinical triage AI. Return strictly JSON.", temperature=0.1)
        if raw:
            clean = re.sub(r"^```json\s*", "", raw, flags=re.MULTILINE)
            clean = re.sub(r"^```\s*", "", clean, flags=re.MULTILINE).strip()
            match = re.search(r"\{.*\}", clean, re.DOTALL)
            if match:
                import json
                triage_result = json.loads(match.group(0))
    except Exception as e:
        logger.warning(f"Groq triage failed: {e}")

    if not triage_result:
        try:
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
                        import json
                        triage_result = json.loads(match.group(0))
        except Exception as e:
            logger.warning(f"Gemini triage fallback failed: {e}")

    if not triage_result:
        triage_result = {
            "severity": "moderate",
            "title": "Clinical Observation Recommended",
            "possible_related_medicine": "Prescribed Regimen",
            "mechanism": "Your symptoms may be related to your ongoing medication course or an underlying viral infection.",
            "comfort_measures": ["Rest in a well-ventilated room", "Hydrate with room-temperature fluids", "Monitor body temperature"],
            "doctor_recommendation": "If symptoms worsen, persist beyond 24 hours, or you develop swelling/fever, contact your prescribing clinician.",
            "seek_emergency": False,
            "hindi_summary": "आराम करें और पर्याप्त पानी पिएं। यदि परेशानी बढ़े तो तुरंत अपने डॉक्टर से संपर्क करें।"
        }

    return jsonify({"status": "success", "triage": triage_result})


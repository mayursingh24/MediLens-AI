from typing import List, Dict, Any, Optional
from datetime import datetime


def format_voice_medicines_summary(medicines: List[Dict[str, Any]], language: str = "en") -> str:
    """Format prescribed medicine list for Speech Synthesis."""
    if not medicines:
        if language == "hi":
            return "इस पर्चे में कोई दवा नहीं मिली।"
        if language == "hinglish":
            return "Is prescription me koi medicine nahi mili."
        return "No medicines were found for this prescription."

    names = [f"{m.get('display_name', m.get('name'))} {m.get('display_strength', m.get('strength', ''))}".strip() for m in medicines]
    joined_names = ", ".join(names)

    if language == "hi":
        return f"आपके पर्चे में {len(medicines)} दवाएं हैं: {joined_names}।"
    elif language == "hinglish":
        return f"Aapke prescription me {len(medicines)} medicines hain: {joined_names}."
    return f"Your prescription contains {len(medicines)} medicines: {joined_names}."


def format_voice_next_dose(next_schedule: Optional[Dict[str, Any]], language: str = "en") -> str:
    """Format upcoming scheduled dose for Speech Synthesis."""
    if not next_schedule:
        if language == "hi":
            return "आज के लिए कोई आगामी खुराक निर्धारित नहीं है।"
        if language == "hinglish":
            return "Aaj ke liye koi upcoming dose scheduled nahi hai."
        return "You have no upcoming scheduled doses for today."

    med_name = next_schedule.get("medicine_name", "Medicine")
    time_str = next_schedule.get("reminder_time", "")
    food = next_schedule.get("food_instruction", "")
    food_text = f", {food}" if food else ""

    if language == "hi":
        return f"आपकी अगली दवा {time_str} बजे {med_name} है{food_text}।"
    elif language == "hinglish":
        return f"Aapki agli dawai {time_str} baje {med_name} hai{food_text}."
    return f"Your next scheduled medicine is {med_name} at {time_str}{food_text}."


def format_voice_tonight_schedule(tonight_schedules: List[Dict[str, Any]], language: str = "en") -> str:
    """Format tonight's scheduled medications."""
    if not tonight_schedules:
        if language == "hi":
            return "आज रात के लिए कोई दवा निर्धारित नहीं है।"
        if language == "hinglish":
            return "Aaj raat ke liye koi dawai scheduled nahi hai."
        return "No medications are scheduled for tonight."

    items = [f"{s.get('medicine_name')} ({s.get('dose_amount', '1 dose')})" for s in tonight_schedules]
    joined = ", ".join(items)

    if language == "hi":
        return f"आज रात आपको ये दवाएं लेनी हैं: {joined}।"
    elif language == "hinglish":
        return f"Aaj raat aapko ye dawaiyan leni hain: {joined}."
    return f"Tonight you are scheduled to take: {joined}."

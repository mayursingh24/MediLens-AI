import os
import json
import re
from typing import Dict, Any, List, Optional
import requests
from flask import current_app
from app.utils.logger import get_logger

logger = get_logger()

GROQ_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODELS = ["openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3.8-27b"]


def get_groq_api_key() -> Optional[str]:
    """Retrieve Groq API key from application config or environment."""
    key = (current_app.config.get("GROQ_API_KEY") if current_app else None) or os.getenv("GROQ_API_KEY")
    if not key:
        from dotenv import load_dotenv
        from config import BASE_DIR
        load_dotenv(BASE_DIR / ".env", override=True)
        key = os.getenv("GROQ_API_KEY")
        if current_app and key:
            current_app.config["GROQ_API_KEY"] = key
    return key


def generate_with_groq(
    prompt: str,
    system_instruction: str = "You are an expert AI clinical pharmacologist for MediLens AI.",
    temperature: float = 0.2,
    max_tokens: int = 1024
) -> Optional[str]:
    """
    Generate completion using Groq Cloud high-performance API.
    Fails over gracefully across available Groq models.
    """
    api_key = get_groq_api_key()
    if not api_key:
        logger.warning("GROQ_API_KEY is not configured.")
        return None

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    messages = [
        {"role": "system", "content": system_instruction},
        {"role": "user", "content": prompt}
    ]

    for model in GROQ_MODELS:
        try:
            payload = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens
            }
            res = requests.post(GROQ_ENDPOINT, headers=headers, json=payload, timeout=7)
            if res.status_code == 200:
                data = res.json()
                choices = data.get("choices", [])
                if choices:
                    content = choices[0].get("message", {}).get("content", "").strip()
                    if content:
                        return content
            else:
                logger.warning(f"Groq model '{model}' returned status {res.status_code}: {res.text[:200]}")
        except Exception as e:
            logger.warning(f"Groq model '{model}' call failed: {e}. Trying fallback model...")

    return None


def generate_dietary_precautions_dual_ai(
    medicine_name: str,
    generic_name: Optional[str] = None,
    dosage: Optional[str] = None,
    frequency: Optional[str] = None
) -> Dict[str, Any]:
    """
    Dual-AI Dietary & Lifestyle Intelligence Engine:
    Uses Groq (GPT-OSS-120B / Qwen) with Gemini failover to generate:
    - Foods to eat (क्या खाएं)
    - Foods to strictly avoid (क्या न खाएं)
    - Substance & beverage warnings (Alcohol / Dairy / Grapefruit / Caffeine)
    - Optimal meal spacing
    - Plain Hindi & English advice
    """
    target_name = generic_name or medicine_name

    prompt = (
        f"You are an expert medical pharmacologist. For the prescribed medication: '{medicine_name}' "
        f"(active substance: '{target_name}', dose: '{dosage or 'standard'}', frequency: '{frequency or 'daily'}'), "
        f"provide evidence-based dietary guidelines and food precautions.\n\n"
        f"Answer STRICTLY in JSON format with these exact keys:\n"
        f"{{\n"
        f'  "foods_to_eat": ["3-4 recommended nutritious foods/drinks that support recovery or ease stomach"],\n'
        f'  "foods_to_avoid": ["3-4 foods/beverages to strictly avoid or space out due to drug absorption interference"],\n'
        f'  "substances_warning": "Specific warning regarding alcohol, smoking, or caffeine interactions",\n'
        f'  "timing_guidance": "Clear instruction on meal spacing, e.g. take 30 mins after meals with plenty of water",\n'
        f'  "hindi_summary": "2-3 short sentences in simple conversational Hindi/Hinglish summarizing what to eat and what to avoid (e.g. हल्का खाना खाएं, खट्टे व तैलीय भोजन से बचें)."\n'
        f"}}\n"
        f"Do not guess. Give safe, established clinical pharmacology advice. Return ONLY JSON."
    )

    # 1. Try Groq high-speed AI first
    raw_response = generate_with_groq(
        prompt=prompt,
        system_instruction="You are an expert clinical pharmacologist. Return strictly JSON."
    )

    # 2. If Groq didn't return, fallback to Gemini
    if not raw_response:
        try:
            from app.services.ai.gemini_service import get_gemini_client
            from google.genai import types
            gemini_client = get_gemini_client()
            if gemini_client:
                for g_model in ["gemini-3.5-flash-lite", "gemini-flash-latest"]:
                    try:
                        g_res = gemini_client.models.generate_content(
                            model=g_model,
                            contents=prompt,
                            config=types.GenerateContentConfig(temperature=0.2)
                        )
                        if g_res and g_res.text:
                            raw_response = g_res.text.strip()
                            break
                    except Exception:
                        continue
        except Exception as e:
            logger.warning(f"Gemini fallback for dietary precautions failed: {e}")

    # Parse JSON
    if raw_response:
        try:
            clean_json = re.sub(r"```json\s*", "", raw_response)
            clean_json = re.sub(r"```\s*", "", clean_json).strip()
            match = re.search(r"\{.*\}", clean_json, re.DOTALL)
            if match:
                parsed = json.loads(match.group(0))
                return {
                    "status": "success",
                    "foods_to_eat": parsed.get("foods_to_eat", ["Light home-cooked meals", "Plenty of warm water"]),
                    "foods_to_avoid": parsed.get("foods_to_avoid", ["Heavy oily food", "Alcohol"]),
                    "substances_warning": parsed.get("substances_warning", "Avoid alcohol while taking this medicine."),
                    "timing_guidance": parsed.get("timing_guidance", "Take after light food with plenty of water."),
                    "hindi_summary": parsed.get("hindi_summary", "हल्का और सुपाच्य भोजन लें। तैलीय और भारी खाने से परहेज करें।")
                }
        except Exception as e:
            logger.warning(f"Failed to parse dietary JSON: {e}")

    # Fallback default safe guidelines
    return {
        "status": "success",
        "foods_to_eat": ["Light, easily digestible home-cooked meals", "Adequate water and hydration", "Fresh seasonal fruits"],
        "foods_to_avoid": ["Excessively oily and spicy foods", "Alcohol and tobacco", "Cold refrigerated foods"],
        "substances_warning": "Do not consume alcohol while taking prescribed medications.",
        "timing_guidance": "Take strictly as directed by your physician with lukewarm water.",
        "hindi_summary": "हल्का, ताजा भोजन करें और खूब पानी पिएं। शराब, खट्टा और ज्यादा तला-भुना खाने से बचें।"
    }

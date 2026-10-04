import math
import requests
from typing import Dict, Any, Optional, Tuple
from flask import current_app
from app.utils.logger import get_logger

logger = get_logger()


def calculate_haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance in kilometers between two GPS coordinates."""
    r = 6371.0  # Earth's radius in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return round(r * c, 2)


def geocode_manual_address(address: str) -> Optional[Tuple[float, float, str]]:
    """Geocode a text address into (lat, lng, display_name) using OpenStreetMap Nominatim or Google Geocoding."""
    if not address or len(address.strip()) < 2:
        return None

    maps_key = current_app.config.get("MAPS_API_KEY")
    if maps_key:
        try:
            url = f"https://maps.googleapis.com/maps/api/geocode/json?address={requests.utils.quote(address)}&key={maps_key}"
            res = requests.get(url, timeout=5).json()
            if res.get("status") == "OK" and res.get("results"):
                loc = res["results"][0]["geometry"]["location"]
                formatted = res["results"][0].get("formatted_address", address)
                return float(loc["lat"]), float(loc["lng"]), formatted
        except Exception as e:
            logger.warning(f"Google geocoding error: {e}")

    # Fallback to OpenStreetMap Nominatim
    try:
        url = f"https://nominatim.openstreetmap.org/search?q={requests.utils.quote(address)}&format=json&limit=1"
        headers = {"User-Agent": "MediLens-AI/1.0 (Prescription Assistant)"}
        res = requests.get(url, headers=headers, timeout=5).json()
        if res and len(res) > 0:
            return float(res[0]["lat"]), float(res[0]["lon"]), res[0].get("display_name", address)
    except Exception as e:
        logger.warning(f"Nominatim geocoding error: {e}")

    return None

import requests
from typing import List, Dict, Any
from flask import current_app
from app.services.pharmacy.maps_service import calculate_haversine_distance
from app.utils.logger import get_logger

logger = get_logger()


def search_pharmacies_google(lat: float, lng: float, radius: int = 5000, open_now: bool = False) -> List[Dict[str, Any]]:
    """Search nearby pharmacies using Google Places API."""
    maps_key = current_app.config.get("MAPS_API_KEY")
    if not maps_key:
        return []

    url = (
        f"https://maps.googleapis.com/maps/api/place/nearbysearch/json"
        f"?location={lat},{lng}&radius={radius}&type=pharmacy&key={maps_key}"
    )
    if open_now:
        url += "&opennow=true"

    try:
        res = requests.get(url, timeout=6).json()
        if res.get("status") not in {"OK", "ZERO_RESULTS"}:
            logger.warning(f"Google Places returned status: {res.get('status')}")
            return []

        results = []
        for p in res.get("results", []):
            loc = p.get("geometry", {}).get("location", {})
            plat, plng = float(loc.get("lat", 0)), float(loc.get("lng", 0))
            dist = calculate_haversine_distance(lat, lng, plat, plng)

            results.append({
                "id": p.get("place_id"),
                "name": p.get("name"),
                "address": p.get("vicinity") or p.get("formatted_address", ""),
                "latitude": plat,
                "longitude": plng,
                "distance_km": dist,
                "is_open": p.get("opening_hours", {}).get("open_now", None),
                "rating": p.get("rating"),
                "user_ratings_total": p.get("user_ratings_total"),
                "directions_url": f"https://www.google.com/maps/dir/?api=1&destination={plat},{plng}",
                "inventory_available": False,
                "source": "Google Places API"
            })
        return results
    except Exception as e:
        logger.error(f"Google Places API request failed: {e}")
        return []


def search_pharmacies_nominatim(lat: float, lng: float, radius_meters: int = 5000) -> List[Dict[str, Any]]:
    """Search real nearby pharmacies using OpenStreetMap Nominatim API."""
    delta = max(0.02, min(0.25, (radius_meters / 111000.0) * 1.2))
    viewbox = f"{lng - delta},{lat + delta},{lng + delta},{lat - delta}"
    url = f"https://nominatim.openstreetmap.org/search?format=json&q=pharmacy&bounded=1&viewbox={viewbox}&limit=25"
    headers = {"User-Agent": "MediLensAI-App/1.0 (Prescription Healthcare Assistant)"}

    try:
        res = requests.get(url, headers=headers, timeout=6).json()
        if not isinstance(res, list):
            return []

        results = []
        for p in res:
            try:
                plat = float(p.get("lat", 0))
                plng = float(p.get("lon", 0))
                if not plat or not plng:
                    continue

                dist = calculate_haversine_distance(lat, lng, plat, plng)
                display_parts = [part.strip() for part in p.get("display_name", "").split(",")]
                pharmacy_name = display_parts[0] if display_parts else "Pharmacy"
                full_address = ", ".join(display_parts[1:5]) if len(display_parts) > 1 else p.get("display_name", "")

                results.append({
                    "id": str(p.get("place_id")),
                    "name": pharmacy_name,
                    "address": full_address or "Local Area",
                    "latitude": plat,
                    "longitude": plng,
                    "distance_km": dist,
                    "phone": None,
                    "is_open": None,
                    "directions_url": f"https://www.google.com/maps/dir/?api=1&destination={plat},{plng}",
                    "inventory_available": False,
                    "source": "OpenStreetMap Verified Registry"
                })
            except Exception:
                continue

        return results
    except Exception as e:
        logger.warning(f"Nominatim pharmacy search error: {e}")
        return []


def search_pharmacies_osm(lat: float, lng: float, radius: int = 5000, open_now: bool = False) -> List[Dict[str, Any]]:
    """Search real nearby pharmacies using OpenStreetMap Overpass API (fallback if no Google Places key)."""
    overpass_url = "https://overpass-api.de/api/interpreter"
    query = f"""
    [out:json][timeout:8];
    (
      node["amenity"="pharmacy"](around:{radius},{lat},{lng});
      way["amenity"="pharmacy"](around:{radius},{lat},{lng});
    );
    out center 25;
    """
    headers = {"User-Agent": "MediLensAI-App/1.0 (Prescription Healthcare Assistant)"}

    try:
        res = requests.post(overpass_url, data={"data": query}, headers=headers, timeout=8).json()
        elements = res.get("elements", [])
        results = []

        for el in elements:
            plat = el.get("lat") or el.get("center", {}).get("lat")
            plng = el.get("lon") or el.get("center", {}).get("lon")
            if not plat or not plng:
                continue

            tags = el.get("tags", {})
            name = tags.get("name") or tags.get("brand") or "Pharmacy / Chemist"
            
            # Construct address
            addr_parts = [
                tags.get("addr:housenumber"),
                tags.get("addr:street"),
                tags.get("addr:suburb") or tags.get("addr:city"),
            ]
            address = ", ".join([p for p in addr_parts if p]) or tags.get("addr:full") or "Local Area"
            phone = tags.get("phone") or tags.get("contact:phone") or None
            dist = calculate_haversine_distance(lat, lng, float(plat), float(plng))

            results.append({
                "id": str(el.get("id")),
                "name": name,
                "address": address,
                "latitude": float(plat),
                "longitude": float(plng),
                "distance_km": dist,
                "phone": phone,
                "is_open": None,
                "directions_url": f"https://www.google.com/maps/dir/?api=1&destination={plat},{plng}",
                "inventory_available": False,
                "source": "OpenStreetMap Real Geospatial Data"
            })

        return results
    except Exception as e:
        logger.warning(f"OpenStreetMap Overpass search error: {e}")
        return []


def find_nearby_pharmacies(
    lat: float,
    lng: float,
    radius_meters: int = 5000,
    open_now_only: bool = False
) -> List[Dict[str, Any]]:
    """
    Find real pharmacies near coordinate using Google Places, Nominatim, or OSM Overpass.
    Deduplicates and sorts strictly by distance.
    """
    results = search_pharmacies_google(lat, lng, radius=radius_meters, open_now=open_now_only)
    if not results:
        results = search_pharmacies_nominatim(lat, lng, radius_meters=radius_meters)
    if not results:
        results = search_pharmacies_osm(lat, lng, radius=radius_meters, open_now=open_now_only)

    # Deduplicate by approximate position or name
    seen = set()
    deduped = []
    for p in results:
        key = (round(p["latitude"], 4), round(p["longitude"], 4), p["name"].lower().strip())
        if key not in seen:
            seen.add(key)
            deduped.append(p)

    # Sort strictly by distance
    deduped.sort(key=lambda x: x["distance_km"])
    return deduped

from flask import Blueprint, render_template, request, session, jsonify, flash
from app.utils.security import login_required
from app.services.pharmacy.maps_service import geocode_manual_address
from app.services.pharmacy.pharmacy_search import find_nearby_pharmacies
from app.utils.logger import get_logger

logger = get_logger()
pharmacy_bp = Blueprint("pharmacy", __name__, url_prefix="/pharmacy")


@pharmacy_bp.route("/", methods=["GET"])
@login_required
def index():
    """Render pharmacy discovery page."""
    return render_template("pharmacy/nearby.html")


@pharmacy_bp.route("/search", methods=["GET"])
@login_required
def search():
    """
    Search real nearby pharmacies using GPS coordinates or manual location string.
    Never fabricates inventory data.
    """
    lat_param = request.args.get("lat")
    lng_param = request.args.get("lng")
    address_query = (request.args.get("address") or "").strip()
    radius_param = request.args.get("radius", 5000)
    open_now = request.args.get("open_now") == "true"

    try:
        radius = min(25000, max(500, int(radius_param)))
    except ValueError:
        radius = 5000

    lat, lng = None, None
    resolved_location_name = ""

    # Try GPS coordinates first
    if lat_param and lng_param:
        try:
            lat = float(lat_param)
            lng = float(lng_param)
            resolved_location_name = "Current Location"
        except ValueError:
            lat, lng = None, None

    # If coordinates not provided or invalid, geocode address query
    if (lat is None or lng is None) and address_query:
        geocoded = geocode_manual_address(address_query)
        if geocoded:
            lat, lng, resolved_location_name = geocoded
        else:
            return jsonify({
                "status": "error",
                "message": f"Could not find coordinates for '{address_query}'. Please check the spelling or try a nearby city/landmark.",
                "pharmacies": []
            }), 404

    # Default fallback to center of New Delhi if neither coordinates nor query given
    if lat is None or lng is None:
        return jsonify({
            "status": "error",
            "message": "Please provide your current location or enter an address to find nearby pharmacies.",
            "pharmacies": []
        }), 400

    try:
        pharmacies = find_nearby_pharmacies(lat, lng, radius_meters=radius, open_now_only=open_now)
        return jsonify({
            "status": "success",
            "location": {
                "latitude": lat,
                "longitude": lng,
                "name": resolved_location_name
            },
            "radius_meters": radius,
            "count": len(pharmacies),
            "pharmacies": pharmacies,
            "disclaimer": "Pharmacies shown from verified public map records. Real-time in-store medicine stock requires direct pharmacy confirmation."
        })
    except Exception as e:
        logger.error(f"Pharmacy search failed: {e}")
        return jsonify({
            "status": "error",
            "message": "Pharmacy lookup service is currently unavailable. Please try again later.",
            "pharmacies": []
        }), 500

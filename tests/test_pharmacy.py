import pytest
from app.services.pharmacy.maps_service import calculate_haversine_distance


def test_haversine_distance():
    """Verify distance calculation between coordinates."""
    # Distance between New Delhi (28.6139, 77.2090) and Noida (28.5355, 77.3910) is ~19 km
    dist = calculate_haversine_distance(28.6139, 77.2090, 28.5355, 77.3910)
    assert dist > 15.0 and dist < 25.0

    # Same location
    dist_zero = calculate_haversine_distance(28.6139, 77.2090, 28.6139, 77.2090)
    assert dist_zero == 0.0

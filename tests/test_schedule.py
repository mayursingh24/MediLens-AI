import pytest
from datetime import date
from app.models.medicine import Medicine
from app.services.medication.schedule_service import generate_schedules_for_medicine


def test_schedule_generation_slots():
    """Verify schedule creation converts 1-0-1 pattern to morning and night slots."""
    med = Medicine(
        id=1,
        prescription_id=1,
        profile_id=1,
        name="Paracetamol",
        strength="500 mg",
        form="Tablet",
        frequency="1-0-1",
        morning=1.0,
        afternoon=0.0,
        evening=0.0,
        night=1.0,
        duration_days=5,
        food_instruction="After food",
    )

    schedules = generate_schedules_for_medicine(med, user_id=1, start_date=date(2026, 10, 1))
    assert len(schedules) == 2

    morning_sched = next((s for s in schedules if s.time_slot == "morning"), None)
    assert morning_sched is not None
    assert morning_sched.reminder_time == "08:00"
    assert morning_sched.dose_amount == "1 Tablet"
    assert morning_sched.food_instruction == "After food"

    night_sched = next((s for s in schedules if s.time_slot == "night"), None)
    assert night_sched is not None
    assert night_sched.reminder_time == "21:00"
    assert night_sched.dose_amount == "1 Tablet"


def test_schedule_respects_custom_times():
    """Verify user can personalize reminder times without altering frequency."""
    med = Medicine(
        id=2,
        prescription_id=1,
        profile_id=1,
        name="Metformin",
        morning=1.0,
        afternoon=0.0,
        evening=0.0,
        night=0.0,
    )

    custom_times = {"morning": "07:30"}
    schedules = generate_schedules_for_medicine(med, user_id=1, custom_times=custom_times)
    assert len(schedules) == 1
    assert schedules[0].reminder_time == "07:30"

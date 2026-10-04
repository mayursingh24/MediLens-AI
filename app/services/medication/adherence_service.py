from datetime import date, datetime, timedelta, timezone
from typing import Dict, Any, List
from app.models.medication_log import MedicationLog
from app.models.schedule import Schedule
from app.extensions import db


def record_medication_action(
    schedule_id: int,
    user_id: int,
    action: str,  # 'taken', 'skipped', 'snoozed'
    target_date: date = None,
    notes: str = None
) -> MedicationLog:
    """Record an adherence action event for a scheduled dose."""
    schedule = Schedule.query.get(schedule_id)
    if not schedule:
        raise ValueError("Schedule not found.")

    eff_date = target_date or date.today()

    # Check if an existing log exists for this schedule on the target date
    existing = MedicationLog.query.filter_by(
        schedule_id=schedule.id,
        scheduled_date=eff_date
    ).first()

    if existing:
        existing.action = action
        existing.logged_at = datetime.now(timezone.utc)
        if notes:
            existing.notes = notes
        log_entry = existing
    else:
        log_entry = MedicationLog(
            schedule_id=schedule.id,
            medicine_id=schedule.medicine_id,
            profile_id=schedule.profile_id,
            user_id=user_id,
            scheduled_date=eff_date,
            scheduled_time=schedule.reminder_time,
            action=action,
            notes=notes,
            logged_at=datetime.now(timezone.utc),
        )
        db.session.add(log_entry)

    db.session.commit()
    return log_entry


def calculate_adherence_metrics(user_id: int, profile_id: int = None, days: int = 7) -> Dict[str, Any]:
    """
    Calculate adherence rate strictly from user-recorded events.
    Returns:
    - adherence_percentage (0 to 100)
    - taken_count
    - skipped_count
    - missed_count
    - total_expected
    """
    start_date = date.today() - timedelta(days=days - 1)
    end_date = date.today()

    query = MedicationLog.query.filter(
        MedicationLog.user_id == user_id,
        MedicationLog.scheduled_date >= start_date,
        MedicationLog.scheduled_date <= end_date
    )
    if profile_id:
        query = query.filter(MedicationLog.profile_id == profile_id)

    logs: List[MedicationLog] = query.all()

    taken = sum(1 for l in logs if l.action == "taken")
    skipped = sum(1 for l in logs if l.action == "skipped")
    snoozed = sum(1 for l in logs if l.action == "snoozed")
    missed = sum(1 for l in logs if l.action == "missed")

    total_recorded = taken + skipped + missed

    # Calculate expected doses from active schedules over date range
    sched_query = Schedule.query.filter_by(user_id=user_id, is_active=True)
    if profile_id:
        sched_query = sched_query.filter_by(profile_id=profile_id)
    active_schedules = sched_query.all()

    # Determine total scheduled doses across the period
    total_expected = 0
    cur = start_date
    while cur <= end_date:
        for s in active_schedules:
            if s.start_date <= cur and (s.end_date is None or s.end_date >= cur):
                total_expected += 1
        cur += timedelta(days=1)

    effective_denominator = max(total_expected, total_recorded)
    adherence_pct = round((taken / effective_denominator * 100), 1) if effective_denominator > 0 else 100.0

    return {
        "adherence_percentage": min(100.0, adherence_pct),
        "taken": taken,
        "skipped": skipped,
        "snoozed": snoozed,
        "missed": missed,
        "total_expected": effective_denominator,
        "period_days": days,
    }

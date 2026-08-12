from datetime import date, datetime, timedelta, timezone

from app.ai.enhanced_agent import EnhancedAIAgent
from app.ai import extractor
from app.ai.doctor_extractor import DoctorExtractor
from app.core import timezone as tz_mod

SAT = date(2026, 8, 1)  # a Saturday
KARACHI = timezone(timedelta(hours=5))


def test_doctor_extractor_handles_special_chars_and_prefixes():
    assert DoctorExtractor.extract("dr_hafsa") == "dr_hafsa"
    assert DoctorExtractor.extract("Dr. Dr. Sara Khan") == "Sara Khan"
    assert DoctorExtractor.extract("book with Dr. Hina Malik") == "Hina Malik"
    assert DoctorExtractor.extract("safiullah") == "safiullah"


def test_next_weekday_uses_today_when_weekday_matches():
    assert EnhancedAIAgent._next_weekday("saturday", SAT) == SAT
    assert EnhancedAIAgent._next_weekday("sunday", SAT) == date(2026, 8, 2)
    assert EnhancedAIAgent._next_weekday("monday", SAT) == date(2026, 8, 3)


def test_extractor_bare_weekday_uses_today_when_weekday_matches():
    orig = extractor.clinic_today
    extractor.clinic_today = lambda: SAT
    try:
        data = {}
        extractor.AppointmentExtractor._extract_date(
            "I want a saturday appointment please", data
        )
        assert data["appointment_date"] == SAT
    finally:
        extractor.clinic_today = orig


def test_timezone_now_is_naive_clinic_time():
    fixed = datetime(2026, 8, 1, 15, 30, tzinfo=KARACHI)
    orig = tz_mod.datetime
    patched = type("FrozenDateTime", (), {"now": classmethod(lambda cls, *a, **k: fixed)})
    tz_mod.datetime = patched
    try:
        assert tz_mod.now() == datetime(2026, 8, 1, 15, 30)
        assert tz_mod.today() == SAT
    finally:
        tz_mod.datetime = orig


if __name__ == "__main__":
    test_doctor_extractor_handles_special_chars_and_prefixes()
    test_next_weekday_uses_today_when_weekday_matches()
    test_extractor_bare_weekday_uses_today_when_weekday_matches()
    test_timezone_now_is_naive_clinic_time()
    print("ok")

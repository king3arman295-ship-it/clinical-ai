import re
from datetime import datetime, date, time, timedelta
from app.common.enums import AppointmentType
from app.core.timezone import today as clinic_today


class AppointmentExtractor:

    DAY_NAMES = {
        "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
        "friday": 4, "saturday": 5, "sunday": 6,
    }

    @staticmethod
    def extract(message: str):
        data = {
            "patient_id": None,
            "doctor_id": None,
            "appointment_date": None,
            "appointment_time": None,
            "appointment_type": None,
            "reason": None,
            "conditions": None,
            "allergies": None,
        }

        AppointmentExtractor._extract_type(message, data)
        AppointmentExtractor._extract_date(message, data)
        AppointmentExtractor._extract_time(message, data)
        AppointmentExtractor._extract_reason(message, data)

        return data

    @staticmethod
    def _extract_type(message: str, data: dict):
        if re.search(r"\b(video|online|virtual|zoom|agora|telehealth|call)\b", message, re.I):
            data["appointment_type"] = AppointmentType.VIDEO
        elif re.search(r"\b(physical|clinic|in-person|in person|walk-in|walkin)\b", message, re.I):
            data["appointment_type"] = AppointmentType.PHYSICAL

    @staticmethod
    def _extract_date(message: str, data: dict):
        # YYYY-MM-DD
        m = re.search(r"(\d{4})-(\d{2})-(\d{2})", message)
        if m:
            data["appointment_date"] = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            return

        # DD/MM/YYYY or MM/DD/YYYY or DD-MM-YYYY
        m = re.search(r"(\d{2})[/-](\d{2})[/-](\d{4})", message)
        if m:
            p1, p2, p3 = int(m.group(1)), int(m.group(2)), int(m.group(3))
            # If first part > 12, it's definitely DD/MM/YYYY
            if p1 > 12:
                data["appointment_date"] = date(p3, p2, p1)
            else:
                data["appointment_date"] = date(p3, p1, p2)
            return

        # "today"
        if re.search(r"\btoday\b", message, re.I):
            data["appointment_date"] = clinic_today()
            return

        # "tomorrow"
        if re.search(r"\btomorrow\b", message, re.I):
            data["appointment_date"] = clinic_today() + timedelta(days=1)
            return

        # "next monday", "next tuesday", etc.
        m = re.search(r"\bnext\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)", message, re.I)
        if m:
            target = AppointmentExtractor.DAY_NAMES[m.group(1).lower()]
            today = clinic_today()
            days_ahead = target - today.weekday()
            if days_ahead <= 0:
                days_ahead += 7
            data["appointment_date"] = today + timedelta(days=days_ahead + 7)
            return

        # bare day name: "monday", "tuesday", etc. → next occurrence
        m = re.search(r"\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", message, re.I)
        if m:
            target = AppointmentExtractor.DAY_NAMES[m.group(1).lower()]
            today = clinic_today()
            days_ahead = target - today.weekday()
            if days_ahead < 0:
                days_ahead += 7
            data["appointment_date"] = today + timedelta(days=days_ahead)
            return

    @staticmethod
    def _extract_time(message: str, data: dict):
        # HH:am or HH:pm — "10:am", "10: pm"
        m = re.search(r"(\d{1,2}):\s*(am|pm)\b", message, re.I)
        if m:
            hour = int(m.group(1))
            ampm = m.group(2).lower()
            if ampm == "pm" and hour != 12:
                hour += 12
            elif ampm == "am" and hour == 12:
                hour = 0
            if 1 <= hour <= 23:
                data["appointment_time"] = time(hour, 0)
            return

        # HH:MM with optional am/pm — "10:30", "10:30 PM"
        m = re.search(r"(\d{1,2}):(\d{2})(?:\s*(am|pm))?", message, re.I)
        if m:
            hour, minute = int(m.group(1)), int(m.group(2))
            ampm = m.group(3)
            if ampm:
                ampm = ampm.lower()
                if ampm == "pm" and hour != 12:
                    hour += 12
                elif ampm == "am" and hour == 12:
                    hour = 0
            if 0 <= hour <= 23 and 0 <= minute <= 59:
                data["appointment_time"] = time(hour, minute)
            return

        # HH.MM with optional am/pm — "10.30", "10.30am", "2.30 PM"
        m = re.search(r"(\d{1,2})[.](\d{2})(?:\s*(am|pm))?", message, re.I)
        if m:
            hour, minute = int(m.group(1)), int(m.group(2))
            ampm = m.group(3)
            if ampm:
                ampm = ampm.lower()
                if ampm == "pm" and hour != 12:
                    hour += 12
                elif ampm == "am" and hour == 12:
                    hour = 0
            if 0 <= hour <= 23 and 0 <= minute <= 59:
                data["appointment_time"] = time(hour, minute)
            return

        # HH o'clock — "10 o'clock", "2 o clock"
        m = re.search(r"(\d{1,2})\s*o['`\u2019]?\s*clock", message, re.I)
        if m:
            hour = int(m.group(1))
            if 1 <= hour <= 12:
                data["appointment_time"] = time(hour, 0)
            return

        # HHam / HH pm — "10am", "2 pm", "2pm"
        m = re.search(r"(\d{1,2})\s*(am|pm)\b", message, re.I)
        if m:
            hour = int(m.group(1))
            ampm = m.group(2).lower()
            if ampm == "pm" and hour != 12:
                hour += 12
            elif ampm == "am" and hour == 12:
                hour = 0
            if 1 <= hour <= 23:
                data["appointment_time"] = time(hour, 0)
            return

        # Bare hour — "at 10", "by 2" — only when time context is clear
        m = re.search(r"\b(\d{1,2})\b", message, re.I)
        if m:
            before = message[:m.start()].strip().lower()
            last_word = before.split()[-1] if before else ""
            if last_word in ("at", "by", "around", "after", "before", "past", "till", "until"):
                hour = int(m.group(1))
                if 1 <= hour <= 12:
                    data["appointment_time"] = time(hour, 0)

    @staticmethod
    def _extract_reason(message: str, data: dict):
        m = re.search(
            r"(?:suffering from|having|feel|feeling|due to|reason|symptoms?|for)\s+([A-Za-z0-9\s,]+?)(?:\.|$|with|doctor|on|at)",
            message, re.I,
        )
        if m:
            data["reason"] = m.group(1).strip()

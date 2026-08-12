from sqlalchemy.orm import Session

from app.ai.intent_detector import IntentDetector
from app.ai.extractor import AppointmentExtractor
from app.ai.doctor_extractor import DoctorExtractor
from app.ai.patient_extractor import PatientExtractor
from app.ai.session_state import SessionState
from app.ai.language_guard import LanguageGuard
from datetime import datetime

from app.ai.smart_recommender import SmartDoctorRecommender

from app.schemas.appointment import AppointmentCreate

from app.services.appointment_service import AppointmentService
from app.services.patient_service import PatientService


class EnhancedAIAgent:

    def __init__(
        self,
        appointment_service: AppointmentService,
        patient_service: PatientService,
        doctor_repository,
        doctor_schedule_repository=None,
        emr_service=None,
    ):
        self.appointment_service = appointment_service
        self.patient_service = patient_service
        self.doctor_repository = doctor_repository
        self.doctor_schedule_repository = doctor_schedule_repository
        self.emr_service = emr_service

    def chat(
        self,
        db: Session,
        session_id: str,
        user_message: str,
        file=None,
        authenticated_patient=None,
    ):
        state = SessionState.get(session_id)

        if authenticated_patient is not None:
            state["authenticated_patient_id"] = authenticated_patient.id
            state["patient_name"] = authenticated_patient.name
            state["phone"] = authenticated_patient.phone
            state["email"] = authenticated_patient.email

        if state.get("flow") == "post_booking_upload":
            return self._handle_post_booking_upload(db, session_id, user_message, file, state)

        if state.get("flow") == "cancel_appointment":
            return self._handle_cancel_flow(db, session_id, user_message, state)

        if file is not None:
            return {
                "response": (
                    "I can help you share a medical record with your doctor right after "
                    "you book an appointment \u2014 or you can upload one anytime from "
                    "Medical Records in your portal."
                ),
                "session_id": session_id,
            }

        if LanguageGuard.is_non_english(user_message):
            return {
                "response": LanguageGuard.ask_for_english_message(),
                "session_id": session_id,
            }

        # Strict scope: only allowed topics OR active booking flow pass through
        has_active_flow = state.get("intent") == "book_appointment"
        if not has_active_flow and not LanguageGuard.is_allowed_topic(user_message):
            return {
                "response": LanguageGuard.scope_restricted_message(),
                "session_id": session_id,
            }

        # Non-flow overrides: view departments / doctors should work
        # regardless of whatever state the conversation is in.
        # Skip during change mode (e.g. "Doctor" means change doctor, not list all).
        in_change_mode = state.get("confirmed") is False
        if not in_change_mode and self._is_department_query(user_message):
            return self._handle_department_info(db, session_id)
        if not in_change_mode and self._is_doctors_query(user_message):
            return self._handle_doctors_info(db, session_id)

        if state.get("intent"):
            intent = state["intent"]
        else:
            intent = IntentDetector.detect(user_message)

        if intent in ("book_appointment", "cancel_appointment", "view_appointments"):
            if not state.get("authenticated_patient_id"):
                return self._require_login(session_id, intent)

        if intent == "book_appointment":
            return self._handle_booking_flow(db, session_id, user_message, state)

        if intent == "cancel_appointment":
            return self._handle_cancel_flow(db, session_id, user_message, state)

        if intent == "view_appointments":
            return self._handle_view_appointments(db, session_id, state)

        if self._is_department_query(user_message):
            return self._handle_department_info(db, session_id)

        if self._is_doctors_query(user_message):
            return self._handle_doctors_info(db, session_id)

        return {
            "response": LanguageGuard.scope_restricted_message(),
            "session_id": session_id,
            "suggestions": ["Book Appointment", "View Departments", "See Available Doctors"],
        }

    def clear_memory(self, session_id: str):
        SessionState.clear(session_id)

    def _require_login(self, session_id: str, intent: str):
        action = {
            "book_appointment": "book an appointment",
            "cancel_appointment": "cancel an appointment",
            "view_appointments": "view your appointments",
        }.get(intent, "do that")

        return {
            "response": (
                f"To {action}, please sign in first \u2014 or create a free account "
                "if you're new here.\n\n"
                "Once you're logged in, just come back and ask me again and "
                "I'll take care of it right away!"
            ),
            "session_id": session_id,
            "requires_auth": True,
        }

    def _is_department_query(self, message: str) -> bool:
        lowered = message.lower().strip(".!? ")
        return any(kw in lowered for kw in [
            "what departments", "list departments", "view departments",
            "show departments", "all departments", "departments available",
            "tell me about departments",
        ]) or lowered in ("department", "departments", "specializations", "specialties")

    def _is_doctors_query(self, message: str) -> bool:
        lowered = message.lower().strip(".!? ")
        return any(kw in lowered for kw in [
            "available doctors", "list doctors", "show doctors",
            "tell me about doctors", "what doctors", "all doctors",
            "see available doctors", "view doctors", "who are the doctors",
        ]) or lowered in ("doctor", "doctors", "specialists")

    def _handle_department_info(self, db: Session, session_id: str):
        all_doctors = self.doctor_repository.get_all(db)

        def _title_dept(s: str) -> str:
            words = s.strip().split()
            if not words:
                return s
            if len(words) == 1 and words[0].isupper():
                return words[0]
            return " ".join(
                w if len(w) <= 4 and w.isupper() else w.capitalize()
                for w in words
            )

        # Group case-insensitively so "cardiology" and "Cardiology" count together
        dept_map = {}
        for d in all_doctors:
            if not d.specialization:
                continue
            key = d.specialization.strip().lower()
            if key not in dept_map:
                dept_map[key] = {"label": _title_dept(d.specialization), "count": 0}
            dept_map[key]["count"] += 1

        if not dept_map:
            return {
                "response": "We are currently updating our department information. Please check back later.",
                "session_id": session_id,
            }

        lines = ["We have the following departments at our clinic:\n"]
        for entry in sorted(dept_map.values(), key=lambda e: e["label"].lower()):
            label, count = entry["label"], entry["count"]
            lines.append(f"\u2022 **{label}** ({count} doctor{'s' if count != 1 else ''})")
        lines.append("\nWould you like to see available doctors in any of these departments?")
        return {"response": "\n".join(lines), "session_id": session_id,
                "suggestions": ["Book Appointment", "View Departments", "See Available Doctors"]}

    def _handle_doctors_info(self, db: Session, session_id: str):
        all_doctors = self.doctor_repository.get_all(db)
        available = [d for d in all_doctors if d.available]
        ranked = SmartDoctorRecommender.rank_doctors(available or all_doctors)

        if not ranked:
            return {
                "response": "No doctors are currently available. Please check back later.",
                "session_id": session_id,
            }

        lines = [f"We have {len(ranked)} doctor{'s' if len(ranked) != 1 else ''} available:\n"]
        for doc in ranked:
            lines.append(                f"\u2022 **{SmartDoctorRecommender.display_name(doc.full_name)}** \u2014 {doc.specialization}")
            if doc.experience_years:
                lines.append(f"  {doc.experience_years} years experience")
            schedule_text = self._get_doctor_schedule_text(db, doc.id)
            if schedule_text:
                lines.append(f"  {schedule_text}")
            lines.append("")
        lines.append("Would you like to book an appointment? Tell me your symptoms and I'll recommend the right doctor!")
        return {"response": "\n".join(lines), "session_id": session_id,
                "suggestions": ["Book Appointment", "View Departments", "See Available Doctors"]}

    def _get_doctor_schedule_text(self, db: Session, doctor_id: int) -> str:
        if not self.doctor_schedule_repository:
            return ""
        try:
            schedules = self.doctor_schedule_repository.get_by_doctor(db, doctor_id)
            if not schedules:
                return ""
            available = [s for s in schedules if s.is_available]
            if not available:
                return ""
            parts = []
            from app.core.timezone import now as clinic_now
            today = clinic_now().strftime("%A")
            for s in available:
                tag = " (Today)" if s.day_of_week.lower() == today.lower() else ""
                parts.append(
                    f"{s.day_of_week}: {s.start_time.strftime('%H:%M')}\u2013{s.end_time.strftime('%H:%M')}{tag}"
                )
            return "Schedule: " + ", ".join(parts)
        except Exception:
            return ""

    def _get_selected_doctor_schedule_text(self, db: Session, doctor) -> str:
        if not self.doctor_schedule_repository:
            return f"I can't find a schedule for {SmartDoctorRecommender.display_name(doctor.full_name)} yet. Please contact the clinic."

        try:
            schedules = self.doctor_schedule_repository.get_by_doctor(db, doctor.id)
            available_schedules = [s for s in schedules if s.is_available]
        except Exception:
            available_schedules = []

        if not available_schedules:
            return (
                f"{SmartDoctorRecommender.display_name(doctor.full_name)} does not have any available clinic hours configured right now. "
                "Please choose another doctor or tell me about another health concern."
            )

        day_order = {
            "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
            "friday": 4, "saturday": 5, "sunday": 6,
        }
        available_schedules.sort(key=lambda s: day_order.get(s.day_of_week.lower(), 99))
        lines = [f"{SmartDoctorRecommender.display_name(doctor.full_name)} is available:"]
        for s in available_schedules:
            lines.append(
                f"- {s.day_of_week}: {s.start_time.strftime('%I:%M %p').lstrip('0')} "
                f"to {s.end_time.strftime('%I:%M %p').lstrip('0')} "
                f"({s.slot_duration}-minute slots)"
            )
        lines.append("What date would you like to come?")
        return "\n".join(lines)

    WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

    SYMPTOM_CATEGORIES = [
        ("Chest / Heart", "Cardiology"),
        ("Head / Brain / Migraine", "Neurology"),
        ("Stomach / Digestion", "Gastroenterology"),
        ("Bone / Joint / Muscle", "Orthopedics"),
        ("Skin / Rash / Allergy", "Dermatology"),
        ("Fever / Cold / Flu", "General Medicine"),
        ("Kidney / Urinary", "Urology"),
        ("Anxiety / Stress / Sleep", "Psychiatry"),
        ("Diabetes / Thyroid", "Endocrinology"),
        ("Eye / Vision", "Ophthalmology"),
        ("Ear / Nose / Throat", "ENT"),
        ("General Checkup", "General Medicine"),
        ("Other \u2014 type your concern", None),
    ]

    @staticmethod
    def _match_day_name(text: str) -> str | None:
        lowered = text.lower().strip()
        for day in EnhancedAIAgent.WEEKDAYS:
            if day in lowered:
                return day.capitalize()
        return None

    def _get_doctor_available_days(self, db, doctor) -> list[str]:
        if not self.doctor_schedule_repository:
            return []
        schedules = self.doctor_schedule_repository.get_by_doctor(db, doctor.id)
        available = [s for s in schedules if s.is_available]
        day_order = {d: i for i, d in enumerate(EnhancedAIAgent.WEEKDAYS)}
        available.sort(key=lambda s: day_order.get(s.day_of_week.lower(), 99))
        return [s.day_of_week for s in available]

    def _format_doctor_available_days(self, db, doctor) -> str:
        if not self.doctor_schedule_repository:
            return ""
        schedules = self.doctor_schedule_repository.get_by_doctor(db, doctor.id)
        available = [s for s in schedules if s.is_available]
        day_order = {d: i for i, d in enumerate(EnhancedAIAgent.WEEKDAYS)}
        available.sort(key=lambda s: day_order.get(s.day_of_week.lower(), 99))
        lines = []
        for s in available:
            st = s.start_time.strftime("%I:%M %p").lstrip("0")
            et = s.end_time.strftime("%I:%M %p").lstrip("0")
            lines.append(f"  \u2022 {s.day_of_week}: {st} to {et} ({s.slot_duration}-minute slots)")
        return "\n".join(lines)

    @staticmethod
    def _next_weekday(day_name: str, today=None):
        from datetime import timedelta
        from app.core.timezone import today as clinic_today
        target = EnhancedAIAgent.WEEKDAYS.index(day_name.lower())
        today = today or clinic_today()
        days_ahead = target - today.weekday()
        if days_ahead < 0:
            days_ahead += 7
        return today + timedelta(days=days_ahead)

    def _get_available_time_slots(self, db, doctor_id: int, day_name: str, appt_date) -> list[str]:
        from datetime import datetime, time
        from app.core.timezone import now as clinic_now
        if not self.doctor_schedule_repository:
            return []
        schedule = self.doctor_schedule_repository.get_schedule(db, doctor_id, day_name)
        if not schedule:
            return []
        start = schedule.start_time
        end = schedule.end_time
        duration = schedule.slot_duration or 30
        end_minutes = end.hour * 60 + end.minute
        if isinstance(appt_date, str):
            appt_date = datetime.strptime(appt_date, "%Y-%m-%d").date()
        clinic_now_dt = clinic_now()
        is_today = appt_date == clinic_now_dt.date()
        now_time = clinic_now_dt.time()
        booked = set()
        booked_appts = self.appointment_service.appointment_repository.get_doctor_schedule(
            db, doctor_id, appt_date
        )
        for appt in booked_appts:
            if appt.appointment_time:
                booked.add((appt.appointment_time.hour, appt.appointment_time.minute))
        slots = []
        cur = start.hour * 60 + start.minute
        while cur < end_minutes:
            h, m = divmod(cur, 60)
            slot_time = time(h, m)
            if is_today and slot_time < now_time:
                cur += duration
                continue
            if (h, m) not in booked:
                slots.append(slot_time.strftime("%I:%M %p").lstrip("0"))
            cur += duration
        return slots

    def _resume_booking(self, db: Session, session_id: str, state: dict) -> dict | None:
        """Resume the booking flow from wherever the user left off.

        Checks stages latest-first so a resuming user always lands back at the
        furthest point they'd reached (e.g. the confirmation, not the doctor list).
        """
        if state.get("appointment_time"):
            if not state.get("appointment_type"):
                return {
                    "response": "Which type of consultation would you prefer?",
                    "session_id": session_id,
                    "suggestions": ["Physical Visit", "Video Consultation"],
                }
            return self._show_confirmation(db, session_id, state)

        if state.get("appointment_day"):
            slots = self._get_available_time_slots(
                db, state["doctor_id"], state["appointment_day"], state["appointment_date"]
            )
            if slots:
                return {
                    "response": f"Available slots on {state['appointment_day']}:\nPlease select a time.",
                    "session_id": session_id,
                    "suggestions": slots,
                }

        if state.get("doctor_id"):
            doctor = self.doctor_repository.get_by_id(db, state["doctor_id"])
            if doctor:
                days = self._get_doctor_available_days(db, doctor)
                return {
                    "response": (
                        f"{SmartDoctorRecommender.display_name(doctor.full_name)} is available on:\n"
                        f"{self._format_doctor_available_days(db, doctor)}\n\n"
                        "Which day works best for you?"
                    ),
                    "session_id": session_id,
                    "suggestions": days,
                }

        if state.get("suggested_department") and state.get("recommended_doctors"):
            doctors = []
            for doc_id in state["recommended_doctors"]:
                doc = self.doctor_repository.get_by_id(db, doc_id)
                if doc:
                    doctors.append(doc)
            if doctors:
                dept = state["suggested_department"]
                return {
                    "response": SmartDoctorRecommender.format_doctor_recommendation(doctors, dept),
                    "session_id": session_id,
                    "suggestions": [d.full_name for d in doctors[:3]],
                }

        return None

    def _reask_doctor_selection(self, db: Session, session_id: str, state: dict, doctor) -> dict:
        """Re-show the recommended doctor list as selectable buttons."""
        doctors = []
        for doc_id in state.get("recommended_doctors", []):
            doc = self.doctor_repository.get_by_id(db, doc_id)
            if doc:
                doctors.append(doc)
        if not doctors:
            return {
                "response": "Please select a doctor from the list I suggested. Just tell me the doctor's name.",
                "session_id": session_id,
            }
        dept = state.get("suggested_department", "recommended")
        response = SmartDoctorRecommender.format_doctor_recommendation(doctors, dept)
        if doctor:
            response = (
                f"{SmartDoctorRecommender.display_name(doctor.full_name)} isn't in my recommended list.\n\n" + response
            )
        return {
            "response": response,
            "session_id": session_id,
            "suggestions": [d.full_name for d in doctors[:3]],
        }

    def _show_confirmation(self, db: Session, session_id: str, state: dict) -> dict:
        """Render the appointment confirmation and mark it as reached."""
        doctor = self.doctor_repository.get_by_id(db, state.get("doctor_id"))
        doctor_name = doctor.full_name if doctor else state.get("doctor_name", "selected doctor")
        raw_type = state.get("appointment_type")
        if isinstance(raw_type, str) and "video" in raw_type.lower():
            appt_type_str = "Video Consultation"
        else:
            appt_type_str = "Physical Visit"
        state["confirmed"] = True
        return {
            "response": (
                f"Please confirm your appointment:\n\n"
                f"\u2022 Patient: {state['patient_name']}\n"
                f"\u2022 Doctor: {SmartDoctorRecommender.display_name(doctor_name)}\n"
                f"\u2022 Date: {state['appointment_date']}\n"
                f"\u2022 Time: {state['appointment_time']}\n"
                f"\u2022 Type: {appt_type_str}\n"
                f"\u2022 Reason: {state.get('reason', 'Consultation')}\n\n"
                f"Say **yes** to confirm or **no** to make changes."
            ),
            "session_id": session_id,
            "suggestions": ["Yes - Confirm", "No - Make Changes"],
        }

    # --- Booking flow ---

    ABORT_WORDS = {"cancel", "stop", "forget", "never mind", "forget it", "abort", "quit", "exit", "nothing", "none"}
    SHOW_AGAIN_WORDS = {"show again", "show doctors", "show options", "repeat", "again", "what were", "tell me again"}

    CHANGE_FIELDS = {
        "doctor": ("doctor", "dr", "doc", "specialist", "physician"),
        "date": ("date", "day", "reschedule", "another day", "different day"),
        "time": ("time", "timing", "slot"),
        "type": ("type", "consultation", "video", "physical"),
    }

    def _handle_booking_flow(self, db: Session, session_id: str, user_message: str, state: dict):
        state["intent"] = "book_appointment"
        text = (user_message or "").strip().lower()

        # ponytail: global lock, per-account locks if throughput matters

        if self._match_any(text, self.ABORT_WORDS):
            SessionState.clear(session_id)
            return {
                "response": "No problem! Feel free to come back whenever you'd like to book an appointment.",
                "session_id": session_id,
                "suggestions": ["Book Appointment", "View Departments", "See Available Doctors"],
            }

        if self._match_any(text, self.SHOW_AGAIN_WORDS):
            if state.get("recommended_doctors"):
                doctors = []
                for doc_id in state["recommended_doctors"]:
                    doc = self.doctor_repository.get_by_id(db, doc_id)
                    if doc:
                        doctors.append(doc)
                if doctors:
                    dept = state.get("suggested_department", "recommended")
                    return {
                        "response": SmartDoctorRecommender.format_doctor_recommendation(doctors, dept),
                        "session_id": session_id,
                    }
            return {
                "response": "We were in the middle of booking. Let me ask again:",
                "session_id": session_id,
            }

        # Generic booking phrases like "Book Appointment" or "book" when
        # the user already has booking progress should resume, not restart.
        RESUME_WORDS = {"book appointment", "book", "make appointment",
                        "schedule", "reserve", "booking", "i want to book"}
        if text in RESUME_WORDS or any(text.startswith(p) for p in RESUME_WORDS):
            if state.get("department_suggested") or state.get("recommended_doctors"):
                result = self._resume_booking(db, session_id, state)
                if result:
                    return result

        if state.get("confirmed") is False:
            changed = False
            for field, keywords in self.CHANGE_FIELDS.items():
                if any(kw in text for kw in keywords):
                    if field == "doctor":
                        state.pop("doctor_id", None)
                        state.pop("doctor_name", None)
                        state.pop("department_suggested", None)
                        state.pop("suggested_department", None)
                        state["confirmed"] = None
                        state.pop("appointment_day", None)
                        state.pop("appointment_date", None)
                        state.pop("appointment_time", None)
                        state.pop("appointment_type", None)
                        return {
                            "response": (
                                f"Let's find a different doctor for you, {state.get('patient_name', '')}.\n\n"
                                "Please tell me your symptoms again so I can recommend the right specialist."
                            ),
                            "session_id": session_id,
                            "suggestions": [c[0] for c in self.SYMPTOM_CATEGORIES],
                        }
                    if field == "date":
                        # Changing the date invalidates the chosen day AND time
                        state.pop("appointment_day", None)
                        state.pop("appointment_date", None)
                        state.pop("appointment_time", None)
                    else:
                        state.pop("appointment_" + field, None)
                    state["confirmed"] = None
                    changed = True
                    break
            if not changed:
                return {
                    "response": "I'm not sure what you'd like to change. Please say: doctor, date, time, or type.",
                    "session_id": session_id,
                    "suggestions": ["Doctor", "Date", "Time", "Type"],
                }

        # Authenticated users already have name/phone from their account.
        # Never override those with text-extracted values (e.g. "Book Appointment"
        # would otherwise be treated as a name by PatientExtractor's fallback).
        if not state.get("authenticated_patient_id"):
            patient_data = PatientExtractor.extract(user_message)
            for key, value in patient_data.items():
                if value is not None:
                    state[key] = value

        if not state.get("patient_name"):
            return {
                "response": "I'd be happy to help you book an appointment!\n\nMay I have your full name, please?",
                "session_id": session_id,
            }

        if not state.get("phone"):
            return {
                "response": f"Thank you, {state['patient_name']}!\n\nCould you please share your phone number?",
                "session_id": session_id,
            }

        if not state.get("symptoms_discussed"):
            state["symptoms_discussed"] = True
            return {
                "response": f"What health concern are you experiencing, {state['patient_name']}?",
                "session_id": session_id,
                "suggestions": [c[0] for c in self.SYMPTOM_CATEGORIES],
            }

        if not state.get("department_suggested"):
            # Check if user picked a symptom category
            symptoms = None
            for cat_label, _ in self.SYMPTOM_CATEGORIES:
                if text == cat_label.lower().strip() or cat_label.lower().startswith(text):
                    # "Other" → ask for free-text
                    if cat_label.startswith("Other"):
                        return {
                            "response": (
                                f"Please tell me what symptoms or health concerns you're experiencing, "
                                f"{state['patient_name']}."
                            ),
                            "session_id": session_id,
                        }
                    symptoms = cat_label
                    break

            if not symptoms:
                # Free-text fallback
                BOOK_PHRASES = {"book appointment", "book", "make appointment",
                                "schedule", "reserve", "booking", "i want to book"}
                if text in BOOK_PHRASES or any(text.startswith(p) for p in BOOK_PHRASES):
                    return {
                        "response": f"Please select a health concern from the options above, {state['patient_name']}.",
                        "session_id": session_id,
                        "suggestions": [c[0] for c in self.SYMPTOM_CATEGORIES],
                    }
                symptoms = user_message
            state["reason"] = symptoms

            department = SmartDoctorRecommender.detect_department_from_symptoms(symptoms)
            state["suggested_department"] = department
            state["department_suggested"] = True

            doctors = SmartDoctorRecommender.get_doctors_by_department(db, self.doctor_repository, department)

            if not doctors:
                state.pop("department_suggested", None)
                state.pop("suggested_department", None)
                return {
                    "response": (
                        f"I'm sorry, we don't have an available {department} doctor for those symptoms right now. "
                        "Do you have any other symptoms or a different health concern I can help with?"
                    ),
                    "session_id": session_id,
                    "suggestions": [c[0] for c in self.SYMPTOM_CATEGORIES],
                }

            recommendation = SmartDoctorRecommender.format_doctor_recommendation(doctors, department)
            ranked = SmartDoctorRecommender.rank_doctors(doctors)
            top_ids = [d.id for d in ranked[:3]]
            state["recommended_doctors"] = top_ids

            return {
                "response": recommendation,
                "session_id": session_id,
                "suggestions": [d.full_name for d in ranked[:3]],
            }

        extracted = AppointmentExtractor.extract(user_message)
        for key, value in extracted.items():
            if value is not None:
                state[key] = value

        doctor_name = DoctorExtractor.extract(user_message)
        if doctor_name:
            doctor = self.doctor_repository.get_by_name(db, doctor_name)
            recommended_ids = state.get("recommended_doctors", [])
            if doctor and doctor.id in recommended_ids:
                is_new_selection = state.get("doctor_id") != doctor.id
                state["doctor_id"] = doctor.id
                state["doctor_name"] = doctor.full_name
                if is_new_selection:
                    days = self._get_doctor_available_days(db, doctor)
                    if not days:
                        return {
                            "response": (
                                f"{SmartDoctorRecommender.display_name(doctor.full_name)} does not have any available clinic hours "
                                "configured right now. Please choose another doctor."
                            ),
                            "session_id": session_id,
                        }
                    return {
                        "response": (
                            f"{SmartDoctorRecommender.display_name(doctor.full_name)} is available on:\n"
                            f"{self._format_doctor_available_days(db, doctor)}\n\n"
                            "Which day works best for you?"
                        ),
                        "session_id": session_id,
                        "suggestions": days,
                    }
            elif doctor and not state.get("doctor_id") and recommended_ids:
                # Named a doctor that isn't in the recommended list → keep the list
                return self._reask_doctor_selection(db, session_id, state, doctor)
            elif doctor and not state.get("doctor_id"):
                return {
                    "response": (
                        f"Tell me about your symptoms and I'll suggest the best "
                        f"doctor for you. What health concerns are you experiencing?"
                    ),
                    "session_id": session_id,
                }

        if not state.get("doctor_id"):
            if state.get("recommended_doctors"):
                return self._reask_doctor_selection(db, session_id, state, None)
            return {
                "response": "Please select a doctor from the list I suggested. Just tell me the doctor's name.",
                "session_id": session_id,
            }

        # --- DAY SELECTION via choice buttons ---
        if not state.get("appointment_day"):
            day = self._match_day_name(user_message)
            if day:
                state["appointment_day"] = day
                appt_date = self._next_weekday(day)
                state["appointment_date"] = appt_date
                slots = self._get_available_time_slots(db, state["doctor_id"], day, appt_date)
                if not slots:
                    state.pop("appointment_day", None)
                    state.pop("appointment_date", None)
                    doctor = self.doctor_repository.get_by_id(db, state["doctor_id"])
                    doc_name = doctor.full_name if doctor else ""
                    days = self._get_doctor_available_days(db, doctor) if doctor else []
                    return {
                        "response": f"Sorry, no slots are available on {day}. Please choose another day.",
                        "session_id": session_id,
                        "suggestions": days,
                    }
                return {
                    "response": (
                        f"Available slots on {day}, {appt_date.strftime('%B %d, %Y')}:\n"
                        "Please select a time."
                    ),
                    "session_id": session_id,
                    "suggestions": slots,
                }
            doctor = self.doctor_repository.get_by_id(db, state["doctor_id"])
            doc_name = doctor.full_name if doctor else state.get("doctor_name", "")
            days = self._get_doctor_available_days(db, doctor) if doctor else []
            return {
                "response": (
                    f"{SmartDoctorRecommender.display_name(doc_name)} is available on:\n"
                    f"{self._format_doctor_available_days(db, doctor) if doctor else ''}\n\n"
                    "Which day works best for you?"
                ),
                "session_id": session_id,
                "suggestions": days,
            }

        # --- TIME SELECTION via choice buttons ---
        if not state.get("appointment_time"):
            extracted_time = AppointmentExtractor.extract(user_message).get("appointment_time")
            if extracted_time:
                state["appointment_time"] = extracted_time
            else:
                slots = self._get_available_time_slots(
                    db, state["doctor_id"], state["appointment_day"], state["appointment_date"]
                )
                if not slots:
                    return {
                        "response": "No slots are available on that day. Would you like to choose another day?",
                        "session_id": session_id,
                    }
                return {
                    "response": f"Available slots on {state['appointment_day']}:\nPlease select a time.",
                    "session_id": session_id,
                    "suggestions": slots,
                }

        try:
            from datetime import date, time, datetime as dt
            appt_date = state["appointment_date"]
            appt_time = state["appointment_time"]
            if isinstance(appt_date, str):
                appt_date_obj = dt.strptime(appt_date, "%Y-%m-%d").date()
            else:
                appt_date_obj = appt_date
            if isinstance(appt_time, str):
                appt_time_obj = dt.strptime(appt_time.replace(".", "").strip(), "%H:%M").time()
            else:
                appt_time_obj = appt_time

            now = dt.now()
            from app.core.timezone import now as clinic_now
            now = clinic_now()
            if appt_date_obj == now.date() and appt_time_obj < now.time():
                state.pop("appointment_time", None)
                return {
                    "response": "That time has already passed today. Please choose a future time.",
                    "session_id": session_id,
                }

            if self.doctor_schedule_repository:
                day_name = appt_date_obj.strftime("%A")
                schedule = self.doctor_schedule_repository.get_schedule(
                    db, state["doctor_id"], day_name
                )
                doctor = self.doctor_repository.get_by_id(db, state["doctor_id"])
                doc_name = doctor.full_name if doctor else state.get("doctor_name", "")

                if appt_time_obj < schedule.start_time or appt_time_obj >= schedule.end_time:
                    state.pop("appointment_time", None)
                    return {
                        "response": (
                            f"{SmartDoctorRecommender.display_name(doc_name)} is available only between "
                            f"{schedule.start_time.strftime('%I:%M %p')} and "
                            f"{schedule.end_time.strftime('%I:%M %p')} on {day_name}. "
                            f"Please choose a time within these hours."
                        ),
                        "session_id": session_id,
                    }

                minutes = appt_time_obj.hour * 60 + appt_time_obj.minute
                start_minutes = schedule.start_time.hour * 60 + schedule.start_time.minute
                if (minutes - start_minutes) % schedule.slot_duration != 0:
                    state.pop("appointment_time", None)
                    return {
                        "response": (
                            f"Appointments with {SmartDoctorRecommender.display_name(doc_name)} must be booked every "
                            f"{schedule.slot_duration} minutes. Please choose a valid time."
                        ),
                        "session_id": session_id,
                    }

                existing = self.appointment_service.appointment_repository.slot_exists(
                    db, state["doctor_id"], appt_date_obj, appt_time_obj
                )
                if existing:
                    state.pop("appointment_time", None)
                    return {
                        "response": "That time slot is already booked. Please choose a different time.",
                        "session_id": session_id,
                    }

        except Exception:
            pass

        if not state.get("appointment_type"):
            return {
                "response": "Which type of consultation would you prefer?",
                "session_id": session_id,
                "suggestions": ["Physical Visit", "Video Consultation"],
            }

        if not state.get("confirmed"):
            return self._show_confirmation(db, session_id, state)

        if state.get("confirmed") and any(w in text.split() for w in ("yes", "y", "confirm", "sure", "ok", "okay", "yeah")):
            return self._finalize_booking(db, session_id, state)
        elif state.get("confirmed"):
            state["confirmed"] = False
            return {
                "response": "What would you like to change?",
                "session_id": session_id,
                "suggestions": ["Doctor", "Date", "Time", "Type"],
            }

        return self._finalize_booking(db, session_id, state)

    @staticmethod
    def _match_any(text: str, words: set) -> bool:
        return any(w in text for w in words)

    def _finalize_booking(self, db: Session, session_id: str, state: dict):
        from datetime import datetime as dt

        authenticated_patient_id = state.get("authenticated_patient_id")
        if authenticated_patient_id is not None:
            patient = self.patient_service.patient_repository.get_by_id(
                db, authenticated_patient_id,
            )
            if not patient:
                return {
                    "response": "Your patient profile could not be found. Please sign in again and try once more.",
                    "session_id": session_id,
                }
        else:
            patient = self.patient_service.find_or_create_patient(
                db=db,
                name=state["patient_name"],
                phone=state["phone"],
                email=state.get("email"),
            )

        state["patient_id"] = patient.id

        from app.common.enums import AppointmentType

        raw_type = state.get("appointment_type")
        if isinstance(raw_type, str) and "video" in raw_type.lower():
            appt_type = AppointmentType.VIDEO
        else:
            appt_type = AppointmentType.PHYSICAL

        reason_text = state.get("reason") or "Consultation"

        appt_date = state["appointment_date"]
        appt_time = state["appointment_time"]
        if isinstance(appt_date, str):
            appt_date = dt.strptime(appt_date, "%Y-%m-%d").date()
        if isinstance(appt_time, str):
            appt_time = dt.strptime(appt_time.replace(".", "").strip(), "%H:%M").time()

        appointment = AppointmentCreate(
            patient_id=patient.id,
            doctor_id=state["doctor_id"],
            appointment_date=appt_date,
            appointment_time=appt_time,
            appointment_type=appt_type,
            reason=reason_text,
            notes="Booked via AI Assistant",
        )

        try:
            result = self.appointment_service.book_appointment(db=db, appointment=appointment)
            booked = result.data

            doctor = self.doctor_repository.get_by_id(db, state["doctor_id"])

            confirmation = f"\u2705 **Appointment Confirmed!**\n\n"
            confirmation += f"\U0001f4cb Booking ID: #{booked.id}\n"
            confirmation += f"\U0001f464 Patient: {state['patient_name']}\n"
            confirmation += f"\U0001f468\u200d\u2695\ufe0f Doctor: {SmartDoctorRecommender.display_name(doctor.full_name)} ({doctor.specialization})\n"
            confirmation += f"\U0001f4c5 Date: {state['appointment_date']}\n"
            confirmation += f"\u23f0 Time: {state['appointment_time']}\n"
            confirmation += f"\U0001f4bc Type: {appt_type.value.title()} Consultation\n"
            if doctor.consultation_fee:
                confirmation += f"\U0001f4b0 Fee: Rs. {doctor.consultation_fee}\n\n"
            else:
                confirmation += "\n"
            confirmation += "You'll receive a notification before your appointment."

            if self.emr_service:
                SessionState.clear(session_id)
                post_state = SessionState.get(session_id)
                post_state["flow"] = "post_booking_upload"
                post_state["step"] = "ask_consent"
                post_state["post_booking_patient_id"] = patient.id
                post_state["post_booking_appointment_id"] = booked.id
                post_state["doctor_name"] = doctor.full_name

                confirmation += (
                    f"\n\nWould you like to upload any medical reports to share "
                    f"with {SmartDoctorRecommender.display_name(doctor.full_name)} before your appointment?"
                )

                return {"response": confirmation, "session_id": session_id, "suggestions": ["Yes", "No"]}

            SessionState.clear(session_id)
            return {"response": confirmation, "session_id": session_id}

        except Exception as e:
            reason = str(e).lower()
            if "past" in reason or "already" in reason:
                hint = "The selected date or time has passed or is unavailable. Please choose a different date/time."
            elif "schedule" in reason or "not available" in reason:
                hint = "The doctor is not available at that time. Please check their schedule and try a different slot."
            elif "already booked" in reason or "conflict" in reason:
                hint = "That time slot is already booked. Please choose a different time."
            else:
                hint = "There was an error booking your appointment. Please try again or contact us directly."
            state.pop("confirmed", None)
            return {
                "response": f"I'm sorry, {hint}",
                "session_id": session_id,
            }

    def _handle_view_appointments(self, db: Session, session_id: str, state: dict):
        patient_id = state["authenticated_patient_id"]
        appointments = self.appointment_service.get_my_appointments(db, patient_id).data

        if not appointments:
            return {
                "response": "You don't have any appointments booked yet. Would you like to book one?",
                "session_id": session_id,
                "suggestions": ["Book Appointment", "View Departments", "See Available Doctors"],
            }

        lines = ["Here are your appointments:\n"]
        for a in sorted(appointments, key=lambda x: (x.appointment_date, x.appointment_time)):
            doctor = self.doctor_repository.get_by_id(db, a.doctor_id)
            doctor_name = f"{SmartDoctorRecommender.display_name(doctor.full_name)}" if doctor else "Unknown doctor"
            lines.append(
                f"\u2022 #{a.id} \u2014 {doctor_name} on {a.appointment_date} at {a.appointment_time} "
                f"({a.status.value if hasattr(a.status, 'value') else a.status})"
            )

        return {"response": "\n".join(lines), "session_id": session_id}

    def _handle_cancel_flow(self, db: Session, session_id: str, user_message: str, state: dict):
        from app.common.enums import AppointmentStatus

        patient_id = state["authenticated_patient_id"]
        text = (user_message or "").strip().lower()

        if self._match_any(text, self.ABORT_WORDS):
            SessionState.clear(session_id)
            return {
                "response": "No problem! Your appointments are unchanged.",
                "session_id": session_id,
            }

        if state.get("flow") == "cancel_appointment":
            step = state.get("step")

            if step == "confirm":
                appointment_id = state.get("pending_cancel_id")
                if any(w in text.split() for w in ("yes", "y", "confirm", "sure", "ok", "okay")):
                    try:
                        self.appointment_service.cancel_appointment(db, appointment_id, patient_id)
                        SessionState.clear(session_id)
                        return {
                            "response": f"\u2705 Your appointment #{appointment_id} has been cancelled.",
                            "session_id": session_id,
                        }
                    except Exception as e:
                        SessionState.clear(session_id)
                        return {
                            "response": f"I couldn't cancel that appointment: {str(e)}",
                            "session_id": session_id,
                        }
                else:
                    SessionState.clear(session_id)
                    return {
                        "response": "No problem, I've left your appointment as it is.",
                        "session_id": session_id,
                    }

            if step == "choose":
                digits = "".join(ch for ch in user_message if ch.isdigit()) if user_message else ""
                candidates = state.get("cancellable_ids", [])
                if digits and int(digits) in candidates:
                    appointment_id = int(digits)
                    state["step"] = "confirm"
                    state["pending_cancel_id"] = appointment_id
                    return {
                        "response": f"Just to confirm \u2014 cancel appointment #{appointment_id}? (yes/no)",
                        "session_id": session_id,
                        "suggestions": ["Yes", "No"],
                    }
                return {
                    "response": (
                        "I didn't recognize that appointment ID. Please reply with the "
                        f"ID of the appointment you'd like to cancel ({', '.join('#' + str(c) for c in candidates)})."
                    ),
                    "session_id": session_id,
                }

        appointments = self.appointment_service.get_my_appointments(db, patient_id).data
        cancellable = [a for a in appointments if a.status == AppointmentStatus.SCHEDULED]

        if not cancellable:
            return {
                "response": "You don't have any upcoming appointments that can be cancelled.",
                "session_id": session_id,
            }

        if len(cancellable) == 1:
            appointment_id = cancellable[0].id
            state["flow"] = "cancel_appointment"
            state["step"] = "confirm"
            state["pending_cancel_id"] = appointment_id
            return {
                "response": f"Just to confirm \u2014 cancel appointment #{appointment_id}? (yes/no)",
                "session_id": session_id,
                "suggestions": ["Yes", "No"],
            }

        state["flow"] = "cancel_appointment"
        state["step"] = "choose"
        state["cancellable_ids"] = [a.id for a in cancellable]

        lines = ["Which appointment would you like to cancel?\n"]
        for a in cancellable:
            doctor = self.doctor_repository.get_by_id(db, a.doctor_id)
            doctor_name = f"{SmartDoctorRecommender.display_name(doctor.full_name)}" if doctor else "Unknown doctor"
            lines.append(f"\u2022 #{a.id} \u2014 {doctor_name} on {a.appointment_date} at {a.appointment_time}")
        lines.append('\nReply with the appointment ID (e.g. "12").')

        return {"response": "\n".join(lines), "session_id": session_id}

    def _handle_post_booking_upload(
        self, db: Session, session_id: str, user_message: str, file, state: dict,
    ):
        step = state.get("step")
        text = (user_message or "").strip()
        lowered = text.lower()
        doctor_name = state.get("doctor_name", "your doctor")

        if step == "ask_consent":
            negative_words = ("no", "nah", "nope", "skip", "not now", "later", "no thanks")
            affirmative_words = ("yes", "yeah", "yep", "yup", "sure", "ok", "okay", "please")

            if any(word in lowered for word in negative_words):
                SessionState.clear(session_id)
                return {
                    "response": (
                        f"No problem! {SmartDoctorRecommender.display_name(doctor_name)} will see you at your scheduled time. "
                        "Is there anything else I can help you with?"
                    ),
                    "session_id": session_id,
                    "suggestions": ["Book Appointment", "View Departments", "See Available Doctors"],
                }

            if any(word in lowered for word in affirmative_words):
                state["step"] = "await_file"
                return {
                    "response": (
                        "Great \u2014 use the attach button that just appeared to upload "
                        "the report or document you'd like to share."
                    ),
                    "session_id": session_id,
                    "awaiting_upload": True,
                }

            return {
                "response": (
                    f"Just to confirm \u2014 would you like to upload a medical record or report "
                    f"to share with {SmartDoctorRecommender.display_name(doctor_name)}? (yes/no)"
                ),
                "session_id": session_id,
                "suggestions": ["Yes", "No"],
            }

        if step == "await_file":
            if file is None:
                if lowered in ("skip", "cancel", "no", "never mind", "nevermind"):
                    SessionState.clear(session_id)
                    return {
                        "response": "No problem, we'll skip the upload. Anything else I can help with?",
                        "session_id": session_id,
                    }
                return {
                    "response": "Whenever you're ready, use the attach button to upload your report \u2014 or type 'skip' if you'd rather not.",
                    "session_id": session_id,
                    "awaiting_upload": True,
                }

            import os, uuid, shutil
            upload_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploads", "reports",
            )
            os.makedirs(upload_dir, exist_ok=True)
            file_ext = os.path.splitext(file.filename)[1]
            unique_name = f"{uuid.uuid4().hex}{file_ext}"
            file_path = os.path.join(upload_dir, unique_name)
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)

            state["upload_file_path"] = f"uploads/reports/{unique_name}"
            state["step"] = "await_report_type"
            return {
                "response": "Thanks! What type of document is this?",
                "session_id": session_id,
                "suggestions": ["Blood Test", "MRI", "CT Scan", "X-Ray", "ECG", "Ultrasound", "Other"],
            }

        if step == "await_report_type":
            report_type = self._match_report_type(lowered)
            patient_id = state.get("post_booking_patient_id")
            appointment_id = state.get("post_booking_appointment_id")

            try:
                report_name = report_type.value.replace("_", " ").title() if hasattr(report_type, "value") else str(report_type)
                self.emr_service.create_report_from_saved_file(
                    db=db,
                    patient_id=patient_id,
                    report_name=report_name,
                    report_type=report_type,
                    file_path=state.get("upload_file_path"),
                    appointment_id=appointment_id,
                )
                response = (
                    f"**Done!** \u2705 Your report has been shared with {SmartDoctorRecommender.display_name(doctor_name)} and saved to your "
                    "**Medical Records**. Is there anything else I can help with?"
                )
            except Exception as e:
                response = (
                    f"I'm sorry, I couldn't save that report ({str(e)}). You can also upload it "
                    "directly from Medical Records in your portal."
                )

            SessionState.clear(session_id)
            return {
                "response": response,
                "session_id": session_id,
                "suggestions": ["Book Appointment", "View Departments", "See Available Doctors"],
            }

        SessionState.clear(session_id)
        return {"response": "Let's continue \u2014 how can I help you today?", "session_id": session_id}

    def _match_report_type(self, text: str) -> str:
        from app.common.enums import ReportType

        text = (text or "").lower()
        mapping = [
            (("blood",), ReportType.BLOOD_TEST),
            (("mri",), ReportType.MRI),
            (("ct scan", "ct-scan", " ct "), ReportType.CT_SCAN),
            (("x-ray", "xray", "x ray"), ReportType.XRAY),
            (("ecg", "ekg"), ReportType.ECG),
            (("ultrasound", "sonogram"), ReportType.ULTRASOUND),
        ]
        for keywords, value in mapping:
            if any(keyword in text for keyword in keywords):
                return value.value
        return ReportType.OTHER.value

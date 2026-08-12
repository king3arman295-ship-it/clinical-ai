from sqlalchemy.orm import Session

from app.ai.llm import LLM
from app.ai.memory import ConversationMemory
from app.ai.prompt import PromptManager
from app.ai.intent_detector import IntentDetector
from app.ai.extractor import AppointmentExtractor
from app.ai.doctor_extractor import DoctorExtractor
from app.ai.patient_extractor import PatientExtractor
from app.ai.session_state import SessionState
from app.ai.language_guard import LanguageGuard

from app.schemas.appointment import AppointmentCreate
from app.schemas.patient import PatientCreate

from app.services.appointment_service import AppointmentService
from app.services.patient_service import PatientService


class AIAgent:
    """
    AI Receptionist Agent.
    """

    def __init__(
        self,
        appointment_service: AppointmentService,
        patient_service: PatientService,
        doctor_repository,
        emr_service=None,
    ):
        self.llm = LLM()
        self.memory = ConversationMemory()

        self.appointment_service = appointment_service
        self.patient_service = patient_service
        self.doctor_repository = doctor_repository
        self.emr_service = emr_service

    def chat(
        self,
        db: Session,
        session_id: str,
        user_message: str,
        file=None,
    ):

        # ---------------------------------
        # Restore Existing Conversation
        # ---------------------------------
        state = SessionState.get(session_id)

        # Process file attachment if present
        is_auto_message = False
        if file is not None:
            import os, uuid, shutil
            upload_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploads", "reports")
            os.makedirs(upload_dir, exist_ok=True)
            file_ext = os.path.splitext(file.filename)[1]
            unique_name = f"{uuid.uuid4().hex}{file_ext}"
            file_path = os.path.join(upload_dir, unique_name)
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            
            relative_path = f"uploads/reports/{unique_name}"
            pending_files = state.get("pending_files", [])
            pending_files.append({
                "filename": file.filename,
                "file_path": relative_path,
            })
            state["pending_files"] = pending_files
            if not user_message or not user_message.strip():
                user_message = f"Uploaded document: {file.filename}"
                is_auto_message = True

        if not is_auto_message:
            if LanguageGuard.is_non_english(user_message):
                return {
                    "response": LanguageGuard.ask_for_english_message(),
                    "session_id": session_id,
                }
            if LanguageGuard.is_out_of_scope(user_message):
                return {
                    "response": LanguageGuard.out_of_scope_message(),
                    "session_id": session_id,
                }

        if state.get("intent"):
            intent = state["intent"]
        else:
            intent = IntentDetector.detect(user_message)

        # =================================
        # BOOK APPOINTMENT
        # =================================
        if intent == "book_appointment":

            state["intent"] = "book_appointment"

            # ---------------------------------
            # Extract Patient Information
            # ---------------------------------
            patient_data = PatientExtractor.extract(
                user_message,
            )

            for key, value in patient_data.items():
                if value is not None:
                    state[key] = value

            # ---------------------------------
            # Ask Patient Name
            # ---------------------------------
            if not state.get("patient_name"):

                return {
                    "response": "May I have your full name?",
                    "session_id": session_id,
                }

            # ---------------------------------
            # Ask Phone Number
            # ---------------------------------
            if not state.get("phone"):

                return {
                    "response": (
                        f"Thank you {state['patient_name']}.\n\n"
                        "May I have your phone number?"
                    ),
                    "session_id": session_id,
                }

            # ---------------------------------
            # Extract Appointment & EMR Information
            # ---------------------------------
            extracted = AppointmentExtractor.extract(
                user_message,
            )

            for key, value in extracted.items():
                if value is not None:
                    state[key] = value

            # ---------------------------------
            # Ask Consultation Type (Physical vs Video)
            # ---------------------------------
            if not state.get("appointment_type"):
                return {
                    "response": (
                        f"Thanks {state['patient_name']}.\n\n"
                        "Would you prefer a **🏥 Physical Clinic Visit** or a **📹 Video Consultation**?"
                    ),
                    "session_id": session_id,
                }

            # ---------------------------------
            # Extract Doctor Name
            # ---------------------------------
            doctor_name = DoctorExtractor.extract(
                user_message,
            )

            if doctor_name:

                doctor = self.doctor_repository.get_by_name(
                    db,
                    doctor_name,
                )

                if doctor:
                    state["doctor_id"] = doctor.id
                    state["doctor_name"] = doctor.full_name

            data = state

            # ---------------------------------
            # Check Missing Information
            # ---------------------------------
            missing = []

            if data.get("doctor_id") is None:
                missing.append("Doctor Name")

            if data.get("appointment_date") is None:
                missing.append("Appointment Date")

            if data.get("appointment_time") is None:
                missing.append("Appointment Time")

            if missing:

                return {
                    "response": (
                        "I still need the following information:\n\n"
                        + "\n".join(
                            f"- {item}"
                            for item in missing
                        )
                    ),
                    "session_id": session_id,
                }

            # ---------------------------------
            # Find or Create Patient
            # ---------------------------------
            patient = self.patient_service.find_or_create_patient(
                db=db,
                name=data["patient_name"],
                phone=data["phone"],
                email=data.get("email"),
            )

            state["patient_id"] = patient.id

            # ---------------------------------
            # Create Appointment Schema
            # ---------------------------------
            from app.common.enums import AppointmentType

            raw_type = data.get("appointment_type")
            if isinstance(raw_type, str) and raw_type.lower() == "video":
                appt_type = AppointmentType.VIDEO
            elif getattr(raw_type, "value", str(raw_type)) == "video":
                appt_type = AppointmentType.VIDEO
            else:
                appt_type = AppointmentType.PHYSICAL

            reason_text = data.get("reason") or "Booked via AI Receptionist"

            appointment = AppointmentCreate(
                patient_id=patient.id,
                doctor_id=data["doctor_id"],
                appointment_date=data["appointment_date"],
                appointment_time=data["appointment_time"],
                appointment_type=appt_type,
                reason=reason_text,
                notes="AI Receptionist intake",
            )

            # ---------------------------------
            # Book Appointment
            # ---------------------------------
            try:

                result = self.appointment_service.book_appointment(
                    db=db,
                    appointment=appointment,
                )

                booked = result.data

                # Create EMR Records (Conditions, Allergies & Attached Files)
                emr_summary = []
                if self.emr_service:
                    from app.schemas.emr import MedicalHistoryCreate, PatientAllergyCreate
                    
                    if data.get("conditions"):
                        cond_list = [c.strip() for c in str(data["conditions"]).split(",") if c.strip()]
                        for cond in cond_list:
                            try:
                                self.emr_service.add_medical_history(
                                    db=db,
                                    data=MedicalHistoryCreate(
                                        patient_id=patient.id,
                                        condition=cond,
                                        notes="Recorded via AI Assistant during booking",
                                    )
                                )
                                emr_summary.append(f"Condition: {cond}")
                            except Exception:
                                pass

                    if data.get("allergies"):
                        alg_list = [a.strip() for a in str(data["allergies"]).split(",") if a.strip()]
                        for alg in alg_list:
                            try:
                                self.emr_service.add_allergy(
                                    db=db,
                                    data=PatientAllergyCreate(
                                        patient_id=patient.id,
                                        allergy_name=alg,
                                        notes="Recorded via AI Assistant during booking",
                                    )
                                )
                                emr_summary.append(f"Allergy: {alg}")
                            except Exception:
                                pass

                    if data.get("pending_files"):
                        for pf in data["pending_files"]:
                            try:
                                from app.models.patient_report import PatientReport
                                from app.core.unit_of_work import UnitOfWork
                                pr = PatientReport(
                                    patient_id=patient.id,
                                    appointment_id=booked.id,
                                    report_name=pf["filename"],
                                    report_type="other",
                                    file_path=pf["file_path"],
                                )
                                with UnitOfWork(db):
                                    db.add(pr)
                                emr_summary.append(f"Report Attached: {pf['filename']}")
                            except Exception:
                                pass

                SessionState.clear(session_id)

                type_label = "📹 Video Consultation" if appt_type == AppointmentType.VIDEO else "🏥 Physical Clinic Visit"
                extra_note = "\n🔔 *You and your doctor will receive a browser notification 5 minutes before the session starts!*" if appt_type == AppointmentType.VIDEO else ""

                emr_str = f"\n• Recorded EMR: {', '.join(emr_summary)}" if emr_summary else ""

                return {
                    "response": (
                        f"✅ Appointment booked successfully!\n\n"
                        f"• Appointment ID: #{booked.id}\n"
                        f"• Patient: {patient.name}\n"
                        f"• Doctor: {data['doctor_name']}\n"
                        f"• Date: {booked.appointment_date}\n"
                        f"• Time: {booked.appointment_time.strftime('%H:%M')}\n"
                        f"• Type: {type_label}\n"
                        f"• Reason/Symptoms: {reason_text}"
                        f"{emr_str}\n\n"
                        f"📁 *Medical Reports*: If you have any previous blood reports, MRIs, or X-Rays, you can upload them to your EMR history or attach them to Appointment #{booked.id}!"
                        f"{extra_note}"
                    ),
                    "session_id": session_id,
                }

            except Exception as e:

                return {
                    "response": str(e),
                    "session_id": session_id,
                }

        # =================================
        # CANCEL APPOINTMENT
        # =================================
        elif intent == "cancel_appointment":

            return {
                "response": (
                    "Appointment cancellation will be implemented next."
                ),
                "session_id": session_id,
            }

        # =================================
        # VIEW APPOINTMENTS
        # =================================
        elif intent == "view_appointments":

            return {
                "response": (
                    "Viewing appointments will be implemented next."
                ),
                "session_id": session_id,
            }

        # Continue in Part 3...
                # =================================
        # NORMAL CHAT
        # =================================

        messages = [
            {
                "role": "system",
                "content": PromptManager.system_prompt(),
            }
        ]

        messages.extend(
            self.memory.get_messages(session_id)
        )

        messages.append(
            {
                "role": "user",
                "content": user_message,
            }
        )

        self.memory.add_message(
            session_id,
            "user",
            user_message,
        )

        response = self.llm.chat(
            messages=messages,
        )

        ai_message = response["content"]

        self.memory.add_message(
            session_id,
            "assistant",
            ai_message,
        )

        return {
            "response": ai_message,
            "session_id": session_id,
        }

    # =================================
    # CLEAR MEMORY
    # =================================

    def clear_memory(
        self,
        session_id: str,
    ):
        """
        Clear conversation state and memory.
        """

        SessionState.clear(session_id)
        self.memory.clear(session_id)
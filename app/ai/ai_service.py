from sqlalchemy.orm import Session

# Try to use enhanced agent, fallback to original if not available
try:
    from app.ai.enhanced_agent import EnhancedAIAgent
    USE_ENHANCED = True
except ImportError:
    from app.ai.agent import AIAgent
    USE_ENHANCED = False

from app.services.appointment_service import AppointmentService
from app.services.patient_service import PatientService

from app.repositories.patient_repository import PatientRepository
from app.repositories.doctor_repository import DoctorRepository
from app.repositories.doctor_schedule_repository import DoctorScheduleRepository
from app.repositories.appointment_repository import AppointmentRepository

from app.common.service_result import ServiceResult


class AIService:
    """
    AI Service

    Acts as the bridge between the API layer
    and the AI Agent.
    """

    def __init__(self):

        # -----------------------------------
        # Repositories
        # -----------------------------------

        self.patient_repository = PatientRepository()

        self.doctor_repository = DoctorRepository()

        self.doctor_schedule_repository = DoctorScheduleRepository()

        self.appointment_repository = AppointmentRepository()

        # -----------------------------------
        # Services
        # -----------------------------------

        self.patient_service = PatientService(
            patient_repository=self.patient_repository,
        )

        self.appointment_service = AppointmentService(
            patient_repository=self.patient_repository,
            doctor_repository=self.doctor_repository,
            doctor_schedule_repository=self.doctor_schedule_repository,
            appointment_repository=self.appointment_repository,
        )

        from app.dependencies.services import get_emr_service
        self.emr_service = get_emr_service()

        # -----------------------------------
        # AI Agent (Enhanced with Smart Recommendations)
        # -----------------------------------

        if USE_ENHANCED:
            self.agent = EnhancedAIAgent(
                appointment_service=self.appointment_service,
                patient_service=self.patient_service,
                doctor_repository=self.doctor_repository,
                doctor_schedule_repository=self.doctor_schedule_repository,
                emr_service=self.emr_service,
            )
        else:
            from app.ai.agent import AIAgent
            self.agent = AIAgent(
                appointment_service=self.appointment_service,
                patient_service=self.patient_service,
                doctor_repository=self.doctor_repository,
                emr_service=self.emr_service,
            )

    # -----------------------------------
    # Chat
    # -----------------------------------

    def upload_patient_document(
        self,
        db: Session,
        patient_id: int,
        file,
    ) -> ServiceResult:
        """Save an authenticated patient's AI attachment directly to their EMR."""
        filename = file.filename or "Uploaded medical document"
        self.emr_service.upload_report(
            db=db,
            patient_id=patient_id,
            report_name=filename,
            report_type="other",
            file=file,
        )
        return ServiceResult.Success(
            "Medical document uploaded successfully.",
            {
                "message": (
                    f"Your document '{filename}' has been added to your medical record. "
                    "You can view it in Medical Records."
                )
            },
        )

    def chat(
        self,
        db: Session,
        session_id: str,
        message: str,
        file=None,
        patient_id: int | None = None,
    ) -> ServiceResult:

        authenticated_patient = None
        if patient_id is not None:
            authenticated_patient = self.patient_repository.get_by_id(db, patient_id)

        # Attachments are handled entirely by the agent's own conversation
        # state now: the assistant only asks for a file once an appointment
        # has just been booked (see
        # EnhancedAIAgent._handle_post_booking_upload), at which point it
        # already knows which patient/doctor/appointment to link the report
        # to and collects the report name + type before saving it. So the
        # file is simply passed straight through to the agent here.
        chat_args = {
            "db": db,
            "session_id": session_id,
            "user_message": message,
            "file": file,
        }
        if USE_ENHANCED:
            chat_args["authenticated_patient"] = authenticated_patient

        result = self.agent.chat(
            **chat_args,
        )

        return ServiceResult.Success(
            "AI response generated successfully.",
            result,
        )

    # -----------------------------------
    # Clear Conversation
    # -----------------------------------

    def clear_conversation(
        self,
        session_id: str,
    ) -> ServiceResult:

        self.agent.clear_memory(session_id)

        return ServiceResult.Success(
            "Conversation cleared successfully.",
            None,
        )

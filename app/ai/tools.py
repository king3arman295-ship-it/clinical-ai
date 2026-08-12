from sqlalchemy.orm import Session

from app.services.appointment_service import AppointmentService
from app.services.doctor_service import DoctorService
from app.services.patient_service import PatientService
from app.services.dashboard_service import DashboardService


class ClinicTools:
    """
    Tools available to the AI Receptionist.

    Every tool should call an existing Service.
    The AI never accesses the database directly.
    """

    def __init__(
        self,
        db: Session,
        appointment_service: AppointmentService,
        doctor_service: DoctorService,
        patient_service: PatientService,
        dashboard_service: DashboardService,
    ):
        self.db = db
        self.appointment_service = appointment_service
        self.doctor_service = doctor_service
        self.patient_service = patient_service
        self.dashboard_service = dashboard_service

    # ----------------------------------------------------
    # Appointment Tools
    # ----------------------------------------------------

    def book_appointment(self, **kwargs):
        """
        Book a new appointment.
        """
        raise NotImplementedError()

    def update_appointment(self, **kwargs):
        """
        Reschedule an appointment.
        """
        raise NotImplementedError()

    def cancel_appointment(self, **kwargs):
        """
        Cancel an appointment.
        """
        raise NotImplementedError()

    def get_appointments(self):
        """
        List appointments.
        """
        raise NotImplementedError()

    # ----------------------------------------------------
    # Doctor Tools
    # ----------------------------------------------------

    def get_doctors(self):
        """
        List all doctors.
        """
        raise NotImplementedError()

    def get_available_doctors(self):
        """
        List available doctors.
        """
        raise NotImplementedError()

    # ----------------------------------------------------
    # Patient Tools
    # ----------------------------------------------------

    def get_patients(self):
        """
        List all patients.
        """
        raise NotImplementedError()

    # ----------------------------------------------------
    # Dashboard Tools
    # ----------------------------------------------------

    def dashboard_summary(self):
        """
        Return dashboard statistics.
        """
        raise NotImplementedError()
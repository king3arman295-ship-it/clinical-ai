from sqlalchemy.orm import Session

from sqlalchemy import or_

from app.repositories.base_repository import BaseRepository

from app.models.medical_history import MedicalHistory
from app.models.patient_report import PatientReport
from app.models.prescription import Prescription
from app.models.prescription_item import PrescriptionItem
from app.models.doctor_note import DoctorNote
from app.models.patient_vital import PatientVital
from app.models.patient_allergy import PatientAllergy
from app.models.diagnosis import Diagnosis
from app.models.appointment import Appointment


# ═════════════════════════════════════════════════════════════
# Medical History Repository
# ═════════════════════════════════════════════════════════════

class MedicalHistoryRepository(BaseRepository[MedicalHistory]):

    def __init__(self):
        super().__init__(MedicalHistory)

    def get_by_patient(
        self,
        db: Session,
        patient_id: int,
    ):
        return (
            db.query(MedicalHistory)
            .filter(
                MedicalHistory.patient_id == patient_id
            )
            .order_by(MedicalHistory.created_at.desc())
            .all()
        )


# ═════════════════════════════════════════════════════════════
# Patient Report Repository
# ═════════════════════════════════════════════════════════════

class PatientReportRepository(BaseRepository[PatientReport]):

    def __init__(self):
        super().__init__(PatientReport)

    def get_by_patient(
        self,
        db: Session,
        patient_id: int,
    ):
        return (
            db.query(PatientReport)
            .filter(
                PatientReport.patient_id == patient_id
            )
            .order_by(PatientReport.uploaded_at.desc())
            .all()
        )

    def get_by_appointment(
        self,
        db: Session,
        appointment_id: int,
    ):
        return (
            db.query(PatientReport)
            .filter(
                PatientReport.appointment_id == appointment_id
            )
            .order_by(PatientReport.uploaded_at.desc())
            .all()
        )

    def get_by_patient_for_doctor(
        self,
        db: Session,
        patient_id: int,
        doctor_id: int,
    ):
        """Return only reports shared with this doctor (directly or via an appointment)."""
        return (
            db.query(PatientReport)
            .outerjoin(Appointment, PatientReport.appointment_id == Appointment.id)
            .filter(
                PatientReport.patient_id == patient_id,
                or_(
                    PatientReport.doctor_id == doctor_id,
                    Appointment.doctor_id == doctor_id,
                ),
            )
            .order_by(PatientReport.uploaded_at.desc())
            .all()
        )


# ═════════════════════════════════════════════════════════════
# Prescription Repository
# ═════════════════════════════════════════════════════════════

class PrescriptionRepository(BaseRepository[Prescription]):

    def __init__(self):
        super().__init__(Prescription)

    def get_by_patient(
        self,
        db: Session,
        patient_id: int,
    ):
        return (
            db.query(Prescription)
            .filter(
                Prescription.patient_id == patient_id
            )
            .order_by(Prescription.created_at.desc())
            .all()
        )

    def get_by_patient_for_doctor(
        self,
        db: Session,
        patient_id: int,
        doctor_id: int,
    ):
        return (
            db.query(Prescription)
            .filter(
                Prescription.patient_id == patient_id,
                Prescription.doctor_id == doctor_id,
            )
            .order_by(Prescription.created_at.desc())
            .all()
        )

    def get_by_appointment(
        self,
        db: Session,
        appointment_id: int,
    ):
        return (
            db.query(Prescription)
            .filter(
                Prescription.appointment_id == appointment_id
            )
            .order_by(Prescription.created_at.desc())
            .all()
        )


# ═════════════════════════════════════════════════════════════
# Prescription Item Repository
# ═════════════════════════════════════════════════════════════

class PrescriptionItemRepository(BaseRepository[PrescriptionItem]):

    def __init__(self):
        super().__init__(PrescriptionItem)

    def get_by_prescription(
        self,
        db: Session,
        prescription_id: int,
    ):
        return (
            db.query(PrescriptionItem)
            .filter(
                PrescriptionItem.prescription_id == prescription_id
            )
            .all()
        )


# ═════════════════════════════════════════════════════════════
# Doctor Note Repository
# ═════════════════════════════════════════════════════════════

class DoctorNoteRepository(BaseRepository[DoctorNote]):

    def __init__(self):
        super().__init__(DoctorNote)

    def get_by_patient(
        self,
        db: Session,
        patient_id: int,
    ):
        return (
            db.query(DoctorNote)
            .filter(
                DoctorNote.patient_id == patient_id
            )
            .order_by(DoctorNote.created_at.desc())
            .all()
        )

    def get_by_patient_for_doctor(
        self,
        db: Session,
        patient_id: int,
        doctor_id: int,
    ):
        return (
            db.query(DoctorNote)
            .filter(
                DoctorNote.patient_id == patient_id,
                DoctorNote.doctor_id == doctor_id,
            )
            .order_by(DoctorNote.created_at.desc())
            .all()
        )

    def get_by_appointment(
        self,
        db: Session,
        appointment_id: int,
    ):
        return (
            db.query(DoctorNote)
            .filter(
                DoctorNote.appointment_id == appointment_id
            )
            .order_by(DoctorNote.created_at.desc())
            .all()
        )


# ═════════════════════════════════════════════════════════════
# Patient Vital Repository
# ═════════════════════════════════════════════════════════════

class PatientVitalRepository(BaseRepository[PatientVital]):

    def __init__(self):
        super().__init__(PatientVital)

    def get_by_patient(
        self,
        db: Session,
        patient_id: int,
    ):
        return (
            db.query(PatientVital)
            .filter(
                PatientVital.patient_id == patient_id
            )
            .order_by(PatientVital.recorded_at.desc())
            .all()
        )

    def get_by_patient_for_doctor(
        self,
        db: Session,
        patient_id: int,
        doctor_id: int,
    ):
        return (
            db.query(PatientVital)
            .join(Appointment, Appointment.id == PatientVital.appointment_id)
            .filter(
                PatientVital.patient_id == patient_id,
                Appointment.doctor_id == doctor_id,
            )
            .order_by(PatientVital.recorded_at.desc())
            .all()
        )

    def get_by_appointment(
        self,
        db: Session,
        appointment_id: int,
    ):
        return (
            db.query(PatientVital)
            .filter(
                PatientVital.appointment_id == appointment_id
            )
            .order_by(PatientVital.recorded_at.desc())
            .all()
        )


# ═════════════════════════════════════════════════════════════
# Patient Allergy Repository
# ═════════════════════════════════════════════════════════════

class PatientAllergyRepository(BaseRepository[PatientAllergy]):

    def __init__(self):
        super().__init__(PatientAllergy)

    def get_by_patient(
        self,
        db: Session,
        patient_id: int,
    ):
        return (
            db.query(PatientAllergy)
            .filter(
                PatientAllergy.patient_id == patient_id
            )
            .all()
        )


# ═════════════════════════════════════════════════════════════
# Diagnosis Repository
# ═════════════════════════════════════════════════════════════

class DiagnosisRepository(BaseRepository[Diagnosis]):

    def __init__(self):
        super().__init__(Diagnosis)

    def get_by_patient(
        self,
        db: Session,
        patient_id: int,
    ):
        return (
            db.query(Diagnosis)
            .filter(
                Diagnosis.patient_id == patient_id
            )
            .all()
        )

    def get_by_patient_for_doctor(
        self,
        db: Session,
        patient_id: int,
        doctor_id: int,
    ):
        return (
            db.query(Diagnosis)
            .join(Appointment, Appointment.id == Diagnosis.appointment_id)
            .filter(
                Diagnosis.patient_id == patient_id,
                Appointment.doctor_id == doctor_id,
            )
            .all()
        )

    def get_by_appointment(
        self,
        db: Session,
        appointment_id: int,
    ):
        return (
            db.query(Diagnosis)
            .filter(
                Diagnosis.appointment_id == appointment_id
            )
            .all()
        )

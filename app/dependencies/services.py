from app.auth.auth_service import AuthService

from app.services.patient_service import PatientService
from app.services.doctor_service import DoctorService
from app.services.appointment_service import AppointmentService
from app.services.dashboard_service import DashboardService
from app.services.emr_service import EMRService
from app.services.admission_service import AdmissionService
from app.services.pharmacy_service import PharmacyService
from app.services.laboratory_service import LaboratoryService
from app.services.nursing_service import NursingService

from app.repositories.dashboard_repository import DashboardRepository

from app.dependencies.repositories import (
    get_nurse_bed_assignment_repository,
    get_medication_course_repository,
    get_medication_course_item_repository,
    get_medication_course_dose_repository,
    get_user_repository,
    get_patient_repository,
    get_doctor_repository,
    get_doctor_schedule_repository,
    get_appointment_repository,
    get_medical_history_repository,
    get_patient_report_repository,
    get_prescription_repository,
    get_prescription_item_repository,
    get_doctor_note_repository,
    get_patient_vital_repository,
    get_patient_allergy_repository,
    get_diagnosis_repository,
    get_ward_repository,
    get_bed_repository,
    get_admission_repository,
    get_admission_note_repository,
    get_medicine_repository,
    get_pharmacy_order_repository,
    get_medication_administration_repository,
    get_lab_test_repository,
    get_lab_order_repository,
    get_lab_result_repository,
)
from app.integrations.agora_service import AgoraService


# -----------------------------------
# Auth Service
# -----------------------------------
def get_auth_service():

    return AuthService(
        user_repository=get_user_repository(),
    )

# -----------------------------------
# Agora Service
# -----------------------------------

def get_agora_service():

    return AgoraService()
# -----------------------------------
# Patient Service
# -----------------------------------
def get_patient_service():

    return PatientService(
        patient_repository=get_patient_repository(),
    )


# -----------------------------------
# Doctor Service
# -----------------------------------
def get_doctor_service():

    return DoctorService(
        doctor_repository=get_doctor_repository(),
        user_repository=get_user_repository(),
    )


# -----------------------------------
# Appointment Service
# -----------------------------------
def get_appointment_service():

    return AppointmentService(
        patient_repository=get_patient_repository(),
        doctor_repository=get_doctor_repository(),
        doctor_schedule_repository=get_doctor_schedule_repository(),
        appointment_repository=get_appointment_repository(),
    )


# -----------------------------------
# Dashboard Service
# -----------------------------------
def get_dashboard_service():

    return DashboardService(
        dashboard_repository=DashboardRepository(),
    )


# -----------------------------------
# Pharmacy Service
# -----------------------------------
def get_pharmacy_service():

    return PharmacyService(
        medicine_repository=get_medicine_repository(),
        pharmacy_order_repository=get_pharmacy_order_repository(),
        medication_administration_repository=get_medication_administration_repository(),
        patient_repository=get_patient_repository(),
        admission_repository=get_admission_repository(),
        user_repository=get_user_repository(),
    )


# -----------------------------------
# Admission Service
# -----------------------------------
def get_admission_service():

    return AdmissionService(
        patient_repository=get_patient_repository(),
        doctor_repository=get_doctor_repository(),
        ward_repository=get_ward_repository(),
        bed_repository=get_bed_repository(),
        admission_repository=get_admission_repository(),
        admission_note_repository=get_admission_note_repository(),
        user_repository=get_user_repository(),
    )


# -----------------------------------
# EMR Service
# -----------------------------------
def get_emr_service():

    return EMRService(
        patient_repository=get_patient_repository(),
        appointment_repository=get_appointment_repository(),
        medical_history_repository=get_medical_history_repository(),
        patient_report_repository=get_patient_report_repository(),
        prescription_repository=get_prescription_repository(),
        prescription_item_repository=get_prescription_item_repository(),
        doctor_note_repository=get_doctor_note_repository(),
        patient_vital_repository=get_patient_vital_repository(),
        patient_allergy_repository=get_patient_allergy_repository(),
        diagnosis_repository=get_diagnosis_repository(),
        doctor_repository=get_doctor_repository(),
        pharmacy_service=get_pharmacy_service(),
        laboratory_service=get_laboratory_service(),
        admission_repository=get_admission_repository(),
    )


# -----------------------------------
# Laboratory Service
# -----------------------------------
def get_laboratory_service():
    return LaboratoryService(
        lab_test_repository=get_lab_test_repository(),
        lab_order_repository=get_lab_order_repository(),
        lab_result_repository=get_lab_result_repository(),
        patient_repository=get_patient_repository(),
        doctor_repository=get_doctor_repository(),
        admission_repository=get_admission_repository(),
        user_repository=get_user_repository(),
        notification_service=None,
        patient_report_repository=get_patient_report_repository(),
    )


def get_nursing_service():
    return NursingService(
        assignment_repo=get_nurse_bed_assignment_repository(),
        course_repo=get_medication_course_repository(),
        item_repo=get_medication_course_item_repository(),
        dose_repo=get_medication_course_dose_repository(),
        admission_repo=get_admission_repository(),
        bed_repo=get_bed_repository(),
        user_repo=get_user_repository(),
        medicine_repo=get_medicine_repository(),
        mar_repo=get_medication_administration_repository(),
        notification_service=None,
        pharmacy_service=get_pharmacy_service(),
    )

from app.repositories.user_repository import UserRepository
from app.repositories.patient_repository import PatientRepository
from app.repositories.doctor_repository import DoctorRepository
from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.doctor_schedule_repository import (
    DoctorScheduleRepository,
)

from app.repositories.emr_repository import (
    MedicalHistoryRepository,
    PatientReportRepository,
    PrescriptionRepository,
    PrescriptionItemRepository,
    DoctorNoteRepository,
    PatientVitalRepository,
    PatientAllergyRepository,
    DiagnosisRepository,
)

from app.repositories.ward_repository import WardRepository
from app.repositories.bed_repository import BedRepository
from app.repositories.admission_repository import (
    AdmissionRepository,
    AdmissionNoteRepository,
)

from app.repositories.medicine_repository import MedicineRepository
from app.repositories.pharmacy_order_repository import (
    PharmacyOrderRepository,
    MedicationAdministrationRepository,
)

def get_doctor_schedule_repository():
    return DoctorScheduleRepository()


# -----------------------------------
# User Repository
# -----------------------------------
def get_user_repository():

    return UserRepository()


# -----------------------------------
# Patient Repository
# -----------------------------------
def get_patient_repository():

    return PatientRepository()


# -----------------------------------
# Doctor Repository
# -----------------------------------
def get_doctor_repository():

    return DoctorRepository()


# -----------------------------------
# Appointment Repository
# -----------------------------------
def get_appointment_repository():

    return AppointmentRepository()


# -----------------------------------
# EMR Repositories
# -----------------------------------
def get_medical_history_repository():
    return MedicalHistoryRepository()


def get_patient_report_repository():
    return PatientReportRepository()


def get_prescription_repository():
    return PrescriptionRepository()


def get_prescription_item_repository():
    return PrescriptionItemRepository()


def get_doctor_note_repository():
    return DoctorNoteRepository()


def get_patient_vital_repository():
    return PatientVitalRepository()


def get_patient_allergy_repository():
    return PatientAllergyRepository()


def get_diagnosis_repository():
    return DiagnosisRepository()


# -----------------------------------
# Admission / Bed Management Repositories
# -----------------------------------
def get_ward_repository():
    return WardRepository()


def get_bed_repository():
    return BedRepository()


def get_admission_repository():
    return AdmissionRepository()


def get_admission_note_repository():
    return AdmissionNoteRepository()


# -----------------------------------
# Pharmacy Repositories
# -----------------------------------
def get_medicine_repository():
    return MedicineRepository()


def get_pharmacy_order_repository():
    return PharmacyOrderRepository()


def get_medication_administration_repository():
    return MedicationAdministrationRepository()

# -----------------------------------
# Laboratory Repositories
# -----------------------------------
from app.repositories.lab_test_repository import LabTestRepository
from app.repositories.lab_order_repository import LabOrderRepository
from app.repositories.lab_result_repository import LabResultRepository


def get_lab_test_repository():
    return LabTestRepository()


def get_lab_order_repository():
    return LabOrderRepository()


def get_lab_result_repository():
    return LabResultRepository()


from app.repositories.nursing_repository import (
    NurseBedAssignmentRepository,
    MedicationCourseRepository,
    MedicationCourseItemRepository,
    MedicationCourseDoseRepository,
)

def get_nurse_bed_assignment_repository():
    return NurseBedAssignmentRepository()

def get_medication_course_repository():
    return MedicationCourseRepository()

def get_medication_course_item_repository():
    return MedicationCourseItemRepository()

def get_medication_course_dose_repository():
    return MedicationCourseDoseRepository()

from enum import Enum


class AppointmentType(str, Enum):
    PHYSICAL = "physical"
    VIDEO = "video"
    HOME = "home"


class AppointmentStatus(str, Enum):
    SCHEDULED = "scheduled"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class MeetingStatus(str, Enum):
    SCHEDULED = "scheduled"
    WAITING = "waiting"
    LIVE = "live"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class ReportType(str, Enum):
    BLOOD_TEST = "blood_test"
    MRI = "mri"
    CT_SCAN = "ct_scan"
    XRAY = "xray"
    ECG = "ecg"
    ULTRASOUND = "ultrasound"
    OTHER = "other"


class ConditionStatus(str, Enum):
    ACTIVE = "active"
    RESOLVED = "resolved"
    CHRONIC = "chronic"


class Severity(str, Enum):
    MILD = "mild"
    MODERATE = "moderate"
    SEVERE = "severe"
    CRITICAL = "critical"


# ---------------------------------------------------------
# Patient care type — OPD (outpatient) vs IPD (admitted/inpatient).
# Flips to IPD the moment an Admission Head allocates a bed, and back
# to OPD on discharge. See app/services/admission_service.py.
# ---------------------------------------------------------
class PatientCareType(str, Enum):
    OPD = "opd"
    IPD = "ipd"


# ---------------------------------------------------------
# Admission / Bed Management (IPD)
# ---------------------------------------------------------
class WardType(str, Enum):
    GENERAL = "general"
    ICU = "icu"
    PRIVATE = "private"
    PEDIATRIC = "pediatric"


class BedStatus(str, Enum):
    VACANT = "vacant"
    OCCUPIED = "occupied"
    MAINTENANCE = "maintenance"


class AdmissionUrgency(str, Enum):
    ROUTINE = "routine"
    URGENT = "urgent"
    EMERGENCY = "emergency"


class AdmissionStatus(str, Enum):
    PENDING = "pending"
    ADMITTED = "admitted"
    DISCHARGED = "discharged"
    CANCELLED = "cancelled"


class ConditionFlag(str, Enum):
    STABLE = "stable"
    CRITICAL = "critical"


# ---------------------------------------------------------
# Pharmacy
# ---------------------------------------------------------
class PharmacyOrderStatus(str, Enum):
    PENDING = "pending"
    DISPENSED = "dispensed"
    OUT_OF_STOCK = "out_of_stock"
    CANCELLED = "cancelled"


class MedicineForm(str, Enum):
    TABLET = "tablet"
    CAPSULE = "capsule"
    SYRUP = "syrup"
    INJECTION = "injection"
    DRIP = "drip"
    OINTMENT = "ointment"
    DROPS = "drops"
    OTHER = "other"

# ---------------------------------------------------------
# Laboratory
# ---------------------------------------------------------
class LabOrderStatus(str, Enum):
    PENDING = "pending"           # ordered, awaiting sample
    SAMPLE_COLLECTED = "sample_collected"
    PROCESSING = "processing"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class LabSampleType(str, Enum):
    BLOOD = "blood"
    URINE = "urine"
    STOOL = "stool"
    SPUTUM = "sputum"
    SWAB = "swab"
    TISSUE = "tissue"
    OTHER = "other"


class LabTestCategory(str, Enum):
    HEMATOLOGY = "hematology"
    BIOCHEMISTRY = "biochemistry"
    MICROBIOLOGY = "microbiology"
    PATHOLOGY = "pathology"
    RADIOLOGY = "radiology"
    SEROLOGY = "serology"
    OTHER = "other"


# ---------------------------------------------------------
# Billing
# ---------------------------------------------------------
class BillStatus(str, Enum):
    DRAFT = "draft"
    ISSUED = "issued"
    PAID = "paid"
    CANCELLED = "cancelled"


class BillItemCategory(str, Enum):
    CONSULTATION = "consultation"
    MEDICINE = "medicine"
    LAB = "lab"
    BED = "bed"
    NURSING = "nursing"
    OTHER = "other"


import os
import uuid
import shutil

from sqlalchemy.orm import Session

from app.common.service_result import ServiceResult

from app.core.logger import logger
from app.core.unit_of_work import UnitOfWork

from app.exceptions.exceptions import (
    NotFoundException,
    BadRequestException,
)

from app.models.medical_history import MedicalHistory
from app.models.patient_report import PatientReport
from app.models.prescription import Prescription
from app.models.prescription_item import PrescriptionItem
from app.models.doctor_note import DoctorNote
from app.models.patient_vital import PatientVital
from app.models.patient_allergy import PatientAllergy
from app.models.diagnosis import Diagnosis

from app.schemas.emr import (
    MedicalHistoryCreate,
    MedicalHistoryUpdate,
    PrescriptionCreate,
    DoctorNoteCreate,
    PatientVitalCreate,
    PatientAllergyCreate,
    PatientAllergyUpdate,
    DiagnosisCreate,
)

UPLOAD_DIR = os.path.join(
    os.path.dirname(
        os.path.dirname(
            os.path.dirname(__file__)
        )
    ),
    "uploads",
    "reports",
)


class EMRService:

    def __init__(
        self,
        patient_repository,
        appointment_repository,
        medical_history_repository,
        patient_report_repository,
        prescription_repository,
        prescription_item_repository,
        doctor_note_repository,
        patient_vital_repository,
        patient_allergy_repository,
        diagnosis_repository,
        doctor_repository,
        pharmacy_service=None,
        laboratory_service=None,
        admission_repository=None,
    ):
        self.patient_repo = patient_repository
        self.appointment_repo = appointment_repository
        self.medical_history_repo = medical_history_repository
        self.report_repo = patient_report_repository
        self.prescription_repo = prescription_repository
        self.prescription_item_repo = prescription_item_repository
        self.doctor_note_repo = doctor_note_repository
        self.vital_repo = patient_vital_repository
        self.allergy_repo = patient_allergy_repository
        self.diagnosis_repo = diagnosis_repository
        self.doctor_repo = doctor_repository
        # Optional — when wired in, every prescription automatically
        # creates one pending PharmacyOrder per item. See
        # app/services/pharmacy_service.py.
        self.pharmacy_service = pharmacy_service
        self.laboratory_service = laboratory_service
        # Optional — needed to validate admission_id on IPD/ward-round
        # prescriptions (see create_prescription below).
        self.admission_repo = admission_repository

    # ─────────────────────────────────────────────────────────
    # Helper: Verify Patient Exists
    # ─────────────────────────────────────────────────────────

    def _get_patient_or_404(self, db, patient_id):
        patient = self.patient_repo.get_by_id(
            db, patient_id,
        )
        if not patient:
            raise NotFoundException("Patient not found.")
        return patient

    # ─────────────────────────────────────────────────────────
    # Helper: Verify Appointment Exists
    # ─────────────────────────────────────────────────────────

    def _get_appointment_or_404(self, db, appointment_id):
        appointment = self.appointment_repo.get_by_id(
            db, appointment_id,
        )
        if not appointment:
            raise NotFoundException("Appointment not found.")
        return appointment

    # ─────────────────────────────────────────────────────────
    # Helper: Verify Doctor Exists
    # ─────────────────────────────────────────────────────────

    def _get_doctor_or_404(self, db, doctor_id):
        doctor = self.doctor_repo.get_by_id(
            db, doctor_id,
        )
        if not doctor:
            raise NotFoundException("Doctor not found.")
        return doctor

    # ─────────────────────────────────────────────────────────
    # Helper: Resolve Report Target Doctor
    # doctor_id takes priority; falls back to the appointment's
    # doctor so the AI flow keeps working unchanged.
    # ─────────────────────────────────────────────────────────

    def _resolve_report_doctor(self, db, doctor_id, appointment_id):
        if doctor_id:
            self._get_doctor_or_404(db, doctor_id)
            return doctor_id
        if appointment_id:
            appointment = self._get_appointment_or_404(db, appointment_id)
            return appointment.doctor_id
        return None

    # ═════════════════════════════════════════════════════════
    # Medical History
    # ═════════════════════════════════════════════════════════

    def add_medical_history(
        self,
        db: Session,
        data: MedicalHistoryCreate,
    ) -> ServiceResult:

        self._get_patient_or_404(db, data.patient_id)

        record = MedicalHistory(
            patient_id=data.patient_id,
            condition=data.condition,
            diagnosed_date=data.diagnosed_date,
            status=data.status,
            notes=data.notes,
        )

        with UnitOfWork(db):
            created = self.medical_history_repo.create(
                db, record,
            )

        logger.info(
            f"Medical history added | "
            f"Patient={data.patient_id} | "
            f"Condition={data.condition}"
        )

        return ServiceResult.Success(
            "Medical history added successfully.",
            created,
        )

    def get_patient_medical_history(
        self,
        db: Session,
        patient_id: int,
    ) -> ServiceResult:

        self._get_patient_or_404(db, patient_id)

        records = self.medical_history_repo.get_by_patient(
            db, patient_id,
        )

        return ServiceResult.Success(
            "Medical history fetched successfully.",
            records,
        )

    def update_medical_history(
        self,
        db: Session,
        history_id: int,
        data: MedicalHistoryUpdate,
    ) -> ServiceResult:

        record = self.medical_history_repo.get_by_id(
            db, history_id,
        )

        if not record:
            raise NotFoundException(
                "Medical history record not found."
            )

        update_data = data.model_dump(exclude_unset=True)

        for key, value in update_data.items():
            setattr(record, key, value)

        with UnitOfWork(db):
            updated = self.medical_history_repo.update(
                db, record,
            )

        logger.info(
            f"Medical history updated | ID={history_id}"
        )

        return ServiceResult.Success(
            "Medical history updated successfully.",
            updated,
        )

    def delete_medical_history(
        self,
        db: Session,
        history_id: int,
    ) -> ServiceResult:

        record = self.medical_history_repo.get_by_id(
            db, history_id,
        )

        if not record:
            raise NotFoundException(
                "Medical history record not found."
            )

        with UnitOfWork(db):
            self.medical_history_repo.delete(
                db, record,
            )

        logger.info(
            f"Medical history deleted | ID={history_id}"
        )

        return ServiceResult.Success(
            "Medical history deleted successfully.",
            None,
        )

    # ═════════════════════════════════════════════════════════
    # Patient Reports (File Upload)
    # ═════════════════════════════════════════════════════════

    def upload_report(
        self,
        db: Session,
        patient_id: int,
        report_name: str,
        report_type: str,
        file,
        appointment_id: int | None = None,
        doctor_id: int | None = None,
    ) -> ServiceResult:

        self._get_patient_or_404(db, patient_id)

        if appointment_id:
            appointment = self._get_appointment_or_404(db, appointment_id)
            if appointment.patient_id != patient_id:
                raise NotFoundException("Appointment does not belong to this patient.")

        doctor_id = self._resolve_report_doctor(db, doctor_id, appointment_id)

        # --------------------------------------------------
        # Save File To Disk
        # --------------------------------------------------
        os.makedirs(UPLOAD_DIR, exist_ok=True)

        file_ext = os.path.splitext(file.filename)[1]
        unique_name = f"{uuid.uuid4().hex}{file_ext}"
        file_path = os.path.join(UPLOAD_DIR, unique_name)

        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # --------------------------------------------------
        # Store relative path in DB
        # --------------------------------------------------
        relative_path = f"uploads/reports/{unique_name}"

        record = PatientReport(
            patient_id=patient_id,
            appointment_id=appointment_id,
            doctor_id=doctor_id,
            report_name=report_name,
            report_type=report_type,
            file_path=relative_path,
        )

        with UnitOfWork(db):
            created = self.report_repo.create(
                db, record,
            )

        logger.info(
            f"Report uploaded | "
            f"Patient={patient_id} | "
            f"File={relative_path}"
        )

        return ServiceResult.Success(
            "Report uploaded successfully.",
            created,
        )

    def create_report_from_saved_file(
        self,
        db: Session,
        patient_id: int,
        report_name: str,
        report_type: str,
        file_path: str,
        appointment_id: int | None = None,
        doctor_id: int | None = None,
    ) -> ServiceResult:
        """
        Create a patient report record for a file that was already written
        to disk (e.g. an attachment collected by the AI assistant), instead
        of saving a fresh UploadFile like `upload_report` does. The AI flow
        needs the file on disk as soon as it's attached, but only has the
        report name/type a couple of chat turns later.
        """

        self._get_patient_or_404(db, patient_id)

        if appointment_id:
            appointment = self._get_appointment_or_404(db, appointment_id)
            if appointment.patient_id != patient_id:
                raise NotFoundException("Appointment does not belong to this patient.")

        doctor_id = self._resolve_report_doctor(db, doctor_id, appointment_id)

        record = PatientReport(
            patient_id=patient_id,
            appointment_id=appointment_id,
            doctor_id=doctor_id,
            report_name=report_name,
            report_type=report_type,
            file_path=file_path,
        )

        with UnitOfWork(db):
            created = self.report_repo.create(
                db, record,
            )

        logger.info(
            f"Report uploaded via AI assistant | "
            f"Patient={patient_id} | "
            f"Appointment={appointment_id} | "
            f"File={file_path}"
        )

        return ServiceResult.Success(
            "Report uploaded successfully.",
            created,
        )

    def get_patient_reports(
        self,
        db: Session,
        patient_id: int,
        doctor_id: int | None = None,
    ) -> ServiceResult:

        self._get_patient_or_404(db, patient_id)

        if doctor_id is None:
            reports = self.report_repo.get_by_patient(db, patient_id)
        else:
            reports = self.report_repo.get_by_patient_for_doctor(
                db, patient_id, doctor_id,
            )

        return ServiceResult.Success(
            "Reports fetched successfully.",
            reports,
        )

    def get_report_by_id(
        self,
        db: Session,
        report_id: int,
    ) -> ServiceResult:

        report = self.report_repo.get_by_id(
            db, report_id,
        )

        if not report:
            raise NotFoundException("Report not found.")

        return ServiceResult.Success(
            "Report fetched successfully.",
            report,
        )

    def delete_report(
        self,
        db: Session,
        report_id: int,
    ) -> ServiceResult:

        report = self.report_repo.get_by_id(
            db, report_id,
        )

        if not report:
            raise NotFoundException("Report not found.")

        # Delete file from disk
        full_path = os.path.join(
            os.path.dirname(
                os.path.dirname(
                    os.path.dirname(__file__)
                )
            ),
            report.file_path,
        )

        if os.path.exists(full_path):
            os.remove(full_path)

        with UnitOfWork(db):
            self.report_repo.delete(db, report)

        logger.info(
            f"Report deleted | ID={report_id}"
        )

        return ServiceResult.Success(
            "Report deleted successfully.",
            None,
        )

    # ═════════════════════════════════════════════════════════
    # Prescriptions
    # ═════════════════════════════════════════════════════════

    def create_prescription(
        self,
        db: Session,
        data: PrescriptionCreate,
    ) -> ServiceResult:

        self._get_patient_or_404(db, data.patient_id)

        if not data.appointment_id and not data.admission_id:
            raise BadRequestException(
                "Prescription needs either an appointment_id (OPD) "
                "or an admission_id (IPD/ward round)."
            )

        if data.appointment_id:
            self._get_appointment_or_404(db, data.appointment_id)

        if data.admission_id and self.admission_repo:
            admission = self.admission_repo.get_by_id(db, data.admission_id)
            if not admission:
                raise NotFoundException("Admission not found.")

        prescription = Prescription(
            appointment_id=data.appointment_id,
            admission_id=data.admission_id,
            patient_id=data.patient_id,
            doctor_id=data.doctor_id,
            diagnosis=data.diagnosis,
            advice=data.advice,
        )

        # Build items
        items = []
        for item_data in data.items:
            from app.services.pharmacy_service import PharmacyService
            qty = PharmacyService._estimate_quantity(
                item_data.frequency,
                item_data.duration,
                getattr(item_data, "quantity", None),
            )
            form_val = (getattr(item_data, "form", None) or None)
            if form_val:
                form_val = str(form_val).strip().lower()
            items.append(
                PrescriptionItem(
                    medicine_name=item_data.medicine_name,
                    form=form_val,
                    dosage=item_data.dosage,
                    frequency=item_data.frequency,
                    duration=item_data.duration,
                    instructions=item_data.instructions,
                    quantity=qty,
                )
            )

        prescription.items = items

        with UnitOfWork(db):
            created = self.prescription_repo.create(
                db, prescription,
            )

            # Fulfillment half of the prescription: one pending
            # PharmacyOrder per item, so the Pharmacist's queue picks
            # it up immediately. Runs in the same transaction so a
            # prescription is never saved without its orders.
            if self.pharmacy_service:
                try:
                    self.pharmacy_service.create_orders_for_prescription(
                        db, created,
                    )
                except Exception as e:
                    logger.error(
                        f"Failed to create pharmacy orders for "
                        f"prescription {created.id}: {e}"
                    )

        logger.info(
            f"Prescription created | "
            f"ID={created.id} | "
            f"Patient={data.patient_id} | "
            f"Items={len(items)}"
        )

        return ServiceResult.Success(
            "Prescription created successfully.",
            created,
        )

    def get_prescription(
        self,
        db: Session,
        prescription_id: int,
    ) -> ServiceResult:

        prescription = self.prescription_repo.get_by_id(
            db, prescription_id,
        )

        if not prescription:
            raise NotFoundException(
                "Prescription not found."
            )

        return ServiceResult.Success(
            "Prescription fetched successfully.",
            prescription,
        )

    def get_prescriptions_by_patient(
        self,
        db: Session,
        patient_id: int,
    ) -> ServiceResult:

        self._get_patient_or_404(db, patient_id)

        prescriptions = self.prescription_repo.get_by_patient(
            db, patient_id,
        )

        return ServiceResult.Success(
            "Prescriptions fetched successfully.",
            prescriptions,
        )

    def get_prescriptions_by_appointment(
        self,
        db: Session,
        appointment_id: int,
    ) -> ServiceResult:

        self._get_appointment_or_404(db, appointment_id)

        prescriptions = self.prescription_repo.get_by_appointment(
            db, appointment_id,
        )

        return ServiceResult.Success(
            "Prescriptions fetched successfully.",
            prescriptions,
        )

    # ═════════════════════════════════════════════════════════
    # Doctor Notes
    # ═════════════════════════════════════════════════════════

    def add_doctor_note(
        self,
        db: Session,
        data: DoctorNoteCreate,
    ) -> ServiceResult:

        self._get_patient_or_404(db, data.patient_id)
        self._get_appointment_or_404(db, data.appointment_id)

        note = DoctorNote(
            appointment_id=data.appointment_id,
            patient_id=data.patient_id,
            doctor_id=data.doctor_id,
            note=data.note,
        )

        with UnitOfWork(db):
            created = self.doctor_note_repo.create(
                db, note,
            )

        logger.info(
            f"Doctor note added | "
            f"Appointment={data.appointment_id}"
        )

        return ServiceResult.Success(
            "Doctor note added successfully.",
            created,
        )

    def get_notes_by_appointment(
        self,
        db: Session,
        appointment_id: int,
    ) -> ServiceResult:

        self._get_appointment_or_404(db, appointment_id)

        notes = self.doctor_note_repo.get_by_appointment(
            db, appointment_id,
        )

        return ServiceResult.Success(
            "Doctor notes fetched successfully.",
            notes,
        )

    def get_notes_by_patient(
        self,
        db: Session,
        patient_id: int,
    ) -> ServiceResult:

        self._get_patient_or_404(db, patient_id)

        notes = self.doctor_note_repo.get_by_patient(
            db, patient_id,
        )

        return ServiceResult.Success(
            "Doctor notes fetched successfully.",
            notes,
        )

    # ═════════════════════════════════════════════════════════
    # Vitals
    # ═════════════════════════════════════════════════════════

    def record_vitals(
        self,
        db: Session,
        data: PatientVitalCreate,
    ) -> ServiceResult:

        self._get_patient_or_404(db, data.patient_id)
        self._get_appointment_or_404(db, data.appointment_id)

        vital = PatientVital(
            appointment_id=data.appointment_id,
            patient_id=data.patient_id,
            height=data.height,
            weight=data.weight,
            temperature=data.temperature,
            blood_pressure=data.blood_pressure,
            pulse=data.pulse,
            oxygen_level=data.oxygen_level,
        )

        with UnitOfWork(db):
            created = self.vital_repo.create(
                db, vital,
            )

        logger.info(
            f"Vitals recorded | "
            f"Patient={data.patient_id} | "
            f"Appointment={data.appointment_id}"
        )

        return ServiceResult.Success(
            "Vitals recorded successfully.",
            created,
        )

    def get_vitals_by_patient(
        self,
        db: Session,
        patient_id: int,
    ) -> ServiceResult:

        self._get_patient_or_404(db, patient_id)

        vitals = self.vital_repo.get_by_patient(
            db, patient_id,
        )

        return ServiceResult.Success(
            "Vitals fetched successfully.",
            vitals,
        )

    def get_vitals_by_appointment(
        self,
        db: Session,
        appointment_id: int,
    ) -> ServiceResult:

        self._get_appointment_or_404(db, appointment_id)

        vitals = self.vital_repo.get_by_appointment(
            db, appointment_id,
        )

        return ServiceResult.Success(
            "Vitals fetched successfully.",
            vitals,
        )

    # ═════════════════════════════════════════════════════════
    # Allergies
    # ═════════════════════════════════════════════════════════

    def add_allergy(
        self,
        db: Session,
        data: PatientAllergyCreate,
    ) -> ServiceResult:

        self._get_patient_or_404(db, data.patient_id)

        allergy = PatientAllergy(
            patient_id=data.patient_id,
            allergy_name=data.allergy_name,
            reaction=data.reaction,
            notes=data.notes,
        )

        with UnitOfWork(db):
            created = self.allergy_repo.create(
                db, allergy,
            )

        logger.info(
            f"Allergy added | "
            f"Patient={data.patient_id} | "
            f"Allergy={data.allergy_name}"
        )

        return ServiceResult.Success(
            "Allergy added successfully.",
            created,
        )

    def get_patient_allergies(
        self,
        db: Session,
        patient_id: int,
    ) -> ServiceResult:

        self._get_patient_or_404(db, patient_id)

        allergies = self.allergy_repo.get_by_patient(
            db, patient_id,
        )

        return ServiceResult.Success(
            "Allergies fetched successfully.",
            allergies,
        )

    def update_allergy(
        self,
        db: Session,
        allergy_id: int,
        data: PatientAllergyUpdate,
    ) -> ServiceResult:

        allergy = self.allergy_repo.get_by_id(
            db, allergy_id,
        )

        if not allergy:
            raise NotFoundException("Allergy not found.")

        update_data = data.model_dump(exclude_unset=True)

        for key, value in update_data.items():
            setattr(allergy, key, value)

        with UnitOfWork(db):
            updated = self.allergy_repo.update(
                db, allergy,
            )

        logger.info(
            f"Allergy updated | ID={allergy_id}"
        )

        return ServiceResult.Success(
            "Allergy updated successfully.",
            updated,
        )

    def delete_allergy(
        self,
        db: Session,
        allergy_id: int,
    ) -> ServiceResult:

        allergy = self.allergy_repo.get_by_id(
            db, allergy_id,
        )

        if not allergy:
            raise NotFoundException("Allergy not found.")

        with UnitOfWork(db):
            self.allergy_repo.delete(db, allergy)

        logger.info(
            f"Allergy deleted | ID={allergy_id}"
        )

        return ServiceResult.Success(
            "Allergy deleted successfully.",
            None,
        )

    # ═════════════════════════════════════════════════════════
    # Diagnoses
    # ═════════════════════════════════════════════════════════

    def add_diagnosis(
        self,
        db: Session,
        data: DiagnosisCreate,
    ) -> ServiceResult:

        self._get_patient_or_404(db, data.patient_id)
        self._get_appointment_or_404(db, data.appointment_id)

        diagnosis = Diagnosis(
            appointment_id=data.appointment_id,
            patient_id=data.patient_id,
            diagnosis=data.diagnosis,
            severity=data.severity,
            notes=data.notes,
        )

        with UnitOfWork(db):
            created = self.diagnosis_repo.create(
                db, diagnosis,
            )

        logger.info(
            f"Diagnosis added | "
            f"Patient={data.patient_id} | "
            f"Diagnosis={data.diagnosis}"
        )

        return ServiceResult.Success(
            "Diagnosis added successfully.",
            created,
        )

    def get_diagnoses_by_patient(
        self,
        db: Session,
        patient_id: int,
    ) -> ServiceResult:

        self._get_patient_or_404(db, patient_id)

        diagnoses = self.diagnosis_repo.get_by_patient(
            db, patient_id,
        )

        return ServiceResult.Success(
            "Diagnoses fetched successfully.",
            diagnoses,
        )

    def get_diagnoses_by_appointment(
        self,
        db: Session,
        appointment_id: int,
    ) -> ServiceResult:

        self._get_appointment_or_404(db, appointment_id)

        diagnoses = self.diagnosis_repo.get_by_appointment(
            db, appointment_id,
        )

        return ServiceResult.Success(
            "Diagnoses fetched successfully.",
            diagnoses,
        )


    # ═════════════════════════════════════════════════════════
    # Lab Orders (from appointment / admission — same pattern as
    # prescriptions → pharmacy)
    # ═════════════════════════════════════════════════════════

    def create_lab_order(
        self,
        db: Session,
        data,
    ) -> ServiceResult:
        """
        Doctor orders lab tests during an OPD appointment or IPD
        ward round. Validates clinical context, then delegates to
        LaboratoryService so the order appears in the lab tech queue.
        """
        from app.schemas.laboratory import LabOrderCreate

        self._get_patient_or_404(db, data.patient_id)

        if not getattr(data, "appointment_id", None) and not getattr(data, "admission_id", None):
            raise BadRequestException(
                "Lab order needs either an appointment_id (OPD) "
                "or an admission_id (IPD/ward round)."
            )

        if data.appointment_id:
            self._get_appointment_or_404(db, data.appointment_id)

        if data.admission_id and self.admission_repo:
            admission = self.admission_repo.get_by_id(db, data.admission_id)
            if not admission:
                raise NotFoundException("Admission not found.")

        if not self.laboratory_service:
            raise BadRequestException("Laboratory module is not available.")

        lab_payload = LabOrderCreate(
            patient_id=data.patient_id,
            ordered_by_doctor_id=data.ordered_by_doctor_id,
            test_ids=data.test_ids,
            appointment_id=data.appointment_id,
            admission_id=data.admission_id,
            prescription_id=getattr(data, "prescription_id", None),
            priority=getattr(data, "priority", None) or "routine",
            clinical_notes=getattr(data, "clinical_notes", None),
        )

        result = self.laboratory_service.create_order(db, lab_payload)
        logger.info(
            f"Lab order created via EMR | ID={getattr(result.data, 'id', '?')} | "
            f"Patient={data.patient_id}"
        )
        return result


    @staticmethod
    def _serialize_lab_order(order) -> dict:
        """Convert a LabOrder (possibly enriched) into a JSON-safe dict."""
        results = []
        for r in getattr(order, "results", None) or []:
            results.append({
                "id": getattr(r, "id", None),
                "lab_order_id": getattr(r, "lab_order_id", None),
                "lab_test_id": getattr(r, "lab_test_id", None),
                "value_numeric": getattr(r, "value_numeric", None),
                "value_text": getattr(r, "value_text", None),
                "unit": getattr(r, "unit", None),
                "is_abnormal": bool(getattr(r, "is_abnormal", False)),
                "remarks": getattr(r, "remarks", None),
                "status": getattr(r, "status", None),
                "test_name": getattr(r, "test_name", None) or (
                    r.lab_test.name if getattr(r, "lab_test", None) else None
                ),
                "test_code": getattr(r, "test_code", None) or (
                    r.lab_test.code if getattr(r, "lab_test", None) else None
                ),
                "sample_type": getattr(r, "sample_type", None) or (
                    r.lab_test.sample_type if getattr(r, "lab_test", None) else None
                ),
                "normal_range_text": getattr(r, "normal_range_text", None),
            })

        created_at = getattr(order, "created_at", None)
        completed_at = getattr(order, "completed_at", None)
        sample_collected_at = getattr(order, "sample_collected_at", None)

        return {
            "id": getattr(order, "id", None),
            "patient_id": getattr(order, "patient_id", None),
            "ordered_by_doctor_id": getattr(order, "ordered_by_doctor_id", None),
            "appointment_id": getattr(order, "appointment_id", None),
            "admission_id": getattr(order, "admission_id", None),
            "prescription_id": getattr(order, "prescription_id", None),
            "status": getattr(order, "status", None),
            "priority": getattr(order, "priority", None),
            "clinical_notes": getattr(order, "clinical_notes", None),
            "sample_collected_at": sample_collected_at.isoformat() if sample_collected_at else None,
            "completed_at": completed_at.isoformat() if completed_at else None,
            "created_at": created_at.isoformat() if created_at else None,
            "patient_name": getattr(order, "patient_name", None) or (
                order.patient.name if getattr(order, "patient", None) else None
            ),
            "doctor_name": getattr(order, "doctor_name", None) or (
                order.ordered_by_doctor.full_name if getattr(order, "ordered_by_doctor", None) else None
            ),
            "source": getattr(order, "source", None) or (
                "ipd" if getattr(order, "admission_id", None) else "opd"
            ),
            "ward_bed_label": getattr(order, "ward_bed_label", None),
            "results": results,
        }

    # ═════════════════════════════════════════════════════════
    # Patient Timeline (Full EMR)
    # ═════════════════════════════════════════════════════════

    def get_patient_timeline(
        self,
        db: Session,
        patient_id: int,
        doctor_id: int | None = None,
    ) -> ServiceResult:

        patient = self._get_patient_or_404(db, patient_id)

        medical_history = self.medical_history_repo.get_by_patient(
            db, patient_id,
        )
        allergies = self.allergy_repo.get_by_patient(
            db, patient_id,
        )
        if doctor_id is None:
            reports = self.report_repo.get_by_patient(db, patient_id)
            prescriptions = self.prescription_repo.get_by_patient(db, patient_id)
            diagnoses = self.diagnosis_repo.get_by_patient(db, patient_id)
            vitals = self.vital_repo.get_by_patient(db, patient_id)
            doctor_notes = self.doctor_note_repo.get_by_patient(db, patient_id)
        else:
            # A doctor only sees their own prescriptions/notes and records
            # shared to them (reports) or from their own appointments.
            reports = self.report_repo.get_by_patient_for_doctor(
                db, patient_id, doctor_id,
            )
            prescriptions = self.prescription_repo.get_by_patient_for_doctor(
                db, patient_id, doctor_id,
            )
            diagnoses = self.diagnosis_repo.get_by_patient_for_doctor(
                db, patient_id, doctor_id,
            )
            vitals = self.vital_repo.get_by_patient_for_doctor(
                db, patient_id, doctor_id,
            )
            doctor_notes = self.doctor_note_repo.get_by_patient_for_doctor(
                db, patient_id, doctor_id,
            )

        lab_orders = []
        if self.laboratory_service:
            try:
                lab_result = self.laboratory_service.get_patient_orders(db, patient_id)
                raw_orders = lab_result.data or []
                # Serialize ORM objects → plain dicts for PatientTimelineResponse
                lab_orders = [
                    self._serialize_lab_order(o) for o in raw_orders
                ]
            except Exception as e:
                logger.warning(f"Could not load lab orders for patient {patient_id}: {e}")

        timeline = {
            "patient_id": patient.id,
            "patient_name": patient.name,
            "phone": patient.phone,
            "email": patient.email,
            "medical_history": medical_history,
            "allergies": allergies,
            "reports": reports,
            "prescriptions": prescriptions,
            "diagnoses": diagnoses,
            "vitals": vitals,
            "doctor_notes": doctor_notes,
            "lab_orders": lab_orders,
        }

        logger.info(
            f"Timeline fetched | Patient={patient_id}"
        )

        return ServiceResult.Success(
            "Patient timeline fetched successfully.",
            timeline,
        )

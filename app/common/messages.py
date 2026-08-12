class Messages:
    """
    Centralized application messages.

    Keeping all user-facing messages here makes it easier to:
    - Maintain consistency
    - Translate the application
    - Avoid duplicate strings
    """

    # ---------------------------------
    # General
    # ---------------------------------

    SUCCESS = "Operation completed successfully."
    INTERNAL_SERVER_ERROR = "Something went wrong."

    # ---------------------------------
    # Patient
    # ---------------------------------

    PATIENT_CREATED = "Patient created successfully."
    PATIENT_UPDATED = "Patient updated successfully."
    PATIENT_DELETED = "Patient deleted successfully."
    PATIENT_NOT_FOUND = "Patient not found."

    # ---------------------------------
    # Doctor
    # ---------------------------------

    DOCTOR_CREATED = "Doctor created successfully."
    DOCTOR_UPDATED = "Doctor updated successfully."
    DOCTOR_DELETED = "Doctor deleted successfully."
    DOCTOR_NOT_FOUND = "Doctor not found."
    DOCTOR_UNAVAILABLE = "Doctor is currently unavailable."

    # ---------------------------------
    # Appointment
    # ---------------------------------

    APPOINTMENT_CREATED = "Appointment booked successfully."
    APPOINTMENT_UPDATED = "Appointment updated successfully."
    APPOINTMENT_CANCELLED = "Appointment cancelled successfully."
    APPOINTMENT_NOT_FOUND = "Appointment not found."

    SLOT_ALREADY_BOOKED = "This appointment slot is already booked."

    APPOINTMENT_IN_PAST = (
        "Appointments cannot be booked in the past."
    )

    # ---------------------------------
    # Authentication
    # ---------------------------------

    INVALID_CREDENTIALS = "Invalid email or password."

    UNAUTHORIZED = "Unauthorized access."

    ACCESS_DENIED = "Access denied."

    # ---------------------------------
    # AI Assistant
    # ---------------------------------

    AI_RESPONSE_ERROR = (
        "Unable to generate an AI response."
    )

    AI_BOOKING_SUCCESS = (
        "Your appointment has been booked successfully."
    )

    AI_BOOKING_FAILED = (
        "Sorry, I couldn't book your appointment."
    )

    # ---------------------------------
    # Admission / Bed Management
    # ---------------------------------

    WARD_NOT_FOUND = "Ward not found."
    WARD_CREATED = "Ward created successfully."
    WARD_UPDATED = "Ward updated successfully."
    WARD_DELETED = "Ward deleted successfully."

    BED_NOT_FOUND = "Bed not found."
    BED_CREATED = "Bed created successfully."
    BED_UPDATED = "Bed updated successfully."
    BED_DELETED = "Bed deleted successfully."
    BED_NOT_VACANT = "This bed is not vacant."

    ADMISSION_NOT_FOUND = "Admission request not found."
    ADMISSION_REQUEST_CREATED = "Admission request created successfully."
    ADMISSION_ALREADY_ADMITTED = (
        "Patient already has an active admission."
    )
    ADMISSION_NOT_PENDING = (
        "Only pending admission requests can be allocated a bed."
    )
    ADMISSION_NOT_ADMITTED = (
        "Only admitted patients can be discharged."
    )
    ADMISSION_ALLOCATED = "Bed allocated successfully — patient admitted."
    ADMISSION_DISCHARGED = "Patient discharged successfully."
    ADMISSION_NOTE_ADDED = "Admission note added successfully."

    # ---------------------------------
    # Pharmacy
    # ---------------------------------

    MEDICINE_NOT_FOUND = "Medicine not found."
    MEDICINE_CREATED = "Medicine added to inventory successfully."
    MEDICINE_UPDATED = "Medicine updated successfully."
    MEDICINE_ALREADY_EXISTS = "This medicine already exists in inventory."
    MEDICINE_RESTOCKED = "Medicine stock updated successfully."

    PHARMACY_ORDER_NOT_FOUND = "Pharmacy order not found."
    PHARMACY_ORDER_ALREADY_DISPENSED = (
        "This pharmacy order has already been dispensed."
    )
    PHARMACY_ORDER_OUT_OF_STOCK = (
        "Cannot dispense — insufficient stock for this medicine."
    )
    PHARMACY_ORDER_DISPENSED = "Medicine dispensed successfully."

    MEDICATION_ADMINISTERED = "Dose logged successfully."
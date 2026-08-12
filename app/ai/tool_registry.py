class ToolRegistry:
    """
    Registry of all tools available to the AI Receptionist.
    """

    @staticmethod
    def get_tools() -> list:
        return [

            # -------------------------------------------------
            # Book Appointment
            # -------------------------------------------------
            {
                "type": "function",
                "function": {
                    "name": "book_appointment",
                    "description": "Book a new appointment for a patient.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "patient_id": {
                                "type": "integer"
                            },
                            "doctor_id": {
                                "type": "integer"
                            },
                            "appointment_date": {
                                "type": "string",
                                "description": "YYYY-MM-DD"
                            },
                            "appointment_time": {
                                "type": "string",
                                "description": "HH:MM"
                            },
                            "reason": {
                                "type": "string"
                            },
                            "notes": {
                                "type": "string"
                            }
                        },
                        "required": [
                            "patient_id",
                            "doctor_id",
                            "appointment_date",
                            "appointment_time"
                        ]
                    }
                }
            },

            # -------------------------------------------------
            # Update Appointment
            # -------------------------------------------------
            {
                "type": "function",
                "function": {
                    "name": "update_appointment",
                    "description": "Reschedule or update an appointment.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "appointment_id": {
                                "type": "integer"
                            },
                            "appointment_date": {
                                "type": "string"
                            },
                            "appointment_time": {
                                "type": "string"
                            }
                        },
                        "required": [
                            "appointment_id"
                        ]
                    }
                }
            },

            # -------------------------------------------------
            # Cancel Appointment
            # -------------------------------------------------
            {
                "type": "function",
                "function": {
                    "name": "cancel_appointment",
                    "description": "Cancel an appointment.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "appointment_id": {
                                "type": "integer"
                            }
                        },
                        "required": [
                            "appointment_id"
                        ]
                    }
                }
            },

            # -------------------------------------------------
            # Get Appointments
            # -------------------------------------------------
            {
                "type": "function",
                "function": {
                    "name": "get_appointments",
                    "description": "Retrieve all appointments.",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            },

            # -------------------------------------------------
            # Get Doctors
            # -------------------------------------------------
            {
                "type": "function",
                "function": {
                    "name": "get_doctors",
                    "description": "Retrieve all doctors.",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            },

            # -------------------------------------------------
            # Get Available Doctors
            # -------------------------------------------------
            {
                "type": "function",
                "function": {
                    "name": "get_available_doctors",
                    "description": "Retrieve all available doctors.",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            },

            # -------------------------------------------------
            # Get Patients
            # -------------------------------------------------
            {
                "type": "function",
                "function": {
                    "name": "get_patients",
                    "description": "Retrieve all patients.",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            },

            # -------------------------------------------------
            # Dashboard Summary
            # -------------------------------------------------
            {
                "type": "function",
                "function": {
                    "name": "dashboard_summary",
                    "description": "Get clinic dashboard statistics.",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            }

        ]
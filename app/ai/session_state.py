class SessionState:
    """
    Stores temporary AI conversation state.

    Example:

    {
        "abc123": {
            "intent": "book_appointment",
            "patient_id": 2,
            "doctor_id": None,
            "appointment_date": None,
            "appointment_time": None,
        }
    }
    """

    _sessions = {}

    @classmethod
    def get(cls, session_id: str):
        if session_id not in cls._sessions:
            cls._sessions[session_id] = {}

        return cls._sessions[session_id]

    @classmethod
    def clear(cls, session_id: str):
        cls._sessions.pop(session_id, None)
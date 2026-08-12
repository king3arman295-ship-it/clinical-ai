class IntentDetector:

    SYMPTOM_KEYWORDS = [
        "pain", "ache", "hurt", "symptom", "fever", "cough", "cold", "flu",
        "headache", "migraine", "chest", "heart", "breathing", "dizzy",
        "nausea", "vomit", "diarrhea", "constipation", "rash", "skin",
        "infection", "swelling", "fracture", "injury", "wound", "burn",
        "allergy", "diabetes", "pressure", "thyroid", "anxiety", "depression",
        "stress", "insomnia", "vision", "hearing", "ear", "throat", "nose",
        "stomach", "abdomen", "back", "joint", "bone", "muscle", "fatigue",
        "weight", "fever", "chills", "sore", "stiff", "numb", "tingling",
        "sick", "unwell", "suffering", "sneeze", "congestion", "infection",
        "sick", "vomit", "diabet", "cough", "fever", "flu",
    ]

    BOOKING_TRIGGER_WORDS = [
        "book", "appointment", "appointments", "schedule", "reserve",
        "reservation", "booking",
        "appoitment", "appoitmnet", "apointment", "appoinment",
    ]

    @staticmethod
    def detect(message: str) -> str:
        message = message.lower()

        if any(word in message for word in ["cancel", "delete"]):
            return "cancel_appointment"

        # "view" and "show" are too broad — only count them as
        # view_appointments when they're clearly about appointments.
        if any(word in message for word in ["my appointments", "my booking", "my appointment"]):
            return "view_appointments"

        words = set(message.split())
        if ("show" in words or "view" in words) and "appointment" in message:
            return "view_appointments"

        if any(kw in message for kw in IntentDetector.SYMPTOM_KEYWORDS):
            return "book_appointment"

        concern_phrases = [
            "i have", "i've been", "i am feeling", "i'm feeling",
            "i feel", "not feeling", "something wrong", "need help",
            "check up", "checkup", "consult", "treatment", "issue with",
            "problem with", "suffering from", "dealing with",
            "i want", "i need", "i would like", "i'd like",
            "want to", "need to", "would like to",
            "looking for", "look for", "need an", "need a",
            "make an", "make a", "set up", "arrange",
            "can i", "can you", "could i", "could you",
            "i am looking", "i'm looking",
            "fix an", "fix a", "get an", "get a",
            "have an", "have a", "had an",
            "want an", "want a", "wanted an", "wanted a",
            "need appointment", "want appointment",
        ]
        if any(phrase in message for phrase in concern_phrases):
            return "book_appointment"

        if any(word in message for word in IntentDetector.BOOKING_TRIGGER_WORDS):
            return "book_appointment"

        return "chat"
import re


class LanguageGuard:
    """
    Keeps the AI Medical Assistant English-only and on-topic.

    Two independent, deterministic checks (no external LLM call):

    - is_non_english(text): flags non-Latin scripts (Urdu/Arabic, Hindi,
      Chinese, etc.) as well as Roman Urdu.
    - is_allowed_topic(text): only passes clinic-specific topics the AI may
      answer — doctors, schedules, departments, appointments/booking.
      Everything else is rejected.
    """

    NON_LATIN_SCRIPT_PATTERN = re.compile(
        r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF"
        r"\u0900-\u097F\u0980-\u09FF\u4E00-\u9FFF\u3040-\u30FF\uAC00-\uD7AF]"
    )

    ROMAN_URDU_WORDS = {
        "hai", "hain", "hun", "hoon", "tha", "thi", "thay", "thoda", "thora",
        "mujhe", "mera", "meri", "mere", "mujhko", "humein", "hamein",
        "tum", "tumhara", "tumhari", "aap", "aapka", "aapki", "aapke",
        "apka", "apki", "apna", "apni", "kya", "kyun", "kyu", "kaisay",
        "kaise", "kesay", "kese", "kahan", "kaha", "kab", "kis", "kaun",
        "kon", "nahi", "nahin", "haan", "achha", "acha", "theek", "thek",
        "bimari", "bimar", "dard", "dawai", "dawa", "davai", "tabiyat",
        "mulaqat", "waqt", "tareekh", "madad", "shukriya", "meherbani",
        "zaroorat", "chahiye", "chahye", "karna", "karo", "kro", "krna",
        "raha", "rahi", "rha", "rhi", "wala", "wali", "bohot", "bahut",
        "zyada", "zada", "bht", "abhi", "kal", "aaj", "parso", "subah",
        "shaam", "raat", "dopeher", "dopahar", "paisa", "paise", "rupay",
        "rupaye", "sahab", "sahib", "bhai", "behen", "ammi", "abbu",
        "matlab", "bata", "batao", "batayen", "bataiye", "dikha", "dikhao",
        "milna", "milega", "milegi", "chalo", "lekin", "magar", "phir",
        "sath", "saath", "bukhar", "khansi", "sar", "pait", "jism",
    }

    # ponytail: O(n) substring scan over ~100 entries, fine for chat-sized input
    ALLOWED_TOPIC_KEYWORDS = {
        "doctor", "dr.", "dr ", "specialist", "physician", "doc",
        "schedule", "scheduled", "scheduling", "available", "availability",
        "timing", "timings", "free slot", "slot", "slots", "free time",
        "working hours", "when is", "when can", "what time",
        "department", "departments", "specialization", "specializations",
        "specialty", "specialties", "speciality", "specialities",
        "book", "booking", "booked", "reserve", "reservation", "reservations",
        "appointment", "appointments",
        "appoitment", "appoitmnet", "apointment", "appoinment", "apointmnet",
        "appotment", "apotment", "appointmentt", "appointmnet", "appointement",
        "appoitnment", "apointnment", "appointment",
        "consult", "consultation", "consulting",
        "checkup", "check-up", "checkups", "checkup",
        "visit", "visiting", "come in", "come to", "walk in",
        "see a doctor", "see dr", "see the doctor", "see specialist",
        "meet doctor", "meet dr",
        "want to", "wanted to", "would like", "looking for", "look for",
        "need to", "needs to", "need an", "need a", "need appointment",
        "make an", "make a", "set up", "arrange", "fix an",
        "symptom", "symptoms", "symptomps", "symtom", "symtoms",
        "pain", "pains", "painful", "ache", "aches", "aching",
        "hurt", "hurts", "hurting", "sick", "unwell",
        "fever", "feverish", "cough", "coughing", "cold", "flu", "flue",
        "headache", "head ache", "migraine", "migrane",
        "nausea", "vomit", "vomiting", "diarrhea", "constipation",
        "rash", "rashes", "skin", "infection", "infections",
        "swelling", "fracture", "injury", "injured", "wound", "burn",
        "allergy", "allergies", "diabetes", "diabetic", "pressure",
        "thyroid", "anxiety", "anxious", "depression", "depressed",
        "stress", "stressed", "insomnia", "sleepless",
        "sore", "stiff", "numb", "numbness", "tingling",
        "breathing", "breath", "chest", "heart",
        "stomach", "abdomen", "abdominal", "back", "joint", "joints",
        "bone", "muscle", "fatigue", "tired", "weak", "weakness",
        "weight", "chills", "sneeze", "sneezing", "congestion",
        "suffering", "suffering from",
        "clinic", "hospital", "lumina", "health",
        "medical", "medicine", "medication", "medicines",
        "test", "tests", "report", "reports",
        "prescription", "prescriptions", "treatment", "treatments",
        "help", "assist", "assistance", "support",
        "please", "thanks", "thank",
        "today", "tomorrow", "yesterday",
        "monday", "tuesday", "wednesday", "thursday", "friday",
        "saturday", "sunday", "morning", "afternoon", "evening",
        "hi", "hello", "hey", "good morning", "good evening",
        "how are you", "how are you doing",
        "who are you", "what is your name", "what are you",
        "bye", "goodbye", "good bye", "see you",
    }

    @classmethod
    def is_non_english(cls, text: str) -> bool:
        if not text or not text.strip():
            return False

        if cls.NON_LATIN_SCRIPT_PATTERN.search(text):
            return True

        words = re.findall(r"[a-zA-Z']+", text.lower())
        if len(words) < 2:
            return False

        roman_hits = sum(1 for w in words if w in cls.ROMAN_URDU_WORDS)
        ratio = roman_hits / len(words)

        return roman_hits >= 2 and ratio >= 0.3

    @classmethod
    def is_allowed_topic(cls, text: str) -> bool:
        if not text:
            return False
        lowered = text.lower()
        return any(kw in lowered for kw in cls.ALLOWED_TOPIC_KEYWORDS)

    @staticmethod
    def ask_for_english_message() -> str:
        return (
            "Sorry, I can only understand English. "
            "Could you please ask in English? "
            "For example: \"What doctors are available?\" or "
            "\"I want to book an appointment.\""
        )

    @staticmethod
    def scope_restricted_message() -> str:
        return (
            "I'm a clinic AI assistant. I can help you with:\n\n"
            "\u2022 Viewing available doctors and their schedules\n"
            "\u2022 Our medical departments and specializations\n"
            "\u2022 Booking appointments\n\n"
            "Please ask me about any of these topics."
        )

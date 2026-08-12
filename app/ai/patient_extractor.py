import re


class PatientExtractor:
    """
    Extract patient information from natural language.

    Currently extracts:
    - Patient name
    - Phone number

    Later we can extend it to:
    - Email
    - Age
    - Gender
    - Address
    """

    @staticmethod
    def extract(message: str) -> dict:

        data = {
            "patient_name": None,
            "phone": None,
        }

        text = message.strip()

        # ---------------------------------
        # Phone Number
        # ---------------------------------
        phone_pattern = (
            r"(03\d{9}|\+92\d{10}|92\d{10})"
        )

        phone_match = re.search(
            phone_pattern,
            text,
        )

        if phone_match:
            data["phone"] = phone_match.group()

        # ---------------------------------
        # Patient Name
        # ---------------------------------
        name_patterns = [

            r"(?:my name is)\s+([A-Za-z ]+)",

            r"(?:i am)\s+([A-Za-z ]+)",

            r"(?:i'm)\s+([A-Za-z ]+)",

            r"(?:this is)\s+([A-Za-z ]+)",

            r"(?:name is)\s+([A-Za-z ]+)",
        ]

        for pattern in name_patterns:

            match = re.search(
                pattern,
                text,
                re.IGNORECASE,
            )

            if match:

                data["patient_name"] = (
                    match.group(1)
                    .strip()
                    .title()
                )

                break

        # If the user's message looks like a plain name (no phone, no common phrases)
        # treat the whole thing as their name
        if not data["patient_name"] and not data["phone"]:
            # Check it's not a symptom/concern phrase
            skip_phrases = [
                "i have", "i've", "i am", "i'm", "i feel", "my", "hello",
                "hi", "hey", "thanks", "thank", "bye", "goodbye", "yes", "no",
                "symptom", "pain", "ache", "fever", "cough", "chest", "head",
                "stomach", "back", "skin", "eye", "ear", "nose", "throat",
                "book", "appointment", "booking", "schedule", "department",
                "doctor", "dr", "view", "show", "available",
            ]
            words = text.split()
            if (
                len(words) <= 4  # "John Doe" → 2 words, safe
                and not any(text.lower().startswith(p) for p in skip_phrases)
            ):
                # First word capitalized looks like a name
                candidate = text.strip().title()
                if candidate and len(candidate) > 1:
                    data["patient_name"] = candidate

        return data
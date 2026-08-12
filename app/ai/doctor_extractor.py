import re


class DoctorExtractor:
    """
    Extract doctor names from natural language.

    Examples:
    ------------------------
    Book appointment with Dr Hamza
    I want to see Dr. Ali
    Book me with Hamza
    Appointment with doctor Ahmed
    Dr. Dr. Sara Khan      (button tap with repeated prefix)
    """

    @staticmethod
    def extract(message: str):

        text = message.strip()
        if not text:
            return None

        # Collapse repeated Dr./doctor prefixes: "Dr. Dr. Sara Khan" -> "Sara Khan"
        text = re.sub(r"\b(?:dr\.?\s+|doctor\s+)", "", text, flags=re.IGNORECASE)

        # Name token: starts with a letter, allows digits and _ . - ' (e.g. "dr_hafsa")
        TOKEN = r"[A-Za-z][A-Za-z0-9_.\-']*"

        patterns = [
            rf"(?:book\s+(?:an\s+)?appointment\s+)?(?:with|see)\s+({TOKEN}(?:\s+{TOKEN}){{0,2}})",
            rf"^({TOKEN}(?:\s+{TOKEN}){{0,2}})$",
        ]

        for pattern in patterns:

            match = re.search(
                pattern,
                text,
                re.IGNORECASE,
            )

            if match:

                return match.group(1)

        return None

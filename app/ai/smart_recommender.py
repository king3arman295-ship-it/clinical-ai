import re
from typing import Dict, Optional
from sqlalchemy.orm import Session

class SmartDoctorRecommender:
    """
    Intelligently recommends doctors based on symptoms, department, experience, and qualifications.
    """
    
    # Symptom to Department/Specialization mapping
    SYMPTOM_DEPARTMENT_MAP = {
        # Cardiology
        "heart": "Cardiology",
        "chest pain": "Cardiology",
        "chest tightness": "Cardiology",
        "palpitations": "Cardiology",
        "blood pressure": "Cardiology",
        "hypertension": "Cardiology",
        "cardiac": "Cardiology",
        "shortness of breath": "Cardiology",
        "difficulty breathing": "Cardiology",
        "chest discomfort": "Cardiology",
        "irregular heartbeat": "Cardiology",
        "heart attack": "Cardiology",
        # Pain in the left arm/hand can be a heart warning sign.
        "left hand pain": "Cardiology",
        "pain in left hand": "Cardiology",
        "left arm pain": "Cardiology",
        "pain in left arm": "Cardiology",
        
        # Orthopedics
        "bone": "Orthopedics",
        "joint": "Orthopedics",
        "fracture": "Orthopedics",
        "arthritis": "Orthopedics",
        "back pain": "Orthopedics",
        "knee pain": "Orthopedics",
        "spine": "Orthopedics",
        "neck pain": "Orthopedics",
        "shoulder": "Orthopedics",
        "muscle": "Orthopedics",
        "ligament": "Orthopedics",
        "sports injury": "Orthopedics",
        "osteoporosis": "Orthopedics",
        "sprain": "Orthopedics",
        "dislocation": "Orthopedics",
        
        # Pediatrics
        "child": "Pediatrics",
        "baby": "Pediatrics",
        "infant": "Pediatrics",
        "vaccination": "Pediatrics",
        "kids": "Pediatrics",
        "newborn": "Pediatrics",
        "growth": "Pediatrics",
        "adolescent": "Pediatrics",
        "toddler": "Pediatrics",
        "developmental": "Pediatrics",
        
        # Neurology
        "brain": "Neurology",
        "headache": "Neurology",
        "migraine": "Neurology",
        "seizure": "Neurology",
        "memory": "Neurology",
        "neurological": "Neurology",
        "stroke": "Neurology",
        "dizziness": "Neurology",
        "vertigo": "Neurology",
        "tremor": "Neurology",
        "parkinson": "Neurology",
        "numbness": "Neurology",
        "tingling": "Neurology",
        "paralysis": "Neurology",
        "alzheimer": "Neurology",
        
        # Dermatology
        "skin": "Dermatology",
        "rash": "Dermatology",
        "acne": "Dermatology",
        "eczema": "Dermatology",
        "psoriasis": "Dermatology",
        "hair": "Dermatology",
        "mole": "Dermatology",
        "warts": "Dermatology",
        "itching": "Dermatology",
        "infection skin": "Dermatology",
        "allergy skin": "Dermatology",
        "fungal": "Dermatology",
        
        # Gastroenterology
        "stomach": "Gastroenterology",
        "digestive": "Gastroenterology",
        "abdomen": "Gastroenterology",
        "constipation": "Gastroenterology",
        "diarrhea": "Gastroenterology",
        "nausea": "Gastroenterology",
        "vomiting": "Gastroenterology",
        "liver": "Gastroenterology",
        "pancreas": "Gastroenterology",
        "gallbladder": "Gastroenterology",
        "ulcer": "Gastroenterology",
        "acidity": "Gastroenterology",
        "heartburn": "Gastroenterology",
        "indigestion": "Gastroenterology",
        "bloating": "Gastroenterology",
        "ibs": "Gastroenterology",
        "colon": "Gastroenterology",
        
        # Ophthalmology
        "eye": "Ophthalmology",
        "vision": "Ophthalmology",
        "blind": "Ophthalmology",
        "cataract": "Ophthalmology",
        "glaucoma": "Ophthalmology",
        "blurred vision": "Ophthalmology",
        "glasses": "Ophthalmology",
        "conjunctivitis": "Ophthalmology",
        
        # ENT
        "ear": "ENT",
        "nose": "ENT",
        "throat": "ENT",
        "hearing": "ENT",
        "sinus": "ENT",
        "tonsil": "ENT",
        "voice": "ENT",
        "adenoid": "ENT",
        "allergic": "ENT",
        "sneeze": "ENT",
        "congestion": "ENT",
        "earache": "ENT",
        "runny nose": "ENT",
        
        # Psychiatry
        "anxiety": "Psychiatry",
        "anxious": "Psychiatry",
        "depression": "Psychiatry",
        "depressed": "Psychiatry",
        "mental": "Psychiatry",
        "stress": "Psychiatry",
        "insomnia": "Psychiatry",
        "bipolar": "Psychiatry",
        "ocd": "Psychiatry",
        "panic": "Psychiatry",
        "phobia": "Psychiatry",
        "addiction": "Psychiatry",
        "adhd": "Psychiatry",
        "trauma": "Psychiatry",
        "counseling": "Psychiatry",
        
        # Endocrinology
        "diabetes": "Endocrinology",
        "thyroid": "Endocrinology",
        "hormone": "Endocrinology",
        "pituitary": "Endocrinology",
        "obesity": "Endocrinology",
        "weight gain": "Endocrinology",
        "cholesterol": "Endocrinology",
        "metabolism": "Endocrinology",
        
        # General Medicine
        "fever": "General Medicine",
        "cold": "General Medicine",
        "cough": "General Medicine",
        "flu": "General Medicine",
        "checkup": "General Medicine",
        "general checkup": "General Medicine",
        "routine": "General Medicine",
        "fatigue": "General Medicine",
        "weakness": "General Medicine",
        "body ache": "General Medicine",
        "sore throat": "General Medicine",
        "flu-like": "General Medicine",
        "malaise": "General Medicine",
        "general check-up": "General Medicine",
        
        # Gynecology / Obstetrics
        "pregnancy": "Gynecology",
        "pregnant": "Gynecology",
        "menstrual": "Gynecology",
        "period": "Gynecology",
        "pap smear": "Gynecology",
        "contraception": "Gynecology",
        "uterus": "Gynecology",
        "ovary": "Gynecology",
        "breast": "Gynecology",
        "menopause": "Gynecology",
        "fertility": "Gynecology",
        
        # Urology
        "urinary": "Urology",
        "kidney": "Urology",
        "bladder": "Urology",
        "prostate": "Urology",
        "uti": "Urology",
        "urine": "Urology",

        # Extra synonyms so natural phrasing ("I have pain in my left hand")
        # still matches the same clinical keys as the exact phrase.
        "dizzy": "Neurology",
        "right arm pain": "Orthopedics",
        "right hand pain": "Orthopedics",
        "arm pain": "Orthopedics",
        "hand pain": "Orthopedics",
        "leg pain": "Orthopedics",
    }

    # Cache of precompiled per-word regexes, built once.
    _COMPILED = None

    @classmethod
    def _compiled_keywords(cls):
        """
        Build (word_count, keyword_len, word_regexes, keyword, department)
        tuples once, sorted so the most specific (most words, then longest)
        keyword is tried first. Checking multi-word keys first means
        "left arm pain" is matched before the more generic "arm pain".
        """
        if cls._COMPILED is None:
            entries = []
            for keyword, department in cls.SYMPTOM_DEPARTMENT_MAP.items():
                words = keyword.split()
                word_regexes = [re.compile(r"\b" + re.escape(w) + r"\b") for w in words]
                entries.append((len(words), len(keyword), word_regexes, keyword, department))
            entries.sort(key=lambda e: (e[0], e[1]), reverse=True)
            cls._COMPILED = entries
        return cls._COMPILED

    # "hurts"/"hurting"/"aches"/"aching" all mean the same thing clinically
    # as "pain" -- normalize them so the dictionary only needs one form.
    _PAIN_SYNONYM_RE = re.compile(r"\bhurt(?:s|ing)?\b|\bach(?:e|es|ing)\b")

    @staticmethod
    def _normalize(text: str) -> str:
        return SmartDoctorRecommender._PAIN_SYNONYM_RE.sub("pain", text)

    @staticmethod
    def detect_department_from_symptoms(symptoms: str) -> Optional[str]:
        """
        Analyze symptoms and suggest the appropriate department.

        Matching is word-boundary and order-independent: every word in a
        mapped phrase must appear somewhere in the message (as a whole
        word), so natural phrasing like "I have pain in my left hand"
        still matches the "left hand pain" / "pain in left hand" entries
        even though the exact substring isn't present. Multi-word (more
        specific) phrases are always checked before shorter/generic ones,
        so "left arm pain" is matched before the generic "arm pain".
        Common synonyms ("hurts", "hurting", "aching") are normalized to
        "pain" first so phrasing differences don't cause a missed match.
        """
        symptoms_lower = SmartDoctorRecommender._normalize(symptoms.lower())

        for _word_count, _kw_len, word_regexes, _keyword, department in (
            SmartDoctorRecommender._compiled_keywords()
        ):
            if all(rx.search(symptoms_lower) for rx in word_regexes):
                return department

        # Default to General Medicine if no specific match
        return "General Medicine"
    
    @staticmethod
    def rank_doctors(doctors: list) -> list:
        """
        Rank doctors based on experience, qualifications, and availability.
        Score: Experience (50%) + Qualification (30%) + Availability (20%)
        """
        def calculate_score(doctor):
            score = 0
            
            # Experience score (max 50 points)
            experience = doctor.experience_years or 0
            score += min(experience * 5, 50)  # 5 points per year, max 50
            
            # Qualification score (max 30 points)
            qual = (doctor.qualification or "").upper()
            if any(q in qual for q in ["FCPS", "FRCS", "MD", "MS"]):
                score += 30
            elif "MBBS" in qual:
                score += 15
            
            # Availability score (20 points if available)
            if doctor.available:
                score += 20
            
            return score
        
        # Sort by score (descending)
        ranked = sorted(doctors, key=calculate_score, reverse=True)
        return ranked
    
    @staticmethod
    def display_name(full_name: str) -> str:
        """Return a doctor's name with exactly one Dr. prefix (idempotent)."""
        name = (full_name or "").strip()
        if re.match(r"(?i)^dr\.?[\s_]", name):
            return name
        return f"Dr. {name}" if name else ""

    @staticmethod
    def format_doctor_recommendation(doctors: list, department: str) -> str:
        if not doctors:
            return f"Sorry, we don't have any {department} specialists available right now."
        ranked = SmartDoctorRecommender.rank_doctors(doctors)
        top = ranked[:3]
        lines = [f"Based on your symptoms, I recommend our {department} department."]
        lines.append("")
        for i, doc in enumerate(top, 1):
            yrs = f"{doc.experience_years} years" if doc.experience_years else ""
            fee = f"Rs. {doc.consultation_fee}" if doc.consultation_fee else ""
            details = ", ".join(filter(None, [yrs, fee]))
            lines.append(f"{i}. {SmartDoctorRecommender.display_name(doc.full_name)}{' (' + details + ')' if details else ''}")
        lines.append("")
        lines.append("Which doctor would you like to book with?")
        return "\n".join(lines)
    
    @staticmethod
    def get_doctors_by_department(db: Session, doctor_repository, department: str) -> list:
        """
        Get all doctors from a specific department/specialization.
        """
        all_doctors = doctor_repository.get_all(db)
        
        # Filter by specialization (case-insensitive, word-boundary match so
        # "urology" doesn't match a Neurologist nor "ent" a Gastroenterologist)
        department_doctors = [
            d for d in all_doctors
            if d.available
            and re.search(
                r"(?<![a-z])" + re.escape(department.lower()) + r"(?![a-z])",
                (d.specialization or "").lower(),
            )
        ]
        
        return department_doctors

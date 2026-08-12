"""Quick self-check: _resume_booking resumes from the furthest point reached."""
import sys
sys.path.insert(0, ".")

from app.ai.enhanced_agent import EnhancedAIAgent


class FakeDoctor:
    id = 1
    full_name = "Test Doctor"
    specialization = "cardiology"
    experience_years = 5
    consultation_fee = 1000
    available = True
    qualification = "MBBS"
    gender = "male"
    specializations = None


class FakeDocRepo:
    def get_by_id(self, db, doc_id):
        return FakeDoctor()


agent = EnhancedAIAgent.__new__(EnhancedAIAgent)
agent.doctor_repository = FakeDocRepo()
agent._get_doctor_available_days = lambda db, doc: ["Monday", "Friday"]
agent._format_doctor_available_days = lambda db, doc: "Monday, Friday"
agent._get_available_time_slots = lambda db, did, day, date: ["09:00", "09:30"]


# 1. Confirmation stage (all fields filled) -> confirmation, not doctor list
state = {
    "patient_name": "harry",
    "doctor_id": 1,
    "appointment_day": "friday",
    "appointment_date": "2026-07-31",
    "appointment_time": "20:30",
    "appointment_type": "video",
    "reason": "Chest / Heart",
    "suggested_department": "cardiology",
    "recommended_doctors": [1],
}
result = agent._resume_booking(None, "sess_test", state)
assert "Please confirm your appointment" in result["response"], result["response"]
assert result["suggestions"] == ["Yes - Confirm", "No - Make Changes"], result
print("OK 1: confirmation-stage resume shows confirmation")

# 2. Day+time picked, no type -> ask consultation type
state2 = dict(state)
state2.pop("appointment_type")
result2 = agent._resume_booking(None, "sess_test", state2)
assert "consultation" in result2["response"].lower(), result2["response"]
assert result2["suggestions"] == ["Physical Visit", "Video Consultation"], result2
print("OK 2: resume lands on consultation type")

# 3. Day picked, no time -> ask time slots
state3 = dict(state)
state3.pop("appointment_time")
result3 = agent._resume_booking(None, "sess_test", state3)
assert "slots" in result3["response"].lower(), result3["response"]
assert result3["suggestions"] == ["09:00", "09:30"], result3
print("OK 3: resume lands on time slots")

# 4. Only doctor picked -> ask day
state4 = {"doctor_id": 1}
result4 = agent._resume_booking(None, "sess_test", state4)
assert "Which day works best" in result4["response"], result4["response"]
assert result4["suggestions"] == ["Monday", "Friday"], result4
print("OK 4: resume lands on day selection")

# 5. Only department/recommendations -> show doctor list
state5 = {"suggested_department": "cardiology", "recommended_doctors": [1]}
result5 = agent._resume_booking(None, "sess_test", state5)
assert "Dr. Test Doctor" in result5["response"], result5["response"]
print("OK 5: resume lands on doctor recommendations")

print("\nAll resume-order checks passed.")

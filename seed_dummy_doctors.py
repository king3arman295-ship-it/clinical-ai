import random
from datetime import time

from sqlalchemy.orm import Session

from app.core.database import Base, engine
from app.models.doctor import Doctor
from app.models.user import User
from app.models.doctor_schedule import DoctorSchedule
from app.auth.security import hash_password

random.seed(42)

PASSWORD = "Doctor@123"

DOCTORS = [
    ("Dr. Zain Ali", "Cardiology", "FCPS Cardiology", "dr_zain"),
    ("Dr. Sara Khan", "Neurology", "MD Neurology", "dr_sara"),
    ("Dr. Hamza Raza", "Gastroenterology", "FCPS Gastroenterology", "dr_hamza"),
    ("Dr. Bilal Hussain", "Orthopedics", "MBBS, FCPS Ortho", "dr_bilal"),
    ("Dr. Ayesha Siddiqui", "Dermatology", "FCPS Dermatology", "dr_ayesha"),
    ("Dr. Usman Tariq", "General Medicine", "MBBS, FCPS Medicine", "dr_usman"),
    ("Dr. Imran Qureshi", "Urology", "FCPS Urology", "dr_imran"),
    ("Dr. Fatima Noor", "Psychiatry", "MD Psychiatry", "dr_fatima"),
    ("Dr. Hina Malik", "Endocrinology", "MD Endocrinology", "dr_hina"),
    ("Dr. Omar Farooq", "Ophthalmology", "FCPS Ophthalmology", "dr_omar"),
    ("Dr. Nadia Akhtar", "ENT", "FCPS ENT", "dr_nadia"),
    ("Dr. Kamran Sheikh", "Pediatrics", "FCPS Pediatrics", "dr_kamran"),
    ("Dr. Rabia Chaudhry", "Gynecology", "FCPS Obstetrics & Gynecology", "dr_rabia"),
    ("Dr. Tariq Mehmood", "General Medicine", "MBBS, FCPS Medicine", "dr_tariq"),
    ("Dr. Asad Iqbal", "General Medicine", "MBBS, FCPS Medicine", "dr_asad"),
    ("Dr. Umar Farhan", "Cardiology", "FCPS Cardiology", "dr_umar"),
    ("Dr. Danish Ali", "Orthopedics", "MBBS, FCPS Ortho", "dr_danish"),
    ("Dr. Maryam Shah", "Dermatology", "FCPS Dermatology", "dr_maryam"),
]

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]


def random_schedules(doctor_id):
    days = random.sample(WEEKDAYS, k=random.randint(3, 5))
    schedules = []
    for day in days:
        start_h = random.randint(9, 11)
        start_min = random.choice([0, 30])
        end_h = random.randint(16, 18)
        end_min = random.choice([0, 30])
        schedules.append(
            DoctorSchedule(
                doctor_id=doctor_id,
                day_of_week=day,
                start_time=time(start_h, start_min),
                end_time=time(end_h, end_min),
                slot_duration=30,
                is_available=True,
            )
        )
    return schedules


def main():
    session = Session(engine)
    created = []
    try:
        for full_name, specialization, qualification, username in DOCTORS:
            if session.query(User).filter(User.username == username).first():
                print(f"SKIP {username} (already exists)")
                continue

            email = f"{username}@lumina.test"
            doctor = Doctor(
                full_name=full_name,
                specialization=specialization,
                qualification=qualification,
                phone=f"+92{random.randint(3000000000, 3999999999)}",
                email=email,
                consultation_fee=random.choice([1500, 2000, 2500, 3000]),
                experience_years=random.randint(4, 18),
                available=True,
            )
            session.add(doctor)
            session.flush()

            session.add(
                User(
                    username=username,
                    email=email,
                    hashed_password=hash_password(PASSWORD),
                    role="doctor",
                    doctor_id=doctor.id,
                )
            )

            for sched in random_schedules(doctor.id):
                session.add(sched)

            created.append((username, full_name, specialization, doctor.id))
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    print(f"\nCreated {len(created)} doctors. Login password for all: {PASSWORD}")
    for username, name, spec, did in created:
        print(f"  username={username:<12} name={name:<24} {spec} (doctor_id={did})")


if __name__ == "__main__":
    main()

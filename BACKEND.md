# 🏥 Clinic AI Assistant — Backend Documentation

> **Stack:** FastAPI · PostgreSQL · SQLAlchemy · Alembic · Python 3.12  
> **Server:** `uvicorn app.main:app --reload`  
> **Base URL:** `http://localhost:8000`  
> **Docs:** `http://localhost:8000/docs`

---

## 📁 Project Structure

```
clinic-ai/
├── app/
│   ├── main.py                  # FastAPI app entry point
│   ├── ai/                      # AI Receptionist engine
│   │   ├── agent.py             # Core conversational agent (state machine)
│   │   ├── ai_service.py        # Bridge between API and Agent
│   │   ├── intent_detector.py   # Detects user intent (book/cancel/view)
│   │   ├── extractor.py         # Extracts appointment date/time
│   │   ├── doctor_extractor.py  # Extracts doctor name from message
│   │   ├── patient_extractor.py # Extracts patient name & phone
│   │   ├── session_state.py     # In-memory session state per session_id
│   │   ├── memory.py            # Conversation message history
│   │   ├── llm.py               # LLM client wrapper
│   │   ├── prompt.py            # System prompt manager
│   │   └── tool_registry.py     # Registered AI tools
│   ├── api/v1/                  # REST API routes
│   │   ├── ai.py                # AI chat endpoints
│   │   ├── auth.py              # Register / Login
│   │   ├── patients.py          # Patient CRUD
│   │   ├── doctors.py           # Doctor CRUD
│   │   ├── appointments.py      # Appointment CRUD
│   │   ├── doctor_schedule.py   # Doctor schedule CRUD
│   │   └── dashboard.py         # Dashboard stats
│   ├── models/                  # SQLAlchemy ORM models
│   ├── schemas/                 # Pydantic request/response schemas
│   ├── services/                # Business logic layer
│   ├── repositories/            # Data access layer
│   ├── auth/                    # JWT auth & role guards
│   ├── core/                    # DB engine, logger, UoW, exception handler
│   ├── common/                  # ServiceResult wrapper
│   └── exceptions/              # Custom exceptions
├── alembic/                     # DB migrations
├── .env                         # Environment variables
└── requirements.txt
```

---

## 🔌 API Endpoints

### 🤖 AI Receptionist — `/ai`

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `POST` | `/ai/chat` | Public | Chat with AI receptionist |
| `DELETE` | `/ai/conversation/{session_id}` | Public | Clear conversation history |

#### `POST /ai/chat`
**Query Params:**
- `session_id` (string) — unique identifier for the conversation session
- `message` (string) — user's message

**Response:**
```json
{
  "response": "May I have your full name?",
  "session_id": "test123"
}
```

**AI Conversation Flow (Book Appointment):**
```
User: "I want to book an appointment"
  → AI asks: name?
User: "My name is Saad"
  → AI asks: phone?
User: "03239895694"
  → Patient created/found in DB
  → AI asks: doctor & date/time?
User: "I want Dr Haza on 2026-08-25 at 10:30"
  → Appointment saved in DB
  → AI confirms booking
```

---

### 🔐 Authentication — `/auth`

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `POST` | `/auth/register` | Public | Register new user |
| `POST` | `/auth/login` | Public | Login (returns JWT token) |

**Roles:** `admin`, `receptionist`, `doctor`

#### Register Body:
```json
{
  "username": "admin",
  "email": "admin@clinic.com",
  "password": "secret123",
  "role": "admin"
}
```

#### Login (OAuth2 form data):
- `username`, `password`
- Returns: `{ "access_token": "...", "token_type": "bearer" }`

---

### 👥 Patients — `/patients`

| Method | Endpoint | Roles | Description |
|--------|----------|-------|-------------|
| `POST` | `/patients/` | admin, receptionist | Create patient |
| `GET` | `/patients/` | admin, receptionist, doctor | Get all patients |
| `GET` | `/patients/{id}` | admin, receptionist, doctor | Get patient by ID |
| `PUT` | `/patients/{id}` | admin, receptionist | Update patient |
| `DELETE` | `/patients/{id}` | admin | Delete patient |

#### Patient Schema:
```json
{
  "name": "Saad",
  "phone": "03239895694",
  "email": "saad@email.com"
}
```

---

### 🩺 Doctors — `/doctors`

| Method | Endpoint | Roles | Description |
|--------|----------|-------|-------------|
| `POST` | `/doctors/` | admin | Create doctor |
| `GET` | `/doctors/` | Public | Get all doctors |
| `GET` | `/doctors/{id}` | Public | Get doctor by ID |
| `PUT` | `/doctors/{id}` | admin | Update doctor |
| `DELETE` | `/doctors/{id}` | admin | Delete doctor |

#### Doctor Schema:
```json
{
  "full_name": "Dr. Haza",
  "specialization": "Cardiology",
  "qualification": "MBBS, MD",
  "phone": "0300-1234567",
  "email": "haza@clinic.com",
  "consultation_fee": 1500,
  "experience_years": 10,
  "available": true
}
```

---

### 📅 Appointments — `/appointments`

| Method | Endpoint | Roles | Description |
|--------|----------|-------|-------------|
| `POST` | `/appointments/` | admin, receptionist | Book appointment |
| `GET` | `/appointments/` | admin, receptionist, doctor | Get all appointments |
| `GET` | `/appointments/{id}` | admin, receptionist, doctor | Get appointment by ID |
| `PUT` | `/appointments/{id}` | admin, receptionist | Update appointment |
| `DELETE` | `/appointments/{id}` | admin | Delete appointment |

#### Appointment Schema:
```json
{
  "patient_id": 1,
  "doctor_id": 2,
  "appointment_date": "2026-08-25",
  "appointment_time": "10:30:00",
  "reason": "Routine checkup",
  "notes": "First visit"
}
```

---

### 🗓️ Doctor Schedules — `/doctor-schedules`

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `POST` | `/doctor-schedules/` | Public | Create schedule |
| `GET` | `/doctor-schedules/` | Public | Get all schedules |
| `GET` | `/doctor-schedules/{id}` | Public | Get schedule by ID |
| `GET` | `/doctor-schedules/doctor/{doctor_id}` | Public | Get doctor's schedule |
| `PUT` | `/doctor-schedules/{id}` | Public | Update schedule |
| `DELETE` | `/doctor-schedules/{id}` | Public | Delete schedule |

---

### 📊 Dashboard — `/dashboard`

| Method | Endpoint | Roles | Description |
|--------|----------|-------|-------------|
| `GET` | `/dashboard/stats` | admin, receptionist, doctor | Overview stats |
| `GET` | `/dashboard/recent-patients` | admin, receptionist | Recent patients list |
| `GET` | `/dashboard/available-doctors` | admin, receptionist, doctor | Available doctors |
| `GET` | `/dashboard/upcoming` | admin, receptionist, doctor | Upcoming appointments |

---

## 🤖 AI Receptionist — Architecture

```
User Message
    ↓
IntentDetector       → detect intent: book_appointment / cancel / view / chat
    ↓
SessionState         → in-memory dict per session_id (persists across turns)
    ↓
PatientExtractor     → extract name, phone from message
    ↓
AppointmentExtractor → extract date, time from message
    ↓
DoctorExtractor      → extract doctor name → lookup in DB
    ↓
PatientService       → find_or_create_patient() → returns Patient ORM object
    ↓
AppointmentService   → book_appointment() → saves to DB
    ↓
ConversationMemory   → stores chat history for normal LLM chat turns
    ↓
LLM (fallback)       → handles general questions via system prompt
```

### Session State Keys (book_appointment flow):

| Key | Type | Description |
|-----|------|-------------|
| `intent` | str | Locked intent for multi-turn conversation |
| `patient_name` | str | Extracted patient name |
| `phone` | str | Extracted phone number |
| `email` | str/None | Optional email |
| `doctor_id` | int | Resolved doctor ID from DB |
| `doctor_name` | str | Resolved doctor full name |
| `appointment_date` | date | Parsed appointment date |
| `appointment_time` | time | Parsed appointment time |
| `patient_id` | int | Created/found patient ID |

---

## 🗄️ Database Models

### Patient
| Field | Type | Notes |
|-------|------|-------|
| id | Integer | PK |
| name | String | |
| phone | String | Unique |
| email | String | Unique, Nullable |

### Doctor
| Field | Type | Notes |
|-------|------|-------|
| id | Integer | PK |
| full_name | String | |
| specialization | String | |
| qualification | String | Nullable |
| phone | String | Nullable |
| email | String | Nullable |
| consultation_fee | Integer | Nullable |
| experience_years | Integer | Nullable |
| available | Boolean | Default True |

### Appointment
| Field | Type | Notes |
|-------|------|-------|
| id | Integer | PK |
| patient_id | FK | → Patient |
| doctor_id | FK | → Doctor |
| appointment_date | Date | |
| appointment_time | Time | |
| status | String | Default: `scheduled` |
| reason | String | Nullable |
| notes | String | Nullable |
| created_at | DateTime | |

### User
| Field | Type | Notes |
|-------|------|-------|
| id | Integer | PK |
| username | String | Unique |
| email | String | Unique |
| password | String | Hashed |
| role | String | admin/receptionist/doctor |

---

## 🔧 Bug Fixed

**File:** `app/ai/agent.py` — Line 162

A trailing comma after `find_or_create_patient(...)` wrapped the `Patient` in a `tuple`:
```python
# Before (broken) — patient was a tuple (Patient,)
patient = self.patient_service.find_or_create_patient(...),

# After (fixed) — patient is a Patient object
patient = self.patient_service.find_or_create_patient(...)
```
Caused: `AttributeError: 'tuple' object has no attribute 'id'` ✅ Fixed.

---

## 🚀 Running the Backend

```bash
# Activate virtual environment
venv\Scripts\activate

# Run dev server
uvicorn app.main:app --reload

# Swagger docs
http://localhost:8000/docs
```

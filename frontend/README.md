# Lumina Health Frontend

Redesigned to match the Lumina Health Figma design — same FastAPI backend integration,
completely new look (Fraunces serif + Inter, sage/charcoal/cream palette, pill buttons).
Every element id/class that js/*.js relies on was kept identical, so no backend or
JS logic changed — only css/style.css, css/landing.css and the static markup/branding
in the .html files.

## Features

### Public Website
- Modern hospital homepage with hero section
- Services showcase
- Doctors directory with real-time availability
- Contact information
- Responsive design for mobile/tablet/desktop

### Patient Portal
- ✅ Book appointments (physical & video consultations)
- ✅ AI-powered appointment assistant with file upload
- ✅ Video consultations (Agora integration)
- ✅ View appointment history
- ✅ Upload and access medical records (EMR)
- ✅ Real-time notifications support

### Admin/Receptionist Portal
- ✅ Complete dashboard with statistics
- ✅ Manage doctors (add, edit, delete, availability)
- ✅ View all patients and their EMR
- ✅ Manage appointments (view, update status, delete)
- ✅ View doctor schedules
- ✅ Search and filter functionality

### Authentication
- ✅ Login for patients, doctors, admin, receptionist
- ✅ Patient registration
- ✅ JWT token-based authentication
- ✅ Role-based access control
- ✅ Auto-redirect to appropriate portal

## Backend Integration

Fully connected to your FastAPI backend at `http://localhost:8000`:

- `/auth/login` - User authentication
- `/auth/patient-register` - Patient registration
- `/doctors/` - Doctor management
- `/patients/` - Patient management
- `/appointments/` - Appointment booking & management
- `/doctor-schedules/` - Schedule management
- `/ai/chat` - AI assistant with file upload
- `/appointments/{id}/join/patient` - Video call joining
- `/appointments/{id}/join/doctor` - Doctor video call joining
- `/appointments/{id}/end` - End video consultation
- `/emr/patients/{id}/reports` - Medical records
- `/emr/reports/upload` - Upload medical documents
- `/emr/reports/{id}/download` - Download medical files

## Installation

1. Extract the zip file
2. Serve the files using any HTTP server:

```bash
# Using Python
python -m http.server 8080

# Using Node.js
npx http-server -p 8080

# Using PHP
php -S localhost:8080
```

3. Open `http://localhost:8080` in your browser

4. Make sure your FastAPI backend is running at `http://localhost:8000`

## File Structure

```
hospital-frontend/
├── index.html              # Homepage
├── patient-portal.html     # Patient portal
├── admin-portal.html       # Admin/Receptionist dashboard
├── login.html              # Login & registration
├── css/
│   └── style.css          # All styles
├── js/
│   ├── config.js          # API configuration & utilities
│   ├── home.js            # Homepage functionality
│   ├── patient-portal.js  # Patient portal logic
│   ├── admin-portal.js    # Admin dashboard logic
│   └── login.js           # Authentication logic
└── README.md              # This file
```

## Usage

### For Patients
1. Visit the homepage
2. Click "Patient Portal" or "Sign In"
3. Register a new patient account
4. Login with your credentials
5. Book appointments, chat with AI assistant, join video calls, upload medical records

### For Doctors
1. Login with doctor credentials (created by admin)
2. Access doctor portal (role-based redirect)
3. View patients, appointments, schedules
4. Join video consultations

### For Admin/Receptionist
1. Login with admin credentials
2. Access admin dashboard
3. Manage doctors, patients, appointments
4. View all schedules and statistics

## Configuration

The API base URL is auto-detected:
- `file://` or `localhost` → `http://localhost:8000`
- Other hosts → `http://{current-host}:8000`

To change the API URL, edit `js/config.js`:

```javascript
const API_CONFIG = 'http://your-backend-url:8000';
```

## Features by Role

| Feature | Public | Patient | Doctor | Admin |
|---------|--------|---------|--------|-------|
| View Doctors | ✅ | ✅ | ✅ | ✅ |
| Book Appointments | ❌ | ✅ | ❌ | ✅ |
| AI Chat Assistant | ❌ | ✅ | ❌ | ❌ |
| Video Consultations | ❌ | ✅ | ✅ | ❌ |
| View Own Records | ❌ | ✅ | ❌ | ❌ |
| Upload Records | ❌ | ✅ | ✅ | ✅ |
| Manage Doctors | ❌ | ❌ | ❌ | ✅ |
| Manage Patients | ❌ | ❌ | ✅ | ✅ |
| View All Appointments | ❌ | ❌ | ✅ | ✅ |
| Manage Schedules | ❌ | ❌ | ✅ | ✅ |

## Browser Requirements

- Modern browser (Chrome, Firefox, Safari, Edge)
- JavaScript enabled
- Camera/microphone access for video consultations
- Must be served over HTTP/HTTPS (not file://) for full functionality

## Video Consultations

Video calls use Agora RTC. Requirements:
- HTTPS or localhost (camera/mic permissions)
- Appointment must have `appointment_type: "video"`
- Backend must provide Agora credentials via join endpoints

## Responsive Design

- Mobile-first approach
- Breakpoints: 640px, 968px, 1200px
- Touch-friendly buttons and inputs
- Collapsible mobile navigation

## Default Test Users

Create these users in your backend for testing:

**Patient:**
- Register via the frontend patient registration form

**Admin:**
- Create via backend `/auth/register` with role="admin"

**Doctor:**
- Create doctor profile via admin panel
- Link to user account with `user_id` field

## Support

For issues or questions, contact your development team.

---

Built with ❤️ for Lumina Health

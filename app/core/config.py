from dotenv import load_dotenv
import os

load_dotenv()

# Clinic local timezone for all scheduling decisions (overridable via env).
# The server may run in a different zone (e.g. UTC / US Pacific).
TIMEZONE = os.getenv("TIMEZONE", "Asia/Karachi")

# ---------------------------------
# Database
# ---------------------------------

DATABASE_URL = os.getenv("DATABASE_URL")

# ---------------------------------
# Agora
# ---------------------------------

AGORA_APP_ID = os.getenv("AGORA_APP_ID")
AGORA_APP_CERTIFICATE = os.getenv("AGORA_APP_CERTIFICATE")
AGORA_TOKEN_EXPIRE= os.getenv("AGORA_TOKEN_EXPIRE")

# ---------------------------------
# Firebase
# ---------------------------------

FIREBASE_CREDENTIALS = os.getenv("FIREBASE_CREDENTIALS")
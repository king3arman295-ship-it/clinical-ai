import os
import json
import base64
import firebase_admin

from firebase_admin import credentials
from firebase_admin import messaging

from app.core.logger import logger

_FIREBASE_INITIALIZED = False

if not firebase_admin._apps:
    # Resolve path relative to this file's project root
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    sa_path = os.path.join(base_dir, "firebase", "service-account.json")

    cred = None
    if os.path.exists(sa_path):
        # Local dev: the gitignored file is present on disk.
        cred = credentials.Certificate(sa_path)
    else:
        # Deployed environments (e.g. Railway): the file is never pushed
        # since it's gitignored (it's a private key). Fall back to a
        # base64-encoded copy stored in an env var instead.
        sa_b64 = os.environ.get("FIREBASE_SERVICE_ACCOUNT_B64")
        if sa_b64:
            try:
                sa_info = json.loads(base64.b64decode(sa_b64))
                cred = credentials.Certificate(sa_info)
            except Exception as e:
                logger.error(f"Failed to parse FIREBASE_SERVICE_ACCOUNT_B64: {e}")

    if cred:
        firebase_admin.initialize_app(cred)
        _FIREBASE_INITIALIZED = True
        logger.info("Firebase Admin SDK initialized successfully.")
    else:
        logger.warning(
            f"Firebase service account not found at {sa_path} and "
            "FIREBASE_SERVICE_ACCOUNT_B64 env var is not set. Notifications disabled."
        )


def send_notification(
    token: str,
    title: str = None,
    body: str = None,
    data: dict = None,
):
    """
    Sends an FCM push notification.

    If `title`/`body` are given, a normal display notification is sent
    (used for reminders etc. — the browser/OS renders it automatically).

    If only `data` is given (title/body left as None), a data-only message
    is sent instead. Browsers never auto-display a data-only message —
    the service worker's onBackgroundMessage (or the page's onMessage, in
    the foreground case) must call showNotification() itself. This is what
    lets the incoming-call notification carry Accept/Decline action
    buttons, which is only possible for notifications shown that way.
    """
    if not _FIREBASE_INITIALIZED:
        logger.warning("Firebase not initialized. Cannot send notification.")
        return None

    # FCM data payloads must be a flat dict of string -> string.
    string_data = {str(k): str(v) for k, v in (data or {}).items()}

    message = messaging.Message(
        notification=(
            messaging.Notification(title=title, body=body)
            if title or body else None
        ),
        data=string_data or None,
        token=token,
    )

    try:
        return messaging.send(message)
    except Exception as e:
        # A DNS/connection failure reaching fcm.googleapis.com (no internet
        # access, DNS resolver down, firewall/VPN blocking Google APIs, etc.)
        # looks nothing like a bug in the notification logic — the call got
        # all the way to attempting delivery and failed on the network hop.
        # Log that distinction clearly (and only here, once) instead of
        # letting it re-raise into the generic "Failed to send FCM
        # notification" logging every caller already does.
        text = str(e)
        if "NameResolutionError" in text or "getaddrinfo failed" in text or "Failed to resolve" in text:
            logger.error(
                "Could not reach fcm.googleapis.com — this server has no "
                "network/DNS route to Google's FCM service right now (check "
                "internet connectivity, DNS, firewall/VPN on this machine). "
                f"Original error: {e}"
            )
            return None
        raise
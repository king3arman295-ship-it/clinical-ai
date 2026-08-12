import { initializeApp } from "https://www.gstatic.com/firebasejs/12.0.0/firebase-app.js";
import {
    getMessaging,
    getToken,
    onMessage
} from "https://www.gstatic.com/firebasejs/12.0.0/firebase-messaging.js";

const firebaseConfig = {
    apiKey: "AIzaSyCp6VEeW2KRUfwL9P0mNx1ZrPe_zBOVaEo",
    authDomain: "clinic-ai-a6a9d.firebaseapp.com",
    projectId: "clinic-ai-a6a9d",
    storageBucket: "clinic-ai-a6a9d.firebasestorage.app",
    messagingSenderId: "153793318399",
    appId: "1:153793318399:web:6a6f3b43809d596aa76bca",
    measurementId: "G-YQRL5LDSKQ"
};

// Auto-detect the API host the same way config.js does
const API = (function () {
    const { protocol, hostname } = window.location;
    if (!hostname || protocol === "file:" || hostname === "localhost" || hostname === "127.0.0.1") {
        return "http://localhost:8000";
    }
    return `${protocol}//${hostname}:8000`;
})();
const VAPID_KEY = "BJDSe0Sc_M5mrP82gD7b3KjN0SmGbqY87fhM36jPO8_RIeNUtqlM7bXiUO5NcO0u2gOgDXJ0SoRCKk4Yo1B2yJQ";

const app = initializeApp(firebaseConfig);
const messaging = getMessaging(app);

// Cached in-memory so we only request permission / fetch the token once
// per page load, no matter how many times something asks for it.
let cachedTokenPromise = null;
let serviceWorkerRegistrationPromise = null;

/**
 * Firebase Messaging needs this worker to receive notifications while the
 * page is in the background. Keeping one shared promise also prevents the
 * login flow from racing the worker registration.
 */
function getMessagingServiceWorkerRegistration() {
    if (!serviceWorkerRegistrationPromise) {
        serviceWorkerRegistrationPromise = navigator.serviceWorker.register(
            "/firebase-messaging-sw.js"
        );
    }

    return serviceWorkerRegistrationPromise;
}

/**
 * Requests notification permission (if not already granted) and returns
 * the FCM token.
 *
 * @param {boolean} [allowPrompt=false] Whether this call is allowed to
 *   actually pop the native permission dialog. Chrome (and other browsers)
 *   auto-downgrade a site to permanently "Block" once its permission prompt
 *   has been shown automatically and ignored/dismissed enough times — see
 *   https://www.chromestatus.com/feature/6443143280984064. Calling
 *   Notification.requestPermission() on every page load/login is exactly
 *   that pattern, so routine calls (login, page refresh) must pass
 *   allowPrompt=false: they'll silently pick up an already-granted
 *   permission but will NOT pop the dialog themselves. Only a call that's
 *   directly tied to the person clicking something explicit (e.g. an
 *   "Enable notifications" button) should pass true.
 */
async function getOrRequestFCMToken(allowPrompt = false) {
    if (cachedTokenPromise) return cachedTokenPromise;

    if (!("Notification" in window) || !("serviceWorker" in navigator)) {
        console.log("Browser notifications are not supported in this browser.");
        return null;
    }

    // Already decided (granted or blocked) — never prompt again either way,
    // just use whatever the answer already is.
    if (Notification.permission !== "default") {
        if (Notification.permission !== "granted") {
            console.log("Notification permission is blocked; not prompting.");
            return null;
        }
    } else if (!allowPrompt) {
        // Not yet decided, and this call isn't tied to an explicit user
        // action — skip asking rather than auto-prompting.
        console.log("Notification permission not yet granted; skipping auto-prompt.");
        return null;
    }

    cachedTokenPromise = (async () => {
        // Waiting here is waiting on the PERSON, not the network — a brand
        // new patient's very first login is the one time this native
        // dialog actually appears, and they may take a few seconds to read
        // and click it. That wait must never be capped by a timeout, or a
        // first-time user who takes a moment to click "Allow" ends up with
        // no token and no notification (works fine on every later login
        // because the browser already knows the answer by then and skips
        // the dialog entirely).
        const permission = await Notification.requestPermission();
        if (permission !== "granted") {
            console.log("Notification permission denied.");
            return null;
        }

        // From here on it's genuine network/browser-API work, so it's fine
        // — and necessary — to bound it with a timeout.
        return withTimeout(fetchTokenAfterPermissionGranted(), 8000);
    })();

    return cachedTokenPromise;
}

async function fetchTokenAfterPermissionGranted() {
    const serviceWorkerRegistration = await getMessagingServiceWorkerRegistration();
    // Make sure the worker is actually active, not merely registered —
    // registration can resolve while the worker is still installing.
    await navigator.serviceWorker.ready;

    // Right after permission is granted for the very first time, the
    // browser's push subscription isn't always ready yet — getToken()
    // can throw or resolve empty on that very first call and then work
    // fine on the next page load. A couple of short retries absorbs that
    // startup race instead of just giving up.
    let token = null;
    for (let attempt = 0; attempt < 3 && !token; attempt++) {
        try {
            token = await getToken(messaging, {
                vapidKey: VAPID_KEY,
                serviceWorkerRegistration,
            });
        } catch (e) {
            console.log(`getToken attempt ${attempt + 1} failed:`, e);
        }
        if (!token && attempt < 2) {
            await new Promise((resolve) => setTimeout(resolve, 700));
        }
    }

    window.fcmToken = token; // kept for backward compatibility with old code
    console.log("FCM Token:", token);
    return token;
}

/**
 * Races a promise against a timeout so a slow/hanging network call to
 * Google's FCM endpoints can never make the caller (e.g. the login screen)
 * wait indefinitely. Resolves to `fallback` if the timeout wins.
 */
function withTimeout(promise, ms, fallback = null) {
    return Promise.race([
        promise,
        new Promise((resolve) => setTimeout(() => resolve(fallback), ms)),
    ]);
}

/**
 * Sends the logged-in user's FCM token to the backend.
 * Used for the appointment-reminder scheduler (tied to User.fcm_token).
 *
 * This is called from two very different places:
 *   1. Right after a successful login (login.js) — pass notifyLogin=true so
 *      the backend fires the one-time "you've logged in" push.
 *   2. On every normal page load of a portal (patient/doctor/admin) so the
 *      scheduler always has a current token — these must pass
 *      notifyLogin=false (the default) or the person gets a "welcome back"
 *      notification on every refresh instead of once at login.
 *
 * Neither of these is allowed to pop the native permission dialog (see
 * getOrRequestFCMToken) — if permission hasn't been granted yet, use
 * enableNotifications() from a real button click instead.
 *
 * @param {boolean} [notifyLogin=false]
 */
async function sendFCMTokenToBackend(notifyLogin = false) {
    const clinicToken = localStorage.getItem("hospital_token");
    if (!clinicToken) {
        console.log("User not logged in yet — skipping admin FCM registration.");
        return;
    }

    const token = await getOrRequestFCMToken(false);
    if (!token) {
        console.log("FCM token not available.");
        return;
    }

    try {
        const response = await fetch(`${API}/auth/fcm-token`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                Authorization: `Bearer ${clinicToken}`,
            },
            body: JSON.stringify({ fcm_token: token, notify_login: notifyLogin }),
        });
        console.log(response.ok ? "✅ Admin FCM token saved." : "❌ Failed to save admin FCM token.");
    } catch (e) {
        console.log("❌ Error saving admin FCM token:", e);
    }
}

/**
 * Call this ONLY from a direct user click (e.g. an "Enable notifications"
 * button). This is the one place allowed to pop the native permission
 * dialog. If permission is granted, also saves the token to the backend —
 * passing notifyLogin=true since enabling notifications for the first time
 * is a good moment to confirm it worked with the welcome push.
 */
async function enableNotifications() {
    const clinicToken = localStorage.getItem("hospital_token");
    // No timeout wraps this call itself — it may legitimately wait on the
    // person clicking the native permission dialog. The network-bound work
    // inside it (service worker + token fetch) already has its own timeout;
    // see fetchTokenAfterPermissionGranted.
    const token = await getOrRequestFCMToken(true);
    if (!token) return false;

    if (clinicToken) {
        try {
            const response = await withTimeout(
                fetch(`${API}/auth/fcm-token`, {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                        Authorization: `Bearer ${clinicToken}`,
                    },
                    body: JSON.stringify({ fcm_token: token, notify_login: true }),
                }),
                4000
            );
            return !!response && response.ok;
        } catch (e) {
            console.log("❌ Error saving FCM token:", e);
            return false;
        }
    }
    return true;
}

/**
 * Registers this browser's FCM token against a specific appointment,
 * as either the patient or doctor side of the call. Call this right
 * before joining the video meeting (from joinMeetingUI in your SPA).
 *
 * @param {string|number} appointmentId
 * @param {"patient"|"doctor"} role
 */
async function registerMeetingFCMToken(appointmentId, role) {
    if (role !== "patient" && role !== "doctor") {
        console.log("registerMeetingFCMToken: role must be 'patient' or 'doctor'");
        return;
    }

    const token = await getOrRequestFCMToken();
    if (!token) {
        console.log("No FCM token available — skipping meeting token registration.");
        return;
    }

    const endpoint = role === "patient" ? "register-patient-token" : "register-doctor-token";

    try {
        const response = await fetch(`${API}/appointments/${appointmentId}/${endpoint}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ fcm_token: token }),
        });
        console.log(
            response.ok
                ? `✅ ${role} FCM token registered for appointment #${appointmentId}.`
                : `❌ Failed to register ${role} FCM token.`
        );
    } catch (e) {
        console.log(`❌ Error registering ${role} FCM token:`, e);
    }
}

// Register early, while getOrRequestFCMToken still awaits the same worker.
if ("serviceWorker" in navigator) {
    getMessagingServiceWorkerRegistration()
        .then((registration) => console.log("Firebase SW registered:", registration.scope))
        .catch((e) => console.log("Firebase SW registration failed:", e));
}

/**
 * Shows a call-style browser notification with Accept/Decline actions for
 * an incoming video call, shared between the foreground path (onMessage,
 * below) and the background path (firebase-messaging-sw.js). Regular
 * `new Notification(...)` can't carry action buttons — only a notification
 * shown via a ServiceWorkerRegistration can — so both paths go through
 * the registration, which is why this works the same whether the tab is
 * open/focused or not.
 *
 * requireInteraction keeps it on screen until the person actually taps
 * Accept/Decline instead of auto-dismissing, since a missed call is much
 * worse than a notification staying visible a little longer.
 */
async function showIncomingCallNotification(data) {
    const appointmentId = data.appointment_id;
    const doctorName = data.doctor_name || "Your doctor";
    if (!appointmentId) return;

    const registration = await getMessagingServiceWorkerRegistration();
    await registration.showNotification(`📹 Incoming video call`, {
        body: `${doctorName} is calling you now for Appointment #${appointmentId}.`,
        icon: "/favicon.ico",
        tag: `call-${appointmentId}`,
        requireInteraction: true,
        data: { type: "incoming_call", appointmentId },
        actions: [
            { action: "accept", title: "Accept" },
            { action: "decline", title: "Decline" },
        ],
    });
}

// Listen for foreground messages (tab is open and focused)
onMessage(messaging, (payload) => {
    console.log("Foreground notification received:", payload);

    if (payload.data?.type === "incoming_call") {
        showIncomingCallNotification(payload.data);
        return;
    }

    if (payload.data?.type === "bill_issued") {
        const title = payload.notification?.title || "New bill from Lumina Health";
        const body = payload.notification?.body || "A new bill is ready in My Bills.";
        if (Notification.permission === "granted") {
            new Notification(title, { body, icon: "/favicon.ico" });
        }
        // Refresh patient portal badge / list if open
        if (typeof window.refreshBillsBadge === "function") {
            window.refreshBillsBadge();
        }
        if (typeof window.Utils?.showToast === "function") {
            window.Utils.showToast(body, "success");
        }
        return;
    }

    const title = payload.notification?.title || "Lumina Health";
    const body = payload.notification?.body || "";
    if (Notification.permission === "granted") {
        new Notification(title, { body, icon: "/favicon.ico" });
    }
});

// Expose to the global scope so the non-module <script> in your SPA can call these
window.sendFCMTokenToBackend = sendFCMTokenToBackend;
window.registerMeetingFCMToken = registerMeetingFCMToken;
window.getOrRequestFCMToken = getOrRequestFCMToken;
window.enableNotifications = enableNotifications;

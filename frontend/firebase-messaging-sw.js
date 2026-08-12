importScripts("https://www.gstatic.com/firebasejs/12.0.0/firebase-app-compat.js");
importScripts("https://www.gstatic.com/firebasejs/12.0.0/firebase-messaging-compat.js");

firebase.initializeApp({
    apiKey: "AIzaSyCp6VEeW2KRUfwL9P0mNx1ZrPe_zBOVaEo",
    authDomain: "clinic-ai-a6a9d.firebaseapp.com",
    projectId: "clinic-ai-a6a9d",
    storageBucket: "clinic-ai-a6a9d.firebasestorage.app",
    messagingSenderId: "153793318399",
    appId: "1:153793318399:web:6a6f3b43809d596aa76bca",
});

const messaging = firebase.messaging();

messaging.onBackgroundMessage((payload) => {
    console.log("[firebase-messaging-sw.js] Received background message ", payload);

    // Incoming video call: data-only message (see firebase_service.py),
    // rendered as a call-style notification with Accept/Decline actions
    // instead of the default title/body display.
    if (payload.data?.type === "incoming_call") {
        const appointmentId = payload.data.appointment_id;
        const doctorName = payload.data.doctor_name || "Your doctor";
        self.registration.showNotification("📹 Incoming video call", {
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
        return;
    }

    const notificationTitle = payload.notification?.title || "Clinic AI Notification";
    const notificationOptions = {
        body: payload.notification?.body || "",
    };
    self.registration.showNotification(notificationTitle, notificationOptions);
});

// Handles taps on the notification itself (or its Accept/Decline action
// buttons). Only incoming-call notifications carry data.type ===
// "incoming_call" — anything else just closes normally.
self.addEventListener("notificationclick", (event) => {
    const data = event.notification.data || {};
    event.notification.close();

    if (data.type !== "incoming_call") return;

    // Declining just dismisses the call — the patient is never taken
    // anywhere and never gets any access to join it.
    if (event.action === "decline") return;

    // Default click or the "Accept" action both join the call.
    const appointmentId = data.appointmentId;
    const targetPath = "patient-portal.html";

    event.waitUntil(
        clients.matchAll({ type: "window", includeUncontrolled: true }).then((clientList) => {
            // Prefer an already-open patient portal tab: focus it and hand
            // it the appointment id directly instead of navigating away
            // from whatever the patient currently has open there.
            for (const client of clientList) {
                if (client.url.includes(targetPath) && "focus" in client) {
                    client.postMessage({ type: "ACCEPT_CALL", appointmentId });
                    return client.focus();
                }
            }
            // No tab open yet — open one straight to the call.
            if (clients.openWindow) {
                return clients.openWindow(`${targetPath}?autojoin=${appointmentId}`);
            }
        })
    );
});

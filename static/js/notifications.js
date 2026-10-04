/**
 * Browser Notification API Service
 */

function requestNotificationPermission() {
  if (!("Notification" in window)) {
    console.warn("Browser does not support desktop notifications.");
    return;
  }
  if (Notification.permission === "default") {
    Notification.requestPermission().then((permission) => {
      if (permission === "granted") {
        showToast("Browser medication reminders enabled!", "success");
      }
    });
  }
}

function triggerBrowserNotification(title, message, options = {}) {
  if (!("Notification" in window) || Notification.permission !== "granted") {
    return;
  }
  const defaultOptions = {
    icon: "/static/images/logo.svg",
    body: message,
    badge: "/static/images/logo.svg",
  };
  new Notification(title, { ...defaultOptions, ...options });
}

document.addEventListener("DOMContentLoaded", () => {
  const notifBtn = document.getElementById("enable-browser-notifications-btn");
  if (notifBtn) {
    if ("Notification" in window && Notification.permission === "granted") {
      notifBtn.innerText = "✓ Reminders Enabled";
      notifBtn.classList.remove("btn-outline-primary");
      notifBtn.classList.add("btn-secondary");
      notifBtn.disabled = true;
    } else {
      notifBtn.addEventListener("click", requestNotificationPermission);
    }
  }
});

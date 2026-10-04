/**
 * Dashboard Interactivity (Dose Logging, Profile switching)
 */
async function logMedicationDose(scheduleId, action) {
  try {
    const res = await fetch("/schedule/log", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ schedule_id: scheduleId, action: action })
    });
    const data = await res.json();
    if (res.ok) {
      showToast(`Dose marked as ${action.toUpperCase()}`, "success");
      const itemEl = document.getElementById(`dose-item-${scheduleId}`);
      if (itemEl) {
        itemEl.className = `dose-item ${action}`;
        const actionContainer = itemEl.querySelector(".dose-actions");
        if (actionContainer) {
          actionContainer.innerHTML = `<span class="badge ${action === 'taken' ? 'badge-verified' : 'badge-unclear'}">${action}</span>`;
        }
      }
    } else {
      showToast(data.error || "Failed to log dose", "danger");
    }
  } catch (err) {
    console.error("Dose log error:", err);
    showToast("Network error while recording dose", "danger");
  }
}

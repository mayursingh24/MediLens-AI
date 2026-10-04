/**
 * MediLens AI — Schedule Interactivity & Circadian Countdown Sentinel
 */

// Web Audio API Synthesized Medical Alert Chime (Hospital-grade soothing two-tone)
function playMedicalChime() {
  try {
    const AudioContext = window.AudioContext || window.webkitAudioContext;
    if (!AudioContext) return;
    const ctx = new AudioContext();

    const now = ctx.currentTime;
    
    // Tone 1: E5 (659.25 Hz)
    const osc1 = ctx.createOscillator();
    const gain1 = ctx.createGain();
    osc1.type = "sine";
    osc1.frequency.setValueAtTime(659.25, now);
    gain1.gain.setValueAtTime(0.2, now);
    gain1.gain.exponentialRampToValueAtTime(0.001, now + 0.3);
    osc1.connect(gain1);
    gain1.connect(ctx.destination);
    osc1.start(now);
    osc1.stop(now + 0.3);

    // Tone 2: A5 (880.00 Hz) - slightly delayed harmony
    const osc2 = ctx.createOscillator();
    const gain2 = ctx.createGain();
    osc2.type = "sine";
    osc2.frequency.setValueAtTime(880.0, now + 0.12);
    gain2.gain.setValueAtTime(0.25, now + 0.12);
    gain2.gain.exponentialRampToValueAtTime(0.001, now + 0.55);
    osc2.connect(gain2);
    gain2.connect(ctx.destination);
    osc2.start(now + 0.12);
    osc2.stop(now + 0.55);

    if (typeof showToast === "function") {
      showToast("🔔 Medical reminder chime tested successfully", "info");
    }
  } catch (e) {
    console.warn("Web Audio API not supported or blocked:", e);
  }
}

async function recordScheduleAction(scheduleId, action) {
  try {
    const res = await fetch("/schedule/log", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ schedule_id: scheduleId, action: action })
    });
    const data = await res.json();
    if (res.ok) {
      if (typeof showToast === "function") {
        showToast(`Medication logged as ${action.toUpperCase()}`, "success");
      }
      const card = document.getElementById(`sched-card-${scheduleId}`);
      if (card) {
        card.classList.remove("pending", "taken", "skipped");
        card.classList.add(action);
        
        // Update the action buttons
        const actionsDiv = card.querySelector(".dose-actions");
        if (actionsDiv) {
          if (action === "taken") {
            actionsDiv.innerHTML = `<span class="badge" style="background: rgba(16, 185, 129, 0.2); color: #34D399; border: 1px solid rgba(16, 185, 129, 0.4); padding: 0.4rem 0.75rem; font-weight: 700;">✓ Taken</span>`;
          } else {
            actionsDiv.innerHTML = `<span class="badge" style="background: rgba(239, 68, 68, 0.2); color: #F87171; border: 1px solid rgba(239, 68, 68, 0.4); padding: 0.4rem 0.75rem;">Skipped</span>`;
          }
        }
      }
    } else {
      if (typeof showToast === "function") {
        showToast(data.error || "Failed to log action", "danger");
      }
    }
  } catch (err) {
    console.error("Schedule action error:", err);
    if (typeof showToast === "function") {
      showToast("Network error logging dose", "danger");
    }
  }
}

// Live Circadian Countdown Logic
function initCircadianCountdown() {
  const widget = document.getElementById("nextDoseWidget");
  if (!widget) return;

  const timerEl = document.getElementById("countdownTimer");
  const headlineEl = document.getElementById("nextDoseHeadline");
  const subtextEl = document.getElementById("nextDoseSubtext");
  const badgeEl = document.getElementById("nextSlotBadge");

  // Collect all schedules from DOM
  const doseCards = document.querySelectorAll(".dose-item");
  if (!doseCards || doseCards.length === 0) {
    widget.style.display = "none";
    return;
  }

  const items = [];
  doseCards.forEach(card => {
    const medNameEl = card.querySelector(".dose-meta h4");
    const timeInput = card.querySelector("input[name='reminder_time']");
    const isTaken = card.classList.contains("taken");
    const subtext = card.querySelector(".dose-subtext") ? card.querySelector(".dose-subtext").innerText : "";

    if (medNameEl && timeInput && timeInput.value) {
      items.push({
        id: card.id,
        name: medNameEl.innerText.trim(),
        time: timeInput.value.trim(), // e.g. "08:00"
        isTaken: isTaken,
        subtext: subtext
      });
    }
  });

  if (items.length === 0) {
    widget.style.display = "none";
    return;
  }

  function tick() {
    const now = new Date();
    const currentMinutes = now.getHours() * 60 + now.getMinutes();
    const currentSeconds = now.getSeconds();

    // Filter pending/upcoming doses
    let upcoming = [];
    items.forEach(item => {
      const parts = item.time.split(":");
      const doseMinutes = parseInt(parts[0], 10) * 60 + parseInt(parts[1], 10);
      let diffMinutes = doseMinutes - currentMinutes;
      let diffSeconds = diffMinutes * 60 - currentSeconds;

      if (diffSeconds > 0 && !item.isTaken) {
        upcoming.push({ ...item, diffSeconds, doseMinutes });
      }
    });

    upcoming.sort((a, b) => a.diffSeconds - b.diffSeconds);

    let target = null;
    let isNextDay = false;

    if (upcoming.length > 0) {
      target = upcoming[0];
    } else {
      // All doses today are either passed or taken; find first dose tomorrow
      isNextDay = true;
      const sortedByTime = [...items].sort((a, b) => {
        const [ah, am] = a.time.split(":").map(Number);
        const [bh, bm] = b.time.split(":").map(Number);
        return (ah * 60 + am) - (bh * 60 + bm);
      });
      const firstDose = sortedByTime[0];
      const [fh, fm] = firstDose.time.split(":").map(Number);
      const doseMinutes = fh * 60 + fm;
      const secondsUntilMidnight = (24 * 60 - currentMinutes) * 60 - currentSeconds;
      const diffSeconds = secondsUntilMidnight + (doseMinutes * 60);
      target = { ...firstDose, diffSeconds, doseMinutes };
    }

    if (target) {
      const hours = Math.floor(target.diffSeconds / 3600);
      const minutes = Math.floor((target.diffSeconds % 3600) / 60);
      const seconds = target.diffSeconds % 60;

      const pad = n => String(n).padStart(2, "0");
      timerEl.innerText = `${pad(hours)}:${pad(minutes)}:${pad(seconds)}`;

      if (isNextDay) {
        badgeEl.innerText = `Tomorrow at ${target.time}`;
        headlineEl.innerText = `First Dose Tomorrow: ${target.name}`;
        subtextEl.innerText = `All today's doses logged. Next cycle begins at ${target.time}.`;
      } else {
        badgeEl.innerText = `Scheduled at ${target.time}`;
        headlineEl.innerText = `Next Dose: ${target.name}`;
        subtextEl.innerText = `${target.subtext || 'Scheduled for today'}`;
      }

      // If exactly reached
      if (target.diffSeconds === 1) {
        playMedicalChime();
        if ("Notification" in window && Notification.permission === "granted") {
          new Notification("MediLens AI Dose Reminder", {
            body: `It is time to take your scheduled dose: ${target.name} (${target.time})`
          });
        }
      }
    }
  }

  tick();
  setInterval(tick, 1000);
}

document.addEventListener("DOMContentLoaded", () => {
  initCircadianCountdown();

  // Request notification permission unobtrusively on first interaction
  if ("Notification" in window && Notification.permission === "default") {
    // Only ask when user clicks anywhere on the schedule
    document.body.addEventListener("click", () => {
      Notification.requestPermission();
    }, { once: true });
  }
});

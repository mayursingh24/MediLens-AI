/**
 * MediLens AI - Global Application Utilities
 */

// Toast notification helper
function showToast(message, type = "info") {
  let container = document.getElementById("toast-container");
  if (!container) {
    container = document.createElement("div");
    container.id = "toast-container";
    document.body.appendChild(container);
  }

  const toast = document.createElement("div");
  toast.className = `toast toast-${type}`;
  toast.innerText = message;

  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transition = "opacity 0.4s ease";
    setTimeout(() => toast.remove(), 400);
  }, 4000);
}

// Dark / Light Theme Toggle
function initTheme() {
  let saved = localStorage.getItem("medilens_theme");
  if (!saved || saved === "light") {
    saved = "dark";
    localStorage.setItem("medilens_theme", "dark");
  }
  document.documentElement.setAttribute("data-theme", saved);

  const toggleBtn = document.getElementById("theme-toggle-btn");
  if (toggleBtn) {
    toggleBtn.innerText = saved === "dark" ? "☀️ Light" : "🌙 Dark";
    toggleBtn.addEventListener("click", () => {
      const current = document.documentElement.getAttribute("data-theme");
      const next = current === "dark" ? "light" : "dark";
      document.documentElement.setAttribute("data-theme", next);
      localStorage.setItem("medilens_theme", next);
      toggleBtn.innerText = next === "dark" ? "☀️ Light" : "🌙 Dark";
    });
  }
}

// Language Switcher Handler
function initLanguageSelector() {
  const langSelect = document.getElementById("global-lang-select");
  if (langSelect) {
    langSelect.addEventListener("change", async (e) => {
      const lang = e.target.value;
      try {
        await fetch("/api/auth/language", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ language: lang })
        });
        showToast(`Language set to: ${lang.toUpperCase()}`, "success");
      } catch (err) {
        console.error("Language update error:", err);
      }
    });
  }
}

// Web Speech Synthesis helper
function speakText(text, lang = "en") {
  if (!("speechSynthesis" in window)) {
    console.warn("Speech synthesis not supported in this browser.");
    return;
  }
  window.speechSynthesis.cancel(); // cancel any ongoing speech
  const utterance = new SpeechSynthesisUtterance(text);
  if (lang === "hi") {
    utterance.lang = "hi-IN";
  } else {
    utterance.lang = "en-US";
  }
  utterance.rate = 0.95;
  window.speechSynthesis.speak(utterance);
}

// Floating Slide-Over AI Assistant Drawer
function initAiDrawer() {
  const trigger = document.getElementById("global-ai-trigger");
  const drawer = document.getElementById("ai-slide-drawer");
  const closeBtn = document.getElementById("close-ai-drawer-btn");
  const form = document.getElementById("drawer-chat-form");
  const input = document.getElementById("drawer-chat-input");
  const messagesContainer = document.getElementById("drawer-messages");
  const quickBtns = document.querySelectorAll(".drawer-quick-btn");

  if (!drawer) return;

  function openDrawer() {
    drawer.style.display = "flex";
    if (input) input.focus();
  }

  function closeDrawer() {
    drawer.style.display = "none";
  }

  if (trigger) trigger.addEventListener("click", openDrawer);
  if (closeBtn) closeBtn.addEventListener("click", closeDrawer);

  // Quick question chip clicks
  quickBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      const q = btn.getAttribute("data-q");
      if (q) {
        if (input) input.value = q;
        submitDrawerMessage(q);
      }
    });
  });

  if (form) {
    form.addEventListener("submit", (e) => {
      e.preventDefault();
      const text = input ? input.value.trim() : "";
      if (!text) return;
      submitDrawerMessage(text);
    });
  }

  async function submitDrawerMessage(questionText) {
    if (!messagesContainer) return;

    // Append User Message
    const userMsgEl = document.createElement("div");
    userMsgEl.style.cssText = "align-self: flex-end; background: linear-gradient(135deg, rgba(0, 229, 255, 0.2), rgba(99, 102, 241, 0.25)); border: 1px solid rgba(0, 229, 255, 0.3); color: #FFFFFF; padding: 0.75rem 1rem; border-radius: var(--radius-lg); border-bottom-right-radius: 2px; max-width: 85%; font-size: 0.88rem;";
    userMsgEl.textContent = questionText;
    messagesContainer.appendChild(userMsgEl);

    if (input) input.value = "";
    messagesContainer.scrollTop = messagesContainer.scrollHeight;

    // Append Loading State
    const loadingEl = document.createElement("div");
    loadingEl.id = "drawer-loading-indicator";
    loadingEl.style.cssText = "align-self: flex-start; background: rgba(255, 255, 255, 0.04); border: 1px solid var(--border-color); color: var(--primary); padding: 0.65rem 0.9rem; border-radius: var(--radius-lg); font-size: 0.82rem; display: flex; align-items: center; gap: 0.5rem;";
    loadingEl.innerHTML = `<span>✨ MediLens AI is analyzing...</span>`;
    messagesContainer.appendChild(loadingEl);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;

    try {
      const res = await fetch("/assistant/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: questionText })
      });
      const data = await res.json();
      loadingEl.remove();

      const aiMsgEl = document.createElement("div");
      aiMsgEl.style.cssText = "align-self: flex-start; background: rgba(14, 20, 36, 0.9); border: 1px solid var(--border-color); color: #E2E8F0; padding: 0.85rem 1.1rem; border-radius: var(--radius-lg); border-bottom-left-radius: 2px; max-width: 90%; font-size: 0.88rem; line-height: 1.55; position: relative;";
      
      const rawText = data.response || "I could not retrieve an answer at this time.";
      // Basic markdown formatting: **bold** and newlines
      const formatted = rawText
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\n\n/g, '<br><br>')
        .replace(/\n/g, '<br>');

      aiMsgEl.innerHTML = `
        <div style="margin-bottom: 0.5rem;">${formatted}</div>
        <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 0.5rem; padding-top: 0.4rem; border-top: 1px solid rgba(255, 255, 255, 0.06); font-size: 0.72rem; color: var(--text-muted);">
          <span>MediLens AI Clinical Assistant</span>
          <button type="button" class="speak-btn" style="background:none; border:none; color:var(--primary); cursor:pointer; font-size:0.78rem;">🔊 Listen</button>
        </div>
      `;

      const speakBtn = aiMsgEl.querySelector(".speak-btn");
      if (speakBtn && data.voice_text) {
        speakBtn.addEventListener("click", () => speakText(data.voice_text));
      }

      messagesContainer.appendChild(aiMsgEl);
      messagesContainer.scrollTop = messagesContainer.scrollHeight;

    } catch (err) {
      console.error("AI Drawer error:", err);
      loadingEl.remove();
      const errEl = document.createElement("div");
      errEl.style.cssText = "align-self: flex-start; color: var(--danger); font-size: 0.82rem; padding: 0.5rem;";
      errEl.textContent = "Unable to connect to AI Assistant. Please check your network.";
      messagesContainer.appendChild(errEl);
    }
  }
}

document.addEventListener("DOMContentLoaded", () => {
  initTheme();
  initLanguageSelector();
  initAiDrawer();
});


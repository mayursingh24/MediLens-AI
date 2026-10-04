/**
 * AI Health Assistant Interactive Chat and Speech Recognition / Synthesis
 */

document.addEventListener("DOMContentLoaded", () => {
  const chatMessages = document.getElementById("chat-messages-container");
  const chatForm = document.getElementById("assistant-chat-form");
  const inputField = document.getElementById("chat-user-input");
  const micBtn = document.getElementById("voice-mic-btn");
  const prescriptionSelect = document.getElementById("chat-prescription-select");
  const langSelect = document.getElementById("chat-language-select");

  // Web Speech Recognition
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  let recognition = null;
  let isRecording = false;

  if (SpeechRecognition && micBtn) {
    recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = false;

    micBtn.addEventListener("click", () => {
      if (isRecording) {
        recognition.stop();
        return;
      }
      const lang = langSelect ? langSelect.value : "en";
      recognition.lang = lang === "hi" ? "hi-IN" : "en-US";
      try {
        recognition.start();
        micBtn.classList.add("recording");
        micBtn.innerText = "🔴 Listening...";
        isRecording = true;
      } catch (e) {
        console.warn("Speech recognition error:", e);
      }
    });

    recognition.onresult = (event) => {
      const transcript = event.results[0][0].transcript;
      inputField.value = transcript;
      sendMessage(transcript);
    };

    recognition.onend = () => {
      isRecording = false;
      micBtn.classList.remove("recording");
      micBtn.innerText = "🎤 Voice";
    };

    recognition.onerror = (e) => {
      console.warn("Recognition error:", e);
      isRecording = false;
      micBtn.classList.remove("recording");
      micBtn.innerText = "🎤 Voice";
    };
  } else if (micBtn) {
    micBtn.style.display = "none"; // Hide if unsupported by browser
  }

  // Preset question triggers
  document.querySelectorAll(".quick-question-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const q = btn.getAttribute("data-question");
      inputField.value = q;
      sendMessage(q);
    });
  });

  if (chatForm) {
    chatForm.addEventListener("submit", (e) => {
      e.preventDefault();
      const text = inputField.value.trim();
      if (!text) return;
      sendMessage(text);
      inputField.value = "";
    });
  }

  async function sendMessage(text) {
    appendMessage(text, "user");

    const prescriptionId = prescriptionSelect ? prescriptionSelect.value : null;
    const language = langSelect ? langSelect.value : "en";

    // Show typing loader
    const typingId = "typing-" + Date.now();
    appendTypingIndicator(typingId);

    try {
      const res = await fetch("/assistant/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: text,
          prescription_id: prescriptionId,
          language: language
        })
      });
      const data = await res.json();
      removeTypingIndicator(typingId);

      if (res.ok) {
        appendMessage(data.response, "assistant", data.safety_warning, data.voice_text, language);
        if (data.voice_text) {
          speakText(data.voice_text, language);
        }
      } else {
        appendMessage(data.error || "Sorry, I could not answer that right now.", "assistant", true);
      }
    } catch (err) {
      removeTypingIndicator(typingId);
      console.error("Chat error:", err);
      appendMessage("Network error. Please try again.", "assistant", true);
    }
  }

  function appendMessage(text, sender, isWarning = false, voiceText = null, lang = "en") {
    const msgDiv = document.createElement("div");
    msgDiv.style.marginBottom = "1rem";
    msgDiv.style.display = "flex";
    msgDiv.style.justifyContent = sender === "user" ? "flex-end" : "flex-start";

    const bubble = document.createElement("div");
    bubble.style.maxWidth = "80%";
    bubble.style.padding = "0.85rem 1.15rem";
    bubble.style.borderRadius = "var(--radius-md)";
    bubble.style.fontSize = "0.92rem";
    bubble.style.lineHeight = "1.5";

    if (sender === "user") {
      bubble.style.background = "var(--primary)";
      bubble.style.color = "#FFFFFF";
      bubble.innerText = text;
    } else {
      bubble.style.background = isWarning ? "var(--warning-light)" : "var(--bg-card)";
      bubble.style.color = isWarning ? "#92400E" : "var(--text-main)";
      bubble.style.border = "1px solid var(--border-color)";
      bubble.innerHTML = formatMarkdown(text);

      if (voiceText) {
        const speakBtn = document.createElement("button");
        speakBtn.className = "btn btn-secondary btn-sm";
        speakBtn.style.marginTop = "0.6rem";
        speakBtn.style.display = "inline-flex";
        speakBtn.style.alignItems = "center";
        speakBtn.style.gap = "0.3rem";
        speakBtn.innerHTML = "🔊 Listen Voice";
        speakBtn.onclick = () => speakText(voiceText, lang);
        bubble.appendChild(document.createElement("br"));
        bubble.appendChild(speakBtn);
      }
    }

    msgDiv.appendChild(bubble);
    chatMessages.appendChild(msgDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  function formatMarkdown(str) {
    if (!str) return "";
    let html = str
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
    // Bold
    html = html.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");
    // Italic
    html = html.replace(/\*(.*?)\*/g, "<em>$1</em>");
    // Bullet lines
    html = html.replace(/^\s*[\-\*]\s+(.*)$/gm, "<li>$1</li>");
    // Newlines
    html = html.replace(/\n\n/g, "<br><br>");
    html = html.replace(/\n/g, "<br>");
    return html;
  }

  function appendTypingIndicator(id) {
    const typingDiv = document.createElement("div");
    typingDiv.id = id;
    typingDiv.style.marginBottom = "1rem";
    typingDiv.innerHTML = "<div class='card' style='display:inline-block; padding:0.5rem 1rem;'><em>MediLens is thinking...</em></div>";
    chatMessages.appendChild(typingDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  function removeTypingIndicator(id) {
    const el = document.getElementById(id);
    if (el) el.remove();
  }
});

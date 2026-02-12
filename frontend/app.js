/* ── MarginCall Frontend ──────────────────────────────────────── */
"use strict";

const APP_NAME  = "stock_analyst";
const USER_ID   = "Trader";

let sessionId   = null;
let isStreaming  = false;

const messagesEl = document.getElementById("messages");
const chatForm   = document.getElementById("chat-form");
const chatInput  = document.getElementById("chat-input");
const sendBtn    = document.getElementById("send-btn");

/* ── Helpers ─────────────────────────────────────────────────── */

function scrollToBottom() {
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function setInputEnabled(enabled) {
  chatInput.disabled = !enabled;
  sendBtn.disabled   = !enabled;
}

/** Append a message bubble and return the content element (for streaming). */
function addMessage(role, text) {
  const wrap = document.createElement("div");
  wrap.className = `message message-${role}`;

  const content = document.createElement("div");
  content.className = "message-content";
  if (role === "agent" && text) {
    content.innerHTML = DOMPurify.sanitize(marked.parse(text));
  } else {
    content.textContent = text || "";
  }

  wrap.appendChild(content);
  messagesEl.appendChild(wrap);
  scrollToBottom();
  return content;
}

function addSystemMessage(text) {
  const el = document.createElement("div");
  el.className = "message message-system";
  el.textContent = text;
  messagesEl.appendChild(el);
  scrollToBottom();
}

/** Format large numbers compactly: 1234567890 → "$1.23B" */
function fmtMoney(val) {
  if (val == null) return "N/A";
  const abs = Math.abs(val);
  const sign = val < 0 ? "-" : "";
  if (abs >= 1e12) return sign + "$" + (abs / 1e12).toFixed(2) + "T";
  if (abs >= 1e9)  return sign + "$" + (abs / 1e9).toFixed(2)  + "B";
  if (abs >= 1e6)  return sign + "$" + (abs / 1e6).toFixed(2)  + "M";
  return sign + "$" + abs.toLocaleString();
}

/* ── Session management ──────────────────────────────────────── */

async function createSession() {
  const res = await fetch(`/apps/${APP_NAME}/users/${USER_ID}/sessions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}),
  });
  if (!res.ok) throw new Error(`Failed to create session: ${res.status}`);
  const session = await res.json();
  sessionId = session.id;
  return sessionId;
}

async function getSessionState() {
  const res = await fetch(
    `/apps/${APP_NAME}/users/${USER_ID}/sessions/${sessionId}`
  );
  if (!res.ok) return null;
  const session = await res.json();
  return session.state || {};
}

/* ── SSE streaming ───────────────────────────────────────────── */

async function sendMessage(text) {
  if (isStreaming || !text.trim()) return;
  isStreaming = true;
  setInputEnabled(false);

  // User bubble
  addMessage("user", text);

  // Agent bubble (will be filled by streaming)
  const agentContent = addMessage("agent", "");

  // Track accumulated text
  let fullText = "";
  // Track the last known stock_report to detect new ones
  let reportBefore = null;
  try {
    const stateBefore = await getSessionState();
    reportBefore = stateBefore ? stateBefore.stock_report : null;
  } catch (_) { /* ignore */ }

  try {
    const res = await fetch("/run_sse", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        app_name: APP_NAME,
        user_id: USER_ID,
        session_id: sessionId,
        new_message: {
          role: "user",
          parts: [{ text: text }],
        },
        streaming: true,
      }),
    });

    if (!res.ok) {
      addSystemMessage("Error: " + res.status + " " + res.statusText);
      return;
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      // Keep last potentially incomplete line in buffer
      buffer = lines.pop() || "";

      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        const json = line.slice(6).trim();
        if (!json) continue;

        let event;
        try { event = JSON.parse(json); } catch (_) { continue; }

        // Extract text from content.parts
        if (event.content && event.content.parts) {
          for (const part of event.content.parts) {
            if (part.text) {
              fullText += part.text;
            }
          }
          // Re-render accumulated text as markdown
          agentContent.innerHTML = DOMPurify.sanitize(marked.parse(fullText));
          scrollToBottom();
        }
      }
    }
  } catch (err) {
    addSystemMessage("Connection error: " + err.message);
  } finally {
    isStreaming = false;
    setInputEnabled(true);
    chatInput.focus();
  }

  // After streaming completes, check for stock_report in session state
  try {
    const state = await getSessionState();
    const report = state ? state.stock_report : null;
    if (report && JSON.stringify(report) !== JSON.stringify(reportBefore)) {
      const card = renderStockReport(report);
      messagesEl.appendChild(card);
      scrollToBottom();
    }
  } catch (_) { /* ignore */ }
}

/* ── Event handlers ──────────────────────────────────────────── */

chatForm.addEventListener("submit", (e) => {
  e.preventDefault();
  const text = chatInput.value.trim();
  if (!text) return;
  chatInput.value = "";
  sendMessage(text);
});

/* ── Init ────────────────────────────────────────────────────── */

(async function init() {
  try {
    await createSession();
    addSystemMessage("Session started. Ask me about any stock.");
    chatInput.focus();
  } catch (err) {
    addSystemMessage("Failed to connect: " + err.message);
  }
})();

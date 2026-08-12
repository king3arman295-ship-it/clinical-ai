// Public AI Chat - No authentication required
//
// The session id used to be a fresh random value on every page load, so a
// browser reload mid-conversation — including the one some mobile browsers
// trigger when the native photo/camera picker opens for a file input, an
// OS-level behavior JS can't prevent — silently orphaned the AI's
// conversation state: the backend still had it sitting under the old
// session id, but the page could never reach it again with a brand new
// one. Reusing the same id for the tab's lifetime (and restoring the
// visible transcript below) means a reload picks the conversation back up
// instead of looking broken.
let chatSessionId = sessionStorage.getItem('public_chat_session_id') || ('public_' + Math.random().toString(36).slice(2, 10));
sessionStorage.setItem('public_chat_session_id', chatSessionId);
let isSending = false;

document.addEventListener('DOMContentLoaded', function() {
  setupChatInput();
  setupMobileMenu();
});

function setupMobileMenu() {
  const mobileMenuBtn = document.getElementById('mobileMenuBtn');
  const navLinks = document.getElementById('navLinks');
  
  if (mobileMenuBtn) {
    mobileMenuBtn.addEventListener('click', () => {
      navLinks.classList.toggle('active');
    });
  }
}

function setupChatInput() {
  const input = document.getElementById('chat-input');
  const fileInput = document.getElementById('chat-file-input');
  
  input.addEventListener('keypress', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendChatMessage();
    }
  });

  // This input has no visible trigger by default. It's only ever opened
  // via the "Attach file" button the assistant adds inline in the chat
  // when it's actually asking for a document (see showChatUploadPrompt).
  fileInput.addEventListener('change', (e) => {
    const file = e.target.files[0];
    fileInput.value = '';
    if (!file) return;

    const prompt = document.getElementById('chat-upload-prompt');
    if (prompt) prompt.remove();

    addChatMessage('user', `\u{1F4CE} ${file.name}`);

    // Restore viewport scroll that the native file picker may have clobbered
    if (typeof _savedScrollY !== 'undefined') {
      window.scrollTo(0, _savedScrollY);
      _savedScrollY = undefined;
    }

    sendToAI('', file);
  });

  restoreChatTranscript();
}

async function sendChatMessage() {
  if (isSending) return;

  const input = document.getElementById('chat-input');
  const message = input.value.trim();
  if (!message) return;

  addChatMessage('user', message);
  input.value = '';
  await sendToAI(message, null);
}

async function sendToAI(message, file) {
  if (isSending) return;

  // Show typing indicator
  const typingDiv = document.createElement('div');
  typingDiv.className = 'chat-message';
  typingDiv.innerHTML = `<div class="chat-avatar">${Icons.bot}</div><div class="chat-bubble" style="padding: 12px 16px;">Typing...</div>`;
  document.getElementById('chat-messages').appendChild(typingDiv);
  scrollChatToBottom();

  // Disable send button
  isSending = true;
  const sendBtn = document.getElementById('send-btn');
  sendBtn.disabled = true;
  sendBtn.textContent = 'Sending...';

  try {
    let response;

    if (file) {
      const formData = new FormData();
      formData.append('file', file);

      // Public endpoint - no auth required
      const res = await fetch(
        `${API.config}/ai/chat?session_id=${encodeURIComponent(chatSessionId)}&message=${encodeURIComponent(message || '')}`,
        {
          method: 'POST',
          body: formData
        }
      );

      response = await res.json();
    } else {
      // Public endpoint - no auth required
      const res = await fetch(
        `${API.config}/ai/chat?session_id=${encodeURIComponent(chatSessionId)}&message=${encodeURIComponent(message)}`,
        {
          method: 'POST'
        }
      );

      response = await res.json();
    }

    typingDiv.remove();
    addChatMessage('ai', response.response || response.message || 'Sorry, I could not process your request.');

    if (response.suggestions && response.suggestions.length > 0) {
      showSuggestions(response.suggestions);
    }

    if (response.awaiting_upload) {
      showChatUploadPrompt();
    }

    scrollChatToBottom();
    setTimeout(scrollChatToBottom, 200);
    setTimeout(scrollChatToBottom, 500);
  } catch (error) {
    console.error('Chat error:', error);
    typingDiv.remove();
    addChatMessage('ai', 'Sorry, I encountered an error. Please make sure the backend server is running and try again.');
    scrollChatToBottom();
  } finally {
    isSending = false;
    sendBtn.disabled = false;
    sendBtn.textContent = 'Send';
  }
}

function showChatUploadPrompt(options = {}) {
  const { persist = true } = options;
  if (document.getElementById('chat-upload-prompt')) return;

  const messagesDiv = document.getElementById('chat-messages');
  const wrap = document.createElement('div');
  wrap.className = 'chat-message';
  wrap.id = 'chat-upload-prompt';
  wrap.innerHTML = `
    <div class="chat-avatar">${Icons.bot}</div>
    <div>
      <div class="chat-bubble">
        <button type="button" class="btn btn-ghost" id="chat-upload-trigger-btn" style="display:inline-flex; align-items:center; gap:6px;">
          ${Icons.paperclip} Attach file
        </button>
      </div>
    </div>
  `;
  messagesDiv.appendChild(wrap);
  scrollChatToBottom();

  document.getElementById('chat-upload-trigger-btn').addEventListener('click', () => {
    _savedScrollY = window.scrollY;
    document.getElementById('chat-file-input').click();
  });

  if (persist) appendToStoredTranscript({ type: 'upload_prompt' });
}

function showSuggestions(suggestions, options = {}) {
  const { persist = true } = options;
  const messagesDiv = document.getElementById('chat-messages');
  const wrap = document.createElement('div');
  wrap.className = 'chat-message ai';
  wrap.innerHTML = `<div class="chat-avatar">${Icons.bot}</div><div class="chat-suggestions"></div>`;
  const container = wrap.querySelector('.chat-suggestions');
  suggestions.forEach(function(label) {
    const btn = document.createElement('button');
    btn.className = 'suggestion-btn';
    btn.textContent = label;
    btn.addEventListener('click', function() {
      document.getElementById('chat-input').value = label;
      sendChatMessage();
    });
    container.appendChild(btn);
  });
  messagesDiv.appendChild(wrap);
  if (persist) appendToStoredTranscript({ type: 'suggestions', labels: suggestions });
  scrollChatToBottom();
}

function addChatMessage(role, text, options = {}) {
  const { persist = true } = options;
  const messagesDiv = document.getElementById('chat-messages');
  const messageDiv = document.createElement('div');
  messageDiv.className = `chat-message ${role}`;
  
  const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  
  messageDiv.innerHTML = `
    <div class="chat-avatar">${role === 'user' ? Icons.person : Icons.bot}</div>
    <div>
      <div class="chat-bubble">${role === 'user' ? Utils.escapeHtml(text).replace(/\n/g, '<br>') : Utils.formatBotText(text)}</div>
      <div style="font-size: 11px; color: var(--text-light); margin-top: 4px; padding: 0 4px;">${time}</div>
    </div>
  `;
  
  messagesDiv.appendChild(messageDiv);
  scrollChatToBottom();

  if (persist) appendToStoredTranscript({ type: 'message', role, text });
}

function scrollChatToBottom() {
  const el = document.getElementById('chat-messages');
  if (!el) return;
  el.scrollTop = el.scrollHeight;
  const last = el.lastElementChild;
  if (last) last.scrollIntoView({ block: 'end' });
  requestAnimationFrame(() => { el.scrollTop = el.scrollHeight; });
}

// --- Refresh chat -------------------------------------------------------
// Clears the visible conversation, drops the saved transcript, and starts
// a brand new session id so the AI has no memory of the old conversation.
async function refreshChat() {
  const btn = document.getElementById('refresh-chat-btn');
  if (btn) btn.disabled = true;

  // Best-effort: also ask the backend to drop the old session's state.
  // The chat still resets locally even if this fails (e.g. offline).
  try {
    await fetch(`${API.config}/ai/conversation/${encodeURIComponent(chatSessionId)}`, {
      method: 'DELETE'
    });
  } catch (e) {
    console.log('Could not clear server-side conversation state:', e);
  }

  sessionStorage.removeItem('public_chat_transcript');
  chatSessionId = 'public_' + Math.random().toString(36).slice(2, 10);
  sessionStorage.setItem('public_chat_session_id', chatSessionId);

  const messagesDiv = document.getElementById('chat-messages');
  messagesDiv.innerHTML = '';
  showWelcomeBubble();
  appendToStoredTranscript({ type: 'welcome' });
  showSuggestions(["Book Appointment", "View Departments", "See Available Doctors"]);

  if (btn) btn.disabled = false;
}

// --- Chat transcript persistence -------------------------------------
// See the comment above chatSessionId — this keeps the visible chat in
// sync with the backend conversation state across an unwanted reload.
function getStoredChatTranscript() {
  try {
    return JSON.parse(sessionStorage.getItem('public_chat_transcript') || '[]');
  } catch (e) {
    return [];
  }
}

function saveChatTranscript(entries) {
  sessionStorage.setItem('public_chat_transcript', JSON.stringify(entries));
}

function appendToStoredTranscript(entry) {
  const entries = getStoredChatTranscript();
  entries.push(entry);
  saveChatTranscript(entries);
}

function showWelcomeBubble() {
  const wrap = document.createElement('div');
  wrap.className = 'chat-message';
  wrap.innerHTML = `
    <div class="chat-avatar">${Icons.bot}</div>
    <div class="chat-bubble">
      <strong>Hello! I'm your Clinic AI Assistant.</strong><br><br>
      I can help you with:<br>
      \u2022 Booking appointments with our doctors<br>
      \u2022 Our medical departments and specializations<br>
      \u2022 Doctor availability and schedules<br><br>
      How can I assist you today?
    </div>
  `;
  document.getElementById('chat-messages').appendChild(wrap);
  scrollChatToBottom();
}

function restoreChatTranscript() {
  const entries = getStoredChatTranscript();
  if (!entries.length) {
    const messagesDiv = document.getElementById('chat-messages');
    messagesDiv.innerHTML = '';
    showWelcomeBubble();
    appendToStoredTranscript({ type: 'welcome' });
    showSuggestions(["Book Appointment", "View Departments", "See Available Doctors"]);
    return;
  }

  document.getElementById('chat-messages').innerHTML = '';

  entries.forEach((entry) => {
    if (entry.type === 'welcome') {
      showWelcomeBubble();
    } else if (entry.type === 'upload_prompt') {
      showChatUploadPrompt({ persist: false });
    } else if (entry.type === 'suggestions') {
      showSuggestions(entry.labels, { persist: false });
    } else {
      addChatMessage(entry.role, entry.text, { persist: false });
    }
  });

  // After a file-picker reload the layout settles late; keep the chat
  // pinned to the bottom so an upload doesn't read as a page refresh.
  [100, 300, 700].forEach(ms => setTimeout(scrollChatToBottom, ms));
}

// Popup JavaScript for Atlas AI Chrome Extension

// Use centralized config
const API_URL = typeof CONFIG !== 'undefined' ? CONFIG.API_URL : 'http://localhost:8001';
const USER_ID = typeof CONFIG !== 'undefined' ? CONFIG.DEFAULT_USER_ID : 'default';

let currentSessionId = generateSessionId();
let settings = null;

function generateSessionId() {
  return 'session_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
}

// Initialize app
async function init() {
  const app = document.getElementById('app');
  
  // Load settings from Chrome storage
  settings = await loadSettings();
  
  if (!settings || !settings.llm_api_key) {
    showConfigureMessage(app);
    return;
  }
  
  renderChatUI(app);
  loadChatHistory();
}

function showConfigureMessage(container) {
  container.innerHTML = `
    <div class="empty-state">
      <svg class="empty-state-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"></path>
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"></path>
      </svg>
      <div class="empty-state-title">Configure Your Assistant</div>
      <div class="empty-state-description">
        Please configure your API settings to start using the assistant.
      </div>
      <button class="button button-primary" id="openSettingsBtn" style="margin-top: 16px;">
        Open Settings
      </button>
    </div>
  `;
  
  // Add event listener after HTML is added
  document.getElementById('openSettingsBtn').addEventListener('click', openSettings);
}

function renderChatUI(container) {
  container.innerHTML = `
    <div class="header" data-testid="chat-header">
      <div class="header-title">Atlas AI</div>
      <div class="header-actions">
        <button class="icon-button" id="clearChatBtn" title="Clear chat" data-testid="clear-chat-btn">
          <svg width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path>
          </svg>
        </button>
        <button class="icon-button" id="settingsBtn" title="Settings" data-testid="settings-btn">
          <svg width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"></path>
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"></path>
          </svg>
        </button>
      </div>
    </div>
    
    <div class="messages-container" id="messages" data-testid="messages-container">
      <div class="empty-state">
        <svg width="48" height="48" fill="none" stroke="currentColor" viewBox="0 0 24 24" style="opacity: 0.3;">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"></path>
        </svg>
        <div class="empty-state-title">Ask me anything!</div>
        <div class="empty-state-description">
          I can help you find information from Confluence, Jira, and the web.
        </div>
      </div>
    </div>
    
    <div class="input-container" data-testid="input-container">
      <div class="input-wrapper">
        <textarea 
          id="messageInput" 
          class="input-field" 
          placeholder="Type your message..."
          rows="1"
          data-testid="message-input"
        ></textarea>
        <button 
          id="sendButton" 
          class="send-button" 
          data-testid="send-button"
        >
          Send
        </button>
      </div>
    </div>
  `;
  
  // Add event listeners
  document.getElementById('clearChatBtn').addEventListener('click', clearChat);
  document.getElementById('settingsBtn').addEventListener('click', openSettings);
  document.getElementById('sendButton').addEventListener('click', sendMessage);
  
  // Auto-resize textarea
  const textarea = document.getElementById('messageInput');
  textarea.addEventListener('input', function() {
    this.style.height = 'auto';
    this.style.height = (this.scrollHeight) + 'px';
  });
  
  // Send on Enter (but not Shift+Enter)
  textarea.addEventListener('keydown', function(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });
}

async function loadSettings() {
  return new Promise((resolve) => {
    chrome.storage.local.get(['settings'], (result) => {
      resolve(result.settings);
    });
  });
}

async function loadChatHistory() {
  try {
    const response = await fetch(`${API_URL}/api/chat/history/${currentSessionId}`);
    if (response.ok) {
      const data = await response.json();
      const messagesDiv = document.getElementById('messages');
      messagesDiv.innerHTML = '';
      
      data.history.forEach(item => {
        addMessage(item.user_message, 'user', false);
        addMessage(item.bot_response, 'bot', false, item.sources);
      });
      
      if (data.history.length === 0) {
        showEmptyState();
      }
    }
  } catch (error) {
    console.error('Error loading history:', error);
  }
}

function showEmptyState() {
  const messagesDiv = document.getElementById('messages');
  messagesDiv.innerHTML = `
    <div class="empty-state">
      <svg width="48" height="48" fill="none" stroke="currentColor" viewBox="0 0 24 24" style="opacity: 0.3;">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"></path>
      </svg>
      <div class="empty-state-title">Ask me anything!</div>
      <div class="empty-state-description">
        I can help you find information from Confluence, Jira, and the web.
      </div>
    </div>
  `;
}

async function sendMessage() {
  const input = document.getElementById('messageInput');
  const message = input.value.trim();
  
  if (!message) return;
  
  const sendButton = document.getElementById('sendButton');
  sendButton.disabled = true;
  sendButton.textContent = 'Sending...';
  
  // Clear input and show user message
  input.value = '';
  input.style.height = 'auto';
  
  const messagesDiv = document.getElementById('messages');
  // Remove empty state if present
  const emptyState = messagesDiv.querySelector('.empty-state');
  if (emptyState) {
    emptyState.remove();
  }
  
  addMessage(message, 'user');
  
  try {
    const response = await fetch(`${API_URL}/api/chat?user_id=${USER_ID}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        message: message,
        session_id: currentSessionId
      })
    });
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to send message');
    }
    
    const data = await response.json();
    addMessage(data.response, 'bot', true, data.sources);
  } catch (error) {
    console.error('Error:', error);
    addMessage(`Error: ${error.message}`, 'bot', true);
  } finally {
    sendButton.disabled = false;
    sendButton.textContent = 'Send';
    input.focus();
  }
}

function addMessage(text, type, scroll = true, sources = []) {
  const messagesDiv = document.getElementById('messages');
  const messageDiv = document.createElement('div');
  messageDiv.className = `message ${type}`;
  messageDiv.setAttribute('data-testid', `message-${type}`);
  
  let sourcesHTML = '';
  if (sources && sources.length > 0) {
    sourcesHTML = `
      <div class="message-sources">
        ${sources.map(s => `<span class="source-badge">${s}</span>`).join('')}
      </div>
    `;
  }
  
  messageDiv.innerHTML = `
    <div class="message-bubble" data-testid="message-bubble">
      ${text}
      ${sourcesHTML}
    </div>
  `;
  
  messagesDiv.appendChild(messageDiv);
  
  if (scroll) {
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
  }
}

async function clearChat() {
  if (!confirm('Are you sure you want to clear the chat history?')) {
    return;
  }
  
  try {
    await fetch(`${API_URL}/api/chat/history/${currentSessionId}`, {
      method: 'DELETE'
    });
    
    const messagesDiv = document.getElementById('messages');
    messagesDiv.innerHTML = '';
    showEmptyState();
    
    // Generate new session
    currentSessionId = generateSessionId();
  } catch (error) {
    console.error('Error clearing chat:', error);
  }
}

function openSettings() {
  chrome.tabs.create({ url: chrome.runtime.getURL('settings.html') });
}

// Initialize on load
document.addEventListener('DOMContentLoaded', init);

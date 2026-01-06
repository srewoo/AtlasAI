// Popup JavaScript for Atlas AI Chrome Extension

// Import theme manager, message renderer, and stream handler
import themeManager from '../shared/theme.js';
import messageRenderer from './messageRenderer.js';
import StreamHandler from './streamHandler.js';

// Use centralized config
const API_URL = typeof CONFIG !== 'undefined' ? CONFIG.API_URL : 'http://localhost:8001';
const USER_ID = typeof CONFIG !== 'undefined' ? CONFIG.DEFAULT_USER_ID : 'default';

let currentSessionId = generateSessionId();
let settings = null;
let streamHandler = new StreamHandler(API_URL);
let currentBotMessageDiv = null; // Track current streaming message

function generateSessionId() {
  return 'session_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
}

// Initialize app
async function init() {
  // Initialize theme manager
  await themeManager.init();

  const app = document.getElementById('app');

  // Load settings from Chrome storage
  settings = await loadSettings();

  if (!settings || !settings.llm_api_key) {
    showConfigureMessage(app);
    return;
  }

  renderChatUI(app);

  // Check for pending query from context menu
  const { pendingQuery, pendingQueryTimestamp, clearChatOnOpen } = await chrome.storage.local.get([
    'pendingQuery',
    'pendingQueryTimestamp',
    'clearChatOnOpen'
  ]);

  // Clear chat if requested (from keyboard shortcut)
  if (clearChatOnOpen) {
    await clearChatSilently();
    await chrome.storage.local.remove('clearChatOnOpen');
  } else {
    await loadChatHistory();
  }

  // Handle pending query (from context menu)
  if (pendingQuery && pendingQueryTimestamp) {
    // Only use if timestamp is within last 5 seconds
    if (Date.now() - pendingQueryTimestamp < 5000) {
      const input = document.getElementById('messageInput');
      if (input) {
        input.value = pendingQuery;
        input.focus();
        // Auto-send the query
        setTimeout(() => sendMessage(), 100);
      }
    }
    // Clear pending query
    await chrome.storage.local.remove(['pendingQuery', 'pendingQueryTimestamp']);
  }

  // Listen for theme changes from keyboard shortcut
  chrome.runtime.onMessage.addListener((request) => {
    if (request.type === 'THEME_CHANGED') {
      themeManager.setTheme(request.theme, false);
      updateThemeIcon(request.theme);
    }
  });
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
        <button class="icon-button" id="themeToggleBtn" title="Toggle theme" data-testid="theme-toggle-btn">
          <svg width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24" id="themeIcon">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z"></path>
          </svg>
        </button>
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
        <button class="icon-button" id="minimizeBtn" title="Minimize panel" data-testid="minimize-btn">
          <svg width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20 12H4"></path>
          </svg>
        </button>
        <button class="icon-button" id="closeBtn" title="Close panel" data-testid="close-btn">
          <svg width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
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
  document.getElementById('themeToggleBtn').addEventListener('click', toggleTheme);
  document.getElementById('clearChatBtn').addEventListener('click', clearChat);
  document.getElementById('settingsBtn').addEventListener('click', openSettings);
  document.getElementById('minimizeBtn').addEventListener('click', minimizePanel);
  document.getElementById('closeBtn').addEventListener('click', closePanel);
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
  const messagesDiv = document.getElementById('messages');

  // Check if using streaming (check settings)
  const useStreaming = settings?.use_streaming !== false; // Default to true

  // Update button to show cancel option during streaming
  sendButton.disabled = true;

  if (useStreaming) {
    sendButton.textContent = 'Cancel';
    sendButton.disabled = false;
    sendButton.onclick = () => {
      streamHandler.cancel();
      sendButton.textContent = 'Send';
      sendButton.onclick = sendMessage;
      if (currentBotMessageDiv) {
        const bubble = currentBotMessageDiv.querySelector('.message-bubble');
        if (bubble) {
          bubble.innerHTML += '<p><em>Response cancelled by user</em></p>';
        }
      }
      currentBotMessageDiv = null;
    };
  } else {
    sendButton.textContent = 'Sending...';
  }

  // Clear input and show user message
  input.value = '';
  input.style.height = 'auto';

  // Remove empty state if present
  const emptyState = messagesDiv.querySelector('.empty-state');
  if (emptyState) {
    emptyState.remove();
  }

  addMessage(message, 'user');

  try {
    if (useStreaming) {
      // Use streaming
      let responseText = '';
      let usedSources = [];
      let documents = [];

      // Create bot message div for streaming
      currentBotMessageDiv = createStreamingMessage();

      await streamHandler.streamChat(message, currentSessionId, USER_ID, {
        onStart: () => {
          showTypingIndicator(currentBotMessageDiv);
        },

        onSources: (detectedSources) => {
          // These are the queried sources, not the actual sources that returned data
        },

        onContext: (context) => {
          usedSources = context.usedSources || [];
          documents = context.documents || [];
        },

        onChunk: (chunk) => {
          hideTypingIndicator(currentBotMessageDiv);
          responseText += chunk;
          updateStreamingMessage(currentBotMessageDiv, responseText, usedSources, documents);
        },

        onDone: (result) => {
          usedSources = result.usedSources || usedSources;
          documents = result.documents || documents;
          hideTypingIndicator(currentBotMessageDiv);
          updateStreamingMessage(currentBotMessageDiv, responseText, usedSources, documents);
          currentBotMessageDiv = null;
        },

        onError: (error) => {
          hideTypingIndicator(currentBotMessageDiv);
          console.error('Streaming error:', error);
          if (!responseText) {
            updateStreamingMessage(currentBotMessageDiv, `Error: ${error.message}`, [], []);
          }
          currentBotMessageDiv = null;
        }
      });

    } else {
      // Fallback to non-streaming
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
    }

  } catch (error) {
    console.error('Error:', error);
    if (currentBotMessageDiv) {
      hideTypingIndicator(currentBotMessageDiv);
      showErrorWithRetry(currentBotMessageDiv, error.message, message);
      currentBotMessageDiv = null;
    } else {
      addErrorWithRetry(error.message, message);
    }
  } finally {
    sendButton.disabled = false;
    sendButton.textContent = 'Send';
    sendButton.onclick = sendMessage;
    input.focus();
  }
}

function addErrorWithRetry(errorMessage, originalMessage) {
  const messagesDiv = document.getElementById('messages');
  const messageDiv = document.createElement('div');
  messageDiv.className = 'message bot error-message';

  const timeString = formatTime(new Date());

  messageDiv.innerHTML = `
    <div class="message-bubble error-bubble">
      <div class="error-icon">⚠️</div>
      <div class="error-content">
        <strong>Error</strong>
        <p>${errorMessage}</p>
        <button class="button button-secondary retry-button" data-message="${escapeHtml(originalMessage)}">
          Retry
        </button>
      </div>
      <div class="message-timestamp">${timeString}</div>
    </div>
  `;

  messagesDiv.appendChild(messageDiv);
  messagesDiv.scrollTop = messagesDiv.scrollHeight;

  // Add retry functionality
  const retryBtn = messageDiv.querySelector('.retry-button');
  if (retryBtn) {
    retryBtn.addEventListener('click', () => {
      const input = document.getElementById('messageInput');
      if (input) {
        input.value = originalMessage;
        sendMessage();
      }
    });
  }
}

function showErrorWithRetry(messageDiv, errorMessage, originalMessage) {
  if (!messageDiv) return;

  const bubble = messageDiv.querySelector('.message-bubble');
  if (!bubble) return;

  const timeString = formatTime(new Date());

  bubble.className = 'message-bubble error-bubble';
  bubble.innerHTML = `
    <div class="error-icon">⚠️</div>
    <div class="error-content">
      <strong>Error</strong>
      <p>${errorMessage}</p>
      <button class="button button-secondary retry-button" data-message="${escapeHtml(originalMessage)}">
        Retry
      </button>
    </div>
    <div class="message-timestamp">${timeString}</div>
  `;

  // Add retry functionality
  const retryBtn = bubble.querySelector('.retry-button');
  if (retryBtn) {
    retryBtn.addEventListener('click', () => {
      const input = document.getElementById('messageInput');
      if (input) {
        input.value = originalMessage;
        sendMessage();
      }
    });
  }
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

function addMessage(text, type, scroll = true, sources = [], timestamp = null) {
  const messagesDiv = document.getElementById('messages');
  const messageDiv = document.createElement('div');
  messageDiv.className = `message ${type}`;
  messageDiv.setAttribute('data-testid', `message-${type}`);

  // Render markdown for bot messages, plain text for user messages
  const contentHtml = type === 'bot'
    ? messageRenderer.renderMarkdown(text)
    : messageRenderer.renderPlainText(text);

  let sourcesHTML = '';
  if (sources && sources.length > 0) {
    sourcesHTML = `
      <div class="message-sources">
        ${sources.map(s => `<span class="source-badge">${getSourceIcon(s)} ${s}</span>`).join('')}
      </div>
    `;
  }

  // Add timestamp
  const time = timestamp ? new Date(timestamp) : new Date();
  const timeString = formatTime(time);

  messageDiv.innerHTML = `
    <div class="message-bubble markdown-content" data-testid="message-bubble">
      ${contentHtml}
      ${sourcesHTML}
      <div class="message-timestamp">${timeString}</div>
    </div>
  `;

  messagesDiv.appendChild(messageDiv);

  // Setup copy buttons for code blocks in bot messages
  if (type === 'bot') {
    messageRenderer.setupCopyButtons(messageDiv);
  }

  if (scroll) {
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
  }
}

function formatTime(date) {
  const hours = date.getHours().toString().padStart(2, '0');
  const minutes = date.getMinutes().toString().padStart(2, '0');
  return `${hours}:${minutes}`;
}

function getSourceIcon(source) {
  const icons = {
    'confluence': '📄',
    'jira': '🎫',
    'web': '🌐',
    'vector_store': '💾'
  };
  return icons[source.toLowerCase()] || '📌';
}

async function clearChat() {
  if (!confirm('Are you sure you want to clear the chat history?')) {
    return;
  }

  await clearChatSilently();
}

async function clearChatSilently() {
  try {
    await fetch(`${API_URL}/api/chat/history/${currentSessionId}`, {
      method: 'DELETE'
    });

    const messagesDiv = document.getElementById('messages');
    if (messagesDiv) {
      messagesDiv.innerHTML = '';
      showEmptyState();
    }

    // Generate new session
    currentSessionId = generateSessionId();
  } catch (error) {
    console.error('Error clearing chat:', error);
  }
}

function toggleTheme() {
  const newTheme = themeManager.toggleTheme();
  updateThemeIcon(newTheme);
}

function updateThemeIcon(theme) {
  const icon = document.getElementById('themeIcon');
  if (!icon) return;

  // Moon icon for dark mode, Sun icon for light mode
  if (theme === 'dark') {
    icon.innerHTML = '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z"></path>';
  } else {
    icon.innerHTML = '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z"></path>';
  }
}

// Streaming helper functions
function createStreamingMessage() {
  const messagesDiv = document.getElementById('messages');
  const messageDiv = document.createElement('div');
  messageDiv.className = 'message bot';
  messageDiv.setAttribute('data-testid', 'message-bot');

  messageDiv.innerHTML = `
    <div class="message-bubble markdown-content" data-testid="message-bubble">
      <div class="typing-indicator">
        <span></span>
        <span></span>
        <span></span>
      </div>
    </div>
  `;

  messagesDiv.appendChild(messageDiv);
  messagesDiv.scrollTop = messagesDiv.scrollHeight;

  return messageDiv;
}

function updateStreamingMessage(messageDiv, text, usedSources = [], documents = []) {
  if (!messageDiv) return;

  const bubble = messageDiv.querySelector('.message-bubble');
  if (!bubble) return;

  // Render markdown for the accumulated text
  const contentHtml = messageRenderer.renderMarkdown(text);

  // Build sources HTML with document links
  let sourcesHTML = '';
  if (documents && documents.length > 0) {
    // Group documents by source
    const docsBySource = {};
    documents.forEach(doc => {
      const src = doc.source || 'unknown';
      if (!docsBySource[src]) docsBySource[src] = [];
      docsBySource[src].push(doc);
    });

    sourcesHTML = `
      <div class="message-sources">
        <div class="sources-header">Sources:</div>
        ${Object.entries(docsBySource).map(([source, docs]) => `
          <div class="source-group">
            <span class="source-badge">${getSourceIcon(source)} ${source}</span>
            <ul class="source-docs">
              ${docs.map(doc => doc.url
                ? `<li><a href="${doc.url}" target="_blank" rel="noopener noreferrer" title="${doc.title}">${truncateText(doc.title, 50)}</a></li>`
                : `<li>${truncateText(doc.title, 50)}</li>`
              ).join('')}
            </ul>
          </div>
        `).join('')}
      </div>
    `;
  } else if (usedSources && usedSources.length > 0) {
    // Fallback to just showing source badges if no documents
    sourcesHTML = `
      <div class="message-sources">
        ${usedSources.map(s => `<span class="source-badge">${getSourceIcon(s)} ${s}</span>`).join('')}
      </div>
    `;
  }

  // Add timestamp
  const timeString = formatTime(new Date());

  bubble.innerHTML = contentHtml + sourcesHTML + `<div class="message-timestamp">${timeString}</div>`;

  // Setup copy buttons for any code blocks
  messageRenderer.setupCopyButtons(messageDiv);

  // Auto-scroll to bottom
  const messagesDiv = document.getElementById('messages');
  messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

function truncateText(text, maxLength) {
  if (!text) return 'Untitled';
  if (text.length <= maxLength) return text;
  return text.substring(0, maxLength) + '...';
}

function showTypingIndicator(messageDiv) {
  if (!messageDiv) return;

  const bubble = messageDiv.querySelector('.message-bubble');
  if (!bubble) return;

  const indicator = bubble.querySelector('.typing-indicator');
  if (indicator) {
    indicator.style.display = 'flex';
  }
}

function hideTypingIndicator(messageDiv) {
  if (!messageDiv) return;

  const bubble = messageDiv.querySelector('.message-bubble');
  if (!bubble) return;

  const indicator = bubble.querySelector('.typing-indicator');
  if (indicator) {
    indicator.remove();
  }
}

function openSettings() {
  chrome.tabs.create({ url: chrome.runtime.getURL('settings.html') });
}

function minimizePanel() {
  // Toggle compact mode - hide messages but keep input visible
  const messagesContainer = document.getElementById('messages');
  const minimizeBtn = document.getElementById('minimizeBtn');

  if (!messagesContainer) return;

  const isMinimized = messagesContainer.classList.contains('minimized');

  if (isMinimized) {
    // Restore
    messagesContainer.classList.remove('minimized');
    messagesContainer.style.display = 'flex';
    if (minimizeBtn) {
      minimizeBtn.innerHTML = `
        <svg width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20 12H4"></path>
        </svg>
      `;
      minimizeBtn.title = 'Minimize panel';
    }
  } else {
    // Minimize - hide messages
    messagesContainer.classList.add('minimized');
    messagesContainer.style.display = 'none';
    if (minimizeBtn) {
      minimizeBtn.innerHTML = `
        <svg width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4"></path>
        </svg>
      `;
      minimizeBtn.title = 'Restore panel';
    }
  }
}

function closePanel() {
  // Close the side panel
  window.close();
}

// Initialize on load
document.addEventListener('DOMContentLoaded', init);

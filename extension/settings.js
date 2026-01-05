// Settings page JavaScript for Atlas AI

// Use centralized config
const API_URL = typeof CONFIG !== 'undefined' ? CONFIG.API_URL : 'http://localhost:8001';
const USER_ID = typeof CONFIG !== 'undefined' ? CONFIG.DEFAULT_USER_ID : 'default';

let currentSettings = null;

async function init() {
  await loadSettings();
  renderSettingsUI();
  populateForm();
}

async function loadSettings() {
  return new Promise((resolve) => {
    chrome.storage.local.get(['settings'], (result) => {
      currentSettings = result.settings || {};
      resolve();
    });
  });
}

function renderSettingsUI() {
  const container = document.getElementById('settings-app');
  
  // Remove old event listeners if any
  const oldSaveBtn = document.getElementById('saveSettingsBtn');
  const oldTestBtn = document.getElementById('testConnectionBtn');
  if (oldSaveBtn) oldSaveBtn.replaceWith(oldSaveBtn.cloneNode(true));
  if (oldTestBtn) oldTestBtn.replaceWith(oldTestBtn.cloneNode(true));
  
  container.innerHTML = `
    <div class="settings-header">
      <div class="settings-title" data-testid="settings-title">Settings</div>
      <div class="settings-subtitle">Configure your Atlas AI assistant</div>
    </div>
    
    <div class="settings-content">
      <div id="messageBanner"></div>
      
      <div class="settings-info">
        <strong>Backend URL Configuration:</strong><br>
        Update the API_URL in popup.js and settings.js with your backend URL before using the extension.
      </div>
      
      <div class="settings-section">
        <div class="section-title">LLM Configuration</div>
        
        <div class="form-group">
          <label class="form-label" for="llmProvider">LLM Provider *</label>
          <select id="llmProvider" class="form-select" required data-testid="llm-provider-select">
            <option value="">Select provider...</option>
            <option value="openai">OpenAI</option>
            <option value="anthropic">Anthropic (Claude)</option>
            <option value="gemini">Google Gemini</option>
            <option value="ollama">Ollama (Local)</option>
          </select>
          <div class="help-text">Choose your preferred LLM provider</div>
        </div>
        
        <div class="form-group">
          <label class="form-label" for="llmModel">Model Name *</label>
          <input 
            type="text" 
            id="llmModel" 
            class="form-input" 
            placeholder="e.g., gpt-5.2, claude-sonnet-4-5-20250929, gemini-3-flash-preview"
            required
            data-testid="llm-model-input"
          >
          <div class="help-text">Enter the specific model name</div>
        </div>
        
        <div class="form-group">
          <label class="form-label" for="llmApiKey">API Key *</label>
          <input 
            type="password" 
            id="llmApiKey" 
            class="form-input" 
            placeholder="Enter your API key"
            required
            data-testid="llm-api-key-input"
          >
          <div class="help-text">Your API key will be stored locally in the browser</div>
        </div>
      </div>
      
      <div class="settings-section">
        <div class="section-title">Confluence Integration</div>
        
        <div class="form-group">
          <label class="form-label" for="confluenceUrl">Confluence URL</label>
          <input 
            type="url" 
            id="confluenceUrl" 
            class="form-input" 
            placeholder="https://your-domain.atlassian.net"
            data-testid="confluence-url-input"
          >
        </div>
        
        <div class="form-group">
          <label class="form-label" for="confluenceUsername">Username/Email</label>
          <input 
            type="email" 
            id="confluenceUsername" 
            class="form-input" 
            placeholder="your-email@example.com"
            data-testid="confluence-username-input"
          >
        </div>
        
        <div class="form-group">
          <label class="form-label" for="confluenceToken">API Token</label>
          <input 
            type="password" 
            id="confluenceToken" 
            class="form-input" 
            placeholder="Enter API token"
            data-testid="confluence-token-input"
          >
          <div class="help-text">Get your token from <a href="https://id.atlassian.com/manage-profile/security/api-tokens" target="_blank">Atlassian API Tokens</a></div>
        </div>
      </div>
      
      <div class="settings-section">
        <div class="section-title">Jira Integration</div>
        
        <div class="form-group">
          <label class="form-label" for="jiraUrl">Jira URL</label>
          <input 
            type="url" 
            id="jiraUrl" 
            class="form-input" 
            placeholder="https://your-domain.atlassian.net"
            data-testid="jira-url-input"
          >
        </div>
        
        <div class="form-group">
          <label class="form-label" for="jiraUsername">Username/Email</label>
          <input 
            type="email" 
            id="jiraUsername" 
            class="form-input" 
            placeholder="your-email@example.com"
            data-testid="jira-username-input"
          >
        </div>
        
        <div class="form-group">
          <label class="form-label" for="jiraToken">API Token</label>
          <input 
            type="password" 
            id="jiraToken" 
            class="form-input" 
            placeholder="Enter API token"
            data-testid="jira-token-input"
          >
          <div class="help-text">Same token as Confluence if using Atlassian Cloud</div>
        </div>
      </div>
      
      <div class="settings-section">
        <div class="section-title">Other Options</div>
        
        <div class="form-group">
          <label class="form-checkbox">
            <input type="checkbox" id="enableWebSearch" checked data-testid="web-search-checkbox">
            <span>Enable web search</span>
          </label>
          <div class="help-text">Allow the assistant to search the internet for information</div>
        </div>
      </div>
    </div>
    
    <div class="settings-actions">
      <button class="button button-primary" id="saveSettingsBtn" data-testid="save-settings-btn">
        Save Settings
      </button>
      <button class="button button-secondary" id="testConnectionBtn" data-testid="test-connection-btn">
        Test Connection
      </button>
    </div>
  `;
  
  // Add event listeners after HTML is rendered
  setTimeout(() => {
    document.getElementById('saveSettingsBtn').addEventListener('click', saveSettings);
    document.getElementById('testConnectionBtn').addEventListener('click', testConnection);
  }, 0);
}

function populateForm() {
  if (!currentSettings) return;
  
  document.getElementById('llmProvider').value = currentSettings.llm_provider || '';
  document.getElementById('llmModel').value = currentSettings.llm_model || '';
  document.getElementById('llmApiKey').value = currentSettings.llm_api_key || '';
  
  document.getElementById('confluenceUrl').value = currentSettings.confluence_url || '';
  document.getElementById('confluenceUsername').value = currentSettings.confluence_username || '';
  document.getElementById('confluenceToken').value = currentSettings.confluence_token || '';
  
  document.getElementById('jiraUrl').value = currentSettings.jira_url || '';
  document.getElementById('jiraUsername').value = currentSettings.jira_username || '';
  document.getElementById('jiraToken').value = currentSettings.jira_token || '';
  
  document.getElementById('enableWebSearch').checked = currentSettings.enable_web_search !== false;
}

async function saveSettings() {
  const settings = {
    llm_provider: document.getElementById('llmProvider').value,
    llm_model: document.getElementById('llmModel').value,
    llm_api_key: document.getElementById('llmApiKey').value,
    confluence_url: document.getElementById('confluenceUrl').value || null,
    confluence_username: document.getElementById('confluenceUsername').value || null,
    confluence_token: document.getElementById('confluenceToken').value || null,
    jira_url: document.getElementById('jiraUrl').value || null,
    jira_username: document.getElementById('jiraUsername').value || null,
    jira_token: document.getElementById('jiraToken').value || null,
    enable_web_search: document.getElementById('enableWebSearch').checked
  };
  
  // Validate required fields
  if (!settings.llm_provider || !settings.llm_model || !settings.llm_api_key) {
    showMessage('Please fill in all required LLM fields', 'error');
    return;
  }
  
  try {
    // Save to Chrome storage
    await new Promise((resolve) => {
      chrome.storage.local.set({ settings }, resolve);
    });
    
    // Save to backend
    const response = await fetch(`${API_URL}/api/settings?user_id=${USER_ID}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(settings)
    });
    
    if (!response.ok) {
      throw new Error('Failed to save settings to backend');
    }
    
    showMessage('Settings saved successfully!', 'success');
    currentSettings = settings;
  } catch (error) {
    console.error('Error saving settings:', error);
    showMessage(`Error: ${error.message}`, 'error');
  }
}

async function testConnection() {
  const settings = {
    llm_provider: document.getElementById('llmProvider').value,
    llm_model: document.getElementById('llmModel').value,
    llm_api_key: document.getElementById('llmApiKey').value,
    confluence_url: document.getElementById('confluenceUrl').value || null,
    confluence_username: document.getElementById('confluenceUsername').value || null,
    confluence_token: document.getElementById('confluenceToken').value || null,
    jira_url: document.getElementById('jiraUrl').value || null,
    jira_username: document.getElementById('jiraUsername').value || null,
    jira_token: document.getElementById('jiraToken').value || null,
    enable_web_search: document.getElementById('enableWebSearch').checked
  };
  
  if (!settings.llm_provider || !settings.llm_model || !settings.llm_api_key) {
    showMessage('Please fill in LLM settings first', 'error');
    return;
  }
  
  showMessage('Testing connections...', 'success');
  
  try {
    const response = await fetch(`${API_URL}/api/test-connection`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(settings)
    });
    
    if (!response.ok) {
      throw new Error('Connection test failed');
    }
    
    const results = await response.json();
    let message = 'Connection Test Results:\n';
    
    for (const [key, value] of Object.entries(results)) {
      message += `\n${key.toUpperCase()}: ${value.status === 'success' ? '✓' : '✗'} ${value.message}`;
    }
    
    showMessage(message, results.llm?.status === 'success' ? 'success' : 'error');
  } catch (error) {
    console.error('Connection test error:', error);
    showMessage(`Test failed: ${error.message}`, 'error');
  }
}

function showMessage(text, type) {
  const banner = document.getElementById('messageBanner');
  banner.innerHTML = `
    <div class="message-banner ${type}">
      ${text.replace(/\n/g, '<br>')}
    </div>
  `;
  
  setTimeout(() => {
    banner.innerHTML = '';
  }, 5000);
}

// Initialize on load
document.addEventListener('DOMContentLoaded', init);

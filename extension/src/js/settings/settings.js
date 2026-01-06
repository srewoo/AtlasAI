// Modern Settings page for Atlas AI
import themeManager from '../shared/theme.js';

const API_URL = typeof CONFIG !== 'undefined' ? CONFIG.API_URL : 'http://localhost:8001';
const USER_ID = typeof CONFIG !== 'undefined' ? CONFIG.DEFAULT_USER_ID : 'default';

let currentSettings = null;

async function init() {
  // Initialize theme
  await themeManager.init();

  await loadSettings();
  renderModernSettingsUI();
  populateForm();
  setupEventListeners();
}

async function loadSettings() {
  return new Promise((resolve) => {
    chrome.storage.local.get(['settings'], (result) => {
      currentSettings = result.settings || {};
      resolve();
    });
  });
}

function renderModernSettingsUI() {
  const container = document.getElementById('settings-app');

  container.innerHTML = `
    <div class="modern-settings-container">
      <!-- Header -->
      <div class="modern-settings-header">
        <div class="header-content">
          <h1 class="settings-main-title">Atlas AI Settings</h1>
          <p class="settings-subtitle">Configure your intelligent assistant</p>
        </div>
        <button class="icon-button" id="themeToggleBtn" title="Toggle theme">
          <svg width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24" id="themeIcon">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z"></path>
          </svg>
        </button>
      </div>

      <!-- Message Banner -->
      <div id="messageBanner"></div>

      <!-- Settings Content -->
      <div class="modern-settings-content">
        <!-- LLM Provider Card -->
        <div class="settings-card">
          <div class="card-header">
            <div class="card-icon">🤖</div>
            <div>
              <h2 class="card-title">AI Model Configuration</h2>
              <p class="card-description">Choose your preferred AI provider and model</p>
            </div>
          </div>
          <div class="card-body">
            <div class="form-row">
              <div class="form-group full-width">
                <label class="modern-label" for="llmProvider">
                  Provider <span class="required">*</span>
                </label>
                <select id="llmProvider" class="modern-select" required>
                  <option value="">Select AI Provider...</option>
                  <option value="openai">OpenAI (GPT-4o, GPT-4, o3)</option>
                  <option value="anthropic">Anthropic (Claude 4.5 Sonnet, Claude 4 Opus)</option>
                  <option value="gemini">Google (Gemini 2.5 Pro, Gemini 2.5 Flash)</option>
                  <option value="ollama">Ollama (Local Models)</option>
                </select>
              </div>
            </div>

            <div class="form-row">
              <div class="form-group">
                <label class="modern-label" for="llmModel">
                  Model Name <span class="required">*</span>
                </label>
                <input type="text" id="llmModel" class="modern-input"
                  placeholder="e.g., gpt-4o-mini, claude-sonnet-4-20250514" required>
                <span class="input-hint">Specify the exact model to use</span>
              </div>

              <div class="form-group">
                <label class="modern-label" for="llmApiKey">
                  API Key <span class="required">*</span>
                </label>
                <input type="password" id="llmApiKey" class="modern-input"
                  placeholder="Enter your API key" required>
                <span class="input-hint">Stored locally and encrypted</span>
              </div>
            </div>
          </div>
        </div>

        <!-- Atlassian Integration Card (Combined Confluence + Jira) -->
        <div class="settings-card">
          <div class="card-header">
            <div class="card-icon">📚</div>
            <div>
              <h2 class="card-title">Atlassian Integration</h2>
              <p class="card-description">Connect to Confluence and Jira (shared credentials)</p>
            </div>
            <label class="toggle-switch">
              <input type="checkbox" id="enableAtlassian">
              <span class="toggle-slider"></span>
            </label>
          </div>
          <div class="card-body" id="atlassianSettings" style="display: none;">
            <div class="info-banner">
              ℹ️ Confluence and Jira use the same Atlassian Cloud credentials
            </div>

            <div class="form-row">
              <div class="form-group full-width">
                <label class="modern-label" for="atlassianDomain">
                  Atlassian Domain
                </label>
                <input type="text" id="atlassianDomain" class="modern-input"
                  placeholder="your-company.atlassian.net">
                <span class="input-hint">Your Atlassian Cloud domain</span>
              </div>
            </div>

            <div class="form-row">
              <div class="form-group">
                <label class="modern-label" for="atlassianEmail">
                  Email Address
                </label>
                <input type="email" id="atlassianEmail" class="modern-input"
                  placeholder="your-email@company.com">
              </div>

              <div class="form-group">
                <label class="modern-label" for="atlassianToken">
                  API Token
                </label>
                <input type="password" id="atlassianToken" class="modern-input"
                  placeholder="Enter API token">
              </div>
            </div>

            <a href="https://id.atlassian.com/manage-profile/security/api-tokens"
              target="_blank" class="external-link">
              → Get API Token from Atlassian
            </a>
          </div>
        </div>

        <!-- Advanced Options Card -->
        <div class="settings-card">
          <div class="card-header">
            <div class="card-icon">⚙️</div>
            <div>
              <h2 class="card-title">Advanced Options</h2>
              <p class="card-description">Configure additional features and preferences</p>
            </div>
          </div>
          <div class="card-body">
            <div class="checkbox-group">
              <label class="modern-checkbox">
                <input type="checkbox" id="enableWebSearch" checked>
                <span class="checkbox-label">
                  <strong>Enable Web Search</strong>
                  <span class="checkbox-desc">Allow searching the internet for current information</span>
                </span>
              </label>

              <label class="modern-checkbox">
                <input type="checkbox" id="enableStreaming" checked>
                <span class="checkbox-label">
                  <strong>Enable Response Streaming</strong>
                  <span class="checkbox-desc">Stream responses word-by-word for faster feedback</span>
                </span>
              </label>
            </div>
          </div>
        </div>
      </div>

      <!-- Action Buttons -->
      <div class="modern-settings-footer">
        <button class="modern-button secondary" id="testConnectionBtn">
          <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path>
          </svg>
          Test Connection
        </button>
        <button class="modern-button primary" id="saveSettingsBtn">
          <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path>
          </svg>
          Save Settings
        </button>
      </div>
    </div>
  `;
}

function setupEventListeners() {
  // Save and test buttons
  document.getElementById('saveSettingsBtn').addEventListener('click', saveSettings);
  document.getElementById('testConnectionBtn').addEventListener('click', testConnection);

  // Theme toggle
  document.getElementById('themeToggleBtn').addEventListener('click', toggleTheme);

  // Atlassian toggle
  const atlassianToggle = document.getElementById('enableAtlassian');
  const atlassianSettings = document.getElementById('atlassianSettings');

  atlassianToggle.addEventListener('change', (e) => {
    atlassianSettings.style.display = e.target.checked ? 'block' : 'none';
  });

  // Provider change handler
  document.getElementById('llmProvider').addEventListener('change', (e) => {
    const defaultModels = {
      'openai': 'gpt-4o-mini',
      'anthropic': 'claude-sonnet-4-20250514',
      'gemini': 'gemini-2.5-flash',
      'ollama': 'llama3.2'
    };

    const modelInput = document.getElementById('llmModel');
    if (!modelInput.value && defaultModels[e.target.value]) {
      modelInput.value = defaultModels[e.target.value];
    }
  });
}

function populateForm() {
  if (!currentSettings) return;

  document.getElementById('llmProvider').value = currentSettings.llm_provider || '';
  document.getElementById('llmModel').value = currentSettings.llm_model || '';
  document.getElementById('llmApiKey').value = currentSettings.llm_api_key || '';

  // Atlassian settings (combined)
  const hasAtlassian = currentSettings.atlassian_domain || currentSettings.confluence_url || currentSettings.jira_url;
  document.getElementById('enableAtlassian').checked = !!hasAtlassian;
  document.getElementById('atlassianSettings').style.display = hasAtlassian ? 'block' : 'none';

  document.getElementById('atlassianDomain').value = currentSettings.atlassian_domain ||
    extractDomain(currentSettings.confluence_url) ||
    extractDomain(currentSettings.jira_url) || '';

  document.getElementById('atlassianEmail').value = currentSettings.atlassian_email ||
    currentSettings.confluence_username ||
    currentSettings.jira_username || '';

  document.getElementById('atlassianToken').value = currentSettings.atlassian_api_token ||
    currentSettings.confluence_token ||
    currentSettings.jira_token || '';

  document.getElementById('enableWebSearch').checked = currentSettings.enable_web_search !== false;
  document.getElementById('enableStreaming').checked = currentSettings.use_streaming !== false;
}

function extractDomain(url) {
  if (!url) return '';
  try {
    const match = url.match(/https?:\/\/([^\/]+)/);
    return match ? match[1] : '';
  } catch {
    return '';
  }
}

async function saveSettings() {
  const atlassianEnabled = document.getElementById('enableAtlassian').checked;
  const atlassianDomain = document.getElementById('atlassianDomain').value;

  const settings = {
    llm_provider: document.getElementById('llmProvider').value,
    llm_model: document.getElementById('llmModel').value,
    llm_api_key: document.getElementById('llmApiKey').value,
    enable_web_search: document.getElementById('enableWebSearch').checked,
    use_streaming: document.getElementById('enableStreaming').checked
  };

  // Add Atlassian settings if enabled
  if (atlassianEnabled && atlassianDomain) {
    const atlassianUrl = atlassianDomain.startsWith('http') ? atlassianDomain : `https://${atlassianDomain}`;
    settings.atlassian_domain = atlassianDomain;
    settings.atlassian_email = document.getElementById('atlassianEmail').value;
    settings.atlassian_api_token = document.getElementById('atlassianToken').value;

    // For backward compatibility
    settings.confluence_url = atlassianUrl;
    settings.confluence_username = settings.atlassian_email;
    settings.confluence_token = settings.atlassian_api_token;
    settings.jira_url = atlassianUrl;
    settings.jira_username = settings.atlassian_email;
    settings.jira_token = settings.atlassian_api_token;
  }

  // Validate required fields
  if (!settings.llm_provider || !settings.llm_model || !settings.llm_api_key) {
    showMessage('⚠️ Please fill in all required AI Model fields', 'error');
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
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(settings)
    });

    if (!response.ok) {
      throw new Error('Failed to save settings to backend');
    }

    showMessage('✓ Settings saved successfully!', 'success');
    currentSettings = settings;
  } catch (error) {
    console.error('Error saving settings:', error);
    showMessage(`✗ Error: ${error.message}`, 'error');
  }
}

async function testConnection() {
  showMessage('🔄 Testing connections...', 'info');

  try {
    const settings = {
      llm_provider: document.getElementById('llmProvider').value,
      llm_model: document.getElementById('llmModel').value,
      llm_api_key: document.getElementById('llmApiKey').value
    };

    if (!settings.llm_provider || !settings.llm_model || !settings.llm_api_key) {
      showMessage('⚠️ Please fill in AI Model settings first', 'error');
      return;
    }

    const response = await fetch(`${API_URL}/api/test-connection`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(settings)
    });

    if (!response.ok) throw new Error('Connection test failed');

    const results = await response.json();
    const success = results.llm?.status === 'success';

    showMessage(
      success ? '✓ Connection successful!' : '✗ Connection failed',
      success ? 'success' : 'error'
    );
  } catch (error) {
    showMessage(`✗ Test failed: ${error.message}`, 'error');
  }
}

function toggleTheme() {
  const newTheme = themeManager.toggleTheme();
  updateThemeIcon(newTheme);
}

function updateThemeIcon(theme) {
  const icon = document.getElementById('themeIcon');
  if (!icon) return;

  if (theme === 'dark') {
    icon.innerHTML = '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z"></path>';
  } else {
    icon.innerHTML = '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z"></path>';
  }
}

function showMessage(text, type) {
  const banner = document.getElementById('messageBanner');
  banner.innerHTML = `
    <div class="modern-message-banner ${type}">
      ${text}
    </div>
  `;

  setTimeout(() => {
    banner.innerHTML = '';
  }, 5000);
}

// Initialize
document.addEventListener('DOMContentLoaded', init);

export default { init, saveSettings, testConnection };

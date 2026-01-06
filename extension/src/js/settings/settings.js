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

      <!-- Help Section -->
      <div class="help-section">
        <div class="help-header" id="helpToggle">
          <div class="help-header-content">
            <span class="help-icon">📖</span>
            <div>
              <h2 class="help-title">Getting Started Guide</h2>
              <p class="help-subtitle">Learn how to set up and use Atlas AI</p>
            </div>
          </div>
          <span class="help-toggle-icon" id="helpToggleIcon">▼</span>
        </div>

        <div class="help-content" id="helpContent">
          <!-- Quick Start -->
          <div class="help-card">
            <h3>🚀 Quick Start</h3>
            <ol class="setup-steps">
              <li><strong>Configure AI Model (Required)</strong> - Select your preferred AI provider and enter your API key</li>
              <li><strong>Enable Integrations</strong> - Turn on the integrations you want to use (Atlassian, Slack, etc.)</li>
              <li><strong>Test Connections</strong> - Click "Test Connection" buttons to verify your credentials</li>
              <li><strong>Save Settings</strong> - Click "Save Settings" to store your configuration</li>
              <li><strong>Start Chatting</strong> - Open the popup and ask questions!</li>
            </ol>
          </div>

          <!-- Integration Setup Guide -->
          <div class="help-card">
            <h3>🔧 Integration Setup</h3>

            <div class="integration-guide">
              <div class="guide-item">
                <h4>🤖 AI Model (Required)</h4>
                <p>Get your API key from:</p>
                <ul>
                  <li><strong>OpenAI:</strong> <a href="https://platform.openai.com/api-keys" target="_blank">platform.openai.com/api-keys</a></li>
                  <li><strong>Anthropic:</strong> <a href="https://console.anthropic.com/settings/keys" target="_blank">console.anthropic.com/settings/keys</a></li>
                  <li><strong>Google:</strong> <a href="https://aistudio.google.com/app/apikey" target="_blank">aistudio.google.com/app/apikey</a></li>
                  <li><strong>Ollama:</strong> Run locally, no API key needed (use "ollama" as key)</li>
                </ul>
              </div>

              <div class="guide-item">
                <h4>📚 Atlassian (Confluence & Jira)</h4>
                <p>Uses same credentials for both services:</p>
                <ol>
                  <li>Go to <a href="https://id.atlassian.com/manage-profile/security/api-tokens" target="_blank">Atlassian API Tokens</a></li>
                  <li>Click "Create API token"</li>
                  <li>Copy the token and paste it here</li>
                  <li>Use your Atlassian email and domain (e.g., company.atlassian.net)</li>
                </ol>
              </div>

              <div class="guide-item">
                <h4>💬 Slack</h4>
                <p>Create a Slack app to get Bot Token:</p>
                <ol>
                  <li>Go to <a href="https://api.slack.com/apps" target="_blank">api.slack.com/apps</a></li>
                  <li>Click "Create New App" → "From scratch"</li>
                  <li>Go to "OAuth & Permissions" in sidebar</li>
                  <li>Add Bot Token Scopes: <code>channels:history</code>, <code>channels:read</code>, <code>search:read</code>, <code>users:read</code></li>
                  <li>Click "Install to Workspace"</li>
                  <li>Copy the "Bot User OAuth Token" (starts with <code>xoxb-</code>)</li>
                </ol>
              </div>

              <div class="guide-item">
                <h4>🐙 GitHub</h4>
                <ol>
                  <li>Go to <a href="https://github.com/settings/tokens" target="_blank">GitHub Settings → Tokens</a></li>
                  <li>Click "Generate new token (classic)"</li>
                  <li>Select scopes: <code>repo</code>, <code>read:org</code>, <code>read:user</code></li>
                  <li>Copy the token (starts with <code>ghp_</code>)</li>
                </ol>
              </div>

              <div class="guide-item">
                <h4>📝 Notion</h4>
                <ol>
                  <li>Go to <a href="https://www.notion.so/my-integrations" target="_blank">Notion Integrations</a></li>
                  <li>Click "New integration"</li>
                  <li>Copy the "Internal Integration Token" (starts with <code>secret_</code>)</li>
                  <li>Share your Notion pages with the integration</li>
                </ol>
              </div>

              <div class="guide-item">
                <h4>📊 Linear</h4>
                <ol>
                  <li>Go to <a href="https://linear.app/settings/api" target="_blank">Linear API Settings</a></li>
                  <li>Click "Create key"</li>
                  <li>Copy the API key (starts with <code>lin_api_</code>)</li>
                </ol>
              </div>

              <div class="guide-item">
                <h4>🎨 Figma</h4>
                <ol>
                  <li>Go to <a href="https://www.figma.com/developers/api#access-tokens" target="_blank">Figma Account Settings</a></li>
                  <li>Scroll to "Personal access tokens"</li>
                  <li>Click "Generate new token"</li>
                  <li>Copy the token (starts with <code>figd_</code>)</li>
                </ol>
              </div>
            </div>
          </div>

          <!-- Sample Queries -->
          <div class="help-card">
            <h3>💡 Sample Queries by Integration</h3>

            <div class="sample-queries">
              <div class="query-group">
                <h4>📚 Jira Queries</h4>
                <ul class="query-list">
                  <li><code>What is the status of CTT-21761?</code></li>
                  <li><code>Show me all open bugs assigned to me</code></li>
                  <li><code>What tickets are in the current sprint?</code></li>
                  <li><code>Find issues related to authentication</code></li>
                  <li><code>Who is working on the payment feature?</code></li>
                </ul>
              </div>

              <div class="query-group">
                <h4>📖 Confluence Queries</h4>
                <ul class="query-list">
                  <li><code>How do I set up the development environment?</code></li>
                  <li><code>Find documentation about API endpoints</code></li>
                  <li><code>What is our deployment process?</code></li>
                  <li><code>Show me the onboarding guide</code></li>
                  <li><code>Where is the architecture documentation?</code></li>
                </ul>
              </div>

              <div class="query-group">
                <h4>💬 Slack Queries</h4>
                <ul class="query-list">
                  <li><code>What was discussed about the release yesterday?</code></li>
                  <li><code>Find messages about the server outage</code></li>
                  <li><code>What did the team decide about the new feature?</code></li>
                  <li><code>Search for messages from @john about deployment</code></li>
                  <li><code>Any updates on the client meeting?</code></li>
                </ul>
              </div>

              <div class="query-group">
                <h4>🐙 GitHub Queries</h4>
                <ul class="query-list">
                  <li><code>Show recent pull requests in the main repo</code></li>
                  <li><code>Find issues labeled as "bug"</code></li>
                  <li><code>What commits were made this week?</code></li>
                  <li><code>Search for code using authentication</code></li>
                </ul>
              </div>

              <div class="query-group">
                <h4>📝 Notion Queries</h4>
                <ul class="query-list">
                  <li><code>Find my meeting notes from last week</code></li>
                  <li><code>What's in the product roadmap?</code></li>
                  <li><code>Search for project planning documents</code></li>
                </ul>
              </div>

              <div class="query-group">
                <h4>📊 Linear Queries</h4>
                <ul class="query-list">
                  <li><code>What issues are assigned to me?</code></li>
                  <li><code>Show the current sprint progress</code></li>
                  <li><code>Find bugs reported this week</code></li>
                </ul>
              </div>

              <div class="query-group">
                <h4>🎨 Figma Queries</h4>
                <ul class="query-list">
                  <li><code>Find the latest design mockups</code></li>
                  <li><code>Show components in the design system</code></li>
                  <li><code>Search for login page designs</code></li>
                </ul>
              </div>

              <div class="query-group">
                <h4>🌐 General Queries</h4>
                <ul class="query-list">
                  <li><code>What is React Server Components?</code></li>
                  <li><code>Explain how OAuth 2.0 works</code></li>
                  <li><code>Best practices for API design</code></li>
                </ul>
              </div>
            </div>
          </div>

          <!-- Tips -->
          <div class="help-card">
            <h3>💎 Pro Tips</h3>
            <ul class="tips-list">
              <li><strong>Be specific:</strong> Include ticket IDs (e.g., "CTT-21761") for precise results</li>
              <li><strong>Use context:</strong> Atlas AI remembers your conversation, so you can ask follow-up questions</li>
              <li><strong>Combine sources:</strong> Ask questions that span multiple integrations - Atlas AI will search all enabled sources</li>
              <li><strong>Priority order:</strong> Internal sources (Jira, Confluence, Slack) are searched before web</li>
              <li><strong>Keyboard shortcut:</strong> Press <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>A</kbd> to quickly open Atlas AI</li>
            </ul>
          </div>
        </div>
      </div>

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
            <div class="test-button-row">
              <button type="button" class="test-integration-btn" id="testLlmBtn">
                <span class="test-icon">🔌</span> Test LLM Connection
              </button>
              <span class="test-result" id="testLlmResult"></span>
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
            <div class="test-button-row">
              <button type="button" class="test-integration-btn" id="testAtlassianBtn">
                <span class="test-icon">🔌</span> Test Atlassian Connection
              </button>
              <span class="test-result" id="testAtlassianResult"></span>
            </div>
          </div>
        </div>

        <!-- Slack Integration Card -->
        <div class="settings-card">
          <div class="card-header">
            <div class="card-icon">💬</div>
            <div>
              <h2 class="card-title">Slack Integration</h2>
              <p class="card-description">Search messages, channels, and files</p>
            </div>
            <label class="toggle-switch">
              <input type="checkbox" id="enableSlack">
              <span class="toggle-slider"></span>
            </label>
          </div>
          <div class="card-body" id="slackSettings" style="display: none;">
            <div class="form-row">
              <div class="form-group full-width">
                <label class="modern-label" for="slackBotToken">Bot Token</label>
                <input type="password" id="slackBotToken" class="modern-input"
                  placeholder="xoxb-...">
              </div>
            </div>
            <a href="https://api.slack.com/apps" target="_blank" class="external-link">
              → Create Slack App
            </a>
            <div class="test-button-row">
              <button type="button" class="test-integration-btn" id="testSlackBtn">
                <span class="test-icon">🔌</span> Test Slack Connection
              </button>
              <span class="test-result" id="testSlackResult"></span>
            </div>
          </div>
        </div>

        <!-- GitHub Integration Card -->
        <div class="settings-card">
          <div class="card-header">
            <div class="card-icon">🐙</div>
            <div>
              <h2 class="card-title">GitHub Integration</h2>
              <p class="card-description">Search code, issues, and pull requests</p>
            </div>
            <label class="toggle-switch">
              <input type="checkbox" id="enableGitHub">
              <span class="toggle-slider"></span>
            </label>
          </div>
          <div class="card-body" id="githubSettings" style="display: none;">
            <div class="form-row">
              <div class="form-group full-width">
                <label class="modern-label" for="githubToken">Personal Access Token</label>
                <input type="password" id="githubToken" class="modern-input"
                  placeholder="ghp_...">
              </div>
            </div>
            <a href="https://github.com/settings/tokens" target="_blank" class="external-link">
              → Generate GitHub Token
            </a>
            <div class="test-button-row">
              <button type="button" class="test-integration-btn" id="testGitHubBtn">
                <span class="test-icon">🔌</span> Test GitHub Connection
              </button>
              <span class="test-result" id="testGitHubResult"></span>
            </div>
          </div>
        </div>

        <!-- Google Workspace Integration Card -->
        <div class="settings-card">
          <div class="card-header">
            <div class="card-icon">🔷</div>
            <div>
              <h2 class="card-title">Google Workspace</h2>
              <p class="card-description">Search Drive, Docs, Gmail, and Calendar</p>
            </div>
            <label class="toggle-switch">
              <input type="checkbox" id="enableGoogle">
              <span class="toggle-slider"></span>
            </label>
          </div>
          <div class="card-body" id="googleSettings" style="display: none;">
            <div class="info-banner">
              ℹ️ Requires OAuth setup via Google Cloud Console
            </div>
            <div class="form-row">
              <div class="form-group">
                <label class="modern-label" for="googleClientId">Client ID</label>
                <input type="text" id="googleClientId" class="modern-input"
                  placeholder="...apps.googleusercontent.com">
              </div>
              <div class="form-group">
                <label class="modern-label" for="googleClientSecret">Client Secret</label>
                <input type="password" id="googleClientSecret" class="modern-input"
                  placeholder="GOCSPX-...">
              </div>
            </div>
            <a href="https://console.cloud.google.com/apis/credentials" target="_blank" class="external-link">
              → Setup Google OAuth
            </a>
            <div class="test-button-row">
              <button type="button" class="test-integration-btn" id="testGoogleBtn">
                <span class="test-icon">🔌</span> Test Google Connection
              </button>
              <span class="test-result" id="testGoogleResult"></span>
            </div>
          </div>
        </div>

        <!-- Notion Integration Card -->
        <div class="settings-card">
          <div class="card-header">
            <div class="card-icon">📝</div>
            <div>
              <h2 class="card-title">Notion Integration</h2>
              <p class="card-description">Search pages and databases</p>
            </div>
            <label class="toggle-switch">
              <input type="checkbox" id="enableNotion">
              <span class="toggle-slider"></span>
            </label>
          </div>
          <div class="card-body" id="notionSettings" style="display: none;">
            <div class="form-row">
              <div class="form-group full-width">
                <label class="modern-label" for="notionApiKey">API Key</label>
                <input type="password" id="notionApiKey" class="modern-input"
                  placeholder="secret_...">
              </div>
            </div>
            <a href="https://www.notion.so/my-integrations" target="_blank" class="external-link">
              → Create Notion Integration
            </a>
            <div class="test-button-row">
              <button type="button" class="test-integration-btn" id="testNotionBtn">
                <span class="test-icon">🔌</span> Test Notion Connection
              </button>
              <span class="test-result" id="testNotionResult"></span>
            </div>
          </div>
        </div>

        <!-- Linear Integration Card -->
        <div class="settings-card">
          <div class="card-header">
            <div class="card-icon">📊</div>
            <div>
              <h2 class="card-title">Linear Integration</h2>
              <p class="card-description">Search issues and projects</p>
            </div>
            <label class="toggle-switch">
              <input type="checkbox" id="enableLinear">
              <span class="toggle-slider"></span>
            </label>
          </div>
          <div class="card-body" id="linearSettings" style="display: none;">
            <div class="form-row">
              <div class="form-group full-width">
                <label class="modern-label" for="linearApiKey">API Key</label>
                <input type="password" id="linearApiKey" class="modern-input"
                  placeholder="lin_api_...">
              </div>
            </div>
            <a href="https://linear.app/settings/api" target="_blank" class="external-link">
              → Get Linear API Key
            </a>
            <div class="test-button-row">
              <button type="button" class="test-integration-btn" id="testLinearBtn">
                <span class="test-icon">🔌</span> Test Linear Connection
              </button>
              <span class="test-result" id="testLinearResult"></span>
            </div>
          </div>
        </div>

        <!-- Microsoft 365 Integration Card -->
        <div class="settings-card">
          <div class="card-header">
            <div class="card-icon">🔵</div>
            <div>
              <h2 class="card-title">Microsoft 365</h2>
              <p class="card-description">Search Teams, SharePoint, Outlook, OneDrive</p>
            </div>
            <label class="toggle-switch">
              <input type="checkbox" id="enableMicrosoft365">
              <span class="toggle-slider"></span>
            </label>
          </div>
          <div class="card-body" id="microsoft365Settings" style="display: none;">
            <div class="info-banner">
              ℹ️ Requires Azure AD App Registration
            </div>
            <div class="form-row">
              <div class="form-group">
                <label class="modern-label" for="msClientId">Client ID</label>
                <input type="text" id="msClientId" class="modern-input"
                  placeholder="Azure AD Application ID">
              </div>
              <div class="form-group">
                <label class="modern-label" for="msClientSecret">Client Secret</label>
                <input type="password" id="msClientSecret" class="modern-input"
                  placeholder="Client secret value">
              </div>
            </div>
            <div class="form-row">
              <div class="form-group full-width">
                <label class="modern-label" for="msTenantId">Tenant ID</label>
                <input type="text" id="msTenantId" class="modern-input"
                  placeholder="Your Azure AD Tenant ID">
              </div>
            </div>
            <a href="https://portal.azure.com/#view/Microsoft_AAD_RegisteredApps/ApplicationsListBlade" target="_blank" class="external-link">
              → Register Azure AD App
            </a>
            <div class="test-button-row">
              <button type="button" class="test-integration-btn" id="testMicrosoft365Btn">
                <span class="test-icon">🔌</span> Test Microsoft 365 Connection
              </button>
              <span class="test-result" id="testMicrosoft365Result"></span>
            </div>
          </div>
        </div>

        <!-- Figma Integration Card -->
        <div class="settings-card">
          <div class="card-header">
            <div class="card-icon">🎨</div>
            <div>
              <h2 class="card-title">Figma Integration</h2>
              <p class="card-description">Search files, components, and design systems</p>
            </div>
            <label class="toggle-switch">
              <input type="checkbox" id="enableFigma">
              <span class="toggle-slider"></span>
            </label>
          </div>
          <div class="card-body" id="figmaSettings" style="display: none;">
            <div class="form-row">
              <div class="form-group">
                <label class="modern-label" for="figmaToken">Access Token</label>
                <input type="password" id="figmaToken" class="modern-input"
                  placeholder="figd_...">
              </div>
              <div class="form-group">
                <label class="modern-label" for="figmaTeamId">Team ID (optional)</label>
                <input type="text" id="figmaTeamId" class="modern-input"
                  placeholder="Your Figma Team ID">
              </div>
            </div>
            <a href="https://www.figma.com/developers/api#access-tokens" target="_blank" class="external-link">
              → Generate Figma Token
            </a>
            <div class="test-button-row">
              <button type="button" class="test-integration-btn" id="testFigmaBtn">
                <span class="test-icon">🔌</span> Test Figma Connection
              </button>
              <span class="test-result" id="testFigmaResult"></span>
            </div>
          </div>
        </div>

        <!-- Developer Tools Integration Card -->
        <div class="settings-card">
          <div class="card-header">
            <div class="card-icon">🛠️</div>
            <div>
              <h2 class="card-title">Developer Tools</h2>
              <p class="card-description">Stack Overflow, npm, PyPI, MDN documentation</p>
            </div>
            <label class="toggle-switch">
              <input type="checkbox" id="enableDevTools">
              <span class="toggle-slider"></span>
            </label>
          </div>
          <div class="card-body" id="devToolsSettings" style="display: none;">
            <div class="info-banner">
              ℹ️ Works without API keys (optional SO key for higher limits)
            </div>
            <div class="form-row">
              <div class="form-group full-width">
                <label class="modern-label" for="stackoverflowKey">Stack Overflow Key (optional)</label>
                <input type="text" id="stackoverflowKey" class="modern-input"
                  placeholder="For higher rate limits">
              </div>
            </div>
            <a href="https://stackapps.com/apps/oauth/register" target="_blank" class="external-link">
              → Register Stack Exchange App
            </a>
          </div>
        </div>

        <!-- Personal Productivity Card -->
        <div class="settings-card">
          <div class="card-header">
            <div class="card-icon">📁</div>
            <div>
              <h2 class="card-title">Personal Productivity</h2>
              <p class="card-description">Local files, notes, bookmarks, clipboard</p>
            </div>
            <label class="toggle-switch">
              <input type="checkbox" id="enableProductivity">
              <span class="toggle-slider"></span>
            </label>
          </div>
          <div class="card-body" id="productivitySettings" style="display: none;">
            <div class="info-banner">
              ℹ️ Searches local Documents, Notes, and synced bookmarks
            </div>
            <div class="checkbox-group">
              <label class="modern-checkbox">
                <input type="checkbox" id="enableLocalFiles" checked>
                <span class="checkbox-label">
                  <strong>Local File Search</strong>
                  <span class="checkbox-desc">Search Documents, Desktop, Downloads</span>
                </span>
              </label>
              <label class="modern-checkbox">
                <input type="checkbox" id="enableBookmarks" checked>
                <span class="checkbox-label">
                  <strong>Browser Bookmarks</strong>
                  <span class="checkbox-desc">Search your saved bookmarks</span>
                </span>
              </label>
              <label class="modern-checkbox">
                <input type="checkbox" id="enableClipboard">
                <span class="checkbox-label">
                  <strong>Clipboard History</strong>
                  <span class="checkbox-desc">Search recent clipboard items</span>
                </span>
              </label>
            </div>
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

  // Help section toggle
  document.getElementById('helpToggle').addEventListener('click', toggleHelpSection);

  // Individual integration test buttons
  document.getElementById('testLlmBtn').addEventListener('click', () => testIntegration('llm'));
  document.getElementById('testAtlassianBtn').addEventListener('click', () => testIntegration('atlassian'));
  document.getElementById('testSlackBtn').addEventListener('click', () => testIntegration('slack'));
  document.getElementById('testGitHubBtn').addEventListener('click', () => testIntegration('github'));
  document.getElementById('testGoogleBtn').addEventListener('click', () => testIntegration('google'));
  document.getElementById('testNotionBtn').addEventListener('click', () => testIntegration('notion'));
  document.getElementById('testLinearBtn').addEventListener('click', () => testIntegration('linear'));
  document.getElementById('testMicrosoft365Btn').addEventListener('click', () => testIntegration('microsoft365'));
  document.getElementById('testFigmaBtn').addEventListener('click', () => testIntegration('figma'));

  // Setup toggle handlers for all integrations
  const integrationToggles = [
    { toggle: 'enableAtlassian', settings: 'atlassianSettings' },
    { toggle: 'enableSlack', settings: 'slackSettings' },
    { toggle: 'enableGitHub', settings: 'githubSettings' },
    { toggle: 'enableGoogle', settings: 'googleSettings' },
    { toggle: 'enableNotion', settings: 'notionSettings' },
    { toggle: 'enableLinear', settings: 'linearSettings' },
    { toggle: 'enableMicrosoft365', settings: 'microsoft365Settings' },
    { toggle: 'enableFigma', settings: 'figmaSettings' },
    { toggle: 'enableDevTools', settings: 'devToolsSettings' },
    { toggle: 'enableProductivity', settings: 'productivitySettings' }
  ];

  integrationToggles.forEach(({ toggle, settings }) => {
    const toggleEl = document.getElementById(toggle);
    const settingsEl = document.getElementById(settings);
    if (toggleEl && settingsEl) {
      toggleEl.addEventListener('change', (e) => {
        settingsEl.style.display = e.target.checked ? 'block' : 'none';
      });
    }
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

  // Slack settings
  const hasSlack = !!currentSettings.slack_bot_token;
  document.getElementById('enableSlack').checked = hasSlack;
  document.getElementById('slackSettings').style.display = hasSlack ? 'block' : 'none';
  document.getElementById('slackBotToken').value = currentSettings.slack_bot_token || '';

  // GitHub settings
  const hasGitHub = !!currentSettings.github_token;
  document.getElementById('enableGitHub').checked = hasGitHub;
  document.getElementById('githubSettings').style.display = hasGitHub ? 'block' : 'none';
  document.getElementById('githubToken').value = currentSettings.github_token || '';

  // Google settings
  const hasGoogle = !!currentSettings.google_client_id;
  document.getElementById('enableGoogle').checked = hasGoogle;
  document.getElementById('googleSettings').style.display = hasGoogle ? 'block' : 'none';
  document.getElementById('googleClientId').value = currentSettings.google_client_id || '';
  document.getElementById('googleClientSecret').value = currentSettings.google_client_secret || '';

  // Notion settings
  const hasNotion = !!currentSettings.notion_api_key;
  document.getElementById('enableNotion').checked = hasNotion;
  document.getElementById('notionSettings').style.display = hasNotion ? 'block' : 'none';
  document.getElementById('notionApiKey').value = currentSettings.notion_api_key || '';

  // Linear settings
  const hasLinear = !!currentSettings.linear_api_key;
  document.getElementById('enableLinear').checked = hasLinear;
  document.getElementById('linearSettings').style.display = hasLinear ? 'block' : 'none';
  document.getElementById('linearApiKey').value = currentSettings.linear_api_key || '';

  // Microsoft 365 settings
  const hasMicrosoft365 = !!currentSettings.ms_client_id;
  document.getElementById('enableMicrosoft365').checked = hasMicrosoft365;
  document.getElementById('microsoft365Settings').style.display = hasMicrosoft365 ? 'block' : 'none';
  document.getElementById('msClientId').value = currentSettings.ms_client_id || '';
  document.getElementById('msClientSecret').value = currentSettings.ms_client_secret || '';
  document.getElementById('msTenantId').value = currentSettings.ms_tenant_id || '';

  // Figma settings
  const hasFigma = !!currentSettings.figma_token;
  document.getElementById('enableFigma').checked = hasFigma;
  document.getElementById('figmaSettings').style.display = hasFigma ? 'block' : 'none';
  document.getElementById('figmaToken').value = currentSettings.figma_token || '';
  document.getElementById('figmaTeamId').value = currentSettings.figma_team_id || '';

  // Developer Tools settings
  const hasDevTools = currentSettings.enable_devtools !== false;
  document.getElementById('enableDevTools').checked = hasDevTools;
  document.getElementById('devToolsSettings').style.display = hasDevTools ? 'block' : 'none';
  document.getElementById('stackoverflowKey').value = currentSettings.stackoverflow_key || '';

  // Personal Productivity settings
  const hasProductivity = currentSettings.enable_productivity !== false;
  document.getElementById('enableProductivity').checked = hasProductivity;
  document.getElementById('productivitySettings').style.display = hasProductivity ? 'block' : 'none';
  document.getElementById('enableLocalFiles').checked = currentSettings.enable_local_files !== false;
  document.getElementById('enableBookmarks').checked = currentSettings.enable_bookmarks !== false;
  document.getElementById('enableClipboard').checked = !!currentSettings.enable_clipboard;

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
  const settings = {
    llm_provider: document.getElementById('llmProvider').value,
    llm_model: document.getElementById('llmModel').value,
    llm_api_key: document.getElementById('llmApiKey').value,
    enable_web_search: document.getElementById('enableWebSearch').checked,
    use_streaming: document.getElementById('enableStreaming').checked
  };

  // Atlassian settings
  const atlassianEnabled = document.getElementById('enableAtlassian').checked;
  const atlassianDomain = document.getElementById('atlassianDomain').value;
  if (atlassianEnabled && atlassianDomain) {
    const atlassianUrl = atlassianDomain.startsWith('http') ? atlassianDomain : `https://${atlassianDomain}`;
    settings.atlassian_domain = atlassianDomain;
    settings.atlassian_email = document.getElementById('atlassianEmail').value;
    settings.atlassian_api_token = document.getElementById('atlassianToken').value;
    settings.confluence_url = atlassianUrl;
    settings.confluence_username = settings.atlassian_email;
    settings.confluence_token = settings.atlassian_api_token;
    settings.jira_url = atlassianUrl;
    settings.jira_username = settings.atlassian_email;
    settings.jira_token = settings.atlassian_api_token;
  }

  // Slack settings
  if (document.getElementById('enableSlack').checked) {
    settings.slack_bot_token = document.getElementById('slackBotToken').value;
  }

  // GitHub settings
  if (document.getElementById('enableGitHub').checked) {
    settings.github_token = document.getElementById('githubToken').value;
  }

  // Google settings
  if (document.getElementById('enableGoogle').checked) {
    settings.google_client_id = document.getElementById('googleClientId').value;
    settings.google_client_secret = document.getElementById('googleClientSecret').value;
  }

  // Notion settings
  if (document.getElementById('enableNotion').checked) {
    settings.notion_api_key = document.getElementById('notionApiKey').value;
  }

  // Linear settings
  if (document.getElementById('enableLinear').checked) {
    settings.linear_api_key = document.getElementById('linearApiKey').value;
  }

  // Microsoft 365 settings
  if (document.getElementById('enableMicrosoft365').checked) {
    settings.ms_client_id = document.getElementById('msClientId').value;
    settings.ms_client_secret = document.getElementById('msClientSecret').value;
    settings.ms_tenant_id = document.getElementById('msTenantId').value;
  }

  // Figma settings
  if (document.getElementById('enableFigma').checked) {
    settings.figma_token = document.getElementById('figmaToken').value;
    settings.figma_team_id = document.getElementById('figmaTeamId').value;
  }

  // Developer Tools settings
  settings.enable_devtools = document.getElementById('enableDevTools').checked;
  if (settings.enable_devtools) {
    settings.stackoverflow_key = document.getElementById('stackoverflowKey').value;
  }

  // Personal Productivity settings
  settings.enable_productivity = document.getElementById('enableProductivity').checked;
  if (settings.enable_productivity) {
    settings.enable_local_files = document.getElementById('enableLocalFiles').checked;
    settings.enable_bookmarks = document.getElementById('enableBookmarks').checked;
    settings.enable_clipboard = document.getElementById('enableClipboard').checked;
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

/**
 * Test individual integration connection
 * @param {string} integration - Integration type to test
 */
async function testIntegration(integration) {
  const resultElement = document.getElementById(`test${capitalize(integration)}Result`);
  const buttonElement = document.getElementById(`test${capitalize(integration)}Btn`);

  // Show loading state
  resultElement.textContent = 'Testing...';
  resultElement.className = 'test-result testing';
  buttonElement.disabled = true;

  try {
    let testConfig = {};
    let testEndpoint = '';

    switch (integration) {
      case 'llm':
        const provider = document.getElementById('llmProvider').value;
        const model = document.getElementById('llmModel').value;
        const apiKey = document.getElementById('llmApiKey').value;

        if (!provider || !model || !apiKey) {
          throw new Error('Please fill in all LLM fields');
        }
        testConfig = { llm_provider: provider, llm_model: model, llm_api_key: apiKey };
        testEndpoint = `${API_URL}/api/test-integration/llm`;
        break;

      case 'atlassian':
        const domain = document.getElementById('atlassianDomain').value;
        const email = document.getElementById('atlassianEmail').value;
        const token = document.getElementById('atlassianToken').value;

        if (!domain || !email || !token) {
          throw new Error('Please fill in all Atlassian fields');
        }
        const atlassianUrl = domain.startsWith('http') ? domain : `https://${domain}`;
        testConfig = {
          confluence_url: atlassianUrl,
          confluence_username: email,
          confluence_token: token,
          jira_url: atlassianUrl,
          jira_username: email,
          jira_token: token
        };
        testEndpoint = `${API_URL}/api/test-integration/atlassian`;
        break;

      case 'slack':
        const slackToken = document.getElementById('slackBotToken').value;
        if (!slackToken) {
          throw new Error('Please enter Slack Bot Token');
        }
        testConfig = { slack_bot_token: slackToken };
        testEndpoint = `${API_URL}/api/test-integration/slack`;
        break;

      case 'github':
        const githubToken = document.getElementById('githubToken').value;
        if (!githubToken) {
          throw new Error('Please enter GitHub Token');
        }
        testConfig = { github_token: githubToken };
        testEndpoint = `${API_URL}/api/test-integration/github`;
        break;

      case 'google':
        const clientId = document.getElementById('googleClientId').value;
        const clientSecret = document.getElementById('googleClientSecret').value;
        if (!clientId || !clientSecret) {
          throw new Error('Please fill in all Google fields');
        }
        testConfig = { google_client_id: clientId, google_client_secret: clientSecret };
        testEndpoint = `${API_URL}/api/test-integration/google`;
        break;

      case 'notion':
        const notionKey = document.getElementById('notionApiKey').value;
        if (!notionKey) {
          throw new Error('Please enter Notion API Key');
        }
        testConfig = { notion_api_key: notionKey };
        testEndpoint = `${API_URL}/api/test-integration/notion`;
        break;

      case 'linear':
        const linearKey = document.getElementById('linearApiKey').value;
        if (!linearKey) {
          throw new Error('Please enter Linear API Key');
        }
        testConfig = { linear_api_key: linearKey };
        testEndpoint = `${API_URL}/api/test-integration/linear`;
        break;

      case 'microsoft365':
        const msClientId = document.getElementById('msClientId').value;
        const msClientSecret = document.getElementById('msClientSecret').value;
        const msTenantId = document.getElementById('msTenantId').value;
        if (!msClientId || !msClientSecret || !msTenantId) {
          throw new Error('Please fill in all Microsoft 365 fields');
        }
        testConfig = {
          ms_client_id: msClientId,
          ms_client_secret: msClientSecret,
          ms_tenant_id: msTenantId
        };
        testEndpoint = `${API_URL}/api/test-integration/microsoft365`;
        break;

      case 'figma':
        const figmaToken = document.getElementById('figmaToken').value;
        if (!figmaToken) {
          throw new Error('Please enter Figma Token');
        }
        testConfig = { figma_token: figmaToken };
        testEndpoint = `${API_URL}/api/test-integration/figma`;
        break;

      default:
        throw new Error('Unknown integration type');
    }

    const response = await fetch(testEndpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(testConfig)
    });

    const result = await response.json();

    if (response.ok && result.status === 'success') {
      resultElement.textContent = `✓ ${result.message || 'Connected!'}`;
      resultElement.className = 'test-result success';
    } else {
      throw new Error(result.detail || result.message || 'Connection failed');
    }
  } catch (error) {
    resultElement.textContent = `✗ ${error.message}`;
    resultElement.className = 'test-result error';
  } finally {
    buttonElement.disabled = false;
  }
}

/**
 * Capitalize first letter of a string
 */
function capitalize(str) {
  if (str === 'llm') return 'Llm';
  if (str === 'github') return 'GitHub';
  if (str === 'microsoft365') return 'Microsoft365';
  return str.charAt(0).toUpperCase() + str.slice(1);
}

function toggleTheme() {
  const newTheme = themeManager.toggleTheme();
  updateThemeIcon(newTheme);
}

function toggleHelpSection() {
  const helpContent = document.getElementById('helpContent');
  const helpToggleIcon = document.getElementById('helpToggleIcon');
  const isExpanded = helpContent.classList.contains('expanded');

  if (isExpanded) {
    helpContent.classList.remove('expanded');
    helpToggleIcon.textContent = '▼';
    helpToggleIcon.style.transform = 'rotate(0deg)';
  } else {
    helpContent.classList.add('expanded');
    helpToggleIcon.textContent = '▲';
    helpToggleIcon.style.transform = 'rotate(180deg)';
  }
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

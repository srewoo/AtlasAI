/**
 * Setup Wizard - First-time user onboarding
 */

let currentStep = 0;
const totalSteps = 4;
let selectedProvider = null;
let wizardData = {
  llm_provider: null,
  llm_api_key: null,
  llm_model: null,
  confluence_url: '',
  jira_url: '',
  atlassian_api_token: ''
};

// Initialize wizard
document.addEventListener('DOMContentLoaded', () => {
  setupEventListeners();
  updateUI();
});

function setupEventListeners() {
  // Next button
  document.getElementById('nextBtn').addEventListener('click', () => {
    if (validateCurrentStep()) {
      nextStep();
    }
  });

  // Back button
  document.getElementById('backBtn').addEventListener('click', () => {
    prevStep();
  });

  // Skip button
  document.getElementById('skipBtn').addEventListener('click', () => {
    if (confirm('Skip setup? You can configure Atlas AI later in settings.')) {
      window.close();
    }
  });

  // Provider cards
  document.querySelectorAll('.provider-card').forEach(card => {
    card.addEventListener('click', () => {
      // Remove selected from all cards
      document.querySelectorAll('.provider-card').forEach(c => c.classList.remove('selected'));

      // Add selected to clicked card
      card.classList.add('selected');
      selectedProvider = card.dataset.provider;

      // Update model based on provider
      wizardData.llm_provider = selectedProvider;
      wizardData.llm_model = getDefaultModel(selectedProvider);
    });
  });

  // API key input
  document.getElementById('apiKeyInput')?.addEventListener('input', (e) => {
    wizardData.llm_api_key = e.target.value.trim();
  });

  // Integration inputs
  document.getElementById('confluenceUrl')?.addEventListener('input', (e) => {
    wizardData.confluence_url = e.target.value.trim();
  });

  document.getElementById('jiraUrl')?.addEventListener('input', (e) => {
    wizardData.jira_url = e.target.value.trim();
  });

  document.getElementById('atlassianToken')?.addEventListener('input', (e) => {
    wizardData.atlassian_api_token = e.target.value.trim();
  });
}

function getDefaultModel(provider) {
  const defaults = {
    openai: 'gpt-4o-mini',
    anthropic: 'claude-sonnet-4-20250514',
    gemini: 'gemini-2.5-flash',
    ollama: 'llama3.2'
  };
  return defaults[provider] || '';
}

function validateCurrentStep() {
  switch (currentStep) {
    case 0: // Welcome
      return true;

    case 1: // Provider selection
      if (!selectedProvider) {
        alert('Please select an AI provider');
        return false;
      }
      if (!wizardData.llm_api_key && selectedProvider !== 'ollama') {
        alert('Please enter your API key');
        return false;
      }
      return true;

    case 2: // Optional integrations
      // All optional, always valid
      return true;

    case 3: // Finish
      return true;

    default:
      return true;
  }
}

function nextStep() {
  if (currentStep < totalSteps - 1) {
    currentStep++;
    updateUI();
  } else {
    // Last step - finish wizard
    finishWizard();
  }
}

function prevStep() {
  if (currentStep > 0) {
    currentStep--;
    updateUI();
  }
}

function updateUI() {
  // Update progress indicators
  document.querySelectorAll('.progress-step').forEach((step, index) => {
    step.classList.remove('active', 'completed');
    if (index < currentStep) {
      step.classList.add('completed');
    } else if (index === currentStep) {
      step.classList.add('active');
    }
  });

  // Update wizard steps
  document.querySelectorAll('.wizard-step').forEach((step, index) => {
    step.classList.remove('active');
    if (index === currentStep) {
      step.classList.add('active');
    }
  });

  // Update buttons
  const backBtn = document.getElementById('backBtn');
  const nextBtn = document.getElementById('nextBtn');
  const skipBtn = document.getElementById('skipBtn');

  // Back button
  if (currentStep === 0) {
    backBtn.style.display = 'none';
  } else {
    backBtn.style.display = 'block';
  }

  // Next/Finish button
  if (currentStep === totalSteps - 1) {
    nextBtn.textContent = 'Finish';
    skipBtn.style.display = 'none';
  } else {
    nextBtn.textContent = 'Next';
    skipBtn.style.display = 'block';
  }
}

async function finishWizard() {
  try {
    // Save settings to Chrome storage
    const settings = {
      llm_provider: wizardData.llm_provider,
      llm_api_key: wizardData.llm_api_key,
      llm_model: wizardData.llm_model,
      confluence_url: wizardData.confluence_url,
      jira_url: wizardData.jira_url,
      atlassian_api_token: wizardData.atlassian_api_token,
      use_streaming: true, // Enable streaming by default
      version: '1.1.0'
    };

    await chrome.storage.local.set({ settings });

    // Mark wizard as completed
    await chrome.storage.local.set({ wizardCompleted: true });

    // Close wizard and open popup
    chrome.action.openPopup();
    window.close();
  } catch (error) {
    console.error('Error saving settings:', error);
    alert('Error saving settings. Please try again.');
  }
}

export default {
  currentStep,
  nextStep,
  prevStep,
  finishWizard
};

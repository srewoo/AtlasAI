/**
 * Settings Migration - Handle settings versioning and updates
 */

const CURRENT_VERSION = '1.1.0';

/**
 * Migrate settings from old version to current version
 * @param {Object} settings - Current settings
 * @returns {Object} Migrated settings
 */
export async function migrateSettings(settings) {
  if (!settings) {
    // No settings exist - return defaults
    return getDefaultSettings();
  }

  const oldVersion = settings.version || '1.0.0';

  if (oldVersion === CURRENT_VERSION) {
    // Already on current version
    return settings;
  }

  console.log(`Migrating settings from ${oldVersion} to ${CURRENT_VERSION}`);

  let migrated = { ...settings };

  // Apply migrations in order
  if (compareVersions(oldVersion, '1.1.0') < 0) {
    migrated = migrateToV1_1_0(migrated);
  }

  // Add future migrations here
  // if (compareVersions(oldVersion, '1.2.0') < 0) {
  //   migrated = migrateToV1_2_0(migrated);
  // }

  // Update version
  migrated.version = CURRENT_VERSION;

  // Save migrated settings
  await chrome.storage.local.set({ settings: migrated });

  return migrated;
}

/**
 * Migrate from 1.0.0 to 1.1.0
 * @param {Object} settings - Settings to migrate
 * @returns {Object} Migrated settings
 */
function migrateToV1_1_0(settings) {
  const migrated = { ...settings };

  // Add new settings with defaults
  if (migrated.use_streaming === undefined) {
    migrated.use_streaming = true;
  }

  // Ensure all required fields exist
  migrated.llm_provider = migrated.llm_provider || 'openai';
  migrated.llm_model = migrated.llm_model || getDefaultModel(migrated.llm_provider);

  return migrated;
}

/**
 * Get default settings
 * @returns {Object} Default settings
 */
function getDefaultSettings() {
  return {
    llm_provider: 'openai',
    llm_api_key: '',
    llm_model: 'gpt-4o-mini',
    confluence_url: '',
    jira_url: '',
    atlassian_api_token: '',
    use_streaming: true,
    version: CURRENT_VERSION
  };
}

/**
 * Get default model for a provider
 * @param {string} provider - LLM provider
 * @returns {string} Default model
 */
function getDefaultModel(provider) {
  const defaults = {
    openai: 'gpt-4o-mini',
    anthropic: 'claude-sonnet-4-20250514',
    gemini: 'gemini-2.5-flash',
    ollama: 'llama3.2'
  };
  return defaults[provider] || 'gpt-4o-mini';
}

/**
 * Compare two semantic versions
 * @param {string} v1 - First version
 * @param {string} v2 - Second version
 * @returns {number} -1 if v1 < v2, 0 if equal, 1 if v1 > v2
 */
function compareVersions(v1, v2) {
  const parts1 = v1.split('.').map(Number);
  const parts2 = v2.split('.').map(Number);

  for (let i = 0; i < 3; i++) {
    const p1 = parts1[i] || 0;
    const p2 = parts2[i] || 0;

    if (p1 < p2) return -1;
    if (p1 > p2) return 1;
  }

  return 0;
}

/**
 * Check if wizard should be shown
 * @returns {Promise<boolean>}
 */
export async function shouldShowWizard() {
  const { wizardCompleted, settings } = await chrome.storage.local.get([
    'wizardCompleted',
    'settings'
  ]);

  // Show wizard if not completed and no settings exist
  return !wizardCompleted && (!settings || !settings.llm_api_key);
}

export default {
  migrateSettings,
  shouldShowWizard,
  CURRENT_VERSION
};

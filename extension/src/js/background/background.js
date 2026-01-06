// Background service worker for Atlas AI Chrome extension
import { initContextMenu, handleContextMenuClick } from '../content/contextMenu.js';
import { migrateSettings, shouldShowWizard } from '../settings/migration.js';

// Configuration
const DEBUG_MODE = false; // Set to false for production/Chrome Store submission

chrome.runtime.onInstalled.addListener(async (details) => {
  // Initialize context menu
  initContextMenu();

  if (details.reason === 'install') {
    // First time installation - open setup wizard
    chrome.tabs.create({ url: chrome.runtime.getURL('wizard.html') });

    // Enable side panel on all sites by default
    await chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true });
  } else if (details.reason === 'update') {
    // Extension updated
    const previousVersion = details.previousVersion;
    const currentVersion = chrome.runtime.getManifest().version;

    if (DEBUG_MODE) {
      console.log(`Atlas AI updated from ${previousVersion} to ${currentVersion}`);
    }

    // Migrate settings if needed
    const { settings } = await chrome.storage.local.get('settings');
    if (settings) {
      await migrateSettings(settings);
    }

    // Check if we should show wizard for users who installed before wizard existed
    const showWizard = await shouldShowWizard();
    if (showWizard) {
      chrome.tabs.create({ url: chrome.runtime.getURL('wizard.html') });
    }

    // Enable side panel on all sites
    await chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true });
  }
});

// Open side panel when extension icon is clicked
chrome.action.onClicked.addListener(async (tab) => {
  await chrome.sidePanel.open({ windowId: tab.windowId });
});

// Handle context menu clicks
chrome.contextMenus.onClicked.addListener(handleContextMenuClick);

// Handle keyboard shortcuts
chrome.commands.onCommand.addListener((command) => {
  switch (command) {
    case 'new-chat':
      // Clear chat history and open popup
      chrome.storage.local.set({ clearChatOnOpen: true });
      chrome.action.openPopup();
      break;

    case 'toggle-theme':
      // Toggle theme
      chrome.storage.local.get(['theme'], (result) => {
        const currentTheme = result.theme || 'light';
        const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
        chrome.storage.local.set({ theme: newTheme });

        // Notify all extension pages to update theme
        chrome.runtime.sendMessage({
          type: 'THEME_CHANGED',
          theme: newTheme
        });
      });
      break;
  }
});

// Handle messages from popup
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.type === 'GET_SETTINGS') {
    chrome.storage.local.get(['settings'], (result) => {
      sendResponse({ settings: result.settings });
    });
    return true;
  }

  if (request.type === 'SAVE_SETTINGS') {
    chrome.storage.local.set({ settings: request.settings }, () => {
      sendResponse({ success: true });
    });
    return true;
  }
});

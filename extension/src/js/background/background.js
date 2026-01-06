// Background service worker for Atlas AI Chrome extension
import { initContextMenu, handleContextMenuClick } from '../content/contextMenu.js';
import { migrateSettings, shouldShowWizard } from '../settings/migration.js';

// Configuration
const DEBUG_MODE = false; // Set to false for production/Chrome Store submission

// Track which tabs have the side panel enabled
const enabledTabs = new Set();

// Initialize side panel settings
async function initSidePanel() {
  try {
    if (chrome.sidePanel) {
      // Enable auto-open on action click - this bypasses user gesture issues
      await chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true });
      if (DEBUG_MODE) {
        console.log('Side panel behavior set: openPanelOnActionClick = true');
      }
    }
  } catch (e) {
    if (DEBUG_MODE) {
      console.error('Error setting panel behavior:', e);
    }
  }
}

chrome.runtime.onInstalled.addListener(async (details) => {
  // Initialize context menu
  initContextMenu();

  // Initialize side panel settings
  await initSidePanel();

  if (details.reason === 'install') {
    // First time installation - open setup wizard
    chrome.tabs.create({ url: chrome.runtime.getURL('wizard.html') });
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
  }
});

// Also initialize on startup (when browser opens with extension already installed)
chrome.runtime.onStartup.addListener(async () => {
  await initSidePanel();
});

// Open side panel only for the clicked tab
// NOTE: We enable openPanelOnActionClick and let Chrome handle the opening
// This avoids the user gesture restriction on sidePanel.open()
chrome.action.onClicked.addListener((tab) => {
  if (!tab.id) return;

  const tabId = tab.id;

  // Track this tab as enabled
  enabledTabs.add(tabId);

  // Enable panel for this tab - Chrome will open it via openPanelOnActionClick
  chrome.sidePanel.setOptions({
    tabId: tabId,
    path: 'popup.html',
    enabled: true
  });

  // Handle restore state cleanup
  chrome.storage.local.get(['atlasMinimized', 'atlasPreparedRestore'], (result) => {
    if (result.atlasMinimized || result.atlasPreparedRestore) {
      chrome.tabs.sendMessage(tabId, { type: 'HIDE_FLOATING_BUTTON' }).catch(() => {});
      chrome.storage.local.set({
        atlasMinimized: false,
        atlasPreparedRestore: false
      });
    }
  });
});

// Disable side panel when tab is closed
chrome.tabs.onRemoved.addListener((tabId) => {
  enabledTabs.delete(tabId);
});

// Disable side panel when navigating to a different tab
chrome.tabs.onActivated.addListener(async (activeInfo) => {
  const activeTabId = activeInfo.tabId;

  // Disable panel for the newly active tab if it wasn't explicitly opened there
  if (!enabledTabs.has(activeTabId)) {
    try {
      await chrome.sidePanel.setOptions({
        tabId: activeTabId,
        enabled: false
      });
    } catch (e) {
      // Tab might not exist yet
    }
  }

  // Also disable panel for all other tabs except the ones in enabledTabs
  try {
    const tabs = await chrome.tabs.query({ currentWindow: true });
    for (const tab of tabs) {
      if (tab.id && tab.id !== activeTabId && !enabledTabs.has(tab.id)) {
        try {
          await chrome.sidePanel.setOptions({
            tabId: tab.id,
            enabled: false
          });
        } catch (e) {
          // Ignore errors for individual tabs
        }
      }
    }
  } catch (e) {
    // Ignore errors
  }
});

// Handle window focus changes - disable panel in other windows
chrome.windows.onFocusChanged.addListener(async (windowId) => {
  if (windowId === chrome.windows.WINDOW_ID_NONE) return;

  try {
    const tabs = await chrome.tabs.query({ windowId });
    for (const tab of tabs) {
      if (tab.id && !enabledTabs.has(tab.id)) {
        try {
          await chrome.sidePanel.setOptions({
            tabId: tab.id,
            enabled: false
          });
        } catch (e) {
          // Ignore errors
        }
      }
    }
  } catch (e) {
    // Ignore errors
  }
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

// Handle messages from popup and content scripts
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

  // Handle minimize - close panel and show floating button
  if (request.type === 'MINIMIZE_PANEL') {
    handleMinimize(request.tabId);
    sendResponse({ success: true });
    return true;
  }

  // Handle prepare restore - enable panel so user can click icon to open
  if (request.type === 'PREPARE_RESTORE') {
    handlePrepareRestore(sender.tab?.id);
    sendResponse({ success: true });
    return true;
  }
});

// Minimize: Close side panel and show floating button
async function handleMinimize(tabId) {
  try {
    // Get current tab if not provided
    if (!tabId) {
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      tabId = tab?.id;
    }

    if (!tabId) return;

    // Store minimized state
    await chrome.storage.local.set({
      atlasMinimized: true,
      atlasMinimizedTabId: tabId
    });

    // Send message to content script to show floating button
    try {
      await chrome.tabs.sendMessage(tabId, { type: 'SHOW_FLOATING_BUTTON' });
    } catch (e) {
      // Content script might not be loaded, inject it
      await chrome.scripting.executeScript({
        target: { tabId },
        files: ['js/content/floatingButton.js']
      });
      // Try again after injection
      setTimeout(async () => {
        try {
          await chrome.tabs.sendMessage(tabId, { type: 'SHOW_FLOATING_BUTTON' });
        } catch (err) {
          console.error('Failed to show floating button:', err);
        }
      }, 100);
    }

    // Close the side panel by disabling it for this tab
    await chrome.sidePanel.setOptions({
      tabId: tabId,
      enabled: false
    });

    enabledTabs.delete(tabId);

    if (DEBUG_MODE) {
      console.log('Panel minimized for tab:', tabId);
    }
  } catch (error) {
    console.error('Error minimizing panel:', error);
  }
}

// Prepare restore: Enable panel so user can click icon to open it
async function handlePrepareRestore(tabId) {
  try {
    if (!tabId) {
      const result = await chrome.storage.local.get(['atlasMinimizedTabId']);
      tabId = result.atlasMinimizedTabId;
    }

    if (!tabId) {
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      tabId = tab?.id;
    }

    if (!tabId) return;

    // Mark that we're preparing to restore (so action.onClicked knows)
    await chrome.storage.local.set({
      atlasPreparedRestore: true,
      atlasPreparedRestoreTabId: tabId
    });

    // Pre-enable the panel for this tab
    await chrome.sidePanel.setOptions({
      tabId: tabId,
      path: 'popup.html',
      enabled: true
    });

    // Add to enabled tabs so it stays enabled when user clicks
    enabledTabs.add(tabId);

    if (DEBUG_MODE) {
      console.log('Panel prepared for restore on tab:', tabId);
    }
  } catch (error) {
    console.error('Error preparing restore:', error);
  }
}

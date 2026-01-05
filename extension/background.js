// Background service worker for Atlas AI Chrome extension

// Configuration
const DEBUG_MODE = false; // Set to false for production/Chrome Store submission

chrome.runtime.onInstalled.addListener((details) => {
  if (details.reason === 'install') {
    // First time installation - open settings page
    chrome.tabs.create({ url: chrome.runtime.getURL('settings.html') });
  } else if (details.reason === 'update') {
    // Extension updated
    if (DEBUG_MODE) {
      const previousVersion = details.previousVersion;
      const currentVersion = chrome.runtime.getManifest().version;
      console.log(`Atlas AI updated from ${previousVersion} to ${currentVersion}`);
    }
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

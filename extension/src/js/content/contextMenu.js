/**
 * Context Menu - Right-click integration for selected text
 */

// This file is loaded as a content script or used by background script
// to handle context menu interactions

/**
 * Initialize context menu
 * Called from background.js
 */
export function initContextMenu() {
  // Create context menu items
  chrome.contextMenus.create({
    id: 'atlas-ai-ask',
    title: 'Ask Atlas AI: "%s"',
    contexts: ['selection']
  });

  chrome.contextMenus.create({
    id: 'atlas-ai-explain',
    title: 'Explain with Atlas AI',
    contexts: ['selection']
  });

  chrome.contextMenus.create({
    id: 'atlas-ai-summarize',
    title: 'Summarize with Atlas AI',
    contexts: ['selection']
  });
}

/**
 * Handle context menu click
 * @param {Object} info - Click info
 * @param {Object} tab - Tab info
 */
export function handleContextMenuClick(info, tab) {
  const selectedText = info.selectionText;

  if (!selectedText) return;

  let query = selectedText;

  // Modify query based on menu item
  switch (info.menuItemId) {
    case 'atlas-ai-ask':
      // Use selected text as-is
      break;
    case 'atlas-ai-explain':
      query = `Explain: ${selectedText}`;
      break;
    case 'atlas-ai-summarize':
      query = `Summarize: ${selectedText}`;
      break;
    default:
      return;
  }

  // Store the query in chrome.storage so popup can pick it up
  chrome.storage.local.set({
    pendingQuery: query,
    pendingQueryTimestamp: Date.now()
  });

  // Open the popup
  chrome.action.openPopup();
}

export default {
  initContextMenu,
  handleContextMenuClick
};

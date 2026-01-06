// Floating restore button for minimized Atlas AI
// This content script injects a floating button when the side panel is minimized

(function() {
  const BUTTON_ID = 'atlas-ai-floating-btn';
  const TOOLTIP_ID = 'atlas-ai-tooltip';

  // Listen for messages from background script
  chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.type === 'SHOW_FLOATING_BUTTON') {
      showFloatingButton();
      sendResponse({ success: true });
    } else if (request.type === 'HIDE_FLOATING_BUTTON') {
      hideFloatingButton();
      sendResponse({ success: true });
    }
    return true;
  });

  function showFloatingButton() {
    // Don't create if already exists
    if (document.getElementById(BUTTON_ID)) return;

    const button = document.createElement('div');
    button.id = BUTTON_ID;
    button.innerHTML = `
      <div class="atlas-floating-btn-inner">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
        </svg>
        <span class="atlas-floating-btn-text">Atlas AI</span>
      </div>
      <div id="${TOOLTIP_ID}" class="atlas-tooltip">
        Click the Atlas AI icon in toolbar to restore
        <div class="atlas-tooltip-arrow"></div>
      </div>
    `;

    // Inject styles
    const style = document.createElement('style');
    style.id = 'atlas-floating-btn-styles';
    style.textContent = `
      #${BUTTON_ID} {
        position: fixed;
        bottom: 20px;
        right: 20px;
        z-index: 2147483647;
        cursor: pointer;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
      }

      #${BUTTON_ID}:hover {
        transform: scale(1.05);
      }

      #${BUTTON_ID}:hover .atlas-floating-btn-inner {
        box-shadow: 0 8px 25px rgba(37, 99, 235, 0.4);
      }

      .atlas-floating-btn-inner {
        display: flex;
        align-items: center;
        gap: 8px;
        background: linear-gradient(135deg, #2563EB 0%, #1D4ED8 100%);
        color: white;
        padding: 12px 16px;
        border-radius: 50px;
        box-shadow: 0 4px 15px rgba(37, 99, 235, 0.3);
        font-size: 14px;
        font-weight: 600;
      }

      .atlas-floating-btn-inner svg {
        flex-shrink: 0;
      }

      .atlas-floating-btn-text {
        white-space: nowrap;
      }

      /* Tooltip styles */
      .atlas-tooltip {
        position: absolute;
        bottom: 100%;
        right: 0;
        margin-bottom: 10px;
        background: #1F2937;
        color: white;
        padding: 10px 14px;
        border-radius: 8px;
        font-size: 13px;
        font-weight: 500;
        white-space: nowrap;
        opacity: 0;
        visibility: hidden;
        transform: translateY(5px);
        transition: all 0.2s ease;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
      }

      .atlas-tooltip-arrow {
        position: absolute;
        bottom: -6px;
        right: 20px;
        width: 12px;
        height: 12px;
        background: #1F2937;
        transform: rotate(45deg);
      }

      #${BUTTON_ID}:hover .atlas-tooltip,
      #${BUTTON_ID}.show-tooltip .atlas-tooltip {
        opacity: 1;
        visibility: visible;
        transform: translateY(0);
      }

      /* Animation on appear */
      @keyframes atlasSlideIn {
        from {
          opacity: 0;
          transform: translateY(20px) scale(0.9);
        }
        to {
          opacity: 1;
          transform: translateY(0) scale(1);
        }
      }

      #${BUTTON_ID} {
        animation: atlasSlideIn 0.3s ease-out;
      }

      /* Pulse animation to draw attention */
      @keyframes atlasPulse {
        0%, 100% {
          box-shadow: 0 4px 15px rgba(37, 99, 235, 0.3);
        }
        50% {
          box-shadow: 0 4px 25px rgba(37, 99, 235, 0.5);
        }
      }

      .atlas-floating-btn-inner {
        animation: atlasPulse 2s ease-in-out infinite;
      }

      #${BUTTON_ID}:hover .atlas-floating-btn-inner {
        animation: none;
      }
    `;

    // Add to page
    if (!document.getElementById('atlas-floating-btn-styles')) {
      document.head.appendChild(style);
    }
    document.body.appendChild(button);

    // Click handler - show tooltip and prepare panel for restoration
    button.addEventListener('click', () => {
      // Show tooltip
      button.classList.add('show-tooltip');

      // Tell background to prepare the panel (enable it for this tab)
      chrome.runtime.sendMessage({ type: 'PREPARE_RESTORE' });

      // Hide tooltip after 3 seconds
      setTimeout(() => {
        button.classList.remove('show-tooltip');
      }, 3000);
    });
  }

  function hideFloatingButton() {
    const button = document.getElementById(BUTTON_ID);
    if (button) {
      button.style.animation = 'none';
      button.style.transition = 'opacity 0.2s ease, transform 0.2s ease';
      button.style.opacity = '0';
      button.style.transform = 'translateY(20px) scale(0.9)';
      setTimeout(() => button.remove(), 200);
    }
  }

  // Check on load if we should show the button
  chrome.storage.local.get(['atlasMinimized'], (result) => {
    if (result.atlasMinimized) {
      showFloatingButton();
    }
  });
})();

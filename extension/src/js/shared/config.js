// Atlas AI Extension Configuration
// Update this file before deploying to Chrome Web Store

const CONFIG = {
  // Backend API URL - REQUIRED
  // For local development: 'http://localhost:8001'
  // For production: 'https://your-backend-domain.com'
  API_URL: 'http://localhost:8001',
  
  // Default user ID (used if not authenticated)
  DEFAULT_USER_ID: 'default',
  
  // Extension settings
  DEBUG_MODE: false,
  
  // Timeouts (in milliseconds)
  REQUEST_TIMEOUT: 30000,
  
  // Version info (auto-populated from manifest)
  get VERSION() {
    return chrome.runtime.getManifest().version;
  },
  
  // Extension ID (useful for debugging)
  get EXTENSION_ID() {
    return chrome.runtime.id;
  }
};

// Freeze config to prevent accidental modifications
Object.freeze(CONFIG);


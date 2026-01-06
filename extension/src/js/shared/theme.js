/**
 * ThemeManager - Manages light/dark theme switching
 */
class ThemeManager {
  constructor() {
    this.currentTheme = null;
  }

  async init() {
    // Prevent transition on initial load
    document.body.classList.add('no-transition');

    // Load saved theme or detect system preference
    const saved = await this.getSavedTheme();
    if (saved) {
      this.setTheme(saved, false);
    } else {
      this.detectSystemTheme();
    }

    // Remove no-transition class after a brief delay
    setTimeout(() => {
      document.body.classList.remove('no-transition');
    }, 100);

    // Listen for system theme changes
    window.matchMedia('(prefers-color-scheme: dark)')
      .addEventListener('change', (e) => {
        if (!this.currentTheme) {
          this.setTheme(e.matches ? 'dark' : 'light', false);
        }
      });
  }

  async getSavedTheme() {
    return new Promise((resolve) => {
      chrome.storage.local.get(['theme'], (result) => {
        resolve(result.theme);
      });
    });
  }

  detectSystemTheme() {
    const isDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    this.setTheme(isDark ? 'dark' : 'light', false);
  }

  setTheme(theme, save = true) {
    this.currentTheme = theme;
    document.documentElement.setAttribute('data-theme', theme);

    if (save) {
      chrome.storage.local.set({ theme });
    }

    // Dispatch event for other components
    window.dispatchEvent(new CustomEvent('themechange', { detail: { theme } }));
  }

  toggleTheme() {
    const newTheme = this.currentTheme === 'dark' ? 'light' : 'dark';
    this.setTheme(newTheme);
    return newTheme;
  }

  getTheme() {
    return this.currentTheme;
  }

  isDark() {
    return this.currentTheme === 'dark';
  }
}

// Export singleton instance
const themeManager = new ThemeManager();
export default themeManager;

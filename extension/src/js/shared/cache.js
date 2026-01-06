/**
 * CacheManager - In-memory caching for API responses
 */
class CacheManager {
  constructor(options = {}) {
    this.cache = new Map();
    this.maxSize = options.maxSize || 50; // Maximum number of cached items
    this.ttl = options.ttl || 5 * 60 * 1000; // Time to live: 5 minutes default
    this.enabled = options.enabled !== false; // Enabled by default
  }

  /**
   * Generate cache key from query
   * @param {string} query - User query
   * @param {string} sessionId - Session ID (optional)
   * @returns {string} Cache key
   */
  generateKey(query, sessionId = '') {
    // Normalize query: trim, lowercase, remove extra spaces
    const normalized = query.trim().toLowerCase().replace(/\s+/g, ' ');
    return `${sessionId}:${normalized}`;
  }

  /**
   * Get cached response
   * @param {string} query - User query
   * @param {string} sessionId - Session ID
   * @returns {Object|null} Cached response or null
   */
  get(query, sessionId = '') {
    if (!this.enabled) return null;

    const key = this.generateKey(query, sessionId);
    const cached = this.cache.get(key);

    if (!cached) return null;

    // Check if expired
    if (Date.now() > cached.expiresAt) {
      this.cache.delete(key);
      return null;
    }

    // Update access time for LRU
    cached.lastAccessed = Date.now();

    return cached.data;
  }

  /**
   * Set cached response
   * @param {string} query - User query
   * @param {Object} data - Response data
   * @param {string} sessionId - Session ID
   */
  set(query, data, sessionId = '') {
    if (!this.enabled) return;

    const key = this.generateKey(query, sessionId);

    // Enforce max size using LRU eviction
    if (this.cache.size >= this.maxSize && !this.cache.has(key)) {
      this.evictLRU();
    }

    this.cache.set(key, {
      data: data,
      createdAt: Date.now(),
      lastAccessed: Date.now(),
      expiresAt: Date.now() + this.ttl
    });
  }

  /**
   * Evict least recently used item
   */
  evictLRU() {
    let oldestKey = null;
    let oldestTime = Infinity;

    for (const [key, value] of this.cache.entries()) {
      if (value.lastAccessed < oldestTime) {
        oldestTime = value.lastAccessed;
        oldestKey = key;
      }
    }

    if (oldestKey) {
      this.cache.delete(oldestKey);
    }
  }

  /**
   * Clear all cached items
   */
  clear() {
    this.cache.clear();
  }

  /**
   * Clear expired items
   */
  clearExpired() {
    const now = Date.now();
    for (const [key, value] of this.cache.entries()) {
      if (now > value.expiresAt) {
        this.cache.delete(key);
      }
    }
  }

  /**
   * Get cache statistics
   * @returns {Object} Cache stats
   */
  getStats() {
    return {
      size: this.cache.size,
      maxSize: this.maxSize,
      ttl: this.ttl,
      enabled: this.enabled
    };
  }

  /**
   * Enable caching
   */
  enable() {
    this.enabled = true;
  }

  /**
   * Disable caching
   */
  disable() {
    this.enabled = false;
  }

  /**
   * Check if caching is enabled
   * @returns {boolean}
   */
  isEnabled() {
    return this.enabled;
  }
}

export default CacheManager;

/**
 * API Client - Handles API requests with retry logic and error handling
 */
class APIClient {
  constructor(baseUrl) {
    this.baseUrl = baseUrl;
    this.maxRetries = 3;
    this.initialRetryDelay = 1000; // 1 second
  }

  /**
   * Make an API request with exponential backoff retry
   * @param {string} endpoint - API endpoint
   * @param {Object} options - Fetch options
   * @param {number} retryCount - Current retry attempt
   * @returns {Promise<Response>}
   */
  async request(endpoint, options = {}, retryCount = 0) {
    const url = `${this.baseUrl}${endpoint}`;

    try {
      const response = await fetch(url, {
        ...options,
        headers: {
          'Content-Type': 'application/json',
          ...options.headers
        }
      });

      // If response is ok, return it
      if (response.ok) {
        return response;
      }

      // Handle specific error codes
      if (response.status === 429) {
        // Rate limited - always retry
        throw new Error('RATE_LIMITED');
      } else if (response.status >= 500) {
        // Server error - retry
        throw new Error('SERVER_ERROR');
      } else if (response.status === 401 || response.status === 403) {
        // Authentication error - don't retry
        const error = await response.json();
        throw new Error(error.detail || 'Authentication failed');
      } else {
        // Other client errors - don't retry
        const error = await response.json();
        throw new Error(error.detail || `Request failed with status ${response.status}`);
      }

    } catch (error) {
      // Network error or rate limit - retry with exponential backoff
      const shouldRetry = (
        error.message === 'RATE_LIMITED' ||
        error.message === 'SERVER_ERROR' ||
        error.name === 'TypeError' // Network errors
      ) && retryCount < this.maxRetries;

      if (shouldRetry) {
        const delay = this.calculateRetryDelay(retryCount);
        console.log(`Retry attempt ${retryCount + 1}/${this.maxRetries} after ${delay}ms`);

        await this.sleep(delay);
        return this.request(endpoint, options, retryCount + 1);
      }

      // Max retries exceeded or non-retryable error
      throw error;
    }
  }

  /**
   * Calculate retry delay with exponential backoff and jitter
   * @param {number} retryCount - Current retry attempt
   * @returns {number} Delay in milliseconds
   */
  calculateRetryDelay(retryCount) {
    // Exponential backoff: delay = initialDelay * 2^retryCount
    const exponentialDelay = this.initialRetryDelay * Math.pow(2, retryCount);

    // Add jitter (random variance of ±25%)
    const jitter = exponentialDelay * 0.25 * (Math.random() * 2 - 1);

    return Math.floor(exponentialDelay + jitter);
  }

  /**
   * Sleep for specified milliseconds
   * @param {number} ms - Milliseconds to sleep
   * @returns {Promise<void>}
   */
  sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  /**
   * GET request
   * @param {string} endpoint - API endpoint
   * @param {Object} options - Additional fetch options
   * @returns {Promise<any>}
   */
  async get(endpoint, options = {}) {
    const response = await this.request(endpoint, {
      method: 'GET',
      ...options
    });
    return response.json();
  }

  /**
   * POST request
   * @param {string} endpoint - API endpoint
   * @param {Object} data - Request body
   * @param {Object} options - Additional fetch options
   * @returns {Promise<any>}
   */
  async post(endpoint, data, options = {}) {
    const response = await this.request(endpoint, {
      method: 'POST',
      body: JSON.stringify(data),
      ...options
    });
    return response.json();
  }

  /**
   * DELETE request
   * @param {string} endpoint - API endpoint
   * @param {Object} options - Additional fetch options
   * @returns {Promise<any>}
   */
  async delete(endpoint, options = {}) {
    const response = await this.request(endpoint, {
      method: 'DELETE',
      ...options
    });

    // DELETE might not return JSON
    const contentType = response.headers.get('content-type');
    if (contentType && contentType.includes('application/json')) {
      return response.json();
    }
    return { success: true };
  }

  /**
   * Stream request (for SSE)
   * @param {string} endpoint - API endpoint
   * @param {Object} data - Request body
   * @param {Object} options - Additional fetch options
   * @returns {Promise<Response>}
   */
  async stream(endpoint, data, options = {}) {
    return this.request(endpoint, {
      method: 'POST',
      body: JSON.stringify(data),
      ...options
    });
  }
}

export default APIClient;

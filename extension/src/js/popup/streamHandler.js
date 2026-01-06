/**
 * StreamHandler - Manages SSE streaming for chat responses
 */
class StreamHandler {
  constructor(apiUrl) {
    this.apiUrl = apiUrl;
    this.currentController = null;
  }

  /**
   * Stream a chat message and handle the response chunks
   * @param {string} message - User message
   * @param {string} sessionId - Session ID
   * @param {string} userId - User ID
   * @param {Object} callbacks - Callback functions for stream events
   * @returns {Promise<Object>} - Final response object
   */
  async streamChat(message, sessionId, userId, callbacks = {}) {
    const {
      onStart = () => {},
      onSources = (sources) => {},
      onContext = (context) => {},
      onChunk = (text) => {},
      onDone = (result) => {},
      onError = (error) => {}
    } = callbacks;

    // Create abort controller for cancellation
    this.currentController = new AbortController();
    const signal = this.currentController.signal;

    let fullResponse = '';
    let sources = [];
    let usedSources = [];
    let documents = [];

    try {
      const response = await fetch(`${this.apiUrl}/api/chat/stream?user_id=${userId}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: message,
          session_id: sessionId
        }),
        signal
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to connect to stream');
      }

      // Read the stream
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();

        if (done) break;

        // Decode the chunk and add to buffer
        buffer += decoder.decode(value, { stream: true });

        // Process complete SSE messages
        const lines = buffer.split('\n');
        buffer = lines.pop() || ''; // Keep incomplete line in buffer

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));

              switch (data.type) {
                case 'start':
                  onStart();
                  break;

                case 'sources':
                  sources = data.sources || [];
                  onSources(sources);
                  break;

                case 'context':
                  usedSources = data.used_sources || [];
                  documents = data.documents || [];
                  onContext({ count: data.count, usedSources, documents });
                  break;

                case 'chunk':
                  fullResponse += data.text;
                  onChunk(data.text);
                  break;

                case 'done':
                  sources = data.sources || sources;
                  usedSources = data.used_sources || usedSources;
                  documents = data.documents || documents;
                  onDone({ sources, usedSources, documents });
                  break;

                case 'error':
                  throw new Error(data.message || 'Stream error');

                default:
                  console.warn('Unknown stream event type:', data.type);
              }
            } catch (parseError) {
              console.error('Error parsing SSE message:', parseError);
            }
          }
        }
      }

      this.currentController = null;

      return {
        response: fullResponse,
        sources: sources,
        usedSources: usedSources,
        documents: documents
      };

    } catch (error) {
      this.currentController = null;

      if (error.name === 'AbortError') {
        throw new Error('Stream cancelled by user');
      }

      onError(error);
      throw error;
    }
  }

  /**
   * Cancel the current stream
   */
  cancel() {
    if (this.currentController) {
      this.currentController.abort();
      this.currentController = null;
    }
  }

  /**
   * Check if a stream is currently active
   */
  isStreaming() {
    return this.currentController !== null;
  }
}

export default StreamHandler;

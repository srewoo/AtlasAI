/**
 * MessageRenderer - Renders markdown with syntax highlighting and XSS protection
 */
import { marked } from 'marked';
import hljs from 'highlight.js';
import DOMPurify from 'dompurify';

class MessageRenderer {
  constructor() {
    this.configureMarked();
  }

  configureMarked() {
    // Configure marked with custom renderer
    const renderer = new marked.Renderer();

    // Custom code block renderer with copy button
    renderer.code = (code, language) => {
      const validLang = language && hljs.getLanguage(language) ? language : 'plaintext';
      const highlighted = hljs.highlight(code, { language: validLang }).value;

      return `
        <div class="code-block-wrapper">
          <button class="code-copy-btn" data-code="${this.escapeHtml(code)}">
            Copy
          </button>
          <pre><code class="hljs language-${validLang}">${highlighted}</code></pre>
        </div>
      `;
    };

    // Custom inline code renderer
    renderer.codespan = (code) => {
      return `<code>${this.escapeHtml(code)}</code>`;
    };

    marked.setOptions({
      renderer,
      gfm: true, // GitHub Flavored Markdown
      breaks: true, // Convert \n to <br>
      pedantic: false,
      sanitize: false // We'll use DOMPurify instead
    });
  }

  renderMarkdown(text) {
    if (!text) return '';

    // Convert markdown to HTML
    const rawHtml = marked.parse(text);

    // Sanitize with DOMPurify to prevent XSS
    const cleanHtml = DOMPurify.sanitize(rawHtml, {
      ALLOWED_TAGS: [
        'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
        'p', 'br', 'strong', 'em', 'u', 'del', 's',
        'ul', 'ol', 'li',
        'a', 'code', 'pre',
        'blockquote', 'table', 'thead', 'tbody', 'tr', 'th', 'td',
        'div', 'span', 'button', 'hr', 'img'
      ],
      ALLOWED_ATTR: [
        'href', 'class', 'data-code', 'target', 'rel',
        'src', 'alt', 'title', 'width', 'height'
      ],
      ALLOWED_URI_REGEXP: /^(?:(?:(?:f|ht)tps?|mailto|tel|callto|cid|xmpp):|[^a-z]|[a-z+.\-]+(?:[^a-z+.\-:]|$))/i,
      ALLOW_DATA_ATTR: true
    });

    return cleanHtml;
  }

  renderPlainText(text) {
    if (!text) return '';

    // Escape HTML and preserve line breaks
    return text
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;')
      .replace(/\n/g, '<br>');
  }

  escapeHtml(text) {
    if (!text) return '';

    return text
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  setupCopyButtons(container) {
    // Add click handlers to copy buttons
    const buttons = container.querySelectorAll('.code-copy-btn');

    buttons.forEach(btn => {
      btn.addEventListener('click', async (e) => {
        e.stopPropagation();
        const code = btn.getAttribute('data-code');

        try {
          await navigator.clipboard.writeText(code);
          const originalText = btn.textContent;
          btn.textContent = 'Copied!';
          btn.style.backgroundColor = 'var(--primary)';
          btn.style.color = 'var(--primary-foreground)';

          setTimeout(() => {
            btn.textContent = originalText;
            btn.style.backgroundColor = '';
            btn.style.color = '';
          }, 2000);
        } catch (err) {
          console.error('Copy failed:', err);
          btn.textContent = 'Failed';

          setTimeout(() => {
            btn.textContent = 'Copy';
          }, 2000);
        }
      });
    });
  }
}

// Export singleton instance
const messageRenderer = new MessageRenderer();
export default messageRenderer;

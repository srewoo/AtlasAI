# Atlas AI - Chrome Web Store Submission Guide

## Pre-Submission Checklist

### ✅ Required Assets

#### Icons (Already Created)
- [x] `icons/icon16.png` (16×16 px)
- [x] `icons/icon48.png` (48×48 px)
- [x] `icons/icon128.png` (128×128 px)

#### Store Listing Assets (Need to Create)
- [ ] **Screenshots** (1280×800 or 640×400) - at least 1, up to 5
  - Screenshot 1: Chat interface with sample conversation
  - Screenshot 2: Settings page
  - Screenshot 3: Source badges showing Confluence/Jira/Web
- [ ] **Small promotional tile** (440×280) - optional but recommended
- [ ] **Large promotional tile** (920×680) - optional
- [ ] **Marquee image** (1400×560) - optional

### ✅ Required Information

#### Store Listing Details
```
Name: Atlas AI
Short Description (132 chars max):
AI-powered assistant for Confluence & Jira. Get instant answers from your docs, tickets, and web using GPT, Claude, or Gemini.

Detailed Description:
Atlas AI is an intelligent Chrome extension that helps you find information across multiple knowledge sources:

🔍 FEATURES:
• Search Confluence documentation instantly
• Query Jira tickets and issues
• Web search for up-to-date information
• Multi-LLM support (OpenAI, Anthropic Claude, Google Gemini, Ollama)
• Agentic RAG for intelligent query routing
• Vector-based caching for fast responses

🎯 HOW IT WORKS:
1. Type your question in natural language
2. Atlas AI analyzes your query
3. Routes to relevant sources (Confluence, Jira, Web)
4. Combines information and generates a comprehensive answer

⚙️ SETUP:
1. Install the extension
2. Configure your LLM API key (OpenAI, Anthropic, or Google)
3. Optionally add Confluence/Jira credentials
4. Start asking questions!

🔒 PRIVACY:
• All credentials stored locally in your browser
• No data sent to third parties (except your chosen LLM provider)
• Self-hostable backend for complete control

Category: Productivity
Language: English
```

#### Privacy Policy (REQUIRED)
You MUST create a privacy policy. Host it at a public URL.

Example privacy policy topics to cover:
1. What data is collected (settings, chat history)
2. Where data is stored (locally in Chrome, on your backend)
3. Third-party services used (LLM providers)
4. How to delete data
5. Contact information

#### Single Purpose Description
"This extension provides an AI-powered chatbot interface that searches Confluence, Jira, and the web to answer user questions."

### ✅ Code Compliance

#### Before Submission
1. **Update config.js** with production backend URL:
   ```javascript
   API_URL: 'https://your-production-backend.com'
   ```

2. **Set DEBUG_MODE to false** in background.js:
   ```javascript
   const DEBUG_MODE = false;
   ```

3. **Remove any console.log statements** or wrap them in DEBUG_MODE checks

4. **Test all functionality** with production backend

### ✅ Packaging for Submission

#### Option 1: ZIP File
```bash
cd extension
zip -r ../atlas-ai-extension.zip . -x "*.DS_Store" -x "*.md" -x "SETUP_INSTRUCTIONS.txt"
```

#### Option 2: Chrome Developer Dashboard
1. Go to https://chrome.google.com/webstore/devconsole
2. Click "New Item"
3. Upload the ZIP file
4. Fill in all required fields
5. Submit for review

### ✅ Review Process

#### Timeline
- Initial review: 1-3 business days
- If issues found: Fix and resubmit
- Total time: Usually 1-7 days

#### Common Rejection Reasons
1. Missing privacy policy
2. Overly broad permissions without justification
3. Non-functional extension
4. Misleading description
5. Missing or low-quality screenshots

### ✅ Post-Submission

#### After Approval
1. Share the Chrome Web Store link
2. Monitor user reviews
3. Track usage via Chrome Developer Dashboard
4. Plan updates based on feedback

#### Updating the Extension
1. Increment version in manifest.json
2. Make changes
3. Upload new ZIP to Developer Dashboard
4. Submit for review

## Backend Hosting Requirements

For the extension to work, you need a hosted backend:

### Recommended Providers
1. **Railway.app** - Easy deployment from Git
2. **Render.com** - Free tier available
3. **Google Cloud Run** - Serverless
4. **AWS ECS** - Enterprise scale

### Backend URL Configuration
After deploying, update `config.js`:
```javascript
API_URL: 'https://your-backend-url.com'
```

### CORS Configuration
Ensure backend allows requests from:
- `chrome-extension://YOUR_EXTENSION_ID`
- Or use `*` for development

## Cost Estimates

### One-Time Costs
- Chrome Developer Account: $5 (one-time registration fee)

### Ongoing Costs
- Backend hosting: $0-50/month (depending on usage)
- MongoDB: $0-25/month (Atlas free tier available)
- LLM API: ~$0.001-0.01 per query (user pays)

## Support Resources

- Chrome Extension Docs: https://developer.chrome.com/docs/extensions/
- Manifest V3 Migration: https://developer.chrome.com/docs/extensions/mv3/intro/
- Store Policies: https://developer.chrome.com/docs/webstore/program-policies/


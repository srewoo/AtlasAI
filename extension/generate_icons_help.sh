#!/bin/bash

# Icon Generator Helper Script
# This script provides instructions and helpers for creating extension icons

echo "=========================================="
echo "Chrome Extension Icon Generator Helper"
echo "=========================================="
echo ""
echo "You need three PNG icons:"
echo "  - icon16.png (16x16 pixels)"
echo "  - icon48.png (48x48 pixels)"
echo "  - icon128.png (128x128 pixels)"
echo ""
echo "Options to create icons:"
echo ""
echo "1. ONLINE ICON GENERATORS (Easiest):"
echo "   - https://favicon.io/"
echo "   - https://www.canva.com/ (Free templates)"
echo "   - https://www.favicon-generator.org/"
echo ""
echo "2. AI IMAGE GENERATORS:"
echo "   - ChatGPT with DALL-E: 'Create a 128x128 icon for an AI chatbot'"
echo "   - Midjourney: '/imagine chatbot icon, simple, blue, 128x128'"
echo ""
echo "3. USE THE PROVIDED SVG:"
echo "   We've created an SVG icon at: /app/extension/icons/icon.svg"
echo "   You can convert it to PNG using:"
echo "   - Online: https://cloudconvert.com/svg-to-png"
echo "   - Command line (if you have ImageMagick):"
echo "     convert icon.svg -resize 16x16 icon16.png"
echo "     convert icon.svg -resize 48x48 icon48.png"
echo "     convert icon.svg -resize 128x128 icon128.png"
echo ""
echo "4. SIMPLE PLACEHOLDER ICONS:"
echo "   Use any simple colored squares from:"
echo "   - https://via.placeholder.com/16/2563EB/FFFFFF?text=AI"
echo "   - Download and save as icon16.png, icon48.png, icon128.png"
echo ""
echo "=========================================="
echo "Quick Check:"
echo "=========================================="
echo ""

cd /app/extension/icons

if [ -f "icon16.png" ]; then
    echo "✓ icon16.png exists"
else
    echo "✗ icon16.png missing"
fi

if [ -f "icon48.png" ]; then
    echo "✓ icon48.png exists"
else
    echo "✗ icon48.png missing"
fi

if [ -f "icon128.png" ]; then
    echo "✓ icon128.png exists"
else
    echo "✗ icon128.png missing"
fi

echo ""
echo "Place your PNG files in: /app/extension/icons/"
echo "=========================================="

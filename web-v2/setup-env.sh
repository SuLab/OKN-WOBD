#!/bin/bash
# Setup script for environment variables

echo "Setting up .env.local file..."

if [ -f .env.local ]; then
  echo "⚠️  .env.local already exists. Backing up to .env.local.backup"
  cp .env.local .env.local.backup
fi

cat > .env.local << 'EOF'
# Anthropic API Key (for LLM-generated SPARQL - Lane B, default)
# Get your key from: https://console.anthropic.com/settings/keys
ANTHROPIC_SHARED_API_KEY=sk-ant-your-key-here

# OpenAI API Key (optional - for OpenAI provider)
# Get your key from: https://platform.openai.com/api-keys
OPENAI_SHARED_API_KEY=sk-your-key-here

# Budget limits for shared API keys (optional)
# Applies to both Anthropic and OpenAI
SHARED_BUDGET_USD=5
SHARED_BUDGET_STOP_USD=4.5

# FRINK Federation Endpoint (optional - already configured in context pack)
# Only set this if you want to override the default
# NEXT_PUBLIC_FRINK_FEDERATION_URL=https://frink.apps.renci.org/federation/sparql

# Query Planner Context Source (optional - for A/B testing)
# Set to true to use *_global.json context files instead of YAML metadata
# USE_JSON_CONTEXT_FOR_PLANNER=true
EOF

echo "✅ Created .env.local"
echo ""
echo "📝 Next steps:"
echo "1. Edit .env.local and replace 'sk-ant-your-key-here' with your actual Anthropic API key"
echo "   (or use OPENAI_SHARED_API_KEY if you prefer OpenAI)"
echo "2. Restart the dev server: npm run dev"
echo ""
echo "💡 The FRINK endpoint is already configured in context/packs/wobd.yaml"
echo "   No additional setup needed for FRINK!"


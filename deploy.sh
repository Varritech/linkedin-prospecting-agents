#!/bin/bash
# deploy-prospecting-agents.sh
# One-command deployment for LinkedIn Prospecting Agents
# Usage: ./deploy.sh

set -e

echo "🚀 Deploying LinkedIn Prospecting Agents..."
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check prerequisites
echo "📋 Checking prerequisites..."

# Check Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker is not installed. Please install Docker first.${NC}"
    echo "   https://docs.docker.com/get-docker/"
    exit 1
fi
echo -e "${GREEN}✓${NC} Docker installed"

# Check Node.js (for n8n CLI)
if ! command -v node &> /dev/null; then
    echo -e "${YELLOW}⚠️  Node.js not found. Some features may be limited.${NC}"
fi

# Create project directory
PROJECT_DIR="linkedin-prospecting-agents"
if [ -d "$PROJECT_DIR" ]; then
    echo -e "${YELLOW}⚠️  Directory $PROJECT_DIR already exists${NC}"
    read -p "Do you want to continue? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
else
    mkdir -p "$PROJECT_DIR"
fi

cd "$PROJECT_DIR"

# Create .env file
echo ""
echo "📝 Creating configuration file..."
cat > .env << EOF
# LinkedIn Prospecting Agents Configuration
# Generated: $(date)

# Composio API (LinkedIn integration)
# Get your key: https://app.composio.dev
COMPOSIO_API_KEY=your_composio_api_key_here

# Anthropic API (AI qualification + messaging)
# Get your key: https://console.anthropic.com
ANTHROPIC_API_KEY=your_anthropic_api_key_here

# Notion API (CRM database)
# Get your token: https://www.notion.so/my-integrations
NOTION_API_KEY=secret_your_notion_integration_token_here

# n8n Configuration
N8N_HOST=localhost:5678
N8N_BASIC_AUTH_USER=admin
N8N_BASIC_AUTH_PASSWORD=admin

# Optional: Slack notifications
# SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL

# Optional: Calendly integration for meeting booking
# CALENDLY_API_KEY=your_calendly_api_key
EOF

echo -e "${GREEN}✓${NC} Created .env file"
echo -e "${YELLOW}⚠️  IMPORTANT: Edit .env and add your API keys before running${NC}"

# Create Docker Compose file
echo ""
echo "🐳 Creating Docker Compose configuration..."
cat > docker-compose.yml << 'EOF'
version: '3.8'

services:
  n8n:
    image: n8n/n8n:latest
    container_name: n8n-prospecting
    ports:
      - "5678:5678"
    environment:
      - N8N_HOST=${N8N_HOST:-localhost:5678}
      - N8N_BASIC_AUTH_ACTIVE=true
      - N8N_BASIC_AUTH_USER=${N8N_BASIC_AUTH_USER:-admin}
      - N8N_BASIC_AUTH_PASSWORD=${N8N_BASIC_AUTH_PASSWORD:-admin}
      - WEBHOOK_URL=http://${N8N_HOST:-localhost:5678}/
      - GENERIC_TIMEZONE=Asia/Seoul
      - TZ=Asia/Seoul
    volumes:
      - n8n_data:/home/node/.n8n
      - ./workflows:/home/node/.n8n/workflows
      - ./credentials:/home/node/.n8n/credentials
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "wget", "--spider", "-q", "http://localhost:5678/healthz"]
      interval: 30s
      timeout: 10s
      retries: 3

volumes:
  n8n_data:
    driver: local
EOF

echo -e "${GREEN}✓${NC} Created docker-compose.yml"

# Create workflows directory
mkdir -p workflows credentials scripts

# Create Scout Agent workflow
echo ""
echo "📡 Creating Scout Agent workflow..."
cat > workflows/scout-agent.json << 'WORKFLOW_EOF'
{
  "name": "LinkedIn Scout Agent",
  "nodes": [
    {
      "parameters": {
        "rule": {
          "interval": [
            {
              "field": "hours",
              "hoursInterval": 4
            }
          ]
        }
      },
      "id": "schedule-trigger",
      "name": "Schedule Trigger",
      "type": "n8n-nodes-base.scheduleTrigger",
      "typeVersion": 1.1,
      "position": [250, 300]
    },
    {
      "parameters": {
        "method": "POST",
        "url": "https://api.composio.dev/linkedin/search",
        "authentication": "genericCredentialType",
        "genericAuthType": "httpHeaderAuth",
        "sendHeaders": true,
        "headerParameters": {
          "parameters": [
            {
              "name": "Content-Type",
              "value": "application/json"
            }
          ]
        },
        "sendBody": true,
        "bodyParameters": {
          "parameters": [
            {
              "name": "keywords",
              "value": "={{ $json.searchTerms }}"
            },
            {
              "name": "title",
              "value": "Founder OR CEO OR CTO OR VP"
            },
            {
              "name": "companySize",
              "value": "1-50"
            },
            {
              "name": "location",
              "value": "United States OR United Kingdom OR Canada"
            },
            {
              "name": "limit",
              "value": "25"
            }
          ]
        },
        "options": {}
      },
      "id": "linkedin-search",
      "name": "Composio LinkedIn Search",
      "type": "n8n-nodes-base.httpRequest",
      "typeVersion": 4.2,
      "position": [470, 300],
      "credentials": {
        "httpHeaderAuth": {
          "id": "composio-credentials-id",
          "name": "Composio API"
        }
      }
    },
    {
      "parameters": {
        "method": "GET",
        "url": "=https://api.composio.dev/linkedin/profile/{{ $json.profileId }}",
        "authentication": "genericCredentialType",
        "genericAuthType": "httpHeaderAuth",
        "sendQuery": true,
        "queryParameters": {
          "parameters": [
            {
              "name": "includePosts",
              "value": true
            },
            {
              "name": "includeActivity",
              "value": true
            }
          ]
        },
        "options": {}
      },
      "id": "profile-enrichment",
      "name": "Profile Enrichment",
      "type": "n8n-nodes-base.httpRequest",
      "typeVersion": 4.2,
      "position": [690, 300],
      "credentials": {
        "httpHeaderAuth": {
          "id": "composio-credentials-id",
          "name": "Composio API"
        }
      }
    },
    {
      "parameters": {
        "operation": "create",
        "databaseId": "YOUR_QUEUE_DATABASE_ID",
        "properties": {
          "properties": [
            {
              "key": "Name",
              "value": "={{ $json.name }}"
            },
            {
              "key": "Profile URL",
              "value": "={{ $json.profileUrl }}"
            },
            {
              "key": "Company",
              "value": "={{ $json.company }}"
            },
            {
              "key": "Title",
              "value": "={{ $json.title }}"
            },
            {
              "key": "Status",
              "value": "Queued"
            },
            {
              "key": "Found At",
              "value": "={{ $now }}"
            }
          ]
        },
        "options": {}
      },
      "id": "add-to-queue",
      "name": "Add to Notion Queue",
      "type": "n8n-nodes-base.notion",
      "typeVersion": 2.1,
      "position": [910, 300],
      "credentials": {
        "notionApi": {
          "id": "notion-credentials-id",
          "name": "Notion API"
        }
      }
    }
  ],
  "pinData": {},
  "connections": {
    "Schedule Trigger": {
      "main": [
        [
          {
            "node": "Composio LinkedIn Search",
            "type": "main",
            "index": 0
          }
        ]
      ]
    },
    "Composio LinkedIn Search": {
      "main": [
        [
          {
            "node": "Profile Enrichment",
            "type": "main",
            "index": 0
          }
        ]
      ]
    },
    "Profile Enrichment": {
      "main": [
        [
          {
            "node": "Add to Notion Queue",
            "type": "main",
            "index": 0
          }
        ]
      ]
    }
  },
  "active": false,
  "settings": {
    "executionOrder": "v1"
  },
  "versionId": "scout-agent-v1",
  "meta": {
    "instanceId": "prospecting-agents"
  },
  "tags": [
    {
      "name": "LinkedIn",
      "createdAt": "2026-04-01T00:00:00.000Z",
      "updatedAt": "2026-04-01T00:00:00.000Z"
    },
    {
      "name": "Scout",
      "createdAt": "2026-04-01T00:00:00.000Z",
      "updatedAt": "2026-04-01T00:00:00.000Z"
    }
  ],
  "id": "scout-agent",
  "createdAt": "2026-04-01T00:00:00.000Z",
  "updatedAt": "2026-04-01T00:00:00.000Z"
}
WORKFLOW_EOF

echo -e "${GREEN}✓${NC} Created Scout Agent workflow"

# Create startup script
echo ""
echo "📜 Creating startup script..."
cat > scripts/start.sh << 'SCRIPT_EOF'
#!/bin/bash
# Start the prospecting agents system

set -e

echo "🚀 Starting LinkedIn Prospecting Agents..."

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Start n8n
echo "📡 Starting n8n..."
docker-compose up -d

# Wait for n8n to be ready
echo "⏳ Waiting for n8n to be ready..."
sleep 10

# Check health
if curl -s http://localhost:5678/healthz > /dev/null; then
    echo -e "\n${GREEN}✅ System is running!${NC}"
    echo ""
    echo "📊 Access n8n at: http://localhost:5678"
    echo "👤 Username: admin"
    echo "🔑 Password: admin (change this!)"
    echo ""
    echo "Next steps:"
    echo "1. Open n8n UI and import workflows from ./workflows/"
    echo "2. Update .env with your API keys"
    echo "3. Create Notion database (see README.md)"
    echo "4. Activate all workflows in n8n"
    echo ""
else
    echo -e "${RED}❌ n8n failed to start. Check logs with: docker-compose logs${NC}"
    exit 1
fi
SCRIPT_EOF

chmod +x scripts/start.sh
echo -e "${GREEN}✓${NC} Created startup script"

# Create Notion database setup script
echo ""
echo "🗄️ Creating Notion database setup script..."
cat > scripts/create-notion-db.js << 'NODESCRIPT_EOF'
#!/usr/bin/env node
/**
 * Create Notion CRM database for LinkedIn Prospecting Agents
 * Usage: node scripts/create-notion-db.js
 */

const { Client } = require('@notionhq/client');
require('dotenv').config();

const notion = new Client({
  auth: process.env.NOTION_API_KEY,
});

async function createDatabase() {
  console.log('🗄️ Creating Notion CRM database...');

  try {
    // Create a new page to hold the database
    const page = await notion.pages.create({
      parent: { type: 'workspace', workspace: true },
      properties: {
        title: [{ text: { content: 'LinkedIn Prospecting CRM' } }],
      },
    });

    // Create database with properties
    const database = await notion.databases.create({
      parent: { type: 'page_id', page_id: page.id },
      title: [{ text: { content: 'Lead Pipeline' } }],
      properties: {
        'Name': { title: {} },
        'Profile URL': { url: {} },
        'Company': { rich_text: {} },
        'Title': { rich_text: {} },
        'Score': { number: { format: 'number' } },
        'Status': {
          select: {
            options: [
              { name: 'Queued', color: 'gray' },
              { name: 'Qualified', color: 'blue' },
              { name: 'Contacted', color: 'yellow' },
              { name: 'Accepted', color: 'green' },
              { name: 'Replied', color: 'green' },
              { name: 'Meeting Booked', color: 'purple' },
              { name: 'Converted', color: 'green' },
              { name: 'Archived', color: 'red' },
            ],
          },
        },
        'Pain Points': { multi_select: { options: [] } },
        'Personalization Angle': { rich_text: {} },
        'Contacted At': { date: {} },
        'Last Follow-up': { date: {} },
        'Messages Sent': { rich_text: {} },
        'Source': {
          select: {
            options: [
              { name: 'Scout Agent', color: 'blue' },
              { name: 'Manual', color: 'gray' },
              { name: 'Import', color: 'default' },
            ],
          },
        },
      },
    });

    console.log('✅ Database created successfully!');
    console.log(`📊 Database URL: ${page.id}`);
    console.log(`📝 Database ID: ${database.id}`);
    console.log('');
    console.log('Update your n8n workflows with this database ID.');

  } catch (error) {
    console.error('❌ Error creating database:', error.message);
    process.exit(1);
  }
}

createDatabase();
NODESCRIPT_EOF

echo -e "${GREEN}✓${NC} Created Notion setup script"

# Create README for the deployment
echo ""
echo "📖 Creating deployment README..."
cat > DEPLOY.md << 'DEPLOY_EOF'
# Deployment Guide - LinkedIn Prospecting Agents

## Quick Start

```bash
# 1. Edit .env with your API keys
nano .env

# 2. Start the system
./scripts/start.sh

# 3. Open n8n UI
open http://localhost:5678
```

## API Keys Required

### Composio (LinkedIn API)
1. Go to https://app.composio.dev
2. Sign up / Log in
3. Navigate to API Keys
4. Create new key
5. Add to `.env` as `COMPOSIO_API_KEY`

### Anthropic (AI Processing)
1. Go to https://console.anthropic.com
2. Log in / Create account
3. Get API Key from dashboard
4. Add to `.env` as `ANTHROPIC_API_KEY`

### Notion (CRM Database)
1. Go to https://www.notion.so/my-integrations
2. Create new integration
3. Copy "Internal Integration Token"
4. Add to `.env` as `NOTION_API_KEY`
5. Share your database with the integration

## Import Workflows

1. Open n8n UI (http://localhost:5678)
2. Click "Workflows" in sidebar
3. Click "Import from File"
4. Select each JSON file from `./workflows/`:
   - scout-agent.json
   - qualify-agent.json
   - outreach-agent.json
   - followup-agent.json
5. Activate each workflow (toggle switch)

## Create Notion Database

Option A: Use the setup script
```bash
npm install @notionhq/client dotenv
node scripts/create-notion-db.js
```

Option B: Manual creation
1. Open Notion
2. Create new page → Database → Table
3. Add properties as listed in README.md
4. Share database with your integration

## Troubleshooting

### n8n won't start
```bash
docker-compose logs
# Check for port conflicts
lsof -i :5678
```

### API connection errors
- Verify API keys in `.env`
- Check network connectivity
- Review API rate limits

### Workflows not triggering
- Ensure workflows are activated (green toggle)
- Check schedule trigger settings
- Review execution logs in n8n

## Support

- Documentation: See main README.md
- Issues: GitHub Issues
- Community: n8n community forum

DEPLOY_EOF

echo -e "${GREEN}✓${NC} Created deployment guide"

# Final instructions
echo ""
echo "=========================================="
echo -e "${GREEN}✅ Deployment preparation complete!${NC}"
echo "=========================================="
echo ""
echo "📁 Project directory: $(pwd)"
echo ""
echo "🔧 Next steps:"
echo ""
echo "1. ${YELLOW}Edit .env${NC} with your API keys:"
echo "   - COMPOSIO_API_KEY (LinkedIn)"
echo "   - ANTHROPIC_API_KEY (AI processing)"
echo "   - NOTION_API_KEY (CRM database)"
echo ""
echo "2. ${YELLOW}Start the system${NC}:"
echo "   ./scripts/start.sh"
echo ""
echo "3. ${YELLOW}Import workflows${NC} in n8n UI:"
echo "   - Open http://localhost:5678"
echo "   - Import JSON files from ./workflows/"
echo "   - Activate all workflows"
echo ""
echo "4. ${YELLOW}Create Notion database${NC}:"
echo "   npm install @notionhq/client dotenv"
echo "   node scripts/create-notion-db.js"
echo ""
echo "5. ${YELLOW}Configure ICP${NC} in qualify-agent.json"
echo ""
echo "📖 Full documentation: README.md"
echo ""
echo "=========================================="
echo ""

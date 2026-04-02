# LinkedIn Prospecting AI Agents

A complete, production-ready LinkedIn prospecting system powered by AI agents. This system automates lead discovery, qualification, outreach, and follow-up sequences.

## 🚀 Features

- **Scout Agent**: Discovers and scores leads from LinkedIn based on your criteria
- **Qualify Agent**: Uses Claude API to analyze lead fit with AI-powered reasoning
- **Outreach Agent**: Generates personalized connection requests and messages
- **Follow-up Agent**: Manages automated follow-up sequences with smart timing
- **Notion Integration**: Full CRM integration for lead tracking
- **Docker Support**: Containerized deployment with scheduled agents

## 📁 Project Structure

```
linkedin-prospecting-agents/
├── scout_agent.py          # Lead discovery and scoring
├── qualify_agent.py        # AI-powered lead qualification
├── outreach_agent.py       # Personalized message generation
├── followup_agent.py       # Follow-up sequence management
├── notion_db.py            # Notion database integration
├── cli.py                  # Unified CLI interface
├── config.yaml             # Configuration file
├── requirements.txt        # Python dependencies
├── .env.example            # Environment variables template
├── Dockerfile              # Container image
├── docker-compose.yml      # Multi-container deployment
├── Makefile                # Common commands
└── README.md               # This file
```

## 🛠️ Installation

### 1. Clone and Setup

```bash
cd linkedin-prospecting-agents

# Install dependencies
make install

# Initialize configuration
make init
```

### 2. Configure Environment

Copy `.env.example` to `.env` and fill in your API keys:

```bash
cp .env.example .env
```

Required API keys:
- **ANTHROPIC_API_KEY**: For Claude AI (qualification & outreach)
- **LINKEDIN_API_KEY**: For LinkedIn data (use Proxycurl, Rainmaker, etc.)
- **NOTION_API_KEY**: For lead database
- **NOTION_DATABASE_ID**: Your Notion database ID

### 3. Customize Configuration

Edit `config.yaml` to set:
- Search criteria (keywords, industries, locations)
- Lead scoring weights
- Ideal customer profile
- Outreach message guidelines
- Follow-up timing

## 🎯 Quick Start

### Run Complete Pipeline

```bash
# Run all agents in sequence
make pipeline

# Or use the CLI directly
python cli.py pipeline --limit 50
```

### Run Individual Agents

```bash
# Step 1: Discover leads
make scout

# Step 2: Qualify leads with AI
make qualify

# Step 3: Generate outreach messages
make outreach

# Step 4: Process follow-ups
make followup
```

### Check Status

```bash
make status
```

## 🤖 Agent Details

### Scout Agent

Discovers leads by searching LinkedIn profiles and scores them based on fit.

**Features:**
- Keyword-based search
- Industry and location filtering
- Lead scoring algorithm
- Configurable thresholds

**Output:** `leads/leads_YYYYMMDD_HHMMSS.json`

```python
from scout_agent import ScoutAgent

agent = ScoutAgent()
leads = agent.discover_leads(keywords=['CTO', 'VP Engineering'], limit=50)
```

### Qualify Agent

Uses Claude API to analyze leads against your ideal customer profile.

**Features:**
- AI-powered fit analysis
- Detailed reasoning and insights
- Strengths/weaknesses identification
- Recommended actions

**Output:** `leads/qualified_YYYYMMDD_HHMMSS.json`

```python
from qualify_agent import QualifyAgent

agent = QualifyAgent()
results = agent.qualify_leads(leads_file='leads/leads_20250101_120000.json')
```

### Outreach Agent

Generates personalized connection requests and messages.

**Features:**
- AI-generated personalization
- Connection request notes (300 char limit)
- Follow-up sequence templates
- Confidence scoring

**Output:** `leads/outreach_YYYYMMDD_HHMMSS.json`

```python
from outreach_agent import OutreachAgent

agent = OutreachAgent()
messages = agent.generate_outreach(leads_file='leads/qualified_20250101_120000.json')
```

### Follow-up Agent

Manages automated follow-up sequences.

**Features:**
- Smart scheduling
- Status tracking
- Pipeline management
- Dry-run mode

**State:** `state/followup_tasks.json`

```python
from followup_agent import FollowupAgent

agent = FollowupAgent()
agent.run(dry_run=True)  # Preview without sending
```

## 📊 Notion Integration

### Create Database

```bash
# Create a new leads database in Notion
python cli.py notion --action create --parent-page YOUR_PAGE_ID
```

### Sync Leads

```bash
# Sync local leads to Notion
python cli.py notion --action sync
```

### View Leads

```bash
# List all leads in Notion
python cli.py notion --action list
```

## 🐳 Docker Deployment

### Build Image

```bash
make docker-build
```

### Run One-off Pipeline

```bash
make docker-run
```

### Run with Docker Compose

```bash
# Run main pipeline
make docker-compose

# Run with scheduled agents (scout every 6h, followup every 1h)
make docker-compose-scheduled

# View logs
make docker-logs
```

### Dashboard (Optional)

```bash
make docker-dashboard
# Access at http://localhost:8080
```

## 🔧 CLI Commands

```bash
# Full pipeline
python cli.py pipeline [OPTIONS]

# Individual agents
python cli.py scout [OPTIONS]
python cli.py qualify [OPTIONS]
python cli.py outreach [OPTIONS]
python cli.py followup [OPTIONS]

# Notion management
python cli.py notion --action [verify|create|list|sync]

# System status
python cli.py status

# Initialize config
python cli.py init-config
```

### Options

```
--config, -c      Config file path (default: config.yaml)
--limit, -l       Max leads to process
--keywords, -k    Search keywords
--dry-run         Don't send actual messages
--verbose, -v     Verbose output
```

## 📝 Configuration

### Search Criteria (`config.yaml`)

```yaml
search:
  keywords:
    - CTO
    - VP Engineering
    - Head of Engineering
  industries:
    - Technology
    - Software
    - SaaS
  locations:
    - San Francisco
    - New York
    - Remote
```

### Lead Scoring

```yaml
scoring:
  weights:
    title_match: 0.3
    industry_match: 0.2
    location_match: 0.1
    company_size: 0.2
    connections: 0.2
  min_threshold: 0.5
```

### Follow-up Timing

```yaml
followup:
  intervals: [3, 7, 14, 30]  # days
  max_followups: 4
```

## 🧪 Development

### Run Tests

```bash
make test
```

### Linting

```bash
make lint
make format
```

### Clean Up

```bash
make clean        # Remove temp files
make clean-data   # Remove leads/state (careful!)
```

## 🔒 Safety & Best Practices

### Rate Limiting

The system includes built-in rate limiting:
- LinkedIn API: 30 calls/minute
- Claude API: 60 calls/minute
- Notion API: 3 calls/second
- Daily connection limit: 100
- Daily message limit: 200

### Dry Run Mode

Always test with `--dry-run` first:

```bash
python cli.py pipeline --dry-run
```

### Data Backup

```bash
make backup
# Creates timestamped backup in backups/
```

## 🐛 Troubleshooting

### API Key Errors

```bash
# Check environment variables
make status

# Verify .env file exists and is populated
cat .env
```

### No Leads Found

- Check search keywords in `config.yaml`
- Verify LinkedIn API key is valid
- Try broader search criteria

### Claude API Errors

- Check `ANTHROPIC_API_KEY` is set
- Verify API key has credits available
- Check rate limits in logs

## 📈 Pipeline Output

### Leads Directory

```
leads/
├── leads_20250101_120000.json      # Discovered leads
├── qualified_20250101_120000.json  # Qualification results
└── outreach_20250101_120000.json   # Generated messages
```

### State Directory

```
state/
├── followup_tasks.json    # Scheduled follow-ups
└── followup_history.json  # Historical data
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests: `make test`
5. Submit a pull request

## 📄 License

MIT License - see LICENSE file for details.

## 🙏 Acknowledgments

- **Claude API** by Anthropic for AI analysis
- **Notion API** for CRM integration
- **Proxycurl** for LinkedIn data (recommended provider)

## 📞 Support

For issues and questions:
- GitHub Issues: [Create an issue]
- Documentation: See `config.yaml` for detailed options

---

**Built with ❤️ for modern B2B sales teams**

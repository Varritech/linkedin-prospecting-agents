# LinkedIn Prospecting Agents - Makefile
# ======================================
# Common commands for development and deployment

.PHONY: help install run-scout run-qualify run-outreach run-pipeline test clean docker-build docker-run lint format

# Default target
help:
	@echo "LinkedIn Prospecting Agents - Available Commands"
	@echo "================================================"
	@echo ""
	@echo "Setup:"
	@echo "  make install        Install Python dependencies"
	@echo "  make init           Initialize config files"
	@echo ""
	@echo "Run Agents:"
	@echo "  make scout          Run scout agent (discover leads)"
	@echo "  make qualify        Run qualify agent (analyze leads)"
	@echo "  make outreach       Run outreach agent (generate messages)"
	@echo "  make followup       Run follow-up agent"
	@echo "  make pipeline       Run complete pipeline"
	@echo ""
	@echo "Development:"
	@echo "  make test           Run tests"
	@echo "  make lint           Run linters"
	@echo "  make format         Format code with black"
	@echo "  make clean          Clean up temporary files"
	@echo ""
	@echo "Docker:"
	@echo "  make docker-build   Build Docker image"
	@echo "  make docker-run     Run in Docker"
	@echo "  make docker-compose Run with docker-compose"
	@echo ""

# Install dependencies
install:
	pip install -r requirements.txt

# Initialize configuration
init:
	python cli.py init-config

# Run scout agent
scout:
	python cli.py scout --limit 50

# Run qualify agent
qualify:
	python cli.py qualify

# Run outreach agent
outreach:
	python cli.py outreach

# Run follow-up agent
followup:
	python cli.py followup

# Run complete pipeline
pipeline:
	python cli.py pipeline --limit 50

# Run pipeline in dry-run mode
pipeline-dry:
	python cli.py pipeline --limit 10 --dry-run

# Run tests
test:
	pytest tests/ -v --cov=. --cov-report=term-missing

# Run tests without coverage
test-simple:
	pytest tests/ -v

# Run linters
lint:
	flake8 *.py --max-line-length=120 --exclude=venv,__pycache__
	mypy *.py --ignore-missing-imports

# Format code
format:
	black *.py --line-length=120

# Check formatting
format-check:
	black *.py --line-length=120 --check

# Clean temporary files
clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name ".pytest_cache" -delete
	find . -type d -name ".mypy_cache" -delete
	rm -rf build/ dist/ *.egg-info/
	rm -rf .coverage htmlcov/

# Clean leads and state (use with caution!)
clean-data:
	rm -rf leads/*.json
	rm -rf state/*.json

# Build Docker image
docker-build:
	docker build -t linkedin-prospecting-agent:latest .

# Run in Docker (one-off)
docker-run:
	docker run --rm -it \
		--env-file .env \
		-v $(PWD)/leads:/app/leads \
		-v $(PWD)/state:/app/state \
		linkedin-prospecting-agent:latest \
		python cli.py pipeline --limit 50

# Run with docker-compose
docker-compose:
	docker-compose up prospecting-agent

# Run scheduled agents
docker-compose-scheduled:
	docker-compose --profile scheduled up -d

# Stop all containers
docker-stop:
	docker-compose down

# View logs
docker-logs:
	docker-compose logs -f

# Dashboard (if enabled)
docker-dashboard:
	docker-compose --profile dashboard up dashboard

# Sync leads to Notion
notion-sync:
	python cli.py notion --action sync

# Create Notion database
notion-create:
	python cli.py notion --action create --parent-page $(PARENT_PAGE)

# Check system status
status:
	python cli.py status

# Quick start (for first-time users)
quickstart: install init
	@echo ""
	@echo "✓ Setup complete!"
	@echo ""
	@echo "Next steps:"
	@echo "1. Edit .env with your API keys"
	@echo "2. Edit config.yaml to customize criteria"
	@echo "3. Run: make pipeline"
	@echo ""

# Development mode (auto-reload)
dev:
	pip install watchdog
	python -c "from watchdog.observers import Observer; print('Watchdog installed')" || pip install watchdog
	@echo "Starting development watcher..."
	@echo "Run agents manually during development"

# Backup leads data
backup:
	@mkdir -p backups
	@tar -czf backups/leads-$$(date +%Y%m%d-%H%M%S).tar.gz leads/ state/
	@echo "Backup created in backups/"

# Restore from backup
restore:
	@if [ -z "$(BACKUP_FILE)" ]; then \
		echo "Error: Specify BACKUP_FILE=<path>"; \
		exit 1; \
	fi
	tar -xzf $(BACKUP_FILE)
	@echo "Restored from $(BACKUP_FILE)"

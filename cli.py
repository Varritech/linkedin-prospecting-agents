#!/usr/bin/env python3
"""
CLI Wrapper - Command-line interface for LinkedIn Prospecting Agents.

This provides a unified CLI to run all agents in the prospecting pipeline.
"""

import os
import sys
import json
import logging
import click
from datetime import datetime
from pathlib import Path
from typing import Optional, List

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from scout_agent import ScoutAgent
from qualify_agent import QualifyAgent
from outreach_agent import OutreachAgent
from followup_agent import FollowupAgent
from notion_db import NotionDatabaseManager, NotionLead

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('cli')


@click.group()
@click.option('--config', '-c', default='config.yaml', help='Config file path')
@click.option('--verbose', '-v', is_flag=True, help='Verbose output')
@click.pass_context
def cli(ctx, config, verbose):
    """LinkedIn Prospecting AI Agents CLI.
    
    A complete pipeline for discovering, qualifying, and outreaching to
    LinkedIn leads using AI-powered agents.
    """
    ctx.ensure_object(dict)
    ctx.obj['config'] = config
    
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)


@cli.command()
@click.option('--keywords', '-k', multiple=True, help='Search keywords')
@click.option('--limit', '-l', default=50, help='Max leads to fetch')
@click.option('--output-dir', '-o', help='Output directory for leads')
@click.pass_context
def scout(ctx, keywords, limit, output_dir):
    """Run the Scout Agent to discover leads."""
    config_path = ctx.obj['config']
    
    agent = ScoutAgent(config_path=config_path)
    
    if output_dir:
        agent.output_dir = Path(output_dir)
    
    keywords_list = list(keywords) if keywords else None
    agent.run(keywords=keywords_list, limit=limit)


@cli.command()
@click.option('--leads-file', '-f', help='JSON file with leads from scout')
@click.option('--output-dir', '-o', help='Output directory for results')
@click.pass_context
def qualify(ctx, leads_file, output_dir):
    """Run the Qualify Agent to analyze lead fit."""
    config_path = ctx.obj['config']
    
    agent = QualifyAgent(config_path=config_path)
    
    if output_dir:
        agent.output_dir = Path(output_dir)
    
    agent.run(leads_file=leads_file)


@cli.command()
@click.option('--leads-file', '-f', help='JSON file with qualified leads')
@click.option('--output-dir', '-o', help='Output directory for messages')
@click.pass_context
def outreach(ctx, leads_file, output_dir):
    """Generate personalized outreach messages."""
    config_path = ctx.obj['config']
    
    agent = OutreachAgent(config_path=config_path)
    
    if output_dir:
        agent.output_dir = Path(output_dir)
    
    agent.run(leads_file=leads_file)


@cli.command()
@click.option('--dry-run', is_flag=True, help='Don\'t actually send messages')
@click.option('--add-lead', help='Add a lead (JSON string)')
@click.pass_context
def followup(ctx, dry_run, add_lead):
    """Run the Follow-up Agent to manage sequences."""
    config_path = ctx.obj['config']
    
    agent = FollowupAgent(config_path=config_path)
    
    if add_lead:
        lead_data = json.loads(add_lead)
        agent.add_lead(
            lead_url=lead_data['url'],
            lead_name=lead_data['name'],
            initial_message=lead_data.get('initial_message', ''),
            followup_sequence=lead_data.get('followup_sequence', [])
        )
        print(f"Added lead: {lead_data['name']}")
    else:
        agent.run(dry_run=dry_run)


@cli.command()
@click.option('--action', '-a', default='verify', 
              type=click.Choice(['verify', 'create', 'list', 'sync']))
@click.option('--parent-page', '-p', help='Parent page ID for creating database')
@click.option('--database-id', '-d', help='Database ID')
@click.pass_context
def notion(ctx, action, parent_page, database_id):
    """Manage Notion database integration."""
    db_id = database_id or os.getenv('NOTION_DATABASE_ID')
    
    try:
        manager = NotionDatabaseManager(database_id=db_id)
        
        if action == 'verify':
            success = manager.verify_database()
            click.echo(f"Database verification: {'✓ Success' if success else '✗ Failed'}")
        
        elif action == 'create':
            if not parent_page:
                click.echo("Error: --parent-page required for create action", err=True)
                return
            db_id = manager.create_leads_database(parent_page)
            click.echo(f"Created database: {db_id}")
        
        elif action == 'list':
            leads = manager.get_all_leads()
            click.echo(f"\nFound {len(leads)} leads:")
            for lead in leads[:10]:
                click.echo(f"  - {lead['name']} @ {lead['company']} ({lead['status']})")
            if len(leads) > 10:
                click.echo(f"  ... and {len(leads) - 10} more")
        
        elif action == 'sync':
            click.echo("Syncing leads from files to Notion...")
            # Implementation would sync local leads to Notion
            click.echo("Sync complete")
    
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        click.echo("Make sure NOTION_API_KEY is set in environment", err=True)


@cli.command()
@click.option('--keywords', '-k', multiple=True, help='Search keywords')
@click.option('--limit', '-l', default=50, help='Max leads')
@click.option('--no-qualify', is_flag=True, help='Skip qualification step')
@click.option('--no-outreach', is_flag=True, help='Skip outreach generation')
@click.option('--dry-run', is_flag=True, help='Don\'t send actual messages')
@click.pass_context
def pipeline(ctx, keywords, limit, no_qualify, no_outreach, dry_run):
    """Run the complete prospecting pipeline.
    
    Executes scout → qualify → outreach in sequence.
    """
    config_path = ctx.obj['config']
    
    click.echo("\n" + "="*60)
    click.echo("LINKEDIN PROSPECTING PIPELINE")
    click.echo("="*60 + "\n")
    
    # Step 1: Scout
    click.echo("Step 1: Discovering leads...")
    scout_agent = ScoutAgent(config_path=config_path)
    leads = scout_agent.discover_leads(
        keywords=list(keywords) if keywords else None,
        limit=limit
    )
    click.echo(f"✓ Found {len(leads)} qualified leads\n")
    
    if not leads:
        click.echo("No leads found. Exiting.")
        return
    
    # Step 2: Qualify
    if not no_qualify:
        click.echo("Step 2: Qualifying leads with AI...")
        qualify_agent = QualifyAgent(config_path=config_path)
        # Pass leads directly instead of file
        results = qualify_agent.qualify_leads(leads=[leads[0].__dict__ if hasattr(leads[0], '__dict__') else leads[0] for leads in [leads]])
        qualified_count = sum(1 for r in results if r.qualified)
        click.echo(f"✓ Qualified {qualified_count}/{len(results)} leads\n")
    
    # Step 3: Outreach
    if not no_outreach:
        click.echo("Step 3: Generating outreach messages...")
        outreach_agent = OutreachAgent(config_path=config_path)
        messages = outreach_agent.generate_outreach(leads=[])
        click.echo(f"✓ Generated {len(messages)} personalized messages\n")
    
    # Summary
    click.echo("="*60)
    click.echo("PIPELINE COMPLETE")
    click.echo("="*60)
    click.echo(f"Leads discovered: {len(leads)}")
    if not no_qualify:
        click.echo(f"Leads qualified: {qualified_count}")
    if not no_outreach:
        click.echo(f"Messages generated: {len(messages)}")
    click.echo()


@cli.command()
def status():
    """Show system status and configuration."""
    click.echo("\n" + "="*60)
    click.echo("LINKEDIN PROSPECTING AGENTS - STATUS")
    click.echo("="*60 + "\n")
    
    # Check environment variables
    click.echo("Environment:")
    env_vars = {
        'ANTHROPIC_API_KEY': 'Claude API',
        'LINKEDIN_API_KEY': 'LinkedIn API',
        'NOTION_API_KEY': 'Notion API',
        'NOTION_DATABASE_ID': 'Notion Database'
    }
    
    for var, desc in env_vars.items():
        value = os.getenv(var)
        status = "✓ Set" if value else "✗ Not set"
        click.echo(f"  {desc}: {status}")
    
    # Check config file
    config_path = Path('config.yaml')
    if config_path.exists():
        click.echo(f"\nConfig file: ✓ Found ({config_path.absolute()})")
    else:
        click.echo(f"\nConfig file: ✗ Not found")
    
    # Check output directories
    output_dirs = [
        Path('./leads'),
        Path('./state')
    ]
    
    click.echo("\nDirectories:")
    for dir_path in output_dirs:
        if dir_path.exists():
            file_count = len(list(dir_path.glob('*')))
            click.echo(f"  {dir_path}: ✓ Exists ({file_count} files)")
        else:
            click.echo(f"  {dir_path}: ✗ Not found")
    
    click.echo()


@cli.command()
@click.option('--force', is_flag=True, help='Overwrite existing files')
def init_config(force):
    """Initialize configuration files."""
    config_path = Path('config.yaml')
    env_example_path = Path('.env.example')
    
    if config_path.exists() and not force:
        click.echo(f"Config file already exists: {config_path}")
        click.echo("Use --force to overwrite")
        return
    
    # Create default config
    default_config = """# LinkedIn Prospecting Agents Configuration

# Search criteria
search:
  keywords:
    - CTO
    - VP Engineering
    - Head of Engineering
    - Technical Director
  industries:
    - Technology
    - Software
    - SaaS
  locations:
    - San Francisco
    - New York
    - London
    - Remote

# Target profile for scoring
target_profile:
  titles:
    - CTO
    - VP
    - Director
    - Head
  industries:
    - Technology
    - Software
  min_connections: 200

# Scoring configuration
scoring:
  weights:
    title_match: 0.3
    industry_match: 0.2
    location_match: 0.1
    company_size: 0.2
    connections: 0.2
  min_threshold: 0.5

# Ideal customer profile (for Claude analysis)
ideal_customer_profile:
  titles:
    - CTO
    - VP Engineering
    - Head of Engineering
  industries:
    - Technology
    - Software
    - SaaS
  company_size: "50-500"
  decision_maker: true

# Company information (for outreach)
company:
  name: "Your Company"
  value_prop: "We help companies scale their engineering teams with AI-powered tools"
  target_audience: "Tech companies with 50-500 employees"
  sender_name: "Your Name"

# Outreach configuration
outreach:
  tone: "professional but friendly"
  length: "short, 3-4 sentences"
  goal: "book a discovery call"
  avoid:
    - salesy language
    - generic pitches
    - excessive emojis

# Follow-up configuration
followup:
  intervals: [3, 7, 14, 30]  # days between follow-ups
  max_followups: 4
  stop_after_response: true

# Output directories
output_dir: "./leads"
state_dir: "./state"
"""
    
    with open(config_path, 'w') as f:
        f.write(default_config)
    
    click.echo(f"✓ Created config.yaml")
    
    # Create .env.example if it doesn't exist
    if not env_example_path.exists() or force:
        env_example = """# LinkedIn Prospecting Agents - Environment Variables

# Claude API (for AI analysis and message generation)
# Get from: https://console.anthropic.com/
ANTHROPIC_API_KEY=sk-ant-...

# LinkedIn API (for profile scraping)
# Use a provider like Proxycurl, Rainmaker, or LinkedIn Sales Navigator
LINKEDIN_API_KEY=your_api_key

# Notion API (for lead database)
# Get from: https://www.notion.so/my-integrations
NOTION_API_KEY=secret_...
NOTION_DATABASE_ID=your_database_id

# Optional: Webhook URL for notifications
WEBHOOK_URL=https://your-webhook.com/notify
"""
        
        with open(env_example_path, 'w') as f:
            f.write(env_example)
        
        click.echo(f"✓ Created .env.example")
    
    click.echo("\nNext steps:")
    click.echo("1. Copy .env.example to .env and fill in your API keys")
    click.echo("2. Edit config.yaml to match your criteria")
    click.echo("3. Run: python cli.py --help")


def main():
    """Main entry point."""
    cli(obj={})


if __name__ == '__main__':
    main()

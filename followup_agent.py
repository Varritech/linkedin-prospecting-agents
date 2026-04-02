#!/usr/bin/env python3
"""
Follow-up Agent - Manages follow-up sequences for leads.

This agent tracks outreach status and automatically sends follow-up
messages based on timing and lead engagement.
"""

import os
import json
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict, field
from pathlib import Path
from enum import Enum

import yaml
import requests

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('followup_agent')


class LeadStatus(Enum):
    """Status of a lead in the outreach pipeline."""
    NEW = "new"
    CONTACTED = "contacted"
    CONNECTED = "connected"
    RESPONDED = "responded"
    MEETING_BOOKED = "meeting_booked"
    NOT_INTERESTED = "not_interested"
    UNRESPONSIVE = "unresponsive"


@dataclass
class FollowupTask:
    """A scheduled follow-up task."""
    lead_url: str
    lead_name: str
    status: str
    last_contact_date: str
    next_followup_date: str
    followup_count: int
    message_template: str
    notes: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


class FollowupScheduler:
    """Manages follow-up scheduling and timing."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config.get('followup', {})
        self.default_intervals = self.config.get('intervals', [3, 7, 14, 30])  # days
        self.max_followups = self.config.get('max_followups', 4)
    
    def get_next_followup_date(
        self,
        last_contact: datetime,
        followup_count: int
    ) -> Optional[datetime]:
        """
        Calculate the next follow-up date.
        
        Args:
            last_contact: Date of last contact
            followup_count: Number of follow-ups already sent
            
        Returns:
            Next follow-up date, or None if max reached
        """
        if followup_count >= self.max_followups:
            return None
        
        # Get interval for this follow-up
        if followup_count < len(self.default_intervals):
            interval_days = self.default_intervals[followup_count]
        else:
            interval_days = self.default_intervals[-1]  # Use last interval
        
        return last_contact + timedelta(days=interval_days)
    
    def should_send_followup(self, task: FollowupTask) -> bool:
        """Check if it's time to send a follow-up."""
        next_date = datetime.fromisoformat(task.next_followup_date)
        return datetime.now() >= next_date
    
    def get_overdue_tasks(self, tasks: List[FollowupTask]) -> List[FollowupTask]:
        """Get all tasks that are overdue for follow-up."""
        return [t for t in tasks if self.should_send_followup(t)]


class LinkedInMessenger:
    """Handles sending messages via LinkedIn (mock implementation)."""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv('LINKEDIN_API_KEY')
        self.base_url = "https://api.linkedin.com/v2"
        self.rate_limiter = RateLimiter(calls_per_minute=30)
    
    def send_connection_request(
        self,
        profile_url: str,
        message: str
    ) -> Dict[str, Any]:
        """Send a LinkedIn connection request with note."""
        self.rate_limiter.wait()
        
        # Mock implementation - in production, use LinkedIn API
        logger.info(f"Sending connection request to {profile_url}")
        
        return {
            'success': True,
            'message_id': f'msg_{int(time.time())}',
            'status': 'sent',
            'sent_at': datetime.now().isoformat()
        }
    
    def send_message(
        self,
        recipient_url: str,
        message: str,
        conversation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Send a message to a connection."""
        self.rate_limiter.wait()
        
        logger.info(f"Sending message to {recipient_url}")
        
        return {
            'success': True,
            'message_id': f'msg_{int(time.time())}',
            'status': 'delivered',
            'sent_at': datetime.now().isoformat()
        }
    
    def check_response(
        self,
        conversation_id: str
    ) -> Dict[str, Any]:
        """Check if lead has responded."""
        # Mock implementation
        return {
            'has_response': False,
            'last_activity': None,
            'message_count': 0
        }


class RateLimiter:
    """Simple rate limiter."""
    
    def __init__(self, calls_per_minute: int = 60):
        self.min_interval = 60.0 / calls_per_minute
        self.last_call = 0.0
    
    def wait(self):
        """Wait if necessary to respect rate limit."""
        elapsed = time.time() - self.last_call
        if elapsed < self.min_interval:
            sleep_time = self.min_interval - elapsed
            time.sleep(sleep_time)
        self.last_call = time.time()


class FollowupAgent:
    """Main follow-up agent."""
    
    def __init__(self, config_path: str = "config.yaml"):
        self.config = self._load_config(config_path)
        self.scheduler = FollowupScheduler(self.config)
        self.messenger = LinkedInMessenger()
        
        self.state_dir = Path(self.config.get('state_dir', './state'))
        self.state_dir.mkdir(parents=True, exist_ok=True)
        
        self.tasks_file = self.state_dir / 'followup_tasks.json'
        self.history_file = self.state_dir / 'followup_history.json'
    
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load configuration from YAML file."""
        try:
            with open(config_path, 'r') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            logger.warning(f"Config file {config_path} not found, using defaults")
            return {}
    
    def _load_tasks(self) -> List[FollowupTask]:
        """Load existing follow-up tasks."""
        if not self.tasks_file.exists():
            return []
        
        with open(self.tasks_file, 'r') as f:
            tasks_data = json.load(f)
        
        return [FollowupTask(**t) for t in tasks_data]
    
    def _save_tasks(self, tasks: List[FollowupTask]):
        """Save follow-up tasks to file."""
        tasks_data = [asdict(t) for t in tasks]
        
        with open(self.tasks_file, 'w') as f:
            json.dump(tasks_data, f, indent=2)
    
    def add_lead(
        self,
        lead_url: str,
        lead_name: str,
        initial_message: str,
        followup_sequence: List[str]
    ) -> FollowupTask:
        """
        Add a new lead to the follow-up system.
        
        Args:
            lead_url: LinkedIn profile URL
            lead_name: Lead's name
            initial_message: First outreach message
            followup_sequence: List of follow-up messages
            
        Returns:
            Created FollowupTask
        """
        now = datetime.now()
        
        task = FollowupTask(
            lead_url=lead_url,
            lead_name=lead_name,
            status=LeadStatus.CONTACTED.value,
            last_contact_date=now.isoformat(),
            next_followup_date=self.scheduler.get_next_followup_date(now, 0).isoformat() if self.scheduler.get_next_followup_date(now, 0) else now.isoformat(),
            followup_count=1,
            message_template=followup_sequence[0] if followup_sequence else "Following up on my previous message",
            notes=f"Initial message: {initial_message[:200]}"
        )
        
        tasks = self._load_tasks()
        tasks.append(task)
        self._save_tasks(tasks)
        
        logger.info(f"Added follow-up task for {lead_name}")
        return task
    
    def process_followups(self, dry_run: bool = False) -> List[Dict[str, Any]]:
        """
        Process all overdue follow-up tasks.
        
        Args:
            dry_run: If True, don't actually send messages
            
        Returns:
            List of processed follow-up results
        """
        tasks = self._load_tasks()
        overdue = self.scheduler.get_overdue_tasks(tasks)
        
        logger.info(f"Found {len(overdue)} overdue follow-up tasks")
        
        results = []
        
        for task in overdue:
            logger.info(f"Processing follow-up for {task.lead_name}")
            
            if dry_run:
                logger.info(f"[DRY RUN] Would send to {task.lead_url}")
                result = {
                    'lead_url': task.lead_url,
                    'status': 'dry_run',
                    'message': task.message_template
                }
            else:
                # Send follow-up message
                result = self.messenger.send_message(
                    recipient_url=task.lead_url,
                    message=task.message_template
                )
                result['lead_url'] = task.lead_url
            
            # Update task
            task.followup_count += 1
            task.last_contact_date = datetime.now().isoformat()
            
            next_date = self.scheduler.get_next_followup_date(
                datetime.now(),
                task.followup_count
            )
            
            if next_date:
                task.next_followup_date = next_date.isoformat()
                task.status = LeadStatus.CONTACTED.value
            else:
                task.status = LeadStatus.UNRESPONSIVE.value
            
            results.append(result)
        
        # Save updated tasks
        self._save_tasks(tasks)
        
        return results
    
    def update_lead_status(
        self,
        lead_url: str,
        new_status: LeadStatus,
        notes: str = ""
    ):
        """
        Update a lead's status (e.g., when they respond).
        
        Args:
            lead_url: LinkedIn profile URL
            new_status: New status value
            notes: Additional notes
        """
        tasks = self._load_tasks()
        
        for task in tasks:
            if task.lead_url == lead_url:
                task.status = new_status.value
                if notes:
                    task.notes += f"\n{datetime.now().isoformat()}: {notes}"
                break
        
        self._save_tasks(tasks)
        logger.info(f"Updated status for {lead_url} to {new_status.value}")
    
    def get_pipeline_summary(self) -> Dict[str, Any]:
        """Get summary of current pipeline status."""
        tasks = self._load_tasks()
        
        status_counts = {}
        for task in tasks:
            status = task.status
            status_counts[status] = status_counts.get(status, 0) + 1
        
        overdue_count = len(self.scheduler.get_overdue_tasks(tasks))
        
        return {
            'total_leads': len(tasks),
            'by_status': status_counts,
            'overdue_followups': overdue_count,
            'last_updated': datetime.now().isoformat()
        }
    
    def run(self, dry_run: bool = False):
        """Run the follow-up agent."""
        try:
            print(f"\n{'='*60}")
            print(f"FOLLOW-UP AGENT")
            print(f"{'='*60}")
            
            # Show pipeline summary
            summary = self.get_pipeline_summary()
            print(f"\nPipeline Summary:")
            print(f"  Total leads: {summary['total_leads']}")
            print(f"  Overdue follow-ups: {summary['overdue_followups']}")
            print(f"\nBy status:")
            for status, count in summary['by_status'].items():
                print(f"  {status}: {count}")
            
            # Process follow-ups
            if summary['overdue_followups'] > 0:
                print(f"\nProcessing {summary['overdue_followups']} follow-ups...")
                results = self.process_followups(dry_run=dry_run)
                
                print(f"\nResults:")
                for result in results:
                    status_emoji = "✓" if result.get('success', False) else "✗"
                    print(f"  {status_emoji} {result['lead_url']}: {result.get('status', 'unknown')}")
            else:
                print("\nNo follow-ups due at this time.")
            
            print(f"\n{'='*60}\n")
            
            return summary
            
        except Exception as e:
            logger.error(f"Follow-up agent failed: {e}", exc_info=True)
            raise


def main():
    """CLI entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Follow-up Management Agent')
    parser.add_argument('--config', default='config.yaml', help='Config file path')
    parser.add_argument('--dry-run', action='store_true', help='Don\'t actually send messages')
    parser.add_argument('--add-lead', help='Add a lead (JSON string)')
    parser.add_argument('--status', help='Get pipeline status')
    
    args = parser.parse_args()
    
    agent = FollowupAgent(config_path=args.config)
    
    if args.status:
        agent.get_pipeline_summary()
    elif args.add_lead:
        lead_data = json.loads(args.add_lead)
        agent.add_lead(
            lead_url=lead_data['url'],
            lead_name=lead_data['name'],
            initial_message=lead_data.get('initial_message', ''),
            followup_sequence=lead_data.get('followup_sequence', [])
        )
    else:
        agent.run(dry_run=args.dry_run)


if __name__ == '__main__':
    main()

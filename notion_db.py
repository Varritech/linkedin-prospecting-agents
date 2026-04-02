#!/usr/bin/env python3
"""
Notion Database Manager - Creates and manages leads database.

This module handles all Notion integration for storing and tracking
LinkedIn leads through the prospecting pipeline.
"""

import os
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict

from notion_client import Client, APIResponseError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('notion_db')


@dataclass
class NotionLead:
    """Lead record for Notion database."""
    name: str
    title: str
    company: str
    linkedin_url: str
    email: Optional[str] = None
    location: str = ""
    industry: str = ""
    score: float = 0.0
    status: str = "New"
    last_contacted: Optional[str] = None
    next_followup: Optional[str] = None
    notes: str = ""
    qualification_result: Optional[Dict] = None
    outreach_messages: Optional[List[Dict]] = None


class NotionDatabaseManager:
    """Manages Notion database for lead tracking."""
    
    def __init__(self, api_key: Optional[str] = None, database_id: Optional[str] = None):
        self.api_key = api_key or os.getenv('NOTION_API_KEY')
        self.database_id = database_id or os.getenv('NOTION_DATABASE_ID')
        
        if not self.api_key:
            raise ValueError("NOTION_API_KEY not set")
        
        self.client = Client(auth=self.api_key)
        
        # Cache database schema
        self._schema = None
    
    def verify_database(self) -> bool:
        """Verify that the database exists and is accessible."""
        try:
            response = self.client.databases.retrieve(database_id=self.database_id)
            self._schema = response.get('properties', {})
            logger.info(f"Connected to Notion database: {response.get('title', [{}])[0].get('plain_text', 'Unknown')}")
            return True
        except APIResponseError as e:
            logger.error(f"Failed to access Notion database: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return False
    
    def create_leads_database(self, parent_page_id: str) -> str:
        """
        Create a new leads database in Notion.
        
        Args:
            parent_page_id: ID of the parent page
            
        Returns:
            Database ID of created database
        """
        database_schema = {
            "parent": {"type": "page_id", "page_id": parent_page_id},
            "title": [{"type": "text", "text": {"content": "LinkedIn Leads"}}],
            "properties": {
                "Name": {
                    "title": {}
                },
                "Title": {
                    "rich_text": {}
                },
                "Company": {
                    "rich_text": {}
                },
                "LinkedIn URL": {
                    "url": {}
                },
                "Email": {
                    "email": {}
                },
                "Location": {
                    "rich_text": {}
                },
                "Industry": {
                    "select": {
                        "options": [
                            {"name": "Technology", "color": "blue"},
                            {"name": "Finance", "color": "green"},
                            {"name": "Healthcare", "color": "red"},
                            {"name": "Retail", "color": "yellow"},
                            {"name": "Other", "color": "gray"}
                        ]
                    }
                },
                "Lead Score": {
                    "number": {
                        "format": "number"
                    }
                },
                "Status": {
                    "select": {
                        "options": [
                            {"name": "New", "color": "blue"},
                            {"name": "Contacted", "color": "yellow"},
                            {"name": "Connected", "color": "green"},
                            {"name": "Responded", "color": "green"},
                            {"name": "Meeting Booked", "color": "purple"},
                            {"name": "Not Interested", "color": "red"},
                            {"name": "Unresponsive", "color": "gray"}
                        ]
                    }
                },
                "Last Contacted": {
                    "date": {}
                },
                "Next Follow-up": {
                    "date": {}
                },
                "Notes": {
                    "rich_text": {}
                },
                "Created": {
                    "created_time": {}
                },
                "Last Edited": {
                    "last_edited_time": {}
                }
            }
        }
        
        try:
            response = self.client.databases.create(**database_schema)
            self.database_id = response['id']
            self._schema = response['properties']
            
            logger.info(f"Created Notion database: {response['id']}")
            return response['id']
            
        except APIResponseError as e:
            logger.error(f"Failed to create database: {e}")
            raise
    
    def add_lead(self, lead: NotionLead) -> Optional[str]:
        """
        Add a new lead to the database.
        
        Args:
            lead: NotionLead object
            
        Returns:
            Page ID of created record, or None if failed
        """
        properties = self._build_lead_properties(lead)
        
        try:
            response = self.client.pages.create(
                parent={"database_id": self.database_id},
                properties=properties
            )
            
            logger.info(f"Added lead to Notion: {lead.name} ({response['id']})")
            return response['id']
            
        except APIResponseError as e:
            logger.error(f"Failed to add lead: {e}")
            return None
    
    def add_leads_batch(self, leads: List[NotionLead]) -> List[Optional[str]]:
        """
        Add multiple leads to the database.
        
        Args:
            leads: List of NotionLead objects
            
        Returns:
            List of page IDs (None for failed inserts)
        """
        results = []
        
        for i, lead in enumerate(leads):
            logger.info(f"Adding lead {i+1}/{len(leads)}: {lead.name}")
            page_id = self.add_lead(lead)
            results.append(page_id)
            
            # Rate limiting (Notion allows 3 requests/second)
            if i < len(leads) - 1:
                import time
                time.sleep(0.4)
        
        return results
    
    def update_lead_status(
        self,
        page_id: str,
        status: str,
        notes: Optional[str] = None
    ) -> bool:
        """
        Update a lead's status.
        
        Args:
            page_id: Notion page ID
            status: New status value
            notes: Optional additional notes
            
        Returns:
            True if successful
        """
        properties = {
            "Status": {
                "select": {"name": status}
            }
        }
        
        if notes:
            properties["Notes"] = {
                "rich_text": [{"type": "text", "text": {"content": notes}}]
            }
        
        try:
            self.client.pages.update(page_id=page_id, properties=properties)
            logger.info(f"Updated lead {page_id} status to {status}")
            return True
        except APIResponseError as e:
            logger.error(f"Failed to update lead: {e}")
            return False
    
    def update_last_contacted(
        self,
        page_id: str,
        contacted_date: Optional[str] = None,
        next_followup: Optional[str] = None
    ) -> bool:
        """Update last contacted date and next follow-up."""
        properties = {}
        
        if contacted_date:
            properties["Last Contacted"] = {
                "date": {"start": contacted_date}
            }
        
        if next_followup:
            properties["Next Follow-up"] = {
                "date": {"start": next_followup}
            }
        
        try:
            self.client.pages.update(page_id=page_id, properties=properties)
            logger.info(f"Updated contact dates for lead {page_id}")
            return True
        except APIResponseError as e:
            logger.error(f"Failed to update dates: {e}")
            return False
    
    def search_leads(
        self,
        filter_property: str = "Status",
        filter_value: str = "New"
    ) -> List[Dict[str, Any]]:
        """
        Search for leads matching criteria.
        
        Args:
            filter_property: Property to filter on
            filter_value: Value to match
            
        Returns:
            List of matching lead records
        """
        try:
            response = self.client.databases.query(
                database_id=self.database_id,
                filter={
                    "property": filter_property,
                    "select": {"equals": filter_value}
                }
            )
            
            leads = []
            for result in response['results']:
                lead_data = self._parse_lead_from_page(result)
                leads.append(lead_data)
            
            logger.info(f"Found {len(leads)} leads matching {filter_property}={filter_value}")
            return leads
            
        except APIResponseError as e:
            logger.error(f"Search failed: {e}")
            return []
    
    def get_all_leads(self) -> List[Dict[str, Any]]:
        """Get all leads from the database."""
        try:
            all_results = []
            next_cursor = None
            
            while True:
                response = self.client.databases.query(
                    database_id=self.database_id,
                    start_cursor=next_cursor
                )
                
                for result in response['results']:
                    lead_data = self._parse_lead_from_page(result)
                    all_results.append(lead_data)
                
                if not response.get('has_more'):
                    break
                
                next_cursor = response.get('next_cursor')
            
            logger.info(f"Retrieved {len(all_results)} total leads")
            return all_results
            
        except APIResponseError as e:
            logger.error(f"Failed to retrieve leads: {e}")
            return []
    
    def _build_lead_properties(self, lead: NotionLead) -> Dict[str, Any]:
        """Convert NotionLead to Notion properties format."""
        properties = {
            "Name": {
                "title": [{"type": "text", "text": {"content": lead.name}}]
            },
            "Title": {
                "rich_text": [{"type": "text", "text": {"content": lead.title}}]
            },
            "Company": {
                "rich_text": [{"type": "text", "text": {"content": lead.company}}]
            },
            "LinkedIn URL": {
                "url": lead.linkedin_url
            },
            "Location": {
                "rich_text": [{"type": "text", "text": {"content": lead.location}}]
            },
            "Industry": {
                "select": {"name": lead.industry if lead.industry else "Other"}
            },
            "Lead Score": {
                "number": lead.score
            },
            "Status": {
                "select": {"name": lead.status}
            },
            "Notes": {
                "rich_text": [{"type": "text", "text": {"content": lead.notes}}]
            }
        }
        
        if lead.email:
            properties["Email"] = {
                "email": lead.email
            }
        
        if lead.last_contacted:
            properties["Last Contacted"] = {
                "date": {"start": lead.last_contacted}
            }
        
        if lead.next_followup:
            properties["Next Follow-up"] = {
                "date": {"start": lead.next_followup}
            }
        
        return properties
    
    def _parse_lead_from_page(self, page: Dict[str, Any]) -> Dict[str, Any]:
        """Parse a Notion page into lead data."""
        props = page.get('properties', {})
        
        def get_text(prop_name: str) -> str:
            prop = props.get(prop_name, {})
            if prop_name == "Name":
                title = prop.get('title', [])
                return title[0]['plain_text'] if title else ""
            else:
                rich_text = prop.get('rich_text', [])
                return rich_text[0]['plain_text'] if rich_text else ""
        
        def get_select(prop_name: str) -> str:
            prop = props.get(prop_name, {})
            select = prop.get('select', {})
            return select.get('name', '') if select else ""
        
        def get_number(prop_name: str) -> float:
            prop = props.get(prop_name, {})
            return prop.get('number', 0.0) or 0.0
        
        def get_date(prop_name: str) -> Optional[str]:
            prop = props.get(prop_name, {})
            date = prop.get('date', {})
            return date.get('start') if date else None
        
        def get_url(prop_name: str) -> str:
            prop = props.get(prop_name, {})
            return prop.get('url', '') or ""
        
        return {
            'page_id': page['id'],
            'name': get_text('Name'),
            'title': get_text('Title'),
            'company': get_text('Company'),
            'linkedin_url': get_url('LinkedIn URL'),
            'email': props.get('Email', {}).get('email', ''),
            'location': get_text('Location'),
            'industry': get_select('Industry'),
            'score': get_number('Lead Score'),
            'status': get_select('Status'),
            'last_contacted': get_date('Last Contacted'),
            'next_followup': get_date('Next Follow-up'),
            'notes': get_text('Notes'),
            'created': props.get('Created', {}).get('created_time'),
            'last_edited': props.get('Last Edited', {}).get('last_edited_time')
        }


def main():
    """CLI entry point for testing."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Notion Database Manager')
    parser.add_argument('--action', choices=['verify', 'create', 'list', 'add-test'], 
                       default='verify', help='Action to perform')
    parser.add_argument('--parent-page', help='Parent page ID for creating database')
    parser.add_argument('--database-id', help='Database ID (overrides env var)')
    
    args = parser.parse_args()
    
    # Override database ID if provided
    db_id = args.database_id or os.getenv('NOTION_DATABASE_ID')
    
    try:
        manager = NotionDatabaseManager(database_id=db_id)
        
        if args.action == 'verify':
            success = manager.verify_database()
            print(f"Database verification: {'✓ Success' if success else '✗ Failed'}")
        
        elif args.action == 'create':
            if not args.parent_page:
                print("Error: --parent-page required for create action")
                return
            db_id = manager.create_leads_database(args.parent_page)
            print(f"Created database: {db_id}")
        
        elif args.action == 'list':
            leads = manager.get_all_leads()
            print(f"\nFound {len(leads)} leads:")
            for lead in leads[:10]:
                print(f"  - {lead['name']} @ {lead['company']} ({lead['status']})")
            if len(leads) > 10:
                print(f"  ... and {len(leads) - 10} more")
        
        elif args.action == 'add-test':
            test_lead = NotionLead(
                name="Test Lead",
                title="CTO",
                company="Test Corp",
                linkedin_url="https://linkedin.com/in/test",
                location="San Francisco",
                industry="Technology",
                score=0.85,
                status="New",
                notes="Test lead from CLI"
            )
            page_id = manager.add_lead(test_lead)
            print(f"Added test lead: {page_id}")
    
    except ValueError as e:
        print(f"Error: {e}")
        print("Make sure NOTION_API_KEY is set in environment")


if __name__ == '__main__':
    main()

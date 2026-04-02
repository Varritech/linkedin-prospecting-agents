#!/usr/bin/env python3
"""
Scout Agent - Scrapes LinkedIn profiles via API and scores leads.

This agent searches for potential leads based on criteria and assigns
a relevance score to each profile found.
"""

import os
import json
import time
import logging
import hashlib
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from pathlib import Path

import requests
import yaml

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('scout_agent')


@dataclass
class Lead:
    """Represents a potential lead from LinkedIn."""
    profile_url: str
    name: str
    title: str
    company: str
    industry: str
    location: str
    connections: int
    score: float
    scraped_at: str
    raw_data: Dict[str, Any]


class RateLimiter:
    """Simple rate limiter to avoid API throttling."""
    
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


class LinkedInScraper:
    """Handles LinkedIn profile scraping via API."""
    
    def __init__(self, api_key: str, base_url: str = "https://api.linkedin.com/v2"):
        self.api_key = api_key
        self.base_url = base_url
        self.rate_limiter = RateLimiter(calls_per_minute=30)
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        })
    
    def search_profiles(
        self,
        keywords: List[str],
        industries: List[str],
        locations: List[str],
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Search for LinkedIn profiles matching criteria.
        
        Note: This is a mock implementation. In production, you would use:
        - LinkedIn Sales Navigator API
        - Proxycurl API (https://nubela.co/proxycurl/)
        - Rainmaker API
        - Or other LinkedIn data providers
        """
        logger.info(f"Searching for profiles with keywords: {keywords}")
        
        # Mock implementation - in production, this would call real API
        profiles = []
        
        for keyword in keywords:
            self.rate_limiter.wait()
            
            # Simulate API call
            mock_profile = {
                'profile_url': f'https://linkedin.com/in/mock-{hashlib.md5(keyword.encode()).hexdigest()[:8]}',
                'name': f'{keyword.title()} Professional',
                'title': f'Senior {keyword} Manager',
                'company': 'Tech Corp',
                'industry': 'Technology',
                'location': locations[0] if locations else 'San Francisco Bay Area',
                'connections': 500,
                'headline': f'Experienced {keyword} professional',
                'summary': f'Passionate about {keyword} and innovation.',
                'experience': [
                    {
                        'title': f'Senior {keyword} Manager',
                        'company': 'Tech Corp',
                        'duration': '2 years'
                    }
                ]
            }
            profiles.append(mock_profile)
            
            if len(profiles) >= limit:
                break
        
        logger.info(f"Found {len(profiles)} profiles")
        return profiles
    
    def get_profile_details(self, profile_url: str) -> Dict[str, Any]:
        """Get detailed profile information."""
        self.rate_limiter.wait()
        
        # Mock implementation
        return {
            'profile_url': profile_url,
            'name': 'John Doe',
            'title': 'VP of Engineering',
            'company': 'Startup Inc',
            'industry': 'Technology',
            'location': 'San Francisco Bay Area',
            'connections': 500,
            'headline': 'Building the future of tech',
            'summary': 'Experienced engineering leader with 15+ years in software development.',
            'experience': [
                {
                    'title': 'VP of Engineering',
                    'company': 'Startup Inc',
                    'start_date': '2020-01',
                    'end_date': None,
                    'duration': '4 years'
                }
            ],
            'education': [
                {
                    'school': 'Stanford University',
                    'degree': 'MS Computer Science',
                    'field': 'Computer Science'
                }
            ],
            'skills': ['Python', 'Leadership', 'Architecture', 'Cloud']
        }


class LeadScorer:
    """Scores leads based on fit criteria."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.weights = config.get('scoring', {}).get('weights', {
            'title_match': 0.3,
            'industry_match': 0.2,
            'location_match': 0.1,
            'company_size': 0.2,
            'connections': 0.2
        })
    
    def score_lead(self, profile: Dict[str, Any], target_criteria: Dict[str, Any]) -> float:
        """
        Calculate a relevance score for a lead (0.0 to 1.0).
        
        Args:
            profile: LinkedIn profile data
            target_criteria: What we're looking for in ideal leads
            
        Returns:
            Score between 0.0 (poor fit) and 1.0 (perfect fit)
        """
        scores = {}
        
        # Title match (does their role match what we're targeting?)
        target_titles = target_criteria.get('titles', [])
        profile_title = profile.get('title', '').lower()
        title_match = any(t.lower() in profile_title for t in target_titles)
        scores['title_match'] = 1.0 if title_match else 0.3
        
        # Industry match
        target_industries = target_criteria.get('industries', [])
        profile_industry = profile.get('industry', '').lower()
        industry_match = any(i.lower() in profile_industry for i in target_industries)
        scores['industry_match'] = 1.0 if industry_match else 0.2
        
        # Location match
        target_locations = target_criteria.get('locations', [])
        profile_location = profile.get('location', '').lower()
        location_match = any(loc.lower() in profile_location for loc in target_locations)
        scores['location_match'] = 1.0 if location_match else 0.5
        
        # Company size (assume larger is better for B2B)
        connections = profile.get('connections', 0)
        if connections > 500:
            scores['company_size'] = 1.0
        elif connections > 200:
            scores['company_size'] = 0.7
        else:
            scores['company_size'] = 0.4
        
        # Network strength
        if connections >= 500:
            scores['connections'] = 1.0
        elif connections >= 200:
            scores['connections'] = 0.6
        else:
            scores['connections'] = 0.3
        
        # Calculate weighted score
        total_score = sum(
            scores[k] * self.weights.get(k, 0.2)
            for k in scores
        )
        
        return round(total_score, 2)


class ScoutAgent:
    """Main scout agent that orchestrates lead discovery and scoring."""
    
    def __init__(self, config_path: str = "config.yaml"):
        self.config = self._load_config(config_path)
        self.scraper = LinkedInScraper(
            api_key=os.getenv('LINKEDIN_API_KEY', 'mock_key')
        )
        self.scorer = LeadScorer(self.config)
        self.output_dir = Path(self.config.get('output_dir', './leads'))
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load configuration from YAML file."""
        try:
            with open(config_path, 'r') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            logger.warning(f"Config file {config_path} not found, using defaults")
            return {}
    
    def discover_leads(
        self,
        keywords: Optional[List[str]] = None,
        limit: int = 50
    ) -> List[Lead]:
        """
        Discover and score new leads.
        
        Args:
            keywords: Search keywords (defaults to config)
            limit: Maximum number of leads to return
            
        Returns:
            List of scored Lead objects
        """
        keywords = keywords or self.config.get('search', {}).get('keywords', ['CTO', 'VP Engineering'])
        industries = self.config.get('search', {}).get('industries', ['Technology', 'Software'])
        locations = self.config.get('search', {}).get('locations', ['San Francisco', 'New York'])
        
        logger.info(f"Starting lead discovery with keywords: {keywords}")
        
        # Search for profiles
        raw_profiles = self.scraper.search_profiles(
            keywords=keywords,
            industries=industries,
            locations=locations,
            limit=limit
        )
        
        # Score each profile
        target_criteria = self.config.get('target_profile', {})
        leads = []
        
        for profile in raw_profiles:
            score = self.scorer.score_lead(profile, target_criteria)
            
            # Only keep leads above threshold
            min_score = self.config.get('scoring', {}).get('min_threshold', 0.5)
            if score >= min_score:
                lead = Lead(
                    profile_url=profile['profile_url'],
                    name=profile['name'],
                    title=profile['title'],
                    company=profile['company'],
                    industry=profile['industry'],
                    location=profile['location'],
                    connections=profile['connections'],
                    score=score,
                    scraped_at=datetime.now().isoformat(),
                    raw_data=profile
                )
                leads.append(lead)
        
        logger.info(f"Discovered {len(leads)} qualified leads (score >= {min_score})")
        
        # Save results
        self._save_leads(leads)
        
        return leads
    
    def _save_leads(self, leads: List[Lead]):
        """Save leads to JSON file."""
        if not leads:
            return
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = self.output_dir / f'leads_{timestamp}.json'
        
        leads_data = [asdict(lead) for lead in leads]
        
        with open(output_file, 'w') as f:
            json.dump(leads_data, f, indent=2)
        
        logger.info(f"Saved {len(leads)} leads to {output_file}")
    
    def run(self, keywords: Optional[List[str]] = None, limit: int = 50):
        """Run the scout agent."""
        try:
            leads = self.discover_leads(keywords=keywords, limit=limit)
            
            # Output summary
            print(f"\n{'='*60}")
            print(f"SCOUT AGENT RESULTS")
            print(f"{'='*60}")
            print(f"Total leads found: {len(leads)}")
            
            if leads:
                avg_score = sum(l.score for l in leads) / len(leads)
                print(f"Average score: {avg_score:.2f}")
                print(f"\nTop 5 leads:")
                
                sorted_leads = sorted(leads, key=lambda x: x.score, reverse=True)
                for i, lead in enumerate(sorted_leads[:5], 1):
                    print(f"  {i}. {lead.name} - {lead.title} @ {lead.company} (Score: {lead.score})")
            
            print(f"{'='*60}\n")
            
            return leads
            
        except Exception as e:
            logger.error(f"Scout agent failed: {e}", exc_info=True)
            raise


def main():
    """CLI entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='LinkedIn Lead Scout Agent')
    parser.add_argument('--config', default='config.yaml', help='Config file path')
    parser.add_argument('--keywords', nargs='+', help='Search keywords')
    parser.add_argument('--limit', type=int, default=50, help='Max leads to fetch')
    parser.add_argument('--output-dir', help='Output directory for leads')
    
    args = parser.parse_args()
    
    agent = ScoutAgent(config_path=args.config)
    
    if args.output_dir:
        agent.output_dir = Path(args.output_dir)
    
    agent.run(keywords=args.keywords, limit=args.limit)


if __name__ == '__main__':
    main()

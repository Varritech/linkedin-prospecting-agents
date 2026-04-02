#!/usr/bin/env python3
"""
Qualify Agent - Analyzes lead fit using Claude API.

This agent takes leads from the scout agent and uses AI to determine
if they're a good fit based on detailed criteria.
"""

import os
import json
import time
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path

import yaml
from anthropic import Anthropic, RateLimitError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('qualify_agent')


@dataclass
class QualificationResult:
    """Result of lead qualification analysis."""
    lead_url: str
    qualified: bool
    confidence: float
    reasoning: str
    strengths: List[str]
    weaknesses: List[str]
    recommended_action: str
    analyzed_at: str


class ClaudeAnalyzer:
    """Uses Claude API to analyze lead fit."""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv('ANTHROPIC_API_KEY')
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not set")
        
        self.client = Anthropic(api_key=self.api_key)
        self.model = "claude-sonnet-4-20250514"
        self.max_retries = 3
        self.base_delay = 2.0  # seconds
    
    def _retry_with_backoff(self, func, *args, **kwargs):
        """Retry API calls with exponential backoff."""
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                return func(*args, **kwargs)
            except RateLimitError as e:
                last_error = e
                delay = self.base_delay * (2 ** attempt)
                logger.warning(f"Rate limited, waiting {delay}s before retry {attempt + 1}")
                time.sleep(delay)
            except Exception as e:
                logger.error(f"API error: {e}")
                raise
        
        raise last_error
    
    def analyze_lead(
        self,
        lead_data: Dict[str, Any],
        ideal_customer_profile: Dict[str, Any]
    ) -> QualificationResult:
        """
        Analyze a lead using Claude to determine fit.
        
        Args:
            lead_data: LinkedIn profile data
            ideal_customer_profile: Criteria for ideal customers
            
        Returns:
            QualificationResult with analysis
        """
        prompt = self._build_analysis_prompt(lead_data, ideal_customer_profile)
        
        def make_request():
            return self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )
        
        response = self._retry_with_backoff(make_request)
        
        # Parse Claude's response
        analysis = self._parse_response(response.content[0].text)
        
        return QualificationResult(
            lead_url=lead_data.get('profile_url', ''),
            qualified=analysis['qualified'],
            confidence=analysis['confidence'],
            reasoning=analysis['reasoning'],
            strengths=analysis['strengths'],
            weaknesses=analysis['weaknesses'],
            recommended_action=analysis['recommended_action'],
            analyzed_at=datetime.now().isoformat()
        )
    
    def _build_analysis_prompt(
        self,
        lead_data: Dict[str, Any],
        icp: Dict[str, Any]
    ) -> str:
        """Build the prompt for Claude analysis."""
        
        lead_info = f"""
PROFILE DATA:
- Name: {lead_data.get('name', 'Unknown')}
- Title: {lead_data.get('title', 'Unknown')}
- Company: {lead_data.get('company', 'Unknown')}
- Industry: {lead_data.get('industry', 'Unknown')}
- Location: {lead_data.get('location', 'Unknown')}
- Connections: {lead_data.get('connections', 0)}
- Headline: {lead_data.get('headline', 'N/A')}
- Summary: {lead_data.get('summary', 'N/A')}
"""
        
        icp_info = f"""
IDEAL CUSTOMER PROFILE:
- Target Titles: {', '.join(icp.get('titles', []))}
- Target Industries: {', '.join(icp.get('industries', []))}
- Target Locations: {', '.join(icp.get('locations', []))}
- Company Size: {icp.get('company_size', 'Any')}
- Decision Maker: {icp.get('decision_maker', 'Yes')}
"""
        
        prompt = f"""
You are a B2B sales qualification expert. Analyze this LinkedIn lead against our Ideal Customer Profile (ICP).

{lead_info}
{icp_info}

Your task:
1. Determine if this lead is QUALIFIED (good fit) or NOT QUALIFIED (poor fit)
2. Assign a confidence score (0.0 to 1.0)
3. Provide detailed reasoning
4. List 3-5 strengths (why they might be a good fit)
5. List 3-5 weaknesses or concerns
6. Recommend next action: "outreach", "nurture", or "disqualify"

Respond in this exact JSON format:
{{
  "qualified": true/false,
  "confidence": 0.0-1.0,
  "reasoning": "detailed explanation",
  "strengths": ["point 1", "point 2"],
  "weaknesses": ["point 1", "point 2"],
  "recommended_action": "outreach|nurture|disqualify"
}}

Only return the JSON, no other text.
"""
        return prompt
    
    def _parse_response(self, response_text: str) -> Dict[str, Any]:
        """Parse Claude's JSON response."""
        try:
            # Extract JSON from response (in case there's extra text)
            start = response_text.find('{')
            end = response_text.rfind('}') + 1
            json_str = response_text[start:end]
            
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Claude response: {e}")
            logger.debug(f"Response text: {response_text}")
            
            # Return default structure
            return {
                'qualified': False,
                'confidence': 0.5,
                'reasoning': 'Failed to parse analysis',
                'strengths': [],
                'weaknesses': [],
                'recommended_action': 'nurture'
            }


class QualifyAgent:
    """Main qualification agent."""
    
    def __init__(self, config_path: str = "config.yaml"):
        self.config = self._load_config(config_path)
        
        # Initialize Claude analyzer
        try:
            self.analyzer = ClaudeAnalyzer()
            self.claude_available = True
        except ValueError:
            logger.warning("Claude API key not available, using mock analyzer")
            self.analyzer = None
            self.claude_available = False
        
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
    
    def qualify_leads(
        self,
        leads_file: Optional[str] = None,
        leads: Optional[List[Dict]] = None
    ) -> List[QualificationResult]:
        """
        Qualify a batch of leads.
        
        Args:
            leads_file: Path to JSON file with leads (from scout agent)
            leads: Direct list of leads (alternative to file)
            
        Returns:
            List of QualificationResult objects
        """
        # Load leads
        if leads:
            leads_data = leads
        elif leads_file:
            with open(leads_file, 'r') as f:
                leads_data = json.load(f)
        else:
            # Find most recent leads file
            leads_files = sorted(self.output_dir.glob('leads_*.json'), reverse=True)
            if leads_files:
                with open(leads_files[0], 'r') as f:
                    leads_data = json.load(f)
            else:
                logger.error("No leads file found and no leads provided")
                return []
        
        logger.info(f"Qualifying {len(leads_data)} leads")
        
        icp = self.config.get('ideal_customer_profile', {})
        results = []
        
        for i, lead in enumerate(leads_data):
            logger.info(f"Analyzing lead {i+1}/{len(leads_data)}: {lead.get('name', 'Unknown')}")
            
            if self.claude_available:
                result = self.analyzer.analyze_lead(lead, icp)
            else:
                # Mock qualification
                result = self._mock_qualify(lead, icp)
            
            results.append(result)
            
            # Rate limiting
            if self.claude_available:
                time.sleep(1.0)  # Be conservative with API calls
        
        # Save results
        self._save_results(results)
        
        return results
    
    def _mock_qualify(
        self,
        lead: Dict[str, Any],
        icp: Dict[str, Any]
    ) -> QualificationResult:
        """Mock qualification when Claude is unavailable."""
        score = lead.get('score', 0.5)
        qualified = score >= 0.6
        
        return QualificationResult(
            lead_url=lead.get('profile_url', ''),
            qualified=qualified,
            confidence=score,
            reasoning=f"Lead scored {score} based on profile match",
            strengths=["Good title match", "Relevant industry"],
            weaknesses=["Limited connection data"],
            recommended_action="outreach" if qualified else "nurture",
            analyzed_at=datetime.now().isoformat()
        )
    
    def _save_results(self, results: List[QualificationResult]):
        """Save qualification results to file."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = self.output_dir / f'qualified_{timestamp}.json'
        
        results_data = [asdict(r) for r in results]
        
        with open(output_file, 'w') as f:
            json.dump(results_data, f, indent=2)
        
        logger.info(f"Saved {len(results)} qualification results to {output_file}")
    
    def run(self, leads_file: Optional[str] = None):
        """Run the qualify agent."""
        try:
            results = self.qualify_leads(leads_file=leads_file)
            
            # Output summary
            qualified_count = sum(1 for r in results if r.qualified)
            avg_confidence = sum(r.confidence for r in results) / len(results) if results else 0
            
            print(f"\n{'='*60}")
            print(f"QUALIFY AGENT RESULTS")
            print(f"{'='*60}")
            print(f"Total leads analyzed: {len(results)}")
            print(f"Qualified: {qualified_count}")
            print(f"Not qualified: {len(results) - qualified_count}")
            print(f"Average confidence: {avg_confidence:.2f}")
            
            if self.claude_available:
                print("Analysis powered by Claude API ✓")
            else:
                print("Using mock analysis (set ANTHROPIC_API_KEY for real analysis)")
            
            print(f"\nTop qualified leads:")
            qualified_results = [r for r in results if r.qualified]
            sorted_results = sorted(qualified_results, key=lambda x: x.confidence, reverse=True)
            
            for i, result in enumerate(sorted_results[:5], 1):
                print(f"  {i}. {result.lead_url}")
                print(f"     Confidence: {result.confidence:.2f}")
                print(f"     Action: {result.recommended_action}")
            
            print(f"{'='*60}\n")
            
            return results
            
        except Exception as e:
            logger.error(f"Qualify agent failed: {e}", exc_info=True)
            raise


def main():
    """CLI entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Lead Qualification Agent (Claude-powered)')
    parser.add_argument('--config', default='config.yaml', help='Config file path')
    parser.add_argument('--leads-file', help='JSON file with leads from scout agent')
    parser.add_argument('--output-dir', help='Output directory for results')
    
    args = parser.parse_args()
    
    agent = QualifyAgent(config_path=args.config)
    
    if args.output_dir:
        agent.output_dir = Path(args.output_dir)
    
    agent.run(leads_file=args.leads_file)


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""
Outreach Agent - Generates personalized connection requests.

This agent creates customized outreach messages for qualified leads
using AI to ensure personalization and relevance.
"""

import os
import json
import time
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from pathlib import Path

import yaml
from anthropic import Anthropic, RateLimitError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('outreach_agent')


@dataclass
class OutreachMessage:
    """Generated outreach message for a lead."""
    lead_url: str
    lead_name: str
    subject: str
    message_body: str
    connection_request_note: str
    followup_sequence: List[str]
    personalization_points: List[str]
    generated_at: str
    confidence: float


class MessageGenerator:
    """Generates personalized outreach messages using Claude."""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv('ANTHROPIC_API_KEY')
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not set")
        
        self.client = Anthropic(api_key=self.api_key)
        self.model = "claude-sonnet-4-20250514"
        self.max_retries = 3
        self.base_delay = 2.0
    
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
    
    def generate_message(
        self,
        lead_data: Dict[str, Any],
        qualification_result: Dict[str, Any],
        company_info: Dict[str, Any],
        outreach_template: Dict[str, Any]
    ) -> OutreachMessage:
        """
        Generate a personalized outreach message.
        
        Args:
            lead_data: LinkedIn profile data
            qualification_result: Analysis from qualify agent
            company_info: Information about sender's company
            outreach_template: Template/guidelines for messaging
            
        Returns:
            OutreachMessage with generated content
        """
        prompt = self._build_message_prompt(
            lead_data, qualification_result, company_info, outreach_template
        )
        
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
        message_data = self._parse_response(response.content[0].text)
        
        return OutreachMessage(
            lead_url=lead_data.get('profile_url', ''),
            lead_name=lead_data.get('name', 'there'),
            subject=message_data.get('subject', 'Quick question'),
            message_body=message_data.get('message_body', ''),
            connection_request_note=message_data.get('connection_request_note', ''),
            followup_sequence=message_data.get('followup_sequence', []),
            personalization_points=message_data.get('personalization_points', []),
            generated_at=datetime.now().isoformat(),
            confidence=message_data.get('confidence', 0.8)
        )
    
    def _build_message_prompt(
        self,
        lead_data: Dict[str, Any],
        qualification_result: Dict[str, Any],
        company_info: Dict[str, Any],
        template: Dict[str, Any]
    ) -> str:
        """Build the prompt for message generation."""
        
        lead_context = f"""
LEAD PROFILE:
- Name: {lead_data.get('name', 'Unknown')}
- Title: {lead_data.get('title', 'Unknown')}
- Company: {lead_data.get('company', 'Unknown')}
- Headline: {lead_data.get('headline', 'N/A')}
- Summary: {lead_data.get('summary', 'N/A')}
- Location: {lead_data.get('location', 'N/A')}

QUALIFICATION ANALYSIS:
- Qualified: {qualification_result.get('qualified', False)}
- Strengths: {', '.join(qualification_result.get('strengths', []))}
- Recommended Action: {qualification_result.get('recommended_action', 'outreach')}
"""
        
        company_context = f"""
YOUR COMPANY:
- Name: {company_info.get('name', 'Our Company')}
- What we do: {company_info.get('value_prop', 'We help companies')}
- Target audience: {company_info.get('target_audience', 'Tech companies')}
"""
        
        template_guidance = f"""
MESSAGE GUIDELINES:
- Tone: {template.get('tone', 'professional but friendly')}
- Length: {template.get('length', 'short, 3-4 sentences')}
- Goal: {template.get('goal', 'book a discovery call')}
- Avoid: {', '.join(template.get('avoid', ['salesy language', 'generic pitches']))}
"""
        
        prompt = f"""
You are an expert B2B SDR writing personalized LinkedIn outreach messages.

{lead_context}
{company_context}
{template_guidance}

Your task:
1. Write a personalized connection request note (max 300 characters - LinkedIn limit)
2. Write a follow-up message body (for after they accept)
3. Create a compelling subject line
4. Identify 3-5 personalization points you used
5. Create a 3-message follow-up sequence (if they don't respond)
6. Assign a confidence score (0.0-1.0) on how well this message will resonate

Key principles:
- Reference something specific from their profile (recent post, experience, etc.)
- Lead with value, not a pitch
- Keep it conversational and human
- Ask a thoughtful question
- Make it about THEM, not you

Respond in this exact JSON format:
{{
  "subject": "subject line",
  "message_body": "full message text",
  "connection_request_note": "300 char max note for connection request",
  "followup_sequence": ["day 3 message", "day 7 message", "day 14 message"],
  "personalization_points": ["point 1", "point 2", "point 3"],
  "confidence": 0.0-1.0
}}

Only return the JSON, no other text.
"""
        return prompt
    
    def _parse_response(self, response_text: str) -> Dict[str, Any]:
        """Parse Claude's JSON response."""
        try:
            start = response_text.find('{')
            end = response_text.rfind('}') + 1
            json_str = response_text[start:end]
            
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse response: {e}")
            return {
                'subject': 'Quick question',
                'message_body': 'Hi, I noticed your profile and wanted to connect.',
                'connection_request_note': 'Hi, would love to connect!',
                'followup_sequence': ['Following up on my connection request', 'Just checking in', 'Last try'],
                'personalization_points': [],
                'confidence': 0.5
            }


class OutreachAgent:
    """Main outreach agent."""
    
    def __init__(self, config_path: str = "config.yaml"):
        self.config = self._load_config(config_path)
        
        # Initialize message generator
        try:
            self.generator = MessageGenerator()
            self.claude_available = True
        except ValueError:
            logger.warning("Claude API key not available, using mock generator")
            self.generator = None
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
    
    def generate_outreach(
        self,
        qualified_leads_file: Optional[str] = None,
        leads: Optional[List[Dict]] = None
    ) -> List[OutreachMessage]:
        """
        Generate outreach messages for qualified leads.
        
        Args:
            qualified_leads_file: Path to qualification results
            leads: Direct list of qualified leads
            
        Returns:
            List of OutreachMessage objects
        """
        # Load qualified leads
        if leads:
            leads_data = leads
        elif qualified_leads_file:
            with open(qualified_leads_file, 'r') as f:
                leads_data = json.load(f)
        else:
            # Find most recent qualified file
            qualified_files = sorted(self.output_dir.glob('qualified_*.json'), reverse=True)
            if qualified_files:
                with open(qualified_files[0], 'r') as f:
                    leads_data = json.load(f)
            else:
                logger.error("No qualified leads file found")
                return []
        
        # Filter to only qualified leads
        qualified = [l for l in leads_data if l.get('qualified', False)]
        logger.info(f"Generating outreach for {len(qualified)} qualified leads")
        
        company_info = self.config.get('company', {})
        outreach_template = self.config.get('outreach', {})
        
        messages = []
        
        for i, lead in enumerate(qualified):
            logger.info(f"Generating message {i+1}/{len(qualified)} for {lead.get('lead_url', 'Unknown')}")
            
            # Reconstruct lead data from qualification result
            lead_data = {
                'profile_url': lead.get('lead_url', ''),
                'name': lead.get('lead_name', 'Unknown'),
                'title': lead.get('title', 'Unknown'),
                'company': lead.get('company', 'Unknown'),
                'headline': lead.get('headline', ''),
                'summary': lead.get('summary', '')
            }
            
            if self.claude_available:
                message = self.generator.generate_message(
                    lead_data=lead_data,
                    qualification_result=lead,
                    company_info=company_info,
                    outreach_template=outreach_template
                )
            else:
                message = self._mock_generate(lead_data, company_info)
            
            messages.append(message)
            
            # Rate limiting
            if self.claude_available:
                time.sleep(1.0)
        
        # Save results
        self._save_messages(messages)
        
        return messages
    
    def _mock_generate(
        self,
        lead_data: Dict[str, Any],
        company_info: Dict[str, Any]
    ) -> OutreachMessage:
        """Mock message generation when Claude is unavailable."""
        name = lead_data.get('name', 'there')
        title = lead_data.get('title', 'Professional')
        company = lead_data.get('company', 'Company')
        
        return OutreachMessage(
            lead_url=lead_data.get('profile_url', ''),
            lead_name=name,
            subject=f"Quick question about {company}",
            message_body=f"""Hi {name},

I noticed you're working as {title} at {company}. We've been helping similar companies streamline their processes with AI.

Would you be open to a brief chat about how we might help {company}?

Best,
{company_info.get('sender_name', 'Our Team')}
""",
            connection_request_note=f"Hi {name}, I noticed your work at {company} and would love to connect.",
            followup_sequence=[
                "Hi, just following up on my connection request",
                "Wanted to circle back on this",
                "Last attempt to reach out"
            ],
            personalization_points=[f"Title: {title}", f"Company: {company}"],
            generated_at=datetime.now().isoformat(),
            confidence=0.7
        )
    
    def _save_messages(self, messages: List[OutreachMessage]):
        """Save generated messages to file."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = self.output_dir / f'outreach_{timestamp}.json'
        
        messages_data = [asdict(m) for m in messages]
        
        with open(output_file, 'w') as f:
            json.dump(messages_data, f, indent=2)
        
        logger.info(f"Saved {len(messages)} outreach messages to {output_file}")
    
    def run(self, leads_file: Optional[str] = None):
        """Run the outreach agent."""
        try:
            messages = self.generate_outreach(qualified_leads_file=leads_file)
            
            # Output summary
            avg_confidence = sum(m.confidence for m in messages) / len(messages) if messages else 0
            
            print(f"\n{'='*60}")
            print(f"OUTREACH AGENT RESULTS")
            print(f"{'='*60}")
            print(f"Messages generated: {len(messages)}")
            print(f"Average confidence: {avg_confidence:.2f}")
            
            if self.claude_available:
                print("Messages powered by Claude API ✓")
            else:
                print("Using mock generation (set ANTHROPIC_API_KEY for real messages)")
            
            print(f"\nSample messages:")
            for i, msg in enumerate(messages[:3], 1):
                print(f"\n  {i}. {msg.lead_name} @ {msg.lead_url}")
                print(f"     Subject: {msg.subject}")
                print(f"     Connection note: {msg.connection_request_note[:100]}...")
                print(f"     Confidence: {msg.confidence:.2f}")
            
            print(f"\n{'='*60}\n")
            
            return messages
            
        except Exception as e:
            logger.error(f"Outreach agent failed: {e}", exc_info=True)
            raise


def main():
    """CLI entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Outreach Message Generator')
    parser.add_argument('--config', default='config.yaml', help='Config file path')
    parser.add_argument('--leads-file', help='JSON file with qualified leads')
    parser.add_argument('--output-dir', help='Output directory for messages')
    
    args = parser.parse_args()
    
    agent = OutreachAgent(config_path=args.config)
    
    if args.output_dir:
        agent.output_dir = Path(args.output_dir)
    
    agent.run(leads_file=args.leads_file)


if __name__ == '__main__':
    main()

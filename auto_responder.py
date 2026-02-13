#!/usr/bin/env python3
"""
Auto-Responder Bot
Automatically responds to auto-detected issues in your repository
"""

import os
import json
import requests
from datetime import datetime, timedelta
from typing import List, Dict

class IssueResponderBot:
    def __init__(self):
        self.github_token = os.environ.get('GITHUB_TOKEN')
        if not self.github_token:
            raise ValueError("GITHUB_TOKEN environment variable not set")
        
        self.headers = {
            'Authorization': f'token {self.github_token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        
        self.target_repo = os.environ.get('TARGET_REPO')
        self.load_responses()
    
    def load_responses(self):
        """Load bot response templates"""
        with open('bot_responses.json', 'r') as f:
            self.responses = json.load(f)
    
    def get_unresponded_issues(self) -> List[Dict]:
        """Get auto-detected issues that haven't been responded to"""
        url = f'https://api.github.com/repos/{self.target_repo}/issues'
        params = {
            'state': 'open',
            'labels': 'auto-detected',
            'per_page': 30,
            'sort': 'created',
            'direction': 'desc'
        }
        
        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=10)
            if response.status_code == 200:
                issues = response.json()
                # Filter issues without bot comments
                unresponded = []
                for issue in issues:
                    if not self.has_bot_comment(issue['number']):
                        unresponded.append(issue)
                return unresponded
            return []
        except Exception as e:
            print(f"Error fetching issues: {str(e)}")
            return []
    
    def has_bot_comment(self, issue_number: int) -> bool:
        """Check if issue already has a bot comment"""
        url = f'https://api.github.com/repos/{self.target_repo}/issues/{issue_number}/comments'
        
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            if response.status_code == 200:
                comments = response.json()
                # Check for any comment containing our signature
                for comment in comments:
                    comment_body = comment.get('body', '')
                    # Look for our unique signature in the comment
                    if '— Stay Awesome 🚀' in comment_body or 'Auto-Response from Bot' in comment_body:
                        return True
            return False
        except Exception as e:
            print(f"Error checking comments: {str(e)}")
            return False
    
    def detect_issue_category(self, issue: Dict) -> str:
        """Detect the category of the issue based on keywords"""
        title = issue.get('title', '').lower()
        body = issue.get('body', '') or ''
        body = body.lower()
        content = f"{title} {body}"
        
        # Check for different categories
        categories = {
            'bug': ['bug', 'error', 'broken', 'not working', 'failed', 'crash'],
            'security': ['security', 'vulnerability', 'exploit', 'hack', 'attack'],
            'help': ['help', 'how to', 'question', 'confused', 'unclear'],
            'transaction': ['transaction', 'swap', 'transfer', 'send', 'receive'],
            'wallet': ['wallet', 'balance', 'account', 'address'],
            'contract': ['contract', 'smart contract', 'deploy', 'solidity'],
            'gas': ['gas', 'fee', 'cost', 'expensive'],
            'token': ['token', 'nft', 'erc20', 'erc721']
        }
        
        for category, keywords in categories.items():
            for keyword in keywords:
                if keyword in content:
                    return category
        
        return 'general'
    
    def post_response(self, issue_number: int, response_text: str):
        """Post a comment response to an issue"""
        url = f'https://api.github.com/repos/{self.target_repo}/issues/{issue_number}/comments'
        
        payload = {
            'body': response_text
        }
        
        try:
            response = requests.post(url, headers=self.headers, json=payload, timeout=10)
            if response.status_code == 201:
                print(f"✅ Responded to issue #{issue_number}")
                return True
            else:
                print(f"⚠️  Failed to post comment: {response.status_code}")
                return False
        except Exception as e:
            print(f"⚠️  Exception posting comment: {str(e)}")
            return False
    
    def respond_to_issues(self):
        """Main function to respond to issues"""
        print(f"\n{'='*60}")
        print(f"🤖 Auto-Responder Bot - {datetime.utcnow().isoformat()}")
        print(f"{'='*60}\n")
        
        issues = self.get_unresponded_issues()
        
        if not issues:
            print("📭 No new issues to respond to")
            return
        
        print(f"📬 Found {len(issues)} issue(s) to respond to\n")
        
        for issue in issues:
            category = self.detect_issue_category(issue)
            print(f"📝 Issue #{issue['number']}: {issue['title'][:50]}...")
            print(f"   Category: {category}")
            
            # Get appropriate response template
            template = self.responses.get(category, self.responses.get('general'))
            
            # Format response with issue details
            response_text = template.format(
                issue_number=issue['number'],
                issue_title=issue['title'],
                timestamp=datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
            )
            
            # Post the response
            self.post_response(issue['number'], response_text)
        
        print(f"\n{'='*60}")
        print(f"✅ Response complete!")
        print(f"{'='*60}\n")

def main():
    try:
        bot = IssueResponderBot()
        bot.respond_to_issues()
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        raise

if __name__ == '__main__':
    main()

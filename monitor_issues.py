#!/usr/bin/env python3
"""
Crypto Issue Monitor Bot - Enhanced Edition
Features: Priority Levels, Duplicate Detection, Auto-Assignment
"""

import os
import json
import time
from datetime import datetime, timedelta
import requests
from typing import List, Dict, Set
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
        self.check_interval_minutes = config.get('check_interval_minutes', 5)
        
        # Load team assignments (Feature #3)
        self.team_assignments = config.get('team_assignments', {
            'wallet': ['@keisinoc'],
            'security': ['@keisinoc'],
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
    
    def get_recent_issues(self, repo: str, since_minutes: int = 10) -> List[Dict]:
        """Get recent issues from a repository"""
        since_time = (datetime.utcnow() - timedelta(minutes=since_minutes)).isoformat() + 'Z'
        
        url = f'https://api.github.com/repos/{repo}/issues'
        params = {
            'state': 'open',
            'since': since_time,
            'per_page': 30,
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
        """Check if issue matches our monitoring criteria"""
        title = issue.get('title', '').lower()
        body = issue.get('body', '') or ''
        body = body.lower()
        content = f"{title} {body}"
        
        for keyword in self.keywords:
            if keyword.lower() in content:
                return True
        return False
    
    def detect_priority(self, issue: Dict) -> str:
        """FEATURE #1: Detect priority level based on keywords"""
        title = issue.get('title', '').lower()
        body = (issue.get('body', '') or '').lower()
        content = f"{title} {body}"
        
        # Critical priority keywords
        if any(word in content for word in ['critical', 'urgent', 'emergency', 'security breach', 'exploit', 'hack', 'funds at risk', 'total loss']):
            return 'priority-critical'
        
        # Urgent priority keywords
        elif any(word in content for word in ['urgent', 'asap', 'immediately', 'cant access', 'locked out', 'lost funds']):
            return 'priority-urgent'
        
        # High priority keywords
        elif any(word in content for word in ['high', 'important', 'stuck', 'frozen', 'missing balance']):
            return 'priority-high'
        
        # Low priority keywords
        elif any(word in content for word in ['minor', 'low', 'suggestion', 'enhancement', 'feature request']):
            return 'priority-low'
        
        # Default: Medium priority
        else:
            return 'priority-medium'
    
    def similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity between two texts"""
        return SequenceMatcher(None, text1.lower(), text2.lower()).ratio()
    
    def check_for_duplicates(self, issue_title: str, issue_body: str) -> List[Dict]:
        """FEATURE #4: Check for duplicate/similar issues in target repo"""
        url = f'https://api.github.com/repos/{self.target_repo}/issues'
        params = {
            'state': 'open',
            'per_page': 50,
            'sort': 'created',
            'direction': 'desc'
        }
        
        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=10)
            if response.status_code == 200:
                existing_issues = response.json()
                duplicates = []
                
                for existing in existing_issues:
                    # Calculate title similarity
                    title_similarity = self.similarity(issue_title, existing['title'])
                    
                    # If titles are 70%+ similar, it's likely a duplicate
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
        """FEATURE #7: Get team member to assign based on issue category"""
        assignees = self.team_assignments.get(category, self.team_assignments.get('general', []))
        # Return first assignee (you can add rotation logic later)
        return assignees[0] if assignees else None
    
    def create_issue_in_target_repo(self, original_issue: Dict, source_repo: str):
        """Create issue with enhanced features"""
        url = f'https://api.github.com/repos/{self.target_repo}/issues'
        
        original_body = original_issue.get('body', '') or '*No description provided*'
        source_url = original_issue['html_url']
        source_user = original_issue['user']['login']
        issue_title = original_issue['title']
        
        # FEATURE #1: Detect priority
        priority_label = self.detect_priority(original_issue)
        print(f"   🎯 Priority: {priority_label}")
        
        # FEATURE #4: Check for duplicates
        duplicates = self.check_for_duplicates(issue_title, original_body)
        duplicate_section = ""
        if duplicates:
            print(f"   🔍 Found {len(duplicates)} similar issue(s)")
            duplicate_section = "\n\n## ⚠️ Possible Duplicates Detected\n\n"
            for dup in duplicates[:3]:  # Show max 3
                duplicate_section += f"- #{dup['number']}: [{dup['title']}]({dup['url']}) (Similarity: {dup['similarity']:.0%})\n"
        
        new_body = f"""## 🔔 Auto-detected Issue from {source_repo}

**Original Issue:** {source_url}  
**Reported by:** @{source_user}  
**Created:** {original_issue['created_at']}  
**Priority:** `{priority_label}`

---

### Original Description:

{original_body}
{duplicate_section}

---

*Automatically imported and tracked by GitHub Support Infrastructure. Issue will be reviewed and assigned to the appropriate team for resolution.*
"""
        
        # Create smart labels with priority
        labels = ['auto-detected']
        
        # Add priority label
        labels.append(priority_label)
        
        # Add category label
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
        
        # Add duplicate label if found
        if duplicates:
            labels.append('possible-duplicate')
        
        # FEATURE #7: Get assignee for this category
        assignee = self.get_assignee_for_category(category)
        print(f"   👤 Assigned to: {assignee}")
        
        payload = {
            'title': f"[AUTO] {issue_title}",
            'body': new_body,
            'labels': labels
        }
        
        # Add assignee if available (remove @ symbol)
        if assignee and assignee.startswith('@'):
            payload['assignees'] = [assignee[1:]]
        
        try:
            response = requests.post(url, headers=self.headers, json=payload, timeout=10)
            if response.status_code == 201:
                new_issue = response.json()
                print(f"✅ Created issue #{new_issue['number']}: {issue_title[:50]}...")
                return new_issue
            else:
                print(f"⚠️  Failed to create issue: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            print(f"⚠️  Exception creating issue: {str(e)}")
            return None
    
    def monitor_repositories(self):
        """Main monitoring function"""
        print(f"\n{'='*60}")
        print(f"🚀 Crypto Issue Monitor - Enhanced Edition")
        print(f"{'='*60}\n")
        
        remaining = self.check_rate_limit()
        if remaining < 100:
            print("⚠️  Low API rate limit. Waiting for reset...")
            return
        
        total_issues_found = 0
        total_issues_created = 0
        
        for repo in self.monitored_repos:
            print(f"\n📂 Checking repository: {repo}")
            
            issues = self.get_recent_issues(repo, since_minutes=self.check_interval_minutes + 5)
            
            if not issues:
                print(f"   No new issues found")
                continue
            
            print(f"   Found {len(issues)} recent issue(s)")
            
            for issue in issues:
                issue_id = f"{repo}#{issue['number']}"
                
                if issue_id in self.processed_issues:
                    continue
                
                if self.matches_criteria(issue):
                    total_issues_found += 1
                    print(f"   ✨ Match found: #{issue['number']} - {issue['title'][:50]}...")
                    
                    created = self.create_issue_in_target_repo(issue, repo)
                    if created:
                        total_issues_created += 1
                        self.processed_issues.add(issue_id)
                else:
                    self.processed_issues.add(issue_id)
        
        self.save_processed_issues()
        
        print(f"\n{'='*60}")
        print(f"📊 Summary:")
        print(f"   - Matching issues found: {total_issues_found}")
        print(f"   - Issues created: {total_issues_created}")
        print(f"   - Total tracked: {len(self.processed_issues)}")
        print(f"{'='*60}\n")
    
    def search_github_for_crypto_issues(self, max_results: int = 30):
        """Search ALL GitHub for crypto issues from last 2 hours"""
        print(f"\n🔍 Searching ALL of GitHub for crypto issues (last 15 minutes)...")
        
        # Search issues from last 2 HOURS (not days!)
        since_time = datetime.utcnow() - timedelta(minutes=20)
        since_formatted = since_time.strftime('%Y-%m-%dT%H:%M:%SZ')
        
        # Search ONLY in crypto-related repos by using language filter
        query = f'is:issue is:open created:>={since_formatted} language:solidity wallet'
        
        url = 'https://api.github.com/search/issues'
        params = {
            'q': query,
            'sort': 'created',
            'order': 'desc',
            'per_page': max_results
        }
        
        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                issues = data.get('items', [])
                print(f"   Found {len(issues)} issues across GitHub")
                
                created_count = 0
                for issue in issues:
                    repo_url_parts = issue['repository_url'].split('/')
                    repo = f"{repo_url_parts[-2]}/{repo_url_parts[-1]}"
                    issue_id = f"{repo}#{issue['number']}"
                    
                    # Check if matches our detailed keywords
                    if issue_id not in self.processed_issues and self.matches_criteria(issue):
                        print(f"   ✨ Match! {repo}: #{issue['number']} - {issue['title'][:40]}")
                        created = self.create_issue_in_target_repo(issue, repo)
                        if created:
                            created_count += 1
                            self.processed_issues.add(issue_id)
                    else:
                        self.processed_issues.add(issue_id)
                
                self.save_processed_issues()
                print(f"   ✅ Created {created_count} new issues")
            else:
                print(f"   ⚠️  Search failed: {response.status_code}")
        except Exception as e:
            print(f"   ⚠️  Search exception: {str(e)}")

def main():
    """Main entry point"""
    try:
        monitor = CryptoIssueMonitor()
        
        use_search = os.environ.get('USE_GITHUB_SEARCH', 'false').lower() == 'true'
        
        if use_search:
            monitor.search_github_for_crypto_issues()
        else:
            monitor.monitor_repositories()
        
        print("✅ Monitoring complete!\n")
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        raise

if __name__ == '__main__':
    main()

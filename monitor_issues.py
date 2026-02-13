#!/usr/bin/env python3
"""
Crypto Issue Monitor Bot
Monitors multiple crypto repositories and copies matching issues to your repo
"""

import os
import json
import time
from datetime import datetime, timedelta
import requests
from typing import List, Dict, Set

class CryptoIssueMonitor:
    def __init__(self):
        self.github_token = os.environ.get('GITHUB_TOKEN')
        if not self.github_token:
            raise ValueError("GITHUB_TOKEN environment variable not set")
        
        self.headers = {
            'Authorization': f'token {self.github_token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        
        # Your repository where issues will be copied
        self.target_repo = os.environ.get('TARGET_REPO')
        
        # Load configuration
        self.load_config()
        
        # Track already processed issues
        self.processed_issues = self.load_processed_issues()
    
    def load_config(self):
        """Load monitoring configuration"""
        with open('config.json', 'r') as f:
            config = json.load(f)
        
        self.monitored_repos = config.get('monitored_repos', [])
        self.keywords = config.get('keywords', [])
        self.topics = config.get('topics', [])
        self.check_interval_minutes = config.get('check_interval_minutes', 5)
    
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
    
    def create_issue_in_target_repo(self, original_issue: Dict, source_repo: str):
        """Create a copy of the issue in your target repository"""
        url = f'https://api.github.com/repos/{self.target_repo}/issues'
        
        original_body = original_issue.get('body', '') or '*No description provided*'
        source_url = original_issue['html_url']
        source_user = original_issue['user']['login']
        
        new_body = f"""## 🔔 Auto-detected Issue from {source_repo}

**Original Issue:** {source_url}  
**Reported by:** @{source_user}  
**Created:** {original_issue['created_at']}

---

### Original Description:

{original_body}

---

*Automatically imported and tracked by GitHub Support Infrastructure. Issue will be reviewed and assigned to the appropriate team for resolution.*
"""
        
        # Create smart labels based on issue content
        labels = ['auto-detected']
        
        title_lower = original_issue['title'].lower()
        body_lower = (original_issue.get('body', '') or '').lower()
        content = f"{title_lower} {body_lower}"
        
        if any(word in content for word in ['bug', 'error', 'broken', 'crash', 'failed']):
            labels.append('bug')
        elif any(word in content for word in ['security', 'vulnerability', 'exploit', 'hack']):
            labels.append('security')
        elif any(word in content for word in ['wallet', 'balance', 'account', 'private key', 'seed phrase']):
            labels.append('wallet')
        elif any(word in content for word in ['transaction', 'swap', 'transfer', 'tx']):
            labels.append('transaction')
        elif any(word in content for word in ['contract', 'smart contract', 'solidity']):
            labels.append('contract')
        elif any(word in content for word in ['gas', 'fee']):
            labels.append('gas-fee')
        elif any(word in content for word in ['help', 'question', 'how to']):
            labels.append('help')
        else:
            labels.append('general')
        
        labels.append(f'source:{source_repo.split("/")[0]}')
        
        payload = {
            'title': f"[AUTO] {original_issue['title']}",
            'body': new_body,
            'labels': labels
        }
        
        try:
            response = requests.post(url, headers=self.headers, json=payload, timeout=10)
            if response.status_code == 201:
                new_issue = response.json()
                print(f"✅ Created issue #{new_issue['number']}: {original_issue['title'][:50]}...")
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
        print(f"🚀 Crypto Issue Monitor - {datetime.utcnow().isoformat()}")
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
        print(f"   - Issues created in target repo: {total_issues_created}")
        print(f"   - Total tracked issues: {len(self.processed_issues)}")
        print(f"{'='*60}\n")
    
    def search_github_for_crypto_issues(self, max_results: int = 30):
        """Search GitHub for crypto-related issues"""
        print(f"\n🔍 Searching GitHub for crypto issues...")
        
        since_date = (datetime.utcnow() - timedelta(days=5)).strftime('%Y-%m-%d')
        query = f'is:issue is:open created:>={since_date} language:solidity OR language:javascript wallet OR transaction OR bug OR error'
        
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
                print(f"   Found {len(issues)} issues via broad search")
                
                created_count = 0
                for issue in issues:
                    repo_url_parts = issue['repository_url'].split('/')
                    repo = f"{repo_url_parts[-2]}/{repo_url_parts[-1]}"
                    issue_id = f"{repo}#{issue['number']}"
                    
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

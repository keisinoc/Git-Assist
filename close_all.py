import requests
import os

token = "YOUR_GITHUB_TOKEN_HERE"  # Get from Settings > Developer > Tokens
repo = "keisinoc/Git-Assist"

headers = {
    'Authorization': f'token {token}',
    'Accept': 'application/vnd.github.v3+json'
}

# Get all open issues
url = f'https://api.github.com/repos/{repo}/issues'
params = {'state': 'open', 'per_page': 100}

response = requests.get(url, headers=headers, params=params)
issues = response.json()

print(f"Found {len(issues)} open issues. Closing...")

for issue in issues:
    if '[AUTO]' in issue['title']:  # Only close auto-detected ones
        close_url = f"https://api.github.com/repos/{repo}/issues/{issue['number']}"
        requests.patch(close_url, headers=headers, json={'state': 'closed'})
        print(f"Closed #{issue['number']}")

print("Done!")

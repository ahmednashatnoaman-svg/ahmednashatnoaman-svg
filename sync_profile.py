import os
import json
import urllib.request
import re

# File paths
README_FILE = "README.md"
CONFIG_FILE = "profile_config.json"

def fetch_top_repos(username):
    url = f"https://api.github.com/users/{username}/repos?sort=updated&per_page=100"
    headers = {}
    if "GITHUB_TOKEN" in os.environ:
        headers["Authorization"] = f"token {os.environ['GITHUB_TOKEN']}"
    
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req) as response:
            repos = json.loads(response.read().decode())
    except Exception as e:
        print(f"Error fetching repos: {e}")
        return []
    
    # Filter out forks and profile repo
    repos = [r for r in repos if not r['fork'] and r['name'] != username]
    # Sort by stargazers_count descending
    repos.sort(key=lambda x: x['stargazers_count'], reverse=True)
    return repos[:6] # Top 6 projects

def generate_badges_html(badges):
    html = '<div align="center">\n'
    for b in badges:
        img_url = f"https://img.shields.io/badge/{b['label']}-{b['message']}-{b['color']}?style=for-the-badge&logo={b['logo']}&logoColor={b['logoColor']}"
        html += f'  <img src="{img_url}" />\n'
    html += '</div>'
    return html

def generate_projects_markdown(repos):
    md = "| Project Name | Description | Tech Stack | Stars |\n"
    md += "| :--- | :--- | :--- | :--- |\n"
    for r in repos:
        name = r['name']
        url = r['html_url']
        desc = r['description'] or "No description"
        lang = r['language'] or "N/A"
        stars = r['stargazers_count']
        
        md += f"| **[{name}]({url})** | {desc} | `{lang}` | ⭐ {stars} |\n"
    return md

def replace_section(content, start_marker, end_marker, new_content):
    pattern = re.compile(rf"{start_marker}.*?{end_marker}", re.DOTALL)
    replacement = f"{start_marker}\n{new_content}\n{end_marker}"
    return re.sub(pattern, replacement, content)

def main():
    with open(CONFIG_FILE, 'r') as f:
        config = json.load(f)
    
    badges_html = generate_badges_html(config.get('badges', []))
    
    # User's GitHub username
    github_username = "ahmednashatnoaman-svg"
    repos = fetch_top_repos(github_username)
    projects_md = generate_projects_markdown(repos)
    
    with open(README_FILE, 'r') as f:
        readme_content = f.read()
    
    readme_content = replace_section(readme_content, "<!-- START_BADGES -->", "<!-- END_BADGES -->", badges_html)
    readme_content = replace_section(readme_content, "<!-- START_DYNAMIC_PROJECTS -->", "<!-- END_DYNAMIC_PROJECTS -->", projects_md)
    
    with open(README_FILE, 'w') as f:
        f.write(readme_content)
        
if __name__ == "__main__":
    main()

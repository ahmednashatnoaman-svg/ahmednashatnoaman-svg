import os
import json
import urllib.request
import re

# File paths
README_FILE = "README.md"
CONFIG_FILE = "profile_config.json"

# Map GitHub languages & topics to skillicons.dev identifiers
ICON_MAP = {
    "python": "py", "c++": "cpp", "typescript": "ts", "javascript": "js",
    "html": "html", "css": "css", "dart": "dart", "jupyter notebook": "py",
    "shell": "bash", "java": "java", "ruby": "rb", "go": "go",
    "rust": "rs", "php": "php", "c#": "cs", "swift": "swift", "kotlin": "kotlin",
    
    # Common Topics
    "fastapi": "fastapi", "docker": "docker", "flutter": "flutter", 
    "react": "react", "postgresql": "postgres", "mysql": "mysql", 
    "mongodb": "mongodb", "aws": "aws", "gcp": "gcp", 
    "tensorflow": "tensorflow", "pytorch": "pytorch", 
    "hadoop": "hadoop", "spark": "spark", "django": "django", 
    "linux": "linux", "github": "github", "git": "git", "scikit-learn": "scikitlearn"
}

def fetch_repos(username):
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
    return [r for r in repos if not r['fork'] and r['name'] != username]

def generate_badges_html(badges):
    html = '<div align="center">\n'
    for b in badges:
        labelColor = b.get('labelColor', '1F2335')
        img_url = f"https://img.shields.io/badge/{b['label']}-{b['message']}-{b['color']}?style=for-the-badge&logo={b['logo']}&logoColor={b['logoColor']}&labelColor={labelColor}"
        html += f'  <img src="{img_url}" />\n'
    html += '</div>'
    return html

def generate_projects_markdown(repos):
    repos.sort(key=lambda x: x['stargazers_count'], reverse=True)
    top_repos = repos[:6] # Top 6 projects
    
    md = "| Project Name | Description | Tech Stack | Stars |\n"
    md += "| :--- | :--- | :--- | :--- |\n"
    for r in top_repos:
        name = r['name']
        url = r['html_url']
        desc = r['description'] or "No description"
        lang = r['language'] or "N/A"
        stars = r['stargazers_count']
        
        md += f"| **[{name}]({url})** | {desc} | `{lang}` | ⭐ {stars} |\n"
    return md

def generate_tech_stack_html(repos, extra_icons):
    icons = set(extra_icons)
    for r in repos:
        # Extract Language
        if r['language']:
            lang_lower = r['language'].lower()
            if lang_lower in ICON_MAP:
                icons.add(ICON_MAP[lang_lower])
        # Extract Topics
        for topic in r.get('topics', []):
            topic_lower = topic.lower()
            if topic_lower in ICON_MAP:
                icons.add(ICON_MAP[topic_lower])
    
    # If no icons found, fallback to some defaults to avoid empty image
    if not icons:
        icons = {"py", "github", "git"}
        
    icon_str = ",".join(sorted(icons))
    html = '<div align="center">\n'
    html += f'  <a href="https://skillicons.dev">\n'
    html += f'    <img src="https://skillicons.dev/icons?i={icon_str}&perline=14" />\n'
    html += f'  </a>\n'
    html += '</div>'
    return html

def replace_section(content, start_marker, end_marker, new_content):
    pattern = re.compile(rf"{start_marker}.*?{end_marker}", re.DOTALL)
    replacement = f"{start_marker}\n{new_content}\n{end_marker}"
    return re.sub(pattern, replacement, content)

def main():
    with open(CONFIG_FILE, 'r') as f:
        config = json.load(f)
    
    badges_html = generate_badges_html(config.get('badges', []))
    
    github_username = "ahmednashatnoaman-svg"
    repos = fetch_repos(github_username)
    
    projects_md = generate_projects_markdown(repos)
    
    # Combine static extra icons configured by user with dynamic icons
    extra_icons = config.get('extra_icons', ["py", "cpp", "postgres", "tensorflow", "docker", "aws"])
    tech_stack_html = generate_tech_stack_html(repos, extra_icons)
    
    with open(README_FILE, 'r') as f:
        readme_content = f.read()
    
    readme_content = replace_section(readme_content, "<!-- START_BADGES -->", "<!-- END_BADGES -->", badges_html)
    readme_content = replace_section(readme_content, "<!-- START_DYNAMIC_PROJECTS -->", "<!-- END_DYNAMIC_PROJECTS -->", projects_md)
    readme_content = replace_section(readme_content, "<!-- START_TECH_STACK -->", "<!-- END_TECH_STACK -->", tech_stack_html)
    
    with open(README_FILE, 'w') as f:
        f.write(readme_content)
        
if __name__ == "__main__":
    main()

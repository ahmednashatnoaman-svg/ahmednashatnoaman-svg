import os
import json
import urllib.request
import urllib.error
import re
import time

# File paths
README_FILE = "README.md"
CONFIG_FILE = "profile_config.json"

VALID_SKILLICONS = {
    "ableton", "activitypub", "actix", "adonis", "ae", "aiscript", "alpine", "anaconda", "androidstudio",
    "angular", "ansible", "apollo", "apple", "appwrite", "arch", "arduino", "astro", "atom",
    "au", "autocad", "aws", "azul", "azure", "babel", "bash", "bevy", "bitbucket", "blender",
    "bootstrap", "bsd", "bun", "c", "cs", "cpp", "crystal", "cassandra", "clion", "clojure",
    "cloudflare", "cmake", "codepen", "coffeescript", "craftjs", "css", "cypress", "d3",
    "dart", "debian", "deno", "devto", "discord", "django", "docker", "dotnet", "dynamodb",
    "eclipse", "elasticsearch", "electron", "elixir", "elysia", "emacs", "ember", "emotion",
    "express", "fastapi", "fediverse", "figma", "firebase", "flask", "flutter", "forth", "fortran",
    "gamemakerstudio", "gatsby", "gcp", "git", "github", "githubactions", "gitlab", "gmail",
    "go", "godot", "golang", "gradle", "grafana", "graphql", "gtk", "gulp", "haskell", "haxe",
    "haxeflixel", "heroku", "hibernate", "html", "htmx", "idea", "ai", "instagram", "ipfs",
    "java", "js", "jenkins", "jest", "jquery", "julia", "kafka", "kali", "kotlin", "ktor",
    "kubernetes", "laravel", "latex", "less", "linkedin", "linux", "lit", "lua", "mac",
    "mariadb", "materialui", "matlab", "maven", "mint", "misskey", "mongodb", "mysql", "neovim",
    "nestjs", "netlify", "nextjs", "nginx", "nim", "nix", "nodejs", "notion", "npm", "nuxtjs",
    "obsidian", "ocaml", "octave", "opencv", "openshift", "openstack", "p5js", "perl", "ps",
    "php", "phpstorm", "pinia", "pkl", "plan9", "planetscale", "pnpm", "postgres", "postman",
    "powershell", "pr", "prettier", "prisma", "processing", "prometheus", "pug", "puppeteer",
    "py", "pytorch", "qt", "r", "rabbitmq", "raspberrypi", "react", "reactivex", "redhat",
    "redis", "redux", "regex", "remix", "replit", "rider", "robloxstudio", "rocket", "rollupjs",
    "ros", "ruby", "rust", "sass", "spring", "sqlite", "stackoverflow", "styledcomponents",
    "sublime", "supabase", "svelte", "svg", "swift", "symfony", "tailwind", "tauri", "tensorflow",
    "terraform", "threejs", "tiktok", "tomcat", "ts", "ubuntu", "unity", "unreal", "v",
    "vala", "vercel", "vim", "visualstudio", "vite", "vitest", "vscode", "vscodium", "vue",
    "vuetify", "wasm", "webflow", "webpack", "webstorm", "windicss", "windows", "wordpress",
    "workers", "xd", "yarn", "yew", "zig"
}

ICON_MAP = {
    "python": "py", "jupyter notebook": "py", "c++": "cpp", "c#": "cs", "javascript": "js",
    "typescript": "ts", "shell": "bash", "golang": "go", 
    "postgresql": "postgres", "amazon-web-services": "aws", "google-cloud-platform": "gcp",
    "microsoft-azure": "azure", "scikit-learn": "scikitlearn", "artificial-intelligence": "ai", 
    "machine-learning": "ai", "deep-learning": "ai"
}

CAT_LANG_DB = {"c", "cs", "cpp", "crystal", "css", "dart", "elixir", "go", "html", "java", "js", "kotlin", "lua", "nim", "php", "py", "r", "rb", "rs", "swift", "ts", "zig", "postgres", "mysql", "mongodb", "sqlite", "redis", "mariadb", "dynamodb", "cassandra", "bash", "powershell"}
CAT_AI_DATA = {"tensorflow", "pytorch", "scikitlearn", "hadoop", "spark", "aws", "gcp", "azure", "ai", "matlab", "julia", "octave", "kafka", "elasticsearch", "grafana", "prometheus"}

def fetch_github_api(url):
    headers = {}
    if "GITHUB_TOKEN" in os.environ:
        headers["Authorization"] = f"token {os.environ['GITHUB_TOKEN']}"
    
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as e:
        print(f"HTTPError on {url}: {e}")
        return None
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None

def fetch_repos(username):
    url = f"https://api.github.com/users/{username}/repos?sort=updated&per_page=100"
    repos = fetch_github_api(url)
    if not repos:
        return []
    
    # Filter out forks and profile repo
    repos = [r for r in repos if not r['fork'] and r['name'] != username]
    
    # For each repo, fetch deep languages
    for r in repos:
        lang_url = r['languages_url']
        r['all_languages'] = []
        if lang_url:
            langs = fetch_github_api(lang_url)
            if langs:
                r['all_languages'] = list(langs.keys())
        time.sleep(0.2) # small delay to prevent rate limit spikes
        
    return repos

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
        # Extract from all deep languages in the repo
        for lang in r.get('all_languages', []):
            lang_lower = lang.lower().replace(" ", "")
            if lang_lower in VALID_SKILLICONS:
                icons.add(lang_lower)
            elif lang.lower() in ICON_MAP:
                icons.add(ICON_MAP[lang.lower()])
                
        # Extract from topics
        for topic in r.get('topics', []):
            topic_lower = topic.lower().replace("-", "")
            if topic_lower in VALID_SKILLICONS:
                icons.add(topic_lower)
            elif topic.lower() in ICON_MAP:
                icons.add(ICON_MAP[topic.lower()])
    
    if not icons:
        icons = {"py", "github", "git"}
        
    core_langs = sorted([i for i in icons if i in CAT_LANG_DB])
    ai_data = sorted([i for i in icons if i in CAT_AI_DATA])
    frameworks = sorted([i for i in icons if i not in CAT_LANG_DB and i not in CAT_AI_DATA])
    
    html = '<div align="center">\n'
    if core_langs:
        html += '  <p><b>Core Languages & Databases</b></p>\n'
        html += f'  <a href="https://skillicons.dev"><img src="https://skillicons.dev/icons?i={",".join(core_langs)}&perline=14" /></a>\n'
        html += '  <br/>\n'
    if ai_data:
        html += '  <p><b>AI, Machine Learning & Big Data</b></p>\n'
        html += f'  <a href="https://skillicons.dev"><img src="https://skillicons.dev/icons?i={",".join(ai_data)}&perline=14" /></a>\n'
        html += '  <br/>\n'
    if frameworks:
        html += '  <p><b>Frameworks & Tools</b></p>\n'
        html += f'  <a href="https://skillicons.dev"><img src="https://skillicons.dev/icons?i={",".join(frameworks)}&perline=14" /></a>\n'
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

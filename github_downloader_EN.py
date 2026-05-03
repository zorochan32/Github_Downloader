"""
GitHub Folder Downloader - Final Version
Developer: ZoroChanW
GitHub: https://github.com/zorochan32
Features:
- Direct file and folder download
- Link extraction and HTML storage
- Tab-based history system
- GitHub token support
- Advanced console user interface
"""

import requests
import json
import os
import sys
import webbrowser
from pathlib import Path
from urllib.parse import urlparse
from datetime import datetime
import time
import shutil

# ============================================
# Settings and Constants
# ============================================
VERSION = "2.0 Final"
GITHUB_API_BASE = "https://api.github.com"
RAW_BASE = "https://raw.githubusercontent.com"

# ============================================
# Helper Functions
# ============================================
def print_banner():
    """Display program banner"""
    banner = f"""
    ╔════════════════════════════════════════════╗
    ║     🚀 GitHub Folder Downloader v{VERSION} 
    ║     Developed with ❤️ by ZoroChanW           
    ║        https://github.com/zorochan32       
    ║
    ╚════════════════════════════════════════════╝
    """
    print(banner)

def print_progress(current, total, prefix='', suffix='', length=50):
    """Display progress bar"""
    percent = ("{0:.1f}").format(100 * (current / float(total)))
    filled_length = int(length * current // total)
    bar = '█' * filled_length + '░' * (length - filled_length)
    print(f'\r{prefix} |{bar}| {percent}% {suffix}', end='\r')
    if current == total:
        print()

def validate_github_url(url):
    """Validate GitHub URL"""
    parsed = urlparse(url)
    if 'github.com' not in parsed.netloc:
        return False
    if '/tree/' not in parsed.path:
        return False
    return True

def parse_github_url(url):
    """
    Parse GitHub URL
    Input: https://github.com/owner/repo/tree/branch/path
    Output: (owner, repo, branch, path)
    """
    if not validate_github_url(url):
        raise ValueError("❌ Invalid GitHub folder URL!")
    
    parts = urlparse(url).path.strip('/').split('/')
    if len(parts) < 5:
        raise ValueError("❌ Invalid URL format!")
    
    return parts[0], parts[1], parts[3], '/'.join(parts[4:]) if len(parts) > 4 else ''

def get_headers(token=None):
    """Create HTTP headers"""
    headers = {
        'Accept': 'application/vnd.github.v3+json',
        'User-Agent': 'GitHub-Downloader/2.0'
    }
    if token:
        headers['Authorization'] = f'token {token}'
    return headers

def human_readable_size(size_bytes):
    """Convert bytes to human readable format"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} TB"

def create_safe_filename(filename):
    """Create safe filename"""
    unsafe_chars = '<>:"/\\|?*'
    for char in unsafe_chars:
        filename = filename.replace(char, '_')
    return filename

# ============================================
# GitHub API Main Functions
# ============================================
class GitHubDownloader:
    """Main GitHub Downloader Class"""
    
    def __init__(self, token=None):
        self.token = token
        self.headers = get_headers(token)
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        self.downloaded_files = 0
        self.failed_files = 0
        self.total_size = 0
        
    def get_api_url(self, owner, repo, branch, path=''):
        """Build API URL"""
        base = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/contents"
        if path:
            return f"{base}/{path}?ref={branch}"
        return f"{base}?ref={branch}"
    
    def get_contents(self, url):
        """Get path contents from API"""
        try:
            response = self.session.get(url)
            
            if response.status_code == 403:
                if 'rate limit exceeded' in response.text.lower():
                    print("⚠️ API rate limit exceeded! Token recommended.")
                    return None
            elif response.status_code == 404:
                print(f"❌ Path not found: {url}")
                return None
            elif response.status_code != 200:
                print(f"❌ Server error: {response.status_code}")
                return None
            
            return response.json()
        except Exception as e:
            print(f"❌ API connection error: {str(e)}")
            return None
    
    def get_all_files_recursive(self, owner, repo, branch, path='', progress_callback=None):
        """Get all files list recursively"""
        all_files = []
        api_url = self.get_api_url(owner, repo, branch, path)
        contents = self.get_contents(api_url)
        
        if not contents:
            return all_files
        
        if not isinstance(contents, list):
            return all_files
        
        for item in contents:
            if item['type'] == 'file':
                file_info = {
                    'name': item['name'],
                    'path': item['path'],
                    'url': item['download_url'],
                    'size': item['size'],
                    'type': 'file'
                }
                all_files.append(file_info)
                if progress_callback:
                    progress_callback(file_info)
                    
            elif item['type'] == 'dir':
                sub_files = self.get_all_files_recursive(
                    owner, repo, branch, item['path'], progress_callback
                )
                all_files.extend(sub_files)
        
        return all_files
    
    def download_file(self, url, local_path, callback=None):
        """Download a file with progress display"""
        try:
            response = self.session.get(url, stream=True)
            if response.status_code == 200:
                os.makedirs(os.path.dirname(local_path), exist_ok=True)
                total_size = int(response.headers.get('content-length', 0))
                downloaded = 0
                
                with open(local_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            if callback and total_size > 0:
                                callback(downloaded, total_size)
                
                self.downloaded_files += 1
                self.total_size += total_size
                return True
            else:
                self.failed_files += 1
                return False
        except Exception as e:
            self.failed_files += 1
            print(f"❌ Download error {url}: {str(e)}")
            return False

# ============================================
# HTML Functions
# ============================================
class HTMLHistoryManager:
    """HTML History Manager"""
    
    def __init__(self, html_file='github_links_history.html'):
        self.html_file = html_file
        self.tabs_data = []
        
    def create_html(self, links_data, folder_info):
        """Create or update HTML file"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        tab_id = f"tab-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        tab_data = {
            'id': tab_id,
            'folder_info': folder_info,
            'links': links_data,
            'timestamp': timestamp
        }
        
        # Read existing file
        if os.path.exists(self.html_file):
            with open(self.html_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Add new tab
            tab_button_html = self._create_tab_button(tab_data)
            tab_content_html = self._create_tab_content(tab_data)
            
            # Add to current content
            content = content.replace('<!-- TABS_HERE -->', tab_button_html + '\n            <!-- TABS_HERE -->')
            content = content.replace('<!-- CONTENTS_HERE -->', tab_content_html + '\n            <!-- CONTENTS_HERE -->')
        else:
            # Create new file
            tab_button_html = self._create_tab_button(tab_data, active=True)
            tab_content_html = self._create_tab_content(tab_data, active=True)
            content = self._get_html_template(tab_button_html, tab_content_html)
        
        # Save file
        with open(self.html_file, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return os.path.abspath(self.html_file)
    
    def _create_tab_button(self, tab_data, active=False):
        """Create tab button"""
        folder_info = tab_data['folder_info']
        label = f"{folder_info['repo']}/{folder_info['path']}" if folder_info['path'] else folder_info['repo']
        active_class = 'active' if active else ''
        return f'<button class="tab-button {active_class}" onclick="openTab(event, \'{tab_data["id"]}\')">{label}</button>'
    
    def _create_tab_content(self, tab_data, active=False):
        """Create tab content"""
        active_class = 'active' if active else ''
        folder_info = tab_data['folder_info']
        
        html = f'''
        <div id="{tab_data['id']}" class="tab-content {active_class}">
            <div class="info-box">
                <h2>📁 {folder_info['owner']}/{folder_info['repo']}</h2>
                <p>📂 Path: {folder_info['path'] if folder_info['path'] else 'Root'}</p>
                <p>🌿 Branch: {folder_info['branch']}</p>
                <p>🕒 Extracted: {tab_data['timestamp']}</p>
                <p>📊 Files: {len(tab_data['links'])}</p>
            </div>
            <div class="links-grid">
        '''
        
        for i, link in enumerate(tab_data['links'], 1):
            html += f'''
                <div class="link-card">
                    <span class="file-index">#{i}</span>
                    <div class="file-info">
                        <strong>{link['name']}</strong>
                        <small>{link['path']}</small>
                        <span class="file-size">{human_readable_size(link['size'])}</span>
                    </div>
                    <div class="file-actions">
                        <a href="{link['url']}" class="btn-download" download>⬇️ Download</a>
                        <button onclick="copyLink('{link['url']}')" class="btn-copy">📋 Copy</button>
                    </div>
                </div>
            '''
        
        html += '''
            </div>
        </div>
        '''
        return html
    
    def _get_html_template(self, tabs_html, contents_html):
        """Complete HTML template"""
        return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>📦 GitHub Downloader - Link History</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: 'Segoe UI', Tahoma; background: #0f0c29; background: linear-gradient(to right, #24243e, #302b63, #0f0c29); min-height: 100vh; padding: 20px; }}
        .container {{ max-width: 1400px; margin: 0 auto; }}
        .header {{ background: rgba(255,255,255,0.1); backdrop-filter: blur(10px); color: white; padding: 30px; border-radius: 20px; text-align: center; margin-bottom: 30px; }}
        .header h1 {{ font-size: 2.5em; margin-bottom: 10px; }}
        .tabs {{ display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 20px; }}
        .tab-button {{ padding: 12px 24px; background: rgba(255,255,255,0.1); color: white; border: none; border-radius: 10px; cursor: pointer; transition: all 0.3s; }}
        .tab-button:hover {{ background: rgba(255,255,255,0.2); }}
        .tab-button.active {{ background: #667eea; }}
        .tab-content {{ display: none; }}
        .tab-content.active {{ display: block; }}
        .info-box {{ background: rgba(255,255,255,0.1); backdrop-filter: blur(10px); color: white; padding: 20px; border-radius: 15px; margin-bottom: 20px; }}
        .links-grid {{ display: grid; gap: 15px; }}
        .link-card {{ background: rgba(255,255,255,0.95); padding: 15px; border-radius: 10px; display: flex; align-items: center; gap: 15px; transition: transform 0.2s; }}
        .link-card:hover {{ transform: translateY(-2px); box-shadow: 0 10px 20px rgba(0,0,0,0.2); }}
        .file-index {{ background: #667eea; color: white; padding: 5px 10px; border-radius: 5px; font-weight: bold; }}
        .file-info {{ flex: 1; }}
        .file-info strong {{ display: block; margin-bottom: 5px; }}
        .file-info small {{ color: #666; display: block; }}
        .file-size {{ color: #667eea; font-weight: bold; }}
        .file-actions {{ display: flex; gap: 10px; }}
        .btn-download, .btn-copy {{ padding: 8px 15px; border: none; border-radius: 5px; cursor: pointer; text-decoration: none; color: white; font-size: 14px; }}
        .btn-download {{ background: #48bb78; }}
        .btn-copy {{ background: #4299e1; }}
        .btn-download:hover {{ background: #38a169; }}
        .btn-copy:hover {{ background: #3182ce; }}
        .notification {{ position: fixed; bottom: 20px; right: 20px; background: #48bb78; color: white; padding: 15px 25px; border-radius: 10px; display: none; animation: slideIn 0.3s; z-index: 1000; }}
        @keyframes slideIn {{ from {{ transform: translateX(100%); opacity: 0; }} to {{ transform: translateX(0); opacity: 1; }} }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 GitHub Downloader History</h1>
            <p>All Your Extracted Download Links</p>
        </div>
        <div class="tabs">
            {tabs_html}
            <!-- TABS_HERE -->
        </div>
        <div class="contents">
            {contents_html}
            <!-- CONTENTS_HERE -->
        </div>
    </div>
    <div class="notification" id="notification">✅ Link Copied!</div>
    <script>
        function openTab(evt, tabId) {{
            document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-button').forEach(b => b.classList.remove('active'));
            document.getElementById(tabId).classList.add('active');
            evt.currentTarget.classList.add('active');
        }}
        function copyLink(text) {{
            navigator.clipboard.writeText(text).then(() => {{
                const n = document.getElementById('notification');
                n.style.display = 'block';
                setTimeout(() => n.style.display = 'none', 2000);
            }});
        }}
    </script>
</body>
</html>'''

# ============================================
# User Interface Functions
# ============================================
def get_token():
    """Get token from file or user"""
    token_file = 'github_token.txt'
    
    if os.path.exists(token_file):
        with open(token_file, 'r') as f:
            token = f.read().strip()
        if token:
            print("✅ Token loaded from saved file.")
            return token
    
    print("\n💡 Tip: Using a token increases API limit (5000 req/hour)")
    use_token = input("Do you want to use a token? (y/n): ").strip().lower()
    
    if use_token == 'y':
        print("\n📌 Go to the following address to create a token:")
        print("https://github.com/settings/tokens")
        print("'public_repo' access is sufficient.")
        token = input("🔑 Enter your token: ").strip()
        
        if token:
            save = input("💾 Save token for future use? (y/n): ").strip().lower()
            if save == 'y':
                with open(token_file, 'w') as f:
                    f.write(token)
                print("✅ Token saved.")
            return token
    
    return None

def show_menu():
    """Display main menu"""
    print("\n" + "═" * 50)
    print("📋 Main Menu - Select an option:")
    print("═" * 50)
    print("1. 📥 Direct Download Files & Folders")
    print("2. 🔗 Extract & Save Links in HTML")
    print("3. 📊 View Previous Download Statistics")
    print("4. 🌐 Open HTML History File")
    print("5. ❌ Exit Program")
    print("═" * 50)
    return input("🎯 Your choice: ").strip()

def download_mode(downloader):
    """Direct download mode"""
    print("\n" + "📥 " * 20)
    print("Direct File Download Mode")
    
    url = input("🔗 GitHub folder URL: ").strip()
    try:
        owner, repo, branch, path = parse_github_url(url)
    except ValueError as e:
        print(f"❌ {e}")
        return
    
    # Select save path
    default_dir = os.path.join(os.getcwd(), f"{repo}-{branch}")
    custom_dir = input(f"📁 Save path (Enter for '{default_dir}'): ").strip()
    save_dir = custom_dir if custom_dir else default_dir
    
    print(f"\n🔍 Scanning files...")
    print(f"📂 Repository: {owner}/{repo}")
    print(f"🌿 Branch: {branch}")
    print(f"📁 Path: {path if path else 'Root'}")
    
    # Get file list
    files = downloader.get_all_files_recursive(owner, repo, branch, path)
    
    if not files:
        print("❌ No files found!")
        return
    
    total_files = len(files)
    total_size = sum(f['size'] for f in files)
    
    print(f"\n📊 Summary:")
    print(f"   📄 Number of files: {total_files}")
    print(f"   💾 Total size: {human_readable_size(total_size)}")
    
    confirm = input("\n✅ Start download? (y/n): ").strip().lower()
    if confirm != 'y':
        print("❌ Download cancelled.")
        return
    
    print("\n⬇️ Starting download...")
    start_time = time.time()
    
    for i, file in enumerate(files, 1):
        relative_path = file['path']
        if path:
            relative_path = relative_path.replace(path + '/', '', 1)
        
        local_path = os.path.join(save_dir, relative_path)
        
        print(f"\n[{i}/{total_files}] 📄 {file['name']}")
        print(f"   📍 Path: {local_path}")
        print(f"   📦 Size: {human_readable_size(file['size'])}")
        
        def progress_callback(downloaded, total):
            if total > 0:
                percent = (downloaded / total) * 100
                print(f"   ⬇️ Progress: {percent:.1f}%", end='\r')
        
        success = downloader.download_file(file['url'], local_path, progress_callback)
        
        if success:
            print(f"   ✅ Download successful")
        else:
            print(f"   ❌ Download failed")
    
    elapsed_time = time.time() - start_time
    
    print("\n" + "✅ " * 20)
    print("📊 Final Download Statistics:")
    print(f"   ✅ Successful: {downloader.downloaded_files}")
    print(f"   ❌ Failed: {downloader.failed_files}")
    print(f"   ⏱️ Time: {elapsed_time:.2f} seconds")
    print(f"   💾 Downloaded size: {human_readable_size(downloader.total_size)}")

def links_mode(downloader, html_manager):
    """Link extraction mode"""
    print("\n" + "🔗 " * 20)
    print("Link Extraction & Storage Mode")
    
    url = input("🔗 GitHub folder URL: ").strip()
    try:
        owner, repo, branch, path = parse_github_url(url)
    except ValueError as e:
        print(f"❌ {e}")
        return
    
    print(f"\n🔍 Extracting links...")
    
    files = downloader.get_all_files_recursive(owner, repo, branch, path)
    
    if not files:
        print("❌ No files found!")
        return
    
    folder_info = {
        'owner': owner,
        'repo': repo,
        'branch': branch,
        'path': path
    }
    
    print(f"✅ {len(files)} links extracted.")
    
    # Save to HTML
    html_path = html_manager.create_html(files, folder_info)
    
    print(f"📄 HTML file saved: {html_path}")
    
    # Open in browser
    open_browser = input("🌐 Open HTML file in browser? (y/n): ").strip().lower()
    if open_browser == 'y':
        webbrowser.open(f'file://{html_path}')
        print("✅ File opened in browser.")

def show_stats():
    """Display HTML file statistics"""
    html_file = 'github_links_history.html'
    if os.path.exists(html_file):
        size = os.path.getsize(html_file)
        modified = datetime.fromtimestamp(os.path.getmtime(html_file))
        print(f"\n📊 History File Statistics:")
        print(f"   📄 Filename: {html_file}")
        print(f"   💾 Size: {human_readable_size(size)}")
        print(f"   🕒 Last Updated: {modified.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   📁 Full Path: {os.path.abspath(html_file)}")
    else:
        print("❌ No history file created yet.")

# ============================================
# Main Function
# ============================================
def main():
    """Main program function"""
    try:
        # Clear screen
        os.system('cls' if os.name == 'nt' else 'clear')
        
        # Display banner
        print_banner()
        
        # Get token
        token = get_token()
        
        # Create main instances
        downloader = GitHubDownloader(token)
        html_manager = HTMLHistoryManager()
        
        # Main program loop
        while True:
            choice = show_menu()
            
            if choice == '1':
                # Reset counters
                downloader.downloaded_files = 0
                downloader.failed_files = 0
                downloader.total_size = 0
                download_mode(downloader)
                
            elif choice == '2':
                links_mode(downloader, html_manager)
                
            elif choice == '3':
                show_stats()
                
            elif choice == '4':
                html_file = 'github_links_history.html'
                if os.path.exists(html_file):
                    webbrowser.open(f'file://{os.path.abspath(html_file)}')
                    print("✅ HTML file opened in browser.")
                else:
                    print("❌ HTML file does not exist.")
                    
            elif choice == '5':
                print("\n👋 Goodbye! Thanks for using the program.")
                print("💡 Note: Your files are saved in the following paths:")
                if os.path.exists('github_links_history.html'):
                    print(f"   📄 History: {os.path.abspath('github_links_history.html')}")
                if os.path.exists('github_token.txt'):
                    print(f"   🔑 Token: {os.path.abspath('github_token.txt')}")
                break
                
            else:
                print("❌ Invalid option! Please try again.")
            
            # Brief pause and screen clear for next selection
            if choice in ['1', '2', '3', '4']:
                input("\n↵ Press Enter to return to main menu...")
                os.system('cls' if os.name == 'nt' else 'clear')
                print_banner()
                
    except KeyboardInterrupt:
        print("\n\n⚠️ Program stopped by user.")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Unexpected error: {str(e)}")
        print("🔄 Please run the program again.")
        sys.exit(1)

# ============================================
# Program Entry Point
# ============================================
if __name__ == "__main__":
    main()

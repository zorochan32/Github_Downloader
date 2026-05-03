"""
GitHub Folder Downloader - نسخه نهایی
توسعه‌دهنده: Deep Seek AI
قابلیت‌ها:
- دانلود مستقیم فایل‌ها و پوشه‌ها
- استخراج و ذخیره لینک‌ها در HTML
- سیستم تاریخچه با Tab
- پشتیبانی از توکن GitHub
- رابط کاربری پیشرفته در کنسول
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
# تنظیمات و ثابت‌ها
# ============================================
VERSION = "2.0 Final"
GITHUB_API_BASE = "https://api.github.com"
RAW_BASE = "https://raw.githubusercontent.com"

# ============================================
# توابع کمکی
# ============================================
def print_banner():
    """نمایش بنر برنامه"""
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
    """نمایش نوار پیشرفت"""
    percent = ("{0:.1f}").format(100 * (current / float(total)))
    filled_length = int(length * current // total)
    bar = '█' * filled_length + '░' * (length - filled_length)
    print(f'\r{prefix} |{bar}| {percent}% {suffix}', end='\r')
    if current == total:
        print()

def validate_github_url(url):
    """اعتبارسنجی لینک گیت‌هاب"""
    parsed = urlparse(url)
    if 'github.com' not in parsed.netloc:
        return False
    if '/tree/' not in parsed.path:
        return False
    return True

def parse_github_url(url):
    """
    تجزیه URL گیت‌هاب
    ورودی: https://github.com/owner/repo/tree/branch/path
    خروجی: (owner, repo, branch, path)
    """
    if not validate_github_url(url):
        raise ValueError("❌ لینک معتبر پوشه گیت‌هاب نیست!")
    
    parts = urlparse(url).path.strip('/').split('/')
    if len(parts) < 5:
        raise ValueError("❌ فرمت لینک نادرست است!")
    
    return parts[0], parts[1], parts[3], '/'.join(parts[4:]) if len(parts) > 4 else ''

def get_headers(token=None):
    """ساخت هدرهای HTTP"""
    headers = {
        'Accept': 'application/vnd.github.v3+json',
        'User-Agent': 'GitHub-Downloader/2.0'
    }
    if token:
        headers['Authorization'] = f'token {token}'
    return headers

def human_readable_size(size_bytes):
    """تبدیل حجم به فرمت خوانا"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} TB"

def create_safe_filename(filename):
    """ایجاد نام فایل امن"""
    unsafe_chars = '<>:"/\\|?*'
    for char in unsafe_chars:
        filename = filename.replace(char, '_')
    return filename

# ============================================
# توابع اصلی GitHub API
# ============================================
class GitHubDownloader:
    """کلاس اصلی دانلودر گیت‌هاب"""
    
    def __init__(self, token=None):
        self.token = token
        self.headers = get_headers(token)
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        self.downloaded_files = 0
        self.failed_files = 0
        self.total_size = 0
        
    def get_api_url(self, owner, repo, branch, path=''):
        """ساخت URL برای API"""
        base = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/contents"
        if path:
            return f"{base}/{path}?ref={branch}"
        return f"{base}?ref={branch}"
    
    def get_contents(self, url):
        """دریافت محتوای یک مسیر از API"""
        try:
            response = self.session.get(url)
            
            if response.status_code == 403:
                if 'rate limit exceeded' in response.text.lower():
                    print("⚠️ محدودیت API! استفاده از توکن توصیه می‌شود.")
                    return None
            elif response.status_code == 404:
                print(f"❌ مسیر یافت نشد: {url}")
                return None
            elif response.status_code != 200:
                print(f"❌ خطای سرور: {response.status_code}")
                return None
            
            return response.json()
        except Exception as e:
            print(f"❌ خطا در ارتباط با API: {str(e)}")
            return None
    
    def get_all_files_recursive(self, owner, repo, branch, path='', progress_callback=None):
        """دریافت لیست تمام فایل‌ها به صورت بازگشتی"""
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
        """دانلود یک فایل با نمایش پیشرفت"""
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
            print(f"❌ خطا در دانلود {url}: {str(e)}")
            return False

# ============================================
# توابع HTML
# ============================================
class HTMLHistoryManager:
    """مدیریت تاریخچه HTML"""
    
    def __init__(self, html_file='github_links_history.html'):
        self.html_file = html_file
        self.tabs_data = []
        
    def create_html(self, links_data, folder_info):
        """ایجاد یا به‌روزرسانی فایل HTML"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        tab_id = f"tab-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        tab_data = {
            'id': tab_id,
            'folder_info': folder_info,
            'links': links_data,
            'timestamp': timestamp
        }
        
        # خواندن فایل موجود
        if os.path.exists(self.html_file):
            with open(self.html_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # اضافه کردن تب جدید
            tab_button_html = self._create_tab_button(tab_data)
            tab_content_html = self._create_tab_content(tab_data)
            
            # افزودن به محتوای فعلی
            content = content.replace('<!-- TABS_HERE -->', tab_button_html + '\n            <!-- TABS_HERE -->')
            content = content.replace('<!-- CONTENTS_HERE -->', tab_content_html + '\n            <!-- CONTENTS_HERE -->')
        else:
            # ایجاد فایل جدید
            tab_button_html = self._create_tab_button(tab_data, active=True)
            tab_content_html = self._create_tab_content(tab_data, active=True)
            content = self._get_html_template(tab_button_html, tab_content_html)
        
        # ذخیره فایل
        with open(self.html_file, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return os.path.abspath(self.html_file)
    
    def _create_tab_button(self, tab_data, active=False):
        """ایجاد دکمه تب"""
        folder_info = tab_data['folder_info']
        label = f"{folder_info['repo']}/{folder_info['path']}" if folder_info['path'] else folder_info['repo']
        active_class = 'active' if active else ''
        return f'<button class="tab-button {active_class}" onclick="openTab(event, \'{tab_data["id"]}\')">{label}</button>'
    
    def _create_tab_content(self, tab_data, active=False):
        """ایجاد محتوای تب"""
        active_class = 'active' if active else ''
        folder_info = tab_data['folder_info']
        
        html = f'''
        <div id="{tab_data['id']}" class="tab-content {active_class}">
            <div class="info-box">
                <h2>📁 {folder_info['owner']}/{folder_info['repo']}</h2>
                <p>📂 مسیر: {folder_info['path'] if folder_info['path'] else 'ریشه'}</p>
                <p>🌿 شاخه: {folder_info['branch']}</p>
                <p>🕒 تاریخ استخراج: {tab_data['timestamp']}</p>
                <p>📊 تعداد فایل‌ها: {len(tab_data['links'])}</p>
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
                        <a href="{link['url']}" class="btn-download" download>⬇️ دانلود</a>
                        <button onclick="copyLink('{link['url']}')" class="btn-copy">📋 کپی</button>
                    </div>
                </div>
            '''
        
        html += '''
            </div>
        </div>
        '''
        return html
    
    def _get_html_template(self, tabs_html, contents_html):
        """قالب کامل HTML"""
        return f'''<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>📦 GitHub Downloader - تاریخچه لینک‌ها</title>
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
        .notification {{ position: fixed; bottom: 20px; left: 20px; background: #48bb78; color: white; padding: 15px 25px; border-radius: 10px; display: none; animation: slideIn 0.3s; z-index: 1000; }}
        @keyframes slideIn {{ from {{ transform: translateX(-100%); opacity: 0; }} to {{ transform: translateX(0); opacity: 1; }} }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 GitHub Downloader History</h1>
            <p>تمام لینک‌های دانلود استخراج شده شما</p>
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
    <div class="notification" id="notification">✅ لینک کپی شد!</div>
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
# توابع رابط کاربری
# ============================================
def get_token():
    """دریافت توکن از فایل یا کاربر"""
    token_file = 'github_token.txt'
    
    if os.path.exists(token_file):
        with open(token_file, 'r') as f:
            token = f.read().strip()
        if token:
            print("✅ توکن از فایل ذخیره شده خوانده شد.")
            return token
    
    print("\n💡 نکته: استفاده از توکن محدودیت API را افزایش می‌دهد (5000 درخواست/ساعت)")
    use_token = input("آیا می‌خواهید از توکن استفاده کنید؟ (y/n): ").strip().lower()
    
    if use_token == 'y':
        print("\n📌 برای ساخت توکن به آدرس زیر بروید:")
        print("https://github.com/settings/tokens")
        print("دسترسی 'public_repo' کافی است.")
        token = input("🔑 توکن خود را وارد کنید: ").strip()
        
        if token:
            save = input("💾 توکن برای استفاده بعدی ذخیره شود؟ (y/n): ").strip().lower()
            if save == 'y':
                with open(token_file, 'w') as f:
                    f.write(token)
                print("✅ توکن ذخیره شد.")
            return token
    
    return None

def show_menu():
    """نمایش منوی اصلی"""
    print("\n" + "═" * 50)
    print("📋 منوی اصلی - یک گزینه را انتخاب کنید:")
    print("═" * 50)
    print("1. 📥 دانلود مستقیم فایل‌ها و پوشه‌ها")
    print("2. 🔗 استخراج و ذخیره لینک‌ها در HTML")
    print("3. 📊 مشاهده آمار دانلودهای قبلی")
    print("4. 🌐 باز کردن فایل تاریخچه HTML")
    print("5. ❌ خروج از برنامه")
    print("═" * 50)
    return input("🎯 انتخاب شما: ").strip()

def download_mode(downloader):
    """حالت دانلود مستقیم"""
    print("\n" + "📥 " * 20)
    print("حالت دانلود مستقیم فایل‌ها")
    
    url = input("🔗 لینک پوشه گیت‌هاب: ").strip()
    try:
        owner, repo, branch, path = parse_github_url(url)
    except ValueError as e:
        print(f"❌ {e}")
        return
    
    # انتخاب مسیر ذخیره
    default_dir = os.path.join(os.getcwd(), f"{repo}-{branch}")
    custom_dir = input(f"📁 مسیر ذخیره (Enter برای '{default_dir}'): ").strip()
    save_dir = custom_dir if custom_dir else default_dir
    
    print(f"\n🔍 در حال اسکن فایل‌ها...")
    print(f"📂 مخزن: {owner}/{repo}")
    print(f"🌿 شاخه: {branch}")
    print(f"📁 مسیر: {path if path else 'ریشه'}")
    
    # دریافت لیست فایل‌ها
    files = downloader.get_all_files_recursive(owner, repo, branch, path)
    
    if not files:
        print("❌ هیچ فایلی پیدا نشد!")
        return
    
    total_files = len(files)
    total_size = sum(f['size'] for f in files)
    
    print(f"\n📊 خلاصه:")
    print(f"   📄 تعداد فایل‌ها: {total_files}")
    print(f"   💾 حجم کل: {human_readable_size(total_size)}")
    
    confirm = input("\n✅ آیا دانلود شروع شود؟ (y/n): ").strip().lower()
    if confirm != 'y':
        print("❌ دانلود لغو شد.")
        return
    
    print("\n⬇️ شروع دانلود...")
    start_time = time.time()
    
    for i, file in enumerate(files, 1):
        relative_path = file['path']
        if path:
            relative_path = relative_path.replace(path + '/', '', 1)
        
        local_path = os.path.join(save_dir, relative_path)
        
        print(f"\n[{i}/{total_files}] 📄 {file['name']}")
        print(f"   📍 مسیر: {local_path}")
        print(f"   📦 حجم: {human_readable_size(file['size'])}")
        
        def progress_callback(downloaded, total):
            if total > 0:
                percent = (downloaded / total) * 100
                print(f"   ⬇️ پیشرفت: {percent:.1f}%", end='\r')
        
        success = downloader.download_file(file['url'], local_path, progress_callback)
        
        if success:
            print(f"   ✅ دانلود موفق")
        else:
            print(f"   ❌ دانلود ناموفق")
    
    elapsed_time = time.time() - start_time
    
    print("\n" + "✅ " * 20)
    print("📊 آمار نهایی دانلود:")
    print(f"   ✅ موفق: {downloader.downloaded_files}")
    print(f"   ❌ ناموفق: {downloader.failed_files}")
    print(f"   ⏱️ زمان: {elapsed_time:.2f} ثانیه")
    print(f"   💾 حجم دانلود شده: {human_readable_size(downloader.total_size)}")

def links_mode(downloader, html_manager):
    """حالت استخراج لینک"""
    print("\n" + "🔗 " * 20)
    print("حالت استخراج و ذخیره لینک‌ها")
    
    url = input("🔗 لینک پوشه گیت‌هاب: ").strip()
    try:
        owner, repo, branch, path = parse_github_url(url)
    except ValueError as e:
        print(f"❌ {e}")
        return
    
    print(f"\n🔍 در حال استخراج لینک‌ها...")
    
    files = downloader.get_all_files_recursive(owner, repo, branch, path)
    
    if not files:
        print("❌ هیچ فایلی پیدا نشد!")
        return
    
    folder_info = {
        'owner': owner,
        'repo': repo,
        'branch': branch,
        'path': path
    }
    
    print(f"✅ {len(files)} لینک استخراج شد.")
    
    # ذخیره در HTML
    html_path = html_manager.create_html(files, folder_info)
    
    print(f"📄 فایل HTML ذخیره شد: {html_path}")
    
    # باز کردن در مرورگر
    open_browser = input("🌐 فایل HTML در مرورگر باز شود؟ (y/n): ").strip().lower()
    if open_browser == 'y':
        webbrowser.open(f'file://{html_path}')
        print("✅ فایل در مرورگر باز شد.")

def show_stats():
    """نمایش آمار فایل HTML"""
    html_file = 'github_links_history.html'
    if os.path.exists(html_file):
        size = os.path.getsize(html_file)
        modified = datetime.fromtimestamp(os.path.getmtime(html_file))
        print(f"\n📊 آمار فایل تاریخچه:")
        print(f"   📄 نام فایل: {html_file}")
        print(f"   💾 حجم: {human_readable_size(size)}")
        print(f"   🕒 آخرین به‌روزرسانی: {modified.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   📁 مسیر کامل: {os.path.abspath(html_file)}")
    else:
        print("❌ هنوز فایل تاریخچه‌ای ایجاد نشده است.")

# ============================================
# تابع اصلی
# ============================================
def main():
    """تابع اصلی برنامه"""
    try:
        # پاکسازی صفحه
        os.system('cls' if os.name == 'nt' else 'clear')
        
        # نمایش بنر
        print_banner()
        
        # دریافت توکن
        token = get_token()
        
        # ایجاد نمونه‌های اصلی
        downloader = GitHubDownloader(token)
        html_manager = HTMLHistoryManager()
        
        # حلقه اصلی برنامه
        while True:
            choice = show_menu()
            
            if choice == '1':
                # بازنشانی شمارنده‌ها
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
                    print("✅ فایل HTML در مرورگر باز شد.")
                else:
                    print("❌ فایل HTML وجود ندارد.")
                    
            elif choice == '5':
                print("\n👋 خدانگهدار! ممنون از استفاده از برنامه.")
                print("💡 نکته: فایل‌های شما در مسیرهای زیر ذخیره شده‌اند:")
                if os.path.exists('github_links_history.html'):
                    print(f"   📄 تاریخچه: {os.path.abspath('github_links_history.html')}")
                if os.path.exists('github_token.txt'):
                    print(f"   🔑 توکن: {os.path.abspath('github_token.txt')}")
                break
                
            else:
                print("❌ گزینه نامعتبر! لطفاً دوباره تلاش کنید.")
            
            # مکث کوتاه و پاکسازی صفحه برای انتخاب بعدی
            if choice in ['1', '2', '3', '4']:
                input("\n↵ برای بازگشت به منوی اصلی Enter بزنید...")
                os.system('cls' if os.name == 'nt' else 'clear')
                print_banner()
                
    except KeyboardInterrupt:
        print("\n\n⚠️ برنامه توسط کاربر متوقف شد.")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ خطای غیرمنتظره: {str(e)}")
        print("🔄 لطفاً برنامه را مجدداً اجرا کنید.")
        sys.exit(1)

# ============================================
# نقطه شروع برنامه
# ============================================
if __name__ == "__main__":
    main()

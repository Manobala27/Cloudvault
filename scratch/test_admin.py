import os
import time
from playwright.sync_api import sync_playwright

def run_test():
    with sync_playwright() as p:
        # Launch browser headlessly
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        
        # 1. Login
        print("Navigating to login page...")
        page.goto("http://127.0.0.1:5000/login")
        
        print("Submitting login form...")
        page.fill("input[name='email']", "test_backup@example.com")
        page.fill("input[name='password']", "password")
        page.click("button[type='submit']")
        
        page.wait_for_url("http://127.0.0.1:5000/dashboard")
        print("Logged in successfully. Redirected to /dashboard.")
        
        # Admin pages to test
        admin_pages = [
            ("dashboard", "http://127.0.0.1:5000/admin/dashboard"),
            ("users", "http://127.0.0.1:5000/admin/users"),
            ("files", "http://127.0.0.1:5000/admin/files"),
            ("storage", "http://127.0.0.1:5000/admin/storage"),
            ("analytics", "http://127.0.0.1:5000/admin/analytics"),
            ("health", "http://127.0.0.1:5000/admin/health"),
            ("activity", "http://127.0.0.1:5000/admin/activity"),
            ("audit_logs", "http://127.0.0.1:5000/admin/audit_logs"),
            ("settings", "http://127.0.0.1:5000/admin/settings"),
            ("reports", "http://127.0.0.1:5000/admin/reports"),
            ("notifications", "http://127.0.0.1:5000/admin/notifications")
        ]
        
        os.makedirs("scratch/admin_screenshots", exist_ok=True)
        
        for name, url in admin_pages:
            print(f"Navigating to {url}...")
            response = page.goto(url)
            status = response.status if response else "No response"
            print(f"Response status: {status}")
            
            # Check for title/content errors
            content = page.content()
            if "Internal Server Error" in content or "500" in page.title() or status == 500:
                print(f"[ERROR] Found 500 error on page: {name}")
                # Print a bit of page source for debug
                print(content[:1000])
            elif status != 200:
                print(f"[WARNING] Non-200 status code {status} on page: {name}")
            else:
                print(f"[OK] Page '{name}' loaded successfully.")
                
            page.screenshot(path=f"scratch/admin_screenshots/{name}.png")
            
        browser.close()

if __name__ == "__main__":
    run_test()

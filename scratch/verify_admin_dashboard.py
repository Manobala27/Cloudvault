import os
import sys
import time
from playwright.sync_api import sync_playwright

def run_test():
    print("Launching browser...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        print("Navigating to login page...")
        page.goto("http://127.0.0.1:5000/login")
        print(f"Current page URL: {page.url}")
        
        # Wait for selectors and fill
        page.wait_for_selector("#email")
        page.fill("#email", "test_backup@example.com")
        page.fill("#password", "password")
        page.click("button[type='submit']")
        
        # Diagnostic wait and screenshot
        time.sleep(2)
        print(f"URL after click: {page.url}")
        page.screenshot(path="scratch/login_after_submit.png")
        
        # Wait for redirection to dashboard
        page.wait_for_url("**/dashboard", timeout=5000)
        print("Successfully logged in!")
        
        # Check if the Admin Panel sidebar link is present
        print("Checking for Admin Panel sidebar link...")
        admin_link = page.query_selector("a[href='/admin/dashboard']")
        if admin_link:
            print("[OK] Admin Panel link is visible for admin user.")
        else:
            print("[ERROR] Admin Panel link not found in sidebar!")
            browser.close()
            sys.exit(1)
            
        # Navigate to Admin Dashboard
        print("Navigating to Admin Dashboard...")
        
        def handle_response(response):
            if "admin" in response.url:
                print(f"Response: {response.url} -> Status: {response.status} {response.status_text}")
                if response.status >= 500:
                    try:
                        print("Error Page Content snippet:")
                        print(response.text()[:2000])
                    except Exception as e:
                        print(f"Could not read error page content: {e}")
                        
        page.on("response", handle_response)
        
        page.goto("http://127.0.0.1:5000/admin/dashboard")
        time.sleep(2)
        page.screenshot(path="scratch/admin_dashboard_debug.png")
        page.wait_for_selector("h2:has-text('Admin Dashboard')")
        print("[OK] Admin Dashboard loaded successfully.")
        
        # Verify Stats are present
        print("Verifying statistics card counts...")
        page.wait_for_selector(".stat-card-premium")
        print("[OK] Stats widgets rendered correctly.")
        
        # Navigate to User Management
        print("Navigating to User Management...")
        page.goto("http://127.0.0.1:5000/admin/users")
        page.wait_for_selector("h2:has-text('User Management')")
        print("[OK] User Management loaded successfully.")
        
        # Navigate to Global File Browser
        print("Navigating to Global File Browser...")
        page.goto("http://127.0.0.1:5000/admin/files")
        page.wait_for_selector("h2:has-text('Global File Browser')")
        print("[OK] Global File Browser loaded successfully.")
        
        # Navigate to Storage Management
        print("Navigating to Storage Management...")
        page.goto("http://127.0.0.1:5000/admin/storage")
        page.wait_for_selector("h2:has-text('Storage Management')")
        print("[OK] Storage Management loaded successfully.")
        
        # Navigate to System Health
        print("Navigating to System Health...")
        page.goto("http://127.0.0.1:5000/admin/health")
        page.wait_for_selector("h2:has-text('System Health')")
        print("[OK] System Health diagnostics loaded successfully.")
        
        # Navigate to Activity logs
        print("Navigating to Activity logs...")
        page.goto("http://127.0.0.1:5000/admin/activity")
        page.wait_for_selector("h2:has-text('Global Activity Monitor')")
        print("[OK] Global Activity Monitor loaded successfully.")

        # Navigate to Audit Logs
        print("Navigating to Audit Logs...")
        page.goto("http://127.0.0.1:5000/admin/audit_logs")
        page.wait_for_selector("h2:has-text('Immutable Audit Logs')")
        print("[OK] Immutable Audit Logs loaded successfully.")

        # Navigate to settings
        print("Navigating to Application Settings...")
        page.goto("http://127.0.0.1:5000/admin/settings")
        page.wait_for_selector("h2:has-text('Application Settings')")
        print("[OK] Application Settings loaded successfully.")
        
        # Navigate to reports
        print("Navigating to Report Center...")
        page.goto("http://127.0.0.1:5000/admin/reports")
        page.wait_for_selector("h2:has-text('Report Compilation Center')")
        print("[OK] Report Compilation Center loaded successfully.")
        
        # Navigate to notifications
        print("Navigating to Alert Center...")
        page.goto("http://127.0.0.1:5000/admin/notifications")
        page.wait_for_selector("h2:has-text('System Alert Center')")
        print("[OK] System Alert Center loaded successfully.")

        # Capture a screenshot of the Admin Dashboard for visual proof
        print("Capturing Admin Dashboard screenshot...")
        page.goto("http://127.0.0.1:5000/admin/dashboard")
        time.sleep(1)
        os.makedirs("scratch", exist_ok=True)
        page.screenshot(path="scratch/admin_dashboard.png", full_page=True)
        print("Screenshot saved to scratch/admin_dashboard.png")
        
        browser.close()
        print("All tests passed successfully!")

if __name__ == "__main__":
    run_test()

import sys
import os
import time
from playwright.sync_api import sync_playwright

def run_test():
    with sync_playwright() as p:
        print("Launching browser...")
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 800})
        page = context.new_page()
        
        print("Navigating to login page...")
        try:
            page.goto("http://127.0.0.1:5000/login", timeout=10000)
            print("Page loaded successfully. Title:", page.title())
        except Exception as e:
            print("Failed to load login page:", e)
            print("Current page URL:", page.url)
            browser.close()
            return
        
        print("Logging in...")
        try:
            page.fill("#email", "test_backup@example.com", timeout=5000)
            page.fill("#password", "password", timeout=5000)
            print("Form fields filled.")
        except Exception as e:
            print("Failed to fill login form fields:", e)
            print("Current page URL:", page.url)
            print("HTML content snapshot:")
            print(page.content()[:2000])
            browser.close()
            return
            
        # Click login button
        page.click("button[type='submit']")
        try:
            page.wait_for_url("**/dashboard", timeout=10000)
            print("Successfully logged in, on dashboard.")
        except Exception as e:
            print("Failed to wait for dashboard URL:", e)
            print("Current page URL:", page.url)
            page.screenshot(path="scratch/login_failure_state.png")
            browser.close()
            return
        
        # Capture initial screenshot
        os.makedirs("scratch", exist_ok=True)
        page.screenshot(path="scratch/dashboard_init.png")
        print("Captured scratch/dashboard_init.png")
        
        # Click New Folder
        print("Clicking 'New Folder' button...")
        page.click("button[data-bs-target='#createFolderModal']")
        
        # Wait for modal to be visible and stable
        page.wait_for_timeout(1000)
        page.screenshot(path="scratch/modal_open_1.png")
        print("Captured scratch/modal_open_1.png")
        
        # Type in input
        print("Typing folder name...")
        page.fill("#createFolderModal input[name='folder_name']", "Playwright Test Folder")
        
        # Click Cancel
        print("Clicking Cancel...")
        page.click("#createFolderModal button[data-bs-dismiss='modal']:has-text('Cancel')")
        
        # Wait for modal to close and backdrop to clear
        page.wait_for_timeout(1000)
        page.screenshot(path="scratch/modal_closed_1.png")
        print("Captured scratch/modal_closed_1.png")
        
        # Click New Folder again
        print("Clicking 'New Folder' button again...")
        page.click("button[data-bs-target='#createFolderModal']")
        
        page.wait_for_timeout(1000)
        page.screenshot(path="scratch/modal_open_2.png")
        print("Captured scratch/modal_open_2.png")
        
        # Type in input again
        print("Typing folder name again...")
        folder_name = f"PWTestFolder{int(time.time())}"
        page.fill("#createFolderModal input[name='folder_name']", folder_name)
        
        # Click Create Folder
        print("Clicking Create Folder...")
        page.click("#createFolderModal button[type='submit']")
        
        # Wait for dashboard reload
        page.wait_for_timeout(2000)
        page.screenshot(path="scratch/dashboard_after_create.png")
        print("Captured scratch/dashboard_after_create.png")
        
        # Verify folder exists in page content
        content = page.content()
        if folder_name in content:
            print(f"SUCCESS: Folder '{folder_name}' is visible on the dashboard!")
        else:
            print(f"FAILED: Folder '{folder_name}' was not found on the dashboard.")
            
        browser.close()

if __name__ == "__main__":
    run_test()

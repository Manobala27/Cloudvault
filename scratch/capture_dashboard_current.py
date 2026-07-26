import os
from playwright.sync_api import sync_playwright

def run_test():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 800})
        page = context.new_page()
        
        page.goto("http://127.0.0.1:5000/login")
        page.fill("input[name='email']", "test_backup@example.com")
        page.fill("input[name='password']", "password")
        page.click("button[type='submit']")
        page.wait_for_url("**/dashboard")
        
        # Navigate to /upload
        page.goto("http://127.0.0.1:5000/upload")
        page.wait_for_load_state("networkidle")
        page.screenshot(path="scratch/current_upload.png")
        print("Captured scratch/current_upload.png")
        browser.close()

if __name__ == '__main__':
    run_test()

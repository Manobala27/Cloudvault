from playwright.sync_api import sync_playwright
import os

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto("http://127.0.0.1:5000/login")
    
    page.wait_for_selector("#email")
    page.fill("#email", "test_backup@example.com")
    page.fill("#password", "password")
    page.screenshot(path="scratch/login_debug_before.png")
    
    page.click(".auth-btn-primary")
    
    try:
        page.wait_for_url("**/dashboard", timeout=5000)
        print("Success! Navigated to dashboard.")
        page.screenshot(path="scratch/login_debug_after.png")
    except Exception as e:
        print("Failed to navigate. Current URL:", page.url)
        page.screenshot(path="scratch/login_debug_failed.png")
    
    browser.close()

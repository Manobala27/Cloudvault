import os
import sys
import subprocess
from playwright.sync_api import sync_playwright

def main():
    subprocess.check_call([sys.executable, "render_dashboard.py"])
    with open("dashboard_test_rendered.html", "r", encoding="utf-8") as f:
        html = f.read()
    
    css_path = os.path.abspath("app/static/css/style.css")
    html = html.replace("/static/css/style.css", f"file:///{css_path.replace(chr(92), '/')}")
    with open("dashboard_test_rendered.html", "w", encoding="utf-8") as f:
        f.write(html)
        
    url = "file:///" + os.path.abspath("dashboard_test_rendered.html").replace('\\', '/')
    
    widths = [1920, 1366, 1024, 768, 425, 375]
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        for w in widths:
            page = browser.new_page(viewport={"width": w, "height": 800})
            page.goto(url)
            page.wait_for_load_state("networkidle")
            
            print(f"\n--- Testing at width {w}px ---")
            
            overflowing = page.evaluate('''() => {
                const overflowing = [];
                document.querySelectorAll('*').forEach(el => {
                    const rect = el.getBoundingClientRect();
                    if (rect.right > window.innerWidth || rect.left < 0) {
                        if (el.tagName.toLowerCase() !== 'html' && el.tagName.toLowerCase() !== 'body') {
                            let path = el.tagName.toLowerCase();
                            if (el.id) path += '#' + el.id;
                            if (el.className && typeof el.className === 'string') {
                                path += '.' + el.className.split(' ').join('.');
                            }
                            overflowing.push({
                                element: path,
                                right: rect.right,
                                left: rect.left,
                                width: rect.width
                            });
                        }
                    }
                });
                return overflowing;
            }''')
            
            metrics = page.evaluate('''() => {
                const docEl = document.documentElement;
                return { scrollWidth: docEl.scrollWidth, clientWidth: docEl.clientWidth, innerWidth: window.innerWidth };
            }''')
            
            print(f"Metrics: ScrollWidth={metrics['scrollWidth']}, ClientWidth={metrics['clientWidth']}")
            if overflowing:
                print("OVERFLOWING ELEMENTS:")
                for item in overflowing:
                    print(f"  - {item['element']} (Left: {item['left']}, Right: {item['right']}, Width: {item['width']})")
            else:
                if metrics['scrollWidth'] > metrics['clientWidth']:
                    print("Document overflows but no specific child element extends beyond bounds!")
                else:
                    print("No horizontal overflow.")
            
        browser.close()

if __name__ == "__main__":
    main()

import re

with open('app/static/css/style.css', 'r', encoding='utf-8') as f:
    lines = f.readlines()

hex_pattern = re.compile(r'#([0-9a-fA-F]{3,8})\b')
background_or_color = re.compile(r'\b(background|color|border)\b')

for idx, line in enumerate(lines):
    line_num = idx + 1
    # Ignore declarations inside the :root or data-bs-theme blocks (lines 1 to 100)
    if line_num <= 85:
        continue
    
    if background_or_color.search(line) and hex_pattern.search(line):
        # Ignore comments
        if '/*' in line or line.strip().startswith('/*'):
            continue
        print(f"Line {line_num}: {line.strip()}")

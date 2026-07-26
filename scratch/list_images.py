import os

for root, dirs, files in os.walk('.'):
    if 'venv' in root or '.git' in root or '.gemini' in root:
        continue
    for file in files:
        if file.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
            print(os.path.join(root, file))

import os

replacements = {
    "CharanCLI": "CharanCLI",
    "charancli": "charancli",
    "CHARANCLI": "CHARANCLI",
    "Charan CLI": "Charan CLI",
    "charan cli": "charan cli",
    "Charan": "Charan",
    "Charan": "Charan",
    "Charan": "Charan",
    "Charan": "Charan",
    "charan": "charan"
}

def process_file(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception:
        return
        
    original = content
    for k, v in replacements.items():
        content = content.replace(k, v)
        
    if content != original:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Updated {filepath}")

for root, dirs, files in os.walk(r'c:\Users\neela\Downloads\CharanCLI-master\CharanCLI-master'):
    if '.git' in root or '.charancli' in root or '__pycache__' in root:
        continue
    for file in files:
        if file.endswith(('.py', '.md', '.toml', '.txt', '.json')) and file != 'rename.py':
            process_file(os.path.join(root, file))

# Rename files
for root, dirs, files in os.walk(r'c:\Users\neela\Downloads\CharanCLI-master\CharanCLI-master', topdown=False):
    if '.git' in root or '.venv' in root or '.charancli' in root or '__pycache__' in root:
        continue
    for name in files:
        if 'charan' in name.lower():
            lower_name = name.lower()
            new_name = name.replace('CharanCLI', 'CharanCLI').replace('charancli', 'charancli').replace('CHARANCLI', 'CHARANCLI').replace('Charan', 'Charan').replace('charan', 'charan')
            if new_name != name:
                os.rename(os.path.join(root, name), os.path.join(root, new_name))
                print(f"Renamed {name} to {new_name}")

# Rename dirs
for root, dirs, files in os.walk(r'c:\Users\neela\Downloads\CharanCLI-master\CharanCLI-master', topdown=False):
    if '.git' in root or '.venv' in root or '.charancli' in root or '__pycache__' in root:
        continue
    for name in dirs:
        if 'charan' in name.lower():
            new_name = name.replace('CharanCLI', 'CharanCLI').replace('charancli', 'charancli').replace('CHARANCLI', 'CHARANCLI').replace('Charan', 'Charan').replace('charan', 'charan')
            if new_name != name:
                os.rename(os.path.join(root, name), os.path.join(root, new_name))
                print(f"Renamed directory {name} to {new_name}")

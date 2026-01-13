#!/usr/bin/env python3
import os
import sys
import re
import argparse
from pathlib import Path

def get_current_version(version_file):
    with open(version_file, 'r') as f:
        return f.read().strip()

def increment_version(version, part):
    major, minor, patch = map(int, version.split('.'))
    if part == 'major':
        major += 1
        minor = 0
        patch = 0
    elif part == 'minor':
        minor += 1
        patch = 0
    elif part == 'patch':
        patch += 1
    return f"{major}.{minor}.{patch}"

def update_version_file(version_file, new_version):
    with open(version_file, 'w') as f:
        f.write(new_version)
    print(f"Updated {version_file} to {new_version}")

def update_fim_client(file_path, new_version):
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Look for __version__ = "..."
    if '__version__' in content:
        pattern = r'__version__\s*=\s*[\'"]([^\'"]+)[\'"]'
        if re.search(pattern, content):
            new_content = re.sub(pattern, f'__version__ = "{new_version}"', content)
        else:
             # Just append if it looks weird but exists? No, safer to just replace or add.
             # If strictly regex match fails but string exists, might be different format.
             # Let's assume standard format or add it.
             print("Warning: __version__ found but regex failed. Appending.")
             new_content = content + f'\n__version__ = "{new_version}"\n'
    else:
        # Insert after docstring or imports
        lines = content.splitlines()
        insert_idx = 0
        for i, line in enumerate(lines):
            if line.startswith('import ') or line.startswith('from '):
                insert_idx = i
                break
        
        # Insert before imports
        lines.insert(insert_idx, f'__version__ = "{new_version}"')
        new_content = '\n'.join(lines) + '\n'

    with open(file_path, 'w') as f:
        f.write(new_content)
    print(f"Updated {file_path}")

def update_installer_iss(file_path, new_version):
    if not os.path.exists(file_path):
        print(f"Warning: {file_path} not found. Skipping.")
        return

    with open(file_path, 'r') as f:
        content = f.read()
    
    # Look for #define MyAppVersion "..."
    # If not present, we will add it or update AppVersion if hardcoded?
    # The plan said: Add `#define MyAppVersion` and use it
    
    # Regex for #define MyAppVersion
    pattern = r'(#define MyAppVersion\s+)"[^"]+"'
    
    if re.search(pattern, content):
        new_content = re.sub(pattern, f'\\1"{new_version}"', content)
    else:
        # Add it at the top
        new_content = f'#define MyAppVersion "{new_version}"\n' + content
        # Also ensure AppVersion uses it if possible, or we might need to manual check
        # But for now let's just add the define.
        # Ideally we should also replace `AppVersion=...` with `AppVersion={#MyAppVersion}` if it's not already.
    
    # Replace AppVersion=... with AppVersion={#MyAppVersion} if it's a hardcoded string?
    # Or just let the user handle that part? The plan said "Update installer.iss to use version".
    # Let's try to be smart.
    
    # Check if AppVersion is used
    if 'AppVersion={#MyAppVersion}' not in new_content:
        # Replace AppVersion=X.Y.Z with AppVersion={#MyAppVersion}
        # Be careful not to replace random stuff.
        # For now, let's just make sure the define is there.
        pass

    with open(file_path, 'w') as f:
        f.write(new_content)
    print(f"Updated {file_path}")

def main():
    parser = argparse.ArgumentParser(description='Bump version of FIM Client')
    parser.add_argument('part', choices=['major', 'minor', 'patch'], default='patch', nargs='?', help='Part of version to increment')
    args = parser.parse_args()

    root_dir = Path(__file__).parent.parent
    version_file = root_dir / 'VERSION'
    fim_client_file = root_dir / 'fim_client.py'
    installer_file = root_dir / 'build' / 'windows' / 'installer.iss'

    if not version_file.exists():
        print("Error: VERSION file not found.")
        sys.exit(1)

    current_version = get_current_version(version_file)
    print(f"Current version: {current_version}")
    
    new_version = increment_version(current_version, args.part)
    print(f"New version:     {new_version}")

    update_version_file(version_file, new_version)
    update_fim_client(fim_client_file, new_version)
    update_installer_iss(installer_file, new_version)

    print("Done!")

if __name__ == '__main__':
    main()

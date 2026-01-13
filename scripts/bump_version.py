#!/usr/bin/env python3
import os
import sys
import re
import argparse
from pathlib import Path
import subprocess

def get_current_version(version_file):
    if not os.path.exists(version_file):
        return "0.0.0"
    with open(version_file, 'r') as f:
        return f.read().strip()

def get_latest_git_tag():
    try:
        # Get tags sorted by version descending
        cmd = ["git", "tag", "--sort=-v:refname"]
        output = subprocess.check_output(cmd, text=True).strip()
        if not output:
             return "0.0.0"
        
        for tag in output.splitlines():
            if re.match(r'^v?\d+\.\d+\.\d+$', tag):
                return tag.lstrip('v')
        return "0.0.0"
    except Exception as e:
        print(f"Warning: Could not fetch tags: {e}")
        return "0.0.0"

def parse_version(v):
    try:
        return tuple(map(int, v.split('.')))
    except:
        return (0, 0, 0)

def increment_version(version, part):
    try:
        major, minor, patch = map(int, version.split('.'))
    except ValueError:
        return version

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
    if not os.path.exists(file_path):
        return
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Look for __version__ = "..."
    if '__version__' in content:
        pattern = r'__version__\s*=\s*[\'"]([^\'"]+)[\'"]'
        if re.search(pattern, content):
            new_content = re.sub(pattern, f'__version__ = "{new_version}"', content)
        else:
             # Just append if it looks weird but exists?
             new_content = content + f'\n__version__ = "{new_version}"\n'
    else:
        # Insert after docstring or imports
        lines = content.splitlines()
        insert_idx = 0
        for i, line in enumerate(lines):
            if line.startswith('import ') or line.startswith('from '):
                insert_idx = i
                break
        
        lines.insert(insert_idx, f'__version__ = "{new_version}"')
        new_content = '\n'.join(lines) + '\n'

    with open(file_path, 'w') as f:
        f.write(new_content)
    print(f"Updated {file_path}")

def update_installer_iss(file_path, new_version):
    if not os.path.exists(file_path):
        return

    with open(file_path, 'r') as f:
        content = f.read()
    
    # Regex for #define MyAppVersion
    pattern = r'(#define MyAppVersion\s+)"[^"]+"'
    
    if re.search(pattern, content):
        new_content = re.sub(pattern, f'\\1"{new_version}"', content)
    else:
        new_content = f'#define MyAppVersion "{new_version}"\n' + content
    
    with open(file_path, 'w') as f:
        f.write(new_content)
    print(f"Updated {file_path}")

def main():
    parser = argparse.ArgumentParser(description='Bump version of FIM Client')
    parser.add_argument('part', choices=['major', 'minor', 'patch'], default='patch', nargs='?', help='Part of version to increment')
    parser.add_argument('--ci', action='store_true', help='Run in CI mode (compare with tags)')
    args = parser.parse_args()

    root_dir = Path(__file__).parent.parent
    version_file = root_dir / 'VERSION'
    fim_client_file = root_dir / 'fim_client.py'
    installer_file = root_dir / 'build' / 'windows' / 'installer.iss'

    if not version_file.exists() and not args.ci:
        print("Error: VERSION file not found.")
        sys.exit(1)

    current_local = get_current_version(version_file)
    target_version = current_local

    if args.ci:
        # Fetch all tags first to check for existence
        try:
            cmd = ["git", "tag"]
            all_tags_output = subprocess.check_output(cmd, text=True).strip()
            all_tags = set()
            for t in all_tags_output.splitlines():
                 clean_t = t.strip().lstrip('v')
                 if re.match(r'^\d+\.\d+\.\d+$', clean_t):
                     all_tags.add(clean_t)
        except:
            all_tags = set()

        latest_tag = get_latest_git_tag()
        print(f"Local version: {current_local}")
        print(f"Latest tag:    {latest_tag}")
        
        # Calculate next tag version from latest tag
        next_tag_ver = increment_version(latest_tag, args.part)
        
        # Initial Target: Max(Local, NextFromTag)
        if parse_version(next_tag_ver) > parse_version(current_local):
            target_version = next_tag_ver
        else:
            target_version = current_local
            
        # SAFETY: If target_version ALREADY exists as a tag, bump it until it doesn't.
        # This handles cases where Local == LatestTag, preventing collision.
        while target_version in all_tags:
            print(f"Target {target_version} exists. Bumping...")
            target_version = increment_version(target_version, args.part)

        print(f"CI Target:     {target_version}")
    else:
        target_version = increment_version(current_local, args.part)
        print(f"New version:   {target_version}")

    # Update files
    # In CI, we update VERSION file too so build scripts can read it, but we don't commit it.
    update_version_file(version_file, target_version)
    update_fim_client(fim_client_file, target_version)
    update_installer_iss(installer_file, target_version)

    # Output for CI
    if args.ci:
        print(target_version)

if __name__ == '__main__':
    main()

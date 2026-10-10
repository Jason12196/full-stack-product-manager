#!/usr/bin/env python3
"""Validate the portable skill bundle without third-party dependencies."""
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import unquote
import re
import shutil
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / 'skills' / 'full-stack-product-manager'
MODULES = ('requirements-and-competitors', 'interaction-design',
           'functional-design', 'implementation-and-acceptance')


def validate(root):
    errors = []
    bundle = root / 'skills' / 'full-stack-product-manager'
    required = ['README.md', 'LICENSE', 'assets/banner.svg',
                'examples/usage.md', 'examples/AGENTS-snippet.md',
                'docs/validation.md', 'scripts/validate.py',
                'skills/full-stack-product-manager/SKILL.md',
                'skills/full-stack-product-manager/agents/openai.yaml',
                'skills/full-stack-product-manager/references/templates.md']
    required += [f'skills/full-stack-product-manager/modules/{name}/SKILL.md'
                 for name in MODULES]
    for name in required:
        if not (root / name).is_file():
            errors.append(f'Missing file: {name}')
    names = set()
    for path in root.rglob('*.md'):
        if '.git' in path.parts:
            continue
        source = path.read_text(encoding='utf-8')
        label = str(path.relative_to(root))
        if re.search(r'/Users/[^/\s]+/|/home/[^/\s]+/|[A-Za-z]:\\Users\\', source):
            errors.append(f'Personal absolute path: {label}')
        if path.name == 'SKILL.md':
            match = re.match(r'\A---\n(.*?)\n---\n', source, re.S)
            if not match:
                errors.append(f'Missing frontmatter: {label}')
                continue
            header = match.group(1)
            fields = dict(re.findall(r'^([a-z_-]+):\s*(.+)$', header, re.M))
            name = fields.get('name', '')
            if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', name) or len(name) > 64:
                errors.append(f'Invalid skill name: {label}')
            if name != path.parent.name:
                errors.append(f'Folder/name mismatch: {label}')
            if name in names:
                errors.append(f'Duplicate skill name: {name}')
            names.add(name)
            if not fields.get('description', '').strip():
                errors.append(f'Missing description: {label}')
        # Exclude fenced examples; inspect relative Markdown links and HTML media.
        prose = re.sub(r'^```[^\n]*\n.*?^```\s*$', '', source, flags=re.M | re.S)
        links = re.findall(r'\]\(([^)]+)\)', prose)
        links += re.findall(r'(?:src|href)="([^"]+)"', prose)
        for link in links:
            link = link.strip('<>')
            if re.match(r'[a-zA-Z][a-zA-Z0-9+.-]*:', link) or link.startswith('#'):
                continue
            target = unquote(link.split('#', 1)[0])
            if target and not (path.parent / target).resolve().exists():
                errors.append(f'Broken local link: {label} -> {target}')
    metadata = bundle / 'agents/openai.yaml'
    if metadata.exists():
        content = metadata.read_text(encoding='utf-8')
        if '$full-stack-product-manager' not in content:
            errors.append('Default prompt does not reference the main skill')
        if not re.search(r'^  allow_implicit_invocation: true$', content, re.M):
            errors.append('Automatic discovery policy missing')
    banner = root / 'assets/banner.svg'
    if banner.exists():
        try:
            ET.parse(banner)
        except ET.ParseError as exc:
            errors.append(f'Invalid banner SVG: {exc}')
    return errors


def installed_bundle_check(bundle):
    """Copy only installable files and prove every module remains reachable."""
    errors = []
    with TemporaryDirectory(prefix='full-stack-pm-') as temporary:
        installed = Path(temporary) / 'skills' / bundle.name
        shutil.copytree(bundle, installed)
        main = (installed / 'SKILL.md').read_text(encoding='utf-8')
        for target in re.findall(r'\]\(([^)]+)\)', main):
            if not re.match(r'[a-zA-Z][a-zA-Z0-9+.-]*:', target):
                if not (installed / target).is_file():
                    errors.append(f'Installed package missing reference: {target}')
        for name in MODULES:
            if not (installed / 'modules' / name / 'SKILL.md').is_file():
                errors.append(f'Installed module missing: {name}')
    return errors


def main():
    errors = validate(ROOT)
    if BUNDLE.is_dir():
        errors += installed_bundle_check(BUNDLE)
    if errors:
        for error in errors:
            print(f'FAIL: {error}', file=sys.stderr)
        return 1
    print('PASS: 5 skill entrypoints, metadata, local links, portable paths, SVG, isolated installation.')
    print('Boundary: this checks packaging, not model behavior or all client compatibility.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

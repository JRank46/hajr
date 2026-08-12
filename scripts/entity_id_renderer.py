#!/usr/bin/env python3
"""Render HA YAML files using a central entity ID mapping from CSV."""

import csv
import os
import re
import sys
from pathlib import Path

ENTITY_CSV = Path(__file__).parent.parent / 'helpers' / 'entity_ids.csv'
TEMPLATE_DIR = Path(__file__).parent.parent / 'templates'
OUTPUT_DIR = Path(__file__).parent.parent
PLACEHOLDER_PATTERN = re.compile(r"\{\{\s*([^\s\}]+)\s*\}\}")


def load_entity_map(csv_path):
    data = {}
    with open(csv_path, encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            key = row['key'].strip()
            entity_id = row['entity_id'].strip()
            data[key] = entity_id
    return data


def render_template(template_path, entity_map):
    text = template_path.read_text(encoding='utf-8')

    def replace(match):
        key = match.group(1)
        if key not in entity_map or not entity_map[key]:
            raise ValueError(f'Missing entity ID for key: {key}')
        return entity_map[key]

    return PLACEHOLDER_PATTERN.sub(replace, text)


def ensure_templates():
    if not TEMPLATE_DIR.exists():
        print(f'Create a templates/ directory and add template files before running this script.')
        sys.exit(1)

    templates = list(TEMPLATE_DIR.rglob('*.yaml'))
    if not templates:
        print('No template files found in templates/.')
        sys.exit(1)
    return templates


def main():
    entity_map = load_entity_map(ENTITY_CSV)
    templates = ensure_templates()
    for template_path in templates:
        rel_path = template_path.relative_to(TEMPLATE_DIR)
        print(f'Rendering {rel_path}')
        rendered = render_template(template_path, entity_map)
        output_path = OUTPUT_DIR / rel_path
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered, encoding='utf-8')
        print(f'Wrote {output_path}')

    print('Rendering complete.')


if __name__ == '__main__':
    main()

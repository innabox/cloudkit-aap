#!/usr/bin/env python3

import sys
import yaml
from pathlib import Path

# Check the actual cloudkit.yaml files
template_paths = [
    'collections/ansible_collections/cloudkit/templates/roles/ocp_4_17_small/meta/cloudkit.yaml',
    'collections/ansible_collections/cloudkit/templates/roles/ocp_4_17_small_github/meta/cloudkit.yaml',
    'collections/ansible_collections/cloudkit/templates/roles/ocp_virt_vm/meta/cloudkit.yaml'
]

for template_path in template_paths:
    print(f"\n=== {template_path} ===")
    if Path(template_path).exists():
        with open(template_path, 'r') as f:
            metadata = yaml.safe_load(f)
        print(f"template_type: {metadata.get('template_type', 'NOT SET')}")
        print(f"title: {metadata.get('title')}")
    else:
        print("FILE NOT FOUND")

# Test the metadata reading in the filter plugin
sys.path.insert(0, 'collections/ansible_collections/cloudkit/service/plugins/filter')

from find_template_roles import Collection
import json

print("\n\n=== TESTING COLLECTION METADATA READING ===")
collection = Collection(parent_path=Path('collections/ansible_collections'), name='cloudkit.templates')

for template_path in Path('collections/ansible_collections/cloudkit/templates/roles').glob('*'):
    print(f"\n--- {template_path.name} ---")
    metadata = collection.read_metadata_for_role(template_path)
    if metadata:
        print(f"metadata.template_type: {metadata.template_type}")
        print(f"metadata.title: {metadata.title}")
    else:
        print("NO METADATA")
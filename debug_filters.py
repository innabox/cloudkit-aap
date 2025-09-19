#!/usr/bin/env python3

import sys
sys.path.insert(0, 'collections/ansible_collections/cloudkit/service/plugins/filter')

from find_template_roles import find_cluster_template_roles_filter, find_vm_template_roles_filter, find_template_roles_filter

print("=== ALL TEMPLATES ===")
all_templates = find_template_roles_filter(['cloudkit.templates'])
for template in all_templates:
    print(f"ID: {template['id']}")
    print(f"Title: {template['title']}")
    print(f"Template Type: {template.get('template_type', 'NOT SET')}")
    print("---")

print("\n=== CLUSTER TEMPLATES ===")
cluster_templates = find_cluster_template_roles_filter(['cloudkit.templates'])
for template in cluster_templates:
    print(f"ID: {template['id']}")
    print(f"Title: {template['title']}")
    print("---")

print("\n=== VM TEMPLATES ===")
vm_templates = find_vm_template_roles_filter(['cloudkit.templates'])
for template in vm_templates:
    print(f"ID: {template['id']}")
    print(f"Title: {template['title']}")
    print("---")
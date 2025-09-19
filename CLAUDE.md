# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is the **Cloudkit Ansible Project** - an Ansible-based automation platform for provisioning and managing OpenShift clusters in cloud environments. It integrates with Red Hat Ansible Automation Platform (AAP) and Event-Driven Ansible (EDA) to provide configuration-as-code and automated cluster lifecycle management.

## Development Environment Setup

### Prerequisites
- Python 3.13+ (specified in pyproject.toml)
- UV package manager for dependency management

### Installation
```bash
# Install all dependencies including development tools
uv sync --all-groups

# Activate the virtual environment
source .venv/bin/activate

# Or run commands through uv
uv run ansible-playbook ...
```

### Re-vendor Ansible Collections
When updating `collections/requirements.yml`, re-vendor the collections:

```bash
# Set up Red Hat Automation Hub access
export ANSIBLE_GALAXY_SERVER_LIST=automation_hub,default
export ANSIBLE_GALAXY_SERVER_AUTOMATION_HUB_URL=https://console.redhat.com/api/automation-hub/content/published/
export ANSIBLE_GALAXY_SERVER_AUTOMATION_HUB_AUTH_URL=https://sso.redhat.com/auth/realms/redhat-external/protocol/openid-connect/token
export ANSIBLE_GALAXY_SERVER_DEFAULT_URL=https://galaxy.ansible.com/
export ANSIBLE_GALAXY_SERVER_AUTOMATION_HUB_TOKEN=<Your token>

# Re-vendor collections
rm -rf vendor
ansible-galaxy collection install -r collections/requirements.yml
```

## Common Commands

### Running Playbooks
```bash
# Main configuration playbook
uv run ansible-playbook playbook_cloudkit_config_as_code.yml

# Cluster management playbooks
uv run ansible-playbook playbook_cloudkit_create_hosted_cluster.yml
uv run ansible-playbook playbook_cloudkit_create_hosted_cluster_post_install.yml
uv run ansible-playbook playbook_cloudkit_delete_hosted_cluster.yml

# Run with ansible-navigator for debugging
ansible-navigator run playbook_name.yml
```

### Development Tools
```bash
# Lint Ansible code
uv run ansible-lint

# Generate changelogs (for collection development)
uv run antsibull-changelog
```

## Architecture Overview

### Collection Structure
The project contains three main Ansible collections:

1. **cloudkit.config_as_code** (`collections/ansible_collections/cloudkit/config_as_code/`)
   - Configures AAP instances with CloudKit-specific settings
   - Manages organizations, projects, credentials, and job templates
   - Handles license management and container groups

2. **cloudkit.service** (`collections/ansible_collections/cloudkit/service/`)
   - Core cluster lifecycle management roles
   - Infrastructure provisioning (hosted_cluster, cluster_infra)
   - Network and access management (external_access, metallb_ingress)
   - Agent management and template publishing

3. **cloudkit.templates** (`collections/ansible_collections/cloudkit/templates/`)
   - OpenShift cluster templates (currently ocp_4_17_small variants)
   - Template-specific installation, deletion, and post-install tasks
   - Template definitions include metadata in `meta/cloudkit.yaml` files

4. **massopencloud.esi** (`collections/ansible_collections/massopencloud/esi/`)
   - ESI (Elastic Secure Infrastructure) integration
   - Network management (L2/L3, floating IPs)

### Key Components

#### Event-Driven Automation
- **Rulebook**: `rulebooks/cluster_fulfillment.yml` - webhook-driven cluster operations
- Listens for create/delete cluster events and triggers appropriate workflows

#### Configuration Management
- **ansible.cfg**: Collections path configuration, timeout settings
- **ansible-navigator.yml**: Logging and artifact configuration for debugging
- **devfile.yaml**: Dev container configuration for cloud development environments

#### Infrastructure Integration
- AWS and OpenStack support through vendored collections
- Kubernetes API integration for cluster management
- Red Hat OpenShift and AAP/EDA integration

## Key Files and Directories

- `playbook_*.yml` - Main orchestration playbooks
- `collections/` - Custom Ansible collections (not vendored)
- `vendor/` - Vendored third-party collections
- `group_vars/` - Global variable definitions
- `inventory/` - Ansible inventory files
- `samples/` - Example configuration files
- `execution-environment/` - Container build configuration

## Development Notes

### Collection Development
When modifying collections under `collections/ansible_collections/cloudkit/`:
- Follow Ansible collection best practices
- Update galaxy.yml versions appropriately
- Run `ansible-lint` before committing
- Test role argument specifications in `meta/argument_specs.yaml`

### Debugging
- Use `ansible-navigator` for interactive playbook debugging
- Check logs in `.logs/` directory (created by ansible-navigator)
- Review playbook artifacts for detailed execution information

## Template System

### Template Definitions
CloudKit uses a template-based approach for cluster provisioning. Templates are Ansible roles with special metadata:

- **Template ID Format**: `cloudkit.templates.{template_name}` (e.g., `ocp.4-17.small`)
- **Template Metadata**: Defined in `meta/cloudkit.yaml` files containing:
  - `title`: Display name for the template
  - `description`: Template description
  - `default_node_request`: Default resource requirements (resourceClass, numberOfNodes)
  - `allowed_resource_classes`: Permitted resource classes for additional nodes

### Current Templates
- **ocp_4_17_small**: Basic OpenShift 4.17 cluster (2 fc430 nodes)
- **ocp_4_17_small_github**: OpenShift 4.17 with GitHub authentication

### Template Usage
Templates are referenced in cluster orders via `templateID`:
```yaml
cluster_order:
  spec:
    templateID: ocp.4-17.small
    templateParameters:
      base_domain: my.cluster
```

The `find_template_roles.py` filter plugin discovers templates by:
1. Scanning collections for roles with `meta/cloudkit.yaml` files
2. Extracting template parameters from `meta/argument_specs.yaml`
3. Converting to fulfillment service API format

### Dependencies
The project uses specific versions of key dependencies:
- Ansible 11.4.0+
- Kubernetes client 32.0.1+
- AWS/OpenStack clients for cloud provider integration
- Custom ESI client from Mass Open Cloud
- I don't have uv
- this repo runs as a podman image using ansible builder
- image builds should be tagged as quay.io/rh-ee-jkary/cloudkit-aap:latest by default.
- my kubeconfig is found at /home/jkary/labs/hcp/deploy/auth/kubeconfig
- We need to translate a VMOrder (which still needs a definition, but can be based on the sample) into an actual VM.  Just like there is a translation from Cluster/ClusterOrder to call the appropiate ansible playbooks.  For the moment the VMs should all run in a namespace called cloudkit-vms
- no VMs have cloud-init for credentials.  If a VM request does not have a cloud-init section then it should create one with a random root password to be saved to the VM order for retrieval later.
- The creation and deletion of the VMs is driven by EDA through a web hook.
- the webhooks are enabled when the cloudkit-aap container pulls changes from the GIT repo it is configured with and once ours is configured to look at quay.io/rh-ee-jkary/cloudkit-aap:feature/ocp-virt-template.
- to build an image you use the command 'ansible-builder build --tag quay.io/rh-ee-jkary/cloudkit-aap:latest -f execution_environment/executation_environment.yaml'
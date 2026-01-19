# OSAC Templates Ansible Collection

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

Base templates for OSAC (Open Sovereign AI Cloud) Fulfillment Services solution,
providing automated provisioning of OpenShift clusters and virtual machines on OpenShift
Virtualization.

## Overview

The `osac.templates` collection provides ready-to-use templates for deploying
infrastructure on OpenShift through the OSAC fulfillment service system. Templates are
defined as Ansible roles with metadata that enables self-service provisioning via the
OSAC [fulfillment service](https://github.com/innabox/fulfillment-service).

## Features

- **Cluster Templates**: Deploy complete OpenShift clusters with customizable configurations
- **VM Templates**: Provision virtual machines on OpenShift Virtualization with cloud-init support

## Installation

### From Ansible Galaxy

```bash
ansible-galaxy collection install osac.templates
```

### From Source

```bash
git clone http://github.com/innabox/osac-templates
cd osac-templates
ansible-galaxy collection build
ansible-galaxy collection install osac-templates-*.tar.gz
```

## Available Templates

### Cluster Templates

#### `ocp_4_17_small`
Minimal OpenShift 4.17 cluster configuration.

**Default Configuration:**
- 2 nodes
- Resource class: fc430
- OpenShift 4.17 release

**Required Parameters:**
- `pull_secret`: Red Hat pull secret for OpenShift installation
- `ssh_public_key`: SSH public key for node access

#### `ocp_4_17_small_github`
OpenShift 4.17 cluster with GitHub OAuth authentication pre-configured.

**Additional Parameters:**
- GitHub OAuth client credentials
- Organization/team membership configuration

### VM Templates

#### `ocp_virt_vm`
Simple virtual machine template with configurable resources and cloud-init support.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `cpu_cores` | int | 2 | Number of CPU cores |
| `memory` | string | "2Gi" | Memory allocation |
| `disk_size` | string | "10Gi" | Root disk size |
| `image_source` | string | "quay.io/containerdisks/fedora:latest" | Container disk image or PVC |
| `cloud_init_config` | string | - | Base64-encoded cloud-init user data |
| `ssh_public_key` | string | - | SSH public key for VM access |
| `exposed_ports` | string | "22/tcp" | Comma-separated ports (e.g., "22/tcp,80/tcp") |

## Usage

Templates are deployed through the OSAC fulfillment service, not directly via
ansible-playbook. The OSAC orchestrator handles template selection, parameter
validation, and lifecycle management.

## Template Development

### Creating a New Cluster Template

1. Create a new role directory under `roles/`:
   ```bash
   mkdir -p roles/my_cluster_template/{tasks,defaults,meta}
   ```

2. Define template metadata in `roles/my_cluster_template/meta/cloudkit.yaml`:
   ```yaml
   title: My Cluster Template
   description: Description of what this template provides
   default_node_request:
   - resourceClass: fc430
     numberOfNodes: 2
   allowed_resource_classes: []
   ```

3. Define parameters in `roles/my_cluster_template/meta/argument_specs.yaml`:
   ```yaml
   argument_specs:
     main:
       options:
         template_parameters:
           type: dict
           options:
             my_param:
               description: Parameter description
               type: str
               required: true
   ```

4. Implement provisioning tasks in `roles/my_cluster_template/tasks/install.yaml`
5. Implement cleanup tasks in `roles/my_cluster_template/tasks/delete.yaml`

### Creating a New VM Template

1. Create role structure as above
2. Set `template_type: vm` in `meta/cloudkit.yaml`
3. Use `create.yaml` and `delete.yaml` instead of `install.yaml`
4. Implement VM creation using `kubernetes.core.k8s` modules

## Architecture

Templates integrate with OSAC through a well-defined interface:

### Cluster Template Lifecycle
1. OSAC creates a dedicated namespace for the cluster
2. Template receives `cluster_order` and `template_parameters` variables
3. OSAC delegates to template id role for provisioning
4. OSAC monitors cluster status and provides kubeconfig access
5. On deletion, template cleans up all resources

### ComputeInstance Template Lifecycle
1. OSAC creates a dedicated namespace for the ComputeInstance
2. OSAC receives `compute_instance` and `template_parameters` variables
3. OSAC delegeates to template id role for provisioning
4. OSAC assigns floating IP and configures port forwarding
5. On deletion, template removes all resources in order

## Dependencies

### Runtime Dependencies
- `cloudkit.service` collection (for cluster templates)
- `kubernetes.core` collection (for VM templates)
- `massopencloud.esi` collection (for floating IP management)

### Environment Requirements
- OpenShift 4.x cluster with cluster-admin access
- OpenShift Virtualization operator (for VM templates)
- OSAC orchestrator and fulfillment service

## Contributing

Contributions are welcome! Please ensure all templates:
- Include comprehensive `meta/cloudkit.yaml` metadata
- Define all parameters in `meta/argument_specs.yaml`
- Implement both create and delete operations
- Follow Ansible best practices
- Include descriptive variable names and comments

## License

Apache License 2.0 - See [LICENSE](LICENSE) for details.

## Support

- **Issues**: http://github.com/innabox/issues/issues
- **Documentation**: http://github.com/innabox/osac-templates/README.md
- **Repository**: http://github.com/innabox/osac-templates

## Author

Jason Kary <jkary@redhat.com>

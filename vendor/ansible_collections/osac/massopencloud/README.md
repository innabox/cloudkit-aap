# osac.massopencloud

An Ansible collection providing OSAC templates for deploying infrastructure on the Mass Open Cloud (MOC). This collection contains roles for provisioning OpenShift clusters and virtual machines using the OSAC platform.

## Overview

The `osac.massopencloud` collection provides pre-configured templates that simplify the deployment of:
- **OpenShift Clusters**: Hosted OpenShift 4.17 clusters with optional GitHub OAuth integration
- **Virtual Machines**: VMs running on OpenShift Virtualization with automated networking and floating IP allocation

These templates are designed to work with the OSAC service infrastructure on the Mass Open Cloud platform.

## Requirements

- Ansible >= 2.15.0
- Access to a OSAC-enabled OpenShift environment
- Required Ansible collections:
  - `osac.templates`
  - `cloudkit.service`
  - `massopencloud.esi`
  - `kubernetes.core`

## Installation

Install the collection from Ansible Galaxy:

```bash
ansible-galaxy collection install osac.massopencloud
```

Or build and install from source:

```bash
ansible-galaxy collection build
ansible-galaxy collection install osac-massopencloud-*.tar.gz
```

## Available Roles

### ocp_virt_vm

Deploy virtual machines on OpenShift Virtualization with automated floating IP allocation and port forwarding.

**Key Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `cpu_cores` | int | 2 | Number of CPU cores for the VM |
| `memory` | str | 2Gi | Amount of memory for the VM |
| `disk_size` | str | 10Gi | Size of the VM root disk |
| `image_source` | str | quay.io/containerdisks/fedora:latest | Container disk image or PVC reference |
| `ssh_public_key` | str | - | Comma-separated list of SSH public keys |
| `exposed_ports` | str | 22/tcp | Ports to expose (format: `22/tcp,80/tcp`) |
| `cloud_init_config` | str | - | Base64-encoded cloud-init configuration |

**Example Usage:**

```yaml
- name: Deploy a virtual machine
  hosts: localhost
  tasks:
    - name: Create ComputeInstance
      ansible.builtin.include_role:
        name: osac.massopencloud.ocp_virt_vm
        tasks_from: create
      vars:
        compute_instance_order:
          metadata:
            name: my-vm
            namespace: default
        template_parameters:
          cpu_cores: 4
          memory: 4Gi
          disk_size: 20Gi
          ssh_public_key: "ssh-rsa AAAA..."
          exposed_ports: "22/tcp,80/tcp,443/tcp"
```

### ocp_4_17_small

Deploy a minimal OpenShift 4.17 cluster using the OSAC hosted cluster infrastructure.

**Key Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `pull_secret` | str | Yes | Credentials for authenticating to image repositories |
| `ssh_public_key` | str | No | SSH public key for cluster node access |

**Example Usage:**

```yaml
- name: Deploy OpenShift cluster
  hosts: localhost
  tasks:
    - name: Install cluster
      ansible.builtin.include_role:
        name: osac.massopencloud.ocp_4_17_small
        tasks_from: install
      vars:
        cluster_order:
          metadata:
            name: my-cluster
          spec:
            nodeRequests:
              - resourceClass: fc430
                numberOfNodes: 2
        cluster_working_namespace: clusters
        template_parameters:
          pull_secret: "{{ lookup('file', 'pull-secret.json') }}"
          ssh_public_key: "ssh-rsa AAAA..."
```

### ocp_4_17_small_github

Deploy an OpenShift 4.17 cluster with GitHub OAuth authentication pre-configured.

**Additional Parameters (beyond ocp_4_17_small):**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `github_client_id` | str | Yes | GitHub OAuth application client ID |
| `github_client_secret` | str | Yes | GitHub OAuth application client secret |
| `github_teams` | list | No | GitHub teams allowed to authenticate |
| `github_organizations` | list | No | GitHub organizations allowed to authenticate |
| `github_mapping_method` | str | No | Identity mapping method (claim/lookup/add) |

**Example Usage:**

```yaml
- name: Deploy cluster with GitHub OAuth
  hosts: localhost
  tasks:
    - name: Install cluster
      ansible.builtin.include_role:
        name: osac.massopencloud.ocp_4_17_small_github
        tasks_from: install
      vars:
        cluster_order:
          metadata:
            name: my-cluster
          spec:
            nodeRequests:
              - resourceClass: fc430
                numberOfNodes: 2
        cluster_working_namespace: clusters
        template_parameters:
          pull_secret: "{{ lookup('file', 'pull-secret.json') }}"
          ssh_public_key: "ssh-rsa AAAA..."
          github_client_id: "your-client-id"
          github_client_secret: "your-client-secret"
          github_organizations:
            - your-org-name
          github_mapping_method: claim
```

## Development

### Pre-commit Hooks

This repository uses pre-commit hooks for code quality. Install and run them before committing:

```bash
# Install pre-commit hooks
pre-commit install

# Run all checks
pre-commit run --all-files
```

### Building the Collection

```bash
# Build collection tarball
ansible-galaxy collection build

# Install locally for testing
ansible-galaxy collection install -p .ansible/collections/ osac-massopencloud-*.tar.gz --force
```

## Documentation

Detailed parameter documentation for each role is available in the respective `meta/argument_specs.yaml` files:
- [ocp_virt_vm parameters](roles/ocp_virt_vm/meta/argument_specs.yaml)
- [ocp_4_17_small parameters](roles/ocp_4_17_small/meta/argument_specs.yaml)
- [ocp_4_17_small_github parameters](roles/ocp_4_17_small_github/meta/argument_specs.yaml)

## License

Apache-2.0

See [LICENSE](LICENSE) for full license text.

## Links

- **Repository**: http://github.com/innabox/osac-massopencloud-templates
- **Issues**: http://github.com/innabox/issues/issues
- **Documentation**: http://github.com/innabox/osac-massopencloud-templates/README.md

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run pre-commit checks: `pre-commit run --all-files`
5. Submit a pull request

All pull requests are automatically validated using GitHub Actions.

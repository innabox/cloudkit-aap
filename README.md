# Cloudkit Ansible Project

This repository contains the Ansible roles, playbooks, rulebooks, and
inventories that are used in the scope of cloudkit.

## Pre-requisites

This project uses uv to install Ansible and other Python dependencies.

Install all the necessary dependencies by running:

```
uv sync --all-groups
```

Then you can run commands like this:

```
uv run ansible-playbook ...
```

Or you can activate the virtual environment so all commands are in your `$PATH` by default:

```
source .venv/bin/activate
```

## Re-vendor Ansible collections

This repository explicitly vendors the Ansible collections that are used as
dependencies, they are located in `vendor/` directory. You'll need
to re-vendor them after an update of `collections/requirements.yaml`.

First set your environment in order to be able to pull some of the collections
available only in Red Hat Automation Hub:

```
export ANSIBLE_GALAXY_SERVER_LIST=automation_hub,default
export ANSIBLE_GALAXY_SERVER_AUTOMATION_HUB_URL=https://console.redhat.com/api/automation-hub/content/published/
export ANSIBLE_GALAXY_SERVER_AUTOMATION_HUB_AUTH_URL=https://sso.redhat.com/auth/realms/redhat-external/protocol/openid-connect/token
export ANSIBLE_GALAXY_SERVER_DEFAULT_URL=https://galaxy.ansible.com/
export ANSIBLE_GALAXY_SERVER_AUTOMATION_HUB_TOKEN=<Get your token from https://console.redhat.com/ansible/automation-hub/token>
```

Then re-vendor the collections:

```
rm -rf vendor
ansible-galaxy collection install -r collections/requirements.yml
```

## Development Tools

### Pre-commit Hooks

This repository uses pre-commit hooks to ensure code quality. Install them with:

```bash
pre-commit install
```

### Optional: Ansible Lint Pre-push Hook

While `ansible-lint` runs automatically in CI on pull requests, you can optionally run it locally before pushing. Since ansible-lint can be slow and generate verbose output, it's recommended to run it as a pre-push hook rather than on every commit.

To set up a local pre-push hook for ansible-lint:

1. Create `.git/hooks/pre-push`:

```bash
#!/bin/bash
echo "Running ansible-lint..."
uv run ansible-lint
```

2. Make it executable:

```bash
chmod +x .git/hooks/pre-push
```

This will run ansible-lint before each `git push`, catching issues before they reach CI.

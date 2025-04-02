# Cloudkit Ansible Project

This repository contains the Ansible roles, playbooks, rulebooks, and
inventories that are used in the scope of cloudkit.

## Pre-requisites

This project uses uv to manages install Ansible and the required dependencies:

```
$ uv sync
$ source .venv/bin/activate
```

Then install the Ansible collections required by CloudKit Ansible playbooks:

```
$ ansible-galaxy collection install -r collections/requirements.yml
```
# Cloudkit Ansible Project

This repository contains the Ansible roles, playbooks, rulebooks, and
inventories that are used in the scope of cloudkit.

## Pre-requisites

This project uses uv to install Ansible and other Python dependencies:

```
$ uv sync
$ source .venv/bin/activate
```

Then install the Ansible collections required by the Ansible playbooks:

```
$ ansible-galaxy collection install -r collections/requirements.yml
```

# Ansible Collection - isaiahstapleton.ai_cluster_ansible

Documentation for the collection.

## Purpose

The purpose of this repo is to be able to automate the installation and configuration of all the components required to do model serving and run AI workloads on Red Hat OpenShift AI.  


## Configuration Components that are Installed

- ***Node Feature Discovery (NFD) Operator:*** Detects and labels nodes based on hardware capabilities for proper AI workload scheduling.
- ***NVIDIA GPU Operator:*** Automates deployment of GPU drivers, CUDA libraries, and dependencies for AI workloads.
- ***OpenShift Service Mesh Operator:*** Provides Istio for managing secure communication between model-serving components.
- ***Red Hat OpenShift Serverless Operator:*** Provides Knative Serving for scalable and event-driven AI model deployment.
- ***Red Hat Authorino Operator:*** Provides authentication and authorization for secure access to AI model endpoints.
- ***Red Hat OpenShift AI Operator:*** Manages and deploys AI components and services within OpenShift.
- ***IBM Autopilot:*** Provides health checks for your AI cluster.

## Workload Components that are Deployed

- ***Minio S3 Storage:*** Provides object storage for your models. A randomized sername and password to minio instance is created, a data connection is set up in RHOAI, and a bucket is created.
- ***AI Model - granite-3.1-2b-instruct-quantized:*** The AI Model that will be deployed. It is automatically uploaded into the bucket created in the minio setup.
- ***vLLM ServingRuntime:*** Used as the ServingRuntime for the deployed Granite Model
- ***llm-load-test-exporter:*** The purpose of this program is to run llm-load-test application and then serve the resulting metrics to a /metrics endpoint. This is used for running a benchmark against the deployed Granite model and serving the performance metrics for prometheus to collect 


## How to Use

There are different playbooks:
- **configure_cluster_and_deploy_workloads**: Will install and deploy everything needed for doing model serving and running AI workloads in the cluster. Including deploying the workloads themselves.
- **configure_cluster**: Configures the cluster to be able to run AI workloads and deploy models.
- **deploy_workloads**: Deploys the AI workloads, cluster must be configured to do so.
- **uninstall_config_and_workloads**: Uninstalls the ai cluster configuration and the ai workloads.
- **uninstall_cluster_config**: Uninstalls the AI cluster configuration
Uninstall_workloads: Uninstalls the ai workloads
- **uninstall_workloads**: Uninstalls the ai workloads


### Prerequisites

You will need to have the `kubernetes` and `ansible` packages installed. You can do this by running the following command from the root directory:

```
pip install -r requirements.txt
```

### Run playbooks

From the root directory, run the following command to run a playbook:

```
ansible-playbook [playbook].yaml
```

For example, to run the `configure-cluster-and-deploy-workloads` playbook, execute the following command:

```
ansible-playbook configure-cluster-and-deploy-workloads.yaml
```

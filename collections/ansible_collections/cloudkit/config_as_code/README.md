# Ansible Collection - cloudkit.config_as_code

This role defines the configuration as code of AAP to run the Ansible playbooks
that are part of CloudKit.

## Credentials

Since AAP runs in an OpenShift cluster, we expect the required credentials to
be passed as environment variables. These environment variables are defined as
`Secrets` in OpenShift, and used by a container group.

We define 2 container groups in AAP, one used to reconcile the configuration of
AAP itself, and one used for cluster fulfillment operations.

### Config-as-code environment variables

In order to reconcile the configuration of AAP, we require the following
variables:

- `RH_USERNAME` and `RH_PASSWORD`: your Red Hat console username and password,
  used to manage the subscription of AAP
- `AAP_HOSTNAME`: URL of the AAP instance to be configured
- `AAP_VALIDATE_CERTS`: true if the SSL certificate behind `AAP_HOSTNAME`
  should be checked
- `AAP_ORGANIZATION_NAME`: the AAP organization that should be created
- `AAP_PROJECT_NAME`: the name of the project to be created
- `AAP_PROJECT_GIT_URI`: the repository that is behind the AAP project
- `AAP_PROJECT_GIT_BRANCH`: the git branch to use
- `AAP_EE_IMAGE`: the registry URL to the execution environment image

These variables must be defined in a secret named:
`${AAP_ORGANIZATION_NAME}-${AAP_PROJECT_NAME}-config-as-code-ig` in the
namespace where AAP is deployed.

Note: since the container group is configured to run in the same namespace as
the AAP instance, the admin credentials to log against AAP are injected into
the pod.

### Cluster fulfillment environment variables

Here we need to define all the credentials required by the cluster fulfillment
use case, e.g.:

- `AWS_*`: AWS credentials
- `OS_*`: OpenStack credentials
- ...whatever in needed

These variables must be defined in a secret named:
`${AAP_ORGANIZATION_NAME}-${AAP_PROJECT_NAME}-cluster-fulfillment-ig` in the
namespace where AAP is deployed.

The cluster fulfillment needs to access the Kube API of the cluster it runs on,
so we expect a service account `cloudkit-sa` to exists with enough rights (TBD).

## Deploy a local AAP installation using CRC

### Download and deploy CRC

CRC is basically OpenShift in a VM, you can download it from Red Hat Console:
https://console.redhat.com/openshift/downloads. You will need `oc` which is
downloadable from the same place.

Extract the package, put the binary in your path, start the cluster, and log as
`kubeadmin`:

```
crc start
oc login -u kubeadmin  https://api.crc.testing:6443
```

## Install AAP

Install the AAP operator (more information
[here](https://docs.redhat.com/en/documentation/red_hat_ansible_automation_platform/2.5/html/installing_on_openshift_container_platform/installing-aap-operator-cli_operator-platform-doc#install-cli-aap-operator_installing-aap-operator-cli)):

```
cat << EOF > aap_install.yml
---
apiVersion: v1
kind: Namespace
metadata:
  labels:
    openshift.io/cluster-monitoring: "true"
  name: aap
---
apiVersion: operators.coreos.com/v1
kind: OperatorGroup
metadata:
  name: ansible-automation-platform-operator
  namespace: aap
spec:
  targetNamespaces:
    - aap
---
apiVersion: operators.coreos.com/v1alpha1
kind: Subscription
metadata:
  name: ansible-automation-platform
  namespace: aap
spec:
  channel: 'stable-2.5-cluster-scoped'
  installPlanApproval: Automatic
  name: ansible-automation-platform-operator
  source: redhat-operators
  sourceNamespace: openshift-marketplace
EOF

oc apply -f aap_install.yml
```

### Deploy AAP

Create a new namespace and deploy an AAP instance using these manifests:

```
cat << EOF > aap.yml
---
apiVersion: v1
kind: Namespace
metadata:
  labels:
    openshift.io/cluster-monitoring: "true"
  name: fulfillment-aap
---
apiVersion: aap.ansible.com/v1alpha1
kind: AnsibleAutomationPlatform
metadata:
  name: fulfillment
  namespace: fulfillment-aap
spec:
  image_pull_policy: IfNotPresent
  controller:
    disabled: false
  eda:
    disabled: false
  hub:
    disabled: true
  lightspeed:
    disabled: true
EOF

oc apply -f aap.yml
```

### Apply CloudKit configuration on AAP instance

#### Prepare OpenShift environment

Create service account and secrets:

```
cat << EOF > cloudkit_env.yml
---
apiVersion: v1
kind: ServiceAccount
metadata:
  name: cloudkit-sa
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: cloudkit-sa
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: cluster-admin
subjects:
  - kind: ServiceAccount
    name: cloudkit-sa
    namespace: fulfillment-aap
---
apiVersion: v1
kind: Secret
metadata:
  name: <your AAP organization>-<your AAP project>-config-as-code-ig
type: Opaque
stringData:
  RH_USERNAME: <your Red Hat username>
  RH_PASSWORD: <your Red Hat password>
  AAP_HOSTNAME: https://fulfillment-fulfillment-aap.apps-crc.testing
  AAP_USERNAME: admin
  AAP_PASSWORD: $(oc get secret/fulfillment-admin-password -n fulfillment-aap -o go-template='{{index .data "password" | base64decode}}')
  AAP_VALIDATE_CERTS: false
  AAP_ORGANIZATION_NAME: <the organization name to be created in AAP>
  AAP_PROJECT_NAME: <the project name to be create in AAP>
  AAP_PROJECT_GIT_URI: <the git repository where your playbooks and rulebooks live>
  AAP_PROJECT_GIT_BRANCH: <the git branch to be tracked>
  AAP_EE_IMAGE: <the execution environment image>
---
apiVersion: v1
kind: Secret
metadata:
  name: <your AAP organization>-<your AAP project>-cluster-fulfillment-ig
type: Opaque
stringData:
  <setup here the credentials required for cluster fulfillment playbooks (AWS, OpenStack, ...)>
EOF

oc apply -f cloudkit_env.yml -n fulfillment-aap
```

#### Option 1: from your local environment

Set your environment (same as above in `<your AAP organization>-<your AAP
project>-config-as-code-ig` secret):

```
export RH_USERNAME=...
export RH_PASSWORD=...
export AAP_HOSTNAME=...
export AAP_USERNAME=...
export AAP_PASSWORD=...
export AAP_VALIDATE_CERTS=...
export AAP_ORGANIZATION_NAME=...
export AAP_PROJECT_NAME=...
export AAP_PROJECT_GIT_URI=...
export AAP_PROJECT_GIT_BRANCH=...
export AAP_EE_IMAGE=...
```

Run subscription and configure playbooks:
```
ansible-playbook cloudkit.config_as_code.subscription
ansible-playbook cloudkit.config_as_code.configure
```

#### Option 2: as a job running in Kubernetes

If this collection is being used in a container image (e.g.: in the custom
execution environment used in AAP), there is the possibility to run the
configuration in a k8s job:

```
cat << EOF > job.yml
apiVersion: batch/v1
kind: Job
metadata:
  name: aap-bootstrap
spec:
  template:
    spec:
      containers:
        - image: <your container image with cloudkit.config_as_code collection in it>
          name: bootstrap
          args:
            - ansible-playbook
            - "cloudkit.config_as_code.subscription"
            - "cloudkit.config_as_code.configure"
          envFrom:
            - secretRef:
                name: <your AAP organization>-<your AAP project>-config-as-code-ig
          env:
            - name: AAP_USERNAME
              value: admin
            - name: AAP_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: fulfillment-admin-password
                  key: password
      restartPolicy: Never
  backoffLimit: 4
EOF

oc apply -f job.yml -n fulfillment-aap
```

# Ansible Collection - cloudkit.config_as_code

This role defines the configuration as code of AAP to run the Ansible playbooks
that are part of CloudKit.

## Credentials

Since AAP runs in an OpenShift cluster, we expect the required credentials to
be passed as environment variables. These environment variables are defined as
`Secrets` in OpenShift, and used by a container group.

We define 2 container groups in AAP, one used to reconcile the configuration of
AAP itself, and one used for cluster fulfillment operations.

### Config-as-code var file

Config-as-code relies on an Ansible var file, this file is specified using
`CONFIG_AS_CODE_EXTRA_VARS_PATH` environment variable.

In order to reconcile the configuration of AAP, we require the following
variables to be defined in the Ansible var file:

- `aap_hostname`, `aap_username`, and `aap_password`: URL and admin credentials
  of the aap instance to be configured
- `aap_validate_certs`: true if the SSL certificate behind `aap_hostname`
  should be checked
- `aap_organization_name`: the AAP organization that should be created
- `aap_project_name`: the name of the project to be created
- `aap_project_git_uri`: the repository that is behind the AAP project
- `aap_project_git_branch`: the git branch to use
- `aap_ee_image`: the registry URL to the execution environment image
- `license_manifest_path`: path to the license manifest file in order to
  register the AAP instance, your can allocate one from your
  [Red Hat account](https://access.redhat.com/management/subscription_allocations)

These variables must be defined in a secret named:
`{{ aap_organization_name }}-{{ aap_project_name }}-config-as-code-ig` in the
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
`{{ aap_organization_name }}-{{ aap_project_name }}-cluster-fulfillment-ig` in the
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

As described above, setup your Red Hat subscription and download the zipped
manifest, then create an Ansible variable file with your settings, and create a
secret in the cluster that contains these files:

```
cat << EOF > vars.yaml
---
aap_hostname: ...
aap_username: "{{ lookup('env', 'AAP_USERNAME') }}"
aap_password: "{{ lookup('env', 'AAP_PASSWORD') }}"
aap_organization_name: ...
aap_project_name: ...
aap_project_git_uri: ...
aap_project_git_branch: ...
aap_ee_image: ...
aap_validate_certs: ...
license_manifest_path: "{{ lookup('env', 'LICENSE_MANIFEST_PATH') }}"
EOF

oc create secret generic <your AAP organization>-<your AAP project>-config-as-code-ig --from-file=vars.yaml=vars.yaml --from-file=license.zip=/path/to/license.zip`
```

To perform fulfillment operations (create, update and delete clusters), you
need to setup a service account that has sufficient rights in the OpenShift
cluster:

```
cat << EOF > cloudkit_sa.yaml
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
EOF

oc apply -f cloudkit_sa.yaml -n fulfillment-aap
```

Finally, create a secret that pass extra environment variables required for the fulfillment
operations, such as AWS and OpenStack credentials:
```
cat < EOF > fulfillment_creds
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=...
OS_AUTH_URL=...
OS_PROJECT_NAME=...
...
EOF

oc create secret generic <your AAP organization>-<your AAP project>-cluster-fulfillment-ig --from-env-file=fufillment_creds`
```

#### Configure AAP

`config-as-code` collection is embedded into the Ansible execution environment
provided as part of this repo, we can use it to trigger the initial
configuration of AAP:

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
        - image: ghcr.io/innabox/cloudkit-aap:latest
          name: bootstrap
          args:
            - ansible-playbook
            - "cloudkit.config_as_code.subscription"
            - "cloudkit.config_as_code.configure"
          volumeMounts:
            - name: config-as-code-volume
              mountPath: /var/secrets/config-as-code
              readOnly: true
          env:
            - name: AAP_USERNAME
              value: admin
            - name: AAP_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: fulfillment-admin-password
                  key: password
            - name: CONFIG_AS_CODE_EXTRA_VARS_PATH
              value: /var/secrets/config-as-code/vars.yaml
            - name: LICENSE_MANIFEST_PATH
              value: /var/secrets/config-as-code/license.zip
      volumes:
        - name: config-as-code-volume
          secret:
            secretName: <your AAP organization>-<your AAP project>-config-as-code-ig
      restartPolicy: Never
  backoffLimit: 4
EOF

oc apply -f job.yml -n fulfillment-aap
```

If you updated `config-as-code` collection or want to use your own Ansible
execution environment, follow this
[readme](https://github.com/innabox/cloudkit-aap/blob/main/execution-environment/README.md).

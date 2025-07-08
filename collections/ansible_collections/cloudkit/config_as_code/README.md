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

- `AAP_HOSTNAME`: URL of the AAP instance to be configured
- `AAP_VALIDATE_CERTS`: true if the SSL certificate behind `AAP_HOSTNAME`
  should be checked
- `AAP_ORGANIZATION_NAME`: the AAP organization that should be created
- `AAP_PROJECT_NAME`: the name of the project to be created
- `AAP_PROJECT_GIT_URI`: the repository that is behind the AAP project
- `AAP_PROJECT_GIT_BRANCH`: the git branch to use
- `AAP_EE_IMAGE`: the registry URL to the execution environment image
- `LICENSE_MANIFEST_PATH`: path to the license manifest file in order to
  register the AAP instance, your can allocate one from your [Red Hat
  account](https://access.redhat.com/management/subscription_allocations)

These variables must be defined in a secret named
`${AAP_ORGANIZATION_NAME}-${AAP_PROJECT_NAME}-config-as-code-ig` in the
namespace where AAP is deployed.

The content of license manifest file must be set in a secret named
`${AAP_ORGANIZATION_NAME}-${AAP_PROJECT_NAME}-config-as-code-manifest-ig` as
`license.zip` in the namespace where AAP is deployed.

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

#### Config-as-code configauration

Create the secrets required for the configuration of AAP:

```
cat << EOF > config-as-code
AAP_HOSTNAME=<your AAP hostname>
AAP_VALIDATE_CERTS=true
AAP_ORGANIZATION_NAME=<the organization name to be created in AAP>
AAP_PROJECT_NAME=<the project name to be create in AAP>
AAP_PROJECT_GIT_URI=<the git repository where your playbooks and rulebooks live>
AAP_PROJECT_GIT_BRANCH=<the git branch to be tracked>
AAP_EE_IMAGE=<the execution environment image>
EOF

oc apply -f config-as-code -n fulfillment-aap
oc create secret generic <your AAP organization>-<your AAP project>-config-as-code-ig --from-env-file=config-as-code -n fulfillment-aap
oc create secret generic <your AAP organization>-<your AAP project>-config-as-code-manifest-ig --from-file=license.zip=/path/to/license.zip` -n fulfillment-aap
```

#### Fulfilment operations configuration

Create service account and secret required for the fulfillment operations, such
as AWS and OpenStack credentials:

```
cat << EOF > cloudkit_sa.yml
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

cat << EOF > fulfillment_creds
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=...
OS_AUTH_URL=...
OS_PROJECT_NAME=...
...
EOF

oc create secret generic <your AAP organization>-<your AAP project>-cluster-fulfillment-ig --from-env-file=fufillment_creds -n fulfillment-aap
```

#### Template publisher configuration

Create the service account, role, and role bindings required by the template
publisher to authenticate against the
[fulfillment-service](https://github.com/innabox/fulfillment-service/):

```
cat << EOF > template-publisher
apiVersion: v1
kind: ServiceAccount
metadata:
  name: template-publisher
  namespace: fulfillment-aap
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: create-controller-token
  namespace: innabox
rules:
  - apiGroups: [""]
    resources: ["serviceaccounts/token"]
    resourceNames: ["controller"] # here is the name of the service account to authenticate against the fulfillment-service
    verbs: ["create"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: aap-fulfillment-template-publisher-binding
  namespace: innabox
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: Role
  name: create-controller-token
subjects:
  - kind: ServiceAccount
    name: template-publisher
    namespace: fulfillment-aap
EOF

oc apply -f template-publisher
```

#### Bootstrap AAP configuration

Use the execution environment built in the scope of `cloudkit-aap` to run the
playbook that will perform the initial configuration of AAP:

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
              - name: LICENSE_MANIFEST_PATH
                value: /var/secrets/config-as-code-manifest/license.zip
          volumeMounts:
            - name: config-as-code-manifest-volume
              mountPath: /var/secrets/config-as-code-manifest
              readOnly: true
        volumes:
          - name: config-as-code-manifest-volume
            secret:
              secretName: <your AAP organization>-<your AAP project>-config-as-code-manifest-ig
      restartPolicy: Never
  backoffLimit: 4
EOF

oc apply -f job.yml -n fulfillment-aap
```

# Cloudkit AAP execution environment

Tools and configuration to run playbooks that interact with both OpenStack/ESI and OpenShift.

## Building the execution environment

1. Update `requirements.txt` from `pyproject.toml` in the top directory:

    ```
    uv pip compile ../pyproject.toml > requirements.txt
    ```

2. Download the `openshift-clients` package from [the customer portal](https://access.redhat.com/downloads/content/290/ver=4.18/rhel---9/4.18.9/x86_64/packages) and place it in
    `openshift-clients.rpm`

3. Grab your Automation Hub token from [Red Hat console](https://console.redhat.com/ansible/automation-hub/token)

4. Run:

    ```
    ansible-builder build --tag cloudkit-aap-ee --build-arg ANSIBLE_GALAXY_SERVER_AUTOMATION_HUB_TOKEN=<your Automation Hub token>
    ```

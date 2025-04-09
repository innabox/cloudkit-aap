# Cloudkit AAP execution environment

Tools and configuration to run playbooks that interact with both OpenStack/ESI and OpenShift.

## Building the execution environment

1. Update `requirements.txt` from `pyproject.toml` in the top directory:

    ```
    uv pip compile ../pyproject.toml > requirements.txt
    ```

1. Download the `openshift-clients` package from [the customer portal] and place it in
    `openshift-clients.rpm`

2. Run:

    ```
    ansible-builder build --tag cloudkit-aap-ee
    ```

[customer portal]: https://access.redhat.com/downloads/content/290/ver=4.18/rhel---9/4.18.7/x86_64/packages

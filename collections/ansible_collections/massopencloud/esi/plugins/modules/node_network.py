#!/usr/bin/python

DOCUMENTATION = r'''
---
module: node_network
short_description: Sets the networks attached to a baremetal node
description:
  - Manage Neutron networks attached to an Ironic node
  - Sets the node's networks to exactly match the specified list
  - This means it will detach any networks not in the list and attach any missing networks
  - If networks is empty or not provided, detaches all networks from the node
options:
  networks:
    description:
      - List of network names or IDs to set on the node
      - If empty or not provided, all networks will be detached
    type: list
    elements: str
  node:
    description:
      - The name or ID of the node
    required: true
    type: str
extends_documentation_fragment:
  - openstack.cloud.openstack
'''

EXAMPLES = r'''
- name: Set a single network on a node
  massopencloud.esi.node_network:
    cloud: "devstack"
    node: "MOC-R4PAC67U12-S3"
    networks:
      - "hypershift"

- name: Set node networks to exactly match the specified list
  massopencloud.esi.node_network:
    cloud: "devstack"
    node: "MOC-R4PAC67U12-S3"
    networks:
      - "hypershift"
      - "provisioning"
      - "storage"

- name: Detach all networks from a node (empty networks list)
  massopencloud.esi.node_network:
    cloud: "devstack"
    node: "MOC-R4PAC67U12-S3"
    networks: []

- name: Detach all networks from a node (no networks parameter)
  massopencloud.esi.node_network:
    cloud: "devstack"
    node: "MOC-R4PAC67U12-S3"
'''

from ansible_collections.openstack.cloud.plugins.module_utils.openstack import (
        OpenStackModule
)


class NodeNetworkModule(OpenStackModule):
    argument_spec = dict(
        networks=dict(type='list', elements='str'),
        node=dict(required=True),
    )

    def run(self):
        node = self.conn.baremetal.find_node(
            self.params['node'], ignore_missing=False)
        desired_networks = self.params['networks'] or []

        baremetal_ports = list(self.conn.baremetal.ports(
            details=True, node_id=node.id))
        networks = list(self.conn.network.networks())

        changed = False

        desired_network_objects = [net for net in networks
                                  if net.name in desired_networks or
                                  net.id in desired_networks]
        current_network_objects = self._get_currently_attached_networks(
            baremetal_ports, networks)

        # Get networks to detach
        desired_network_ids = {net.id for net in desired_network_objects}
        networks_to_detach = [net for net in current_network_objects
                             if net.id not in desired_network_ids]

        # Get networks to attach
        current_network_ids = {net.id for net in current_network_objects}
        networks_to_attach = [net for net in desired_network_objects
                             if net.id not in current_network_ids]

        # Detach unwanted networks
        for network in networks_to_detach:
            network_port = self._find_network_port(node.name, network.name)
            if not network_port:
                continue

            baremetal_port = self._find_matching_baremetal_port(
                baremetal_ports, network_port)
            if baremetal_port:
                self.conn.baremetal.detach_vif_from_node(
                    node, network_port.id)
                self.conn.network.delete_port(network_port.id)
                changed = True

        # Attach missing networks
        for network in networks_to_attach:
            # need to refresh baremetal_ports to update its tenant_vif_port_id
            baremetal_ports = list(self.conn.baremetal.ports(
                details=True, node_id=node.id))

            network_port = self._find_network_port(node.name, network.name)
            if not network_port:
                network_port = self._create_network_port(node.name, network)

            baremetal_port = self._find_matching_baremetal_port(
                baremetal_ports, network_port)
            if baremetal_port:
                continue

            baremetal_port = self._find_free_baremetal_port(baremetal_ports)
            if not baremetal_port:
                self.fail_json(msg='Node %s has no free ports \
                    for network %s' % (node.id, network.name))

            self.conn.baremetal.attach_vif_to_node(
                node, network_port.id, port_id=baremetal_port.id)
            changed = True

        self.exit_json(changed=changed)

    def _find_network_port(self, node_name, network_name):
        port_name = "%s-%s" % (node_name, network_name)
        existing_ports = list(self.conn.network.ports(name=port_name))

        if existing_ports:
            return existing_ports[0]
        return None

    def _create_network_port(self, node_name, network):
        port_name = "%s-%s" % (node_name, network.name)
        return self.conn.network.create_port(
            name=port_name,
            network_id=network.id,
            device_owner='baremetal:none'
        )

    def _find_matching_baremetal_port(self, baremetal_ports, network_port):
        if network_port is None:
            return None

        for bp in baremetal_ports:
            if bp.internal_info.get('tenant_vif_port_id') == network_port.id:
                return bp

        return None

    def _find_free_baremetal_port(self, baremetal_ports):
        for bp in baremetal_ports:
            if "tenant_vif_port_id" not in bp.internal_info:
                return bp

        return None

    def _get_currently_attached_networks(self, baremetal_ports, networks):
        """Get list of network names currently attached to the node."""
        attached_networks = []

        for bp in baremetal_ports:
            if 'tenant_vif_port_id' in bp.internal_info:
                network_port = self.conn.network.find_port(
                    bp.internal_info['tenant_vif_port_id'], ignore_missing=True)
                if network_port:
                    try:
                        network = next(net for net in networks
                                       if net.id == network_port.network_id)
                        if network:
                            attached_networks.append(network)
                    except StopIteration:
                        continue

        return attached_networks


def main():
    module = NodeNetworkModule()
    module()


if __name__ == "__main__":
    main()

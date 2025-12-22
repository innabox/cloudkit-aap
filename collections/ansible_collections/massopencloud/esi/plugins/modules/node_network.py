#!/usr/bin/python

DOCUMENTATION = r'''
---
module: node_network
short_description: Attaches/detaches networks to/from a baremetal node
author: Innabox
description:
  - Attach or detach Neutron networks to or from an Ironic node
options:
  mac_address:
    description:
      - The MAC address of the baremetal port
    type: str
  network:
    description:
      - The name or ID of the network to attach or detach
    type: str
  node:
    description:
      - The name or ID of the node
    required: true
    type: str
  port:
    description:
      - The name or ID of the vif to attach or detach
    type: str
  state:
    description:
      - Indicates whether the attachment should be present or absent
    choices: ['present', 'absent']
    default: present
    type: str
  trunk:
    description:
      - The name or ID of the trunk to attach or detach its parent port
    type: str
extends_documentation_fragment:
  - openstack.cloud.openstack
'''

EXAMPLES = r'''
- name: Attach a network to a node
  massopencloud.esi.node_network:
    cloud: "devstack"
    state: "present"
    node: "MOC-R4PAC67U12-S3"
    network: "hypershift"

- name: Detach a network from a node
  massopencloud.esi.node_network:
    cloud: "devstack"
    state: "absent"
    node: "MOC-R4PAC67U12-S3"
    network: "hypershift"

- name: Detach all networks from a node
  massopencloud.esi.node_network:
    cloud: "devstack"
    state: "absent"
    node: "MOC-R4PAC67U12-S3"
'''

from ansible_collections.openstack.cloud.plugins.module_utils.openstack import (
        OpenStackModule
)


class NodeNetworkModule(OpenStackModule):
    argument_spec = dict(
        mac_address=dict(),
        network=dict(),
        node=dict(required=True),
        port=dict(),
        state=dict(default='present', choices=['present', 'absent']),
        trunk=dict(),
    )
    module_kwargs = dict(
        required_if=[
            ['state', 'present', ['network', 'port', 'trunk'], True],
        ],
        mutually_exclusive=[
            ['network', 'port', 'trunk'],
        ],
    )

    def run(self):
        node = self.conn.baremetal.find_node(self.params['node'],
                                             ignore_missing=False)
        mac_address = self.params['mac_address']
        network = self.params['network']
        port = self.params['port']
        trunk = self.params['trunk']

        network_port = self._find_or_create_network_port(node.name, network,
                                                         port, trunk)
        baremetal_ports = list(self.conn.baremetal.ports(
            details=True, node_id=node.id, address=mac_address))

        changed = False
        if self.params['state'] == 'present':
            baremetal_port = self._find_matching_baremetal_port(
                baremetal_ports, network_port, mac_address)
            if baremetal_port:
                self.exit_json(changed=changed)

            baremetal_port = self._find_free_baremetal_port(
                baremetal_ports, mac_address)
            if not baremetal_port:
                self.fail_json(msg='Node %s has no free ports' % node.id)

            self.conn.baremetal.attach_vif_to_node(
                node, network_port.id, port_id=baremetal_port.id)
            changed = True

        elif self.params['state'] == 'absent':
            if network or port or trunk:
                baremetal_port = self._find_matching_baremetal_port(
                    baremetal_ports, network_port, mac_address)
                if baremetal_port:
                    self.conn.baremetal.detach_vif_from_node(
                        node, network_port.id)
                    changed = True
            else:
                for bp in baremetal_ports:
                    if mac_address and bp.address != mac_address:
                        continue
                    if 'tenant_vif_port_id' in bp.internal_info:
                        self.conn.baremetal.detach_vif_from_node(
                            node, bp.internal_info['tenant_vif_port_id'])
                        changed = True

        else:
            self.fail_json(
                msg='Invalid choice for "state": %s' % self.params['state'])

        self.exit_json(changed=changed)

    def _find_or_create_network_port(self, node_name, network,
                                     network_port, trunk):
        port = None

        if network:
            network = self.conn.network.find_network(
                network, ignore_missing=False)
            port_name = "%s-%s" % (node_name, network.name)
            existing_ports = list(self.conn.network.ports(name=port_name))
            if existing_ports:
                port = existing_ports[0]
            elif self.params['state'] == 'present':
                port = self.conn.network.create_port(
                    name=port_name,
                    network_id=network.id,
                    device_owner='baremetal:none'
                )

        elif network_port:
            port = self.conn.network.find_port(
                network_port, ignore_missing=False)

        elif trunk:
            trunk_network = self.conn.network.find_trunk(
                trunk, ignore_missing=False)
            port = self.conn.network.find_port(
                trunk_network.port_id, ignore_missing=False)

        return port

    def _find_matching_baremetal_port(self, baremetal_ports,
                                      network_port, mac_address):
        if network_port is None:
            return None

        for bp in baremetal_ports:
            if mac_address and bp.address != mac_address:
                continue
            if bp.internal_info.get('tenant_vif_port_id') == network_port.id:
                return bp

        return None

    def _find_free_baremetal_port(self, baremetal_ports, mac_address):
        for bp in baremetal_ports:
            if mac_address and bp.address != mac_address:
                continue
            if "tenant_vif_port_id" not in bp.internal_info:
                return bp

        return None


def main():
    module = NodeNetworkModule()
    module()


if __name__ == "__main__":
    main()

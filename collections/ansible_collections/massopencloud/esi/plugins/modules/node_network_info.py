#!/usr/bin/python

DOCUMENTATION = r'''
---
module: node_network_info
short_description: Get information about networks attached to a baremetal node
author: Innabox
description:
  - Gather information about Neutron networks attached to an Ironic node
  - Returns details about network attachments and baremetal ports
options:
  nodes:
    description:
      - A list of node names or IDs
    type: list
    element: str
  network:
    description:
      - Filter by specific network name or ID
    type: str
extends_documentation_fragment:
  - openstack.cloud.openstack
'''

EXAMPLES = r'''
'''

RETURN = r'''
node_networks:
  description:
    - List of information about network attachments on the nodes
  returned: success
  type: list
  elements: dict
  contains:
    name:
      description:
        - The name of the node
      returned: success
      type: str
    id:
      description:
        - The ID of the node
      returned: success
      type: str
    ports_info:
      description:
        - A list of the node's port information
      returned: success
      type: list
      elements: dict
      contains:
        baremetal_port_id:
          description:
            - The ID of the baremetal port
          returned: success
          type: str
        mac_address:
          description:
            - The baremetal port's MAC address
          returned: success
          type: str
        network_port:
          description:
            - A dict of info for the attached port
          returned: When baremetal port is attached
          type: dict
          contains:
            name:
              description:
                - The network port's name
              returned: When baremetal port is attached
              type: str
            id:
              description:
                - The network port's ID
              returned: When baremetal port is attached
              type: str
            fixed_ips:
              description:
                - A list of the network port's IPs
              returned: When baremetal port is attached
              type: list
              elements: str
        network:
          description:
            - A dict of info for the attached network
          returned: When a network is attached
          type: dict
          contains:
            name:
              description:
                - The network's name
              returned: When a network is attached
              type: str
            id:
              description:
                - The network's ID
              returned: When a network is attached
              type: str
            vlan_id:
              description:
                - The network's vlan ID
              returned: When a network is attached
              type: int
        floating_ip:
          description:
            - A dict of info for an attached floating ip
          returned: When a floating IP is attached
          type: dict
          contains:
            address:
              description:
                - The address of the floating IP
              returned: When a floating IP is attached
              type: str
            id:
              description:
                - The ID of the floating IP
              returned: When a floating IP is attached
              type: str
            port_forwardings:
              description:
                - The floating IP's port forwardings
              returned: When a floating IP is attached
              type: list
              elements: dict
              contains:
                external_port:
                  description:
                    - The floating IP port forwarding's external protocol port
                  returned: When a floating IP with port forwarding is attached
                  type: int
                internal_port:
                  description:
                    - The floating IP port forwarding's internal protocol port
                  returned: When a floating IP with port forwarding is attached
                  type: int
        floating_network:
          description:
            - A dict of info for the external network
          returned: When a floating IP is attached
          type: dict
          contains:
            name:
              description:
                - The external network's name
              returned: When an external network is attached
              type: str
            id:
              description:
                - The external network's ID
              returned: When an external network is attached
              type: str
            vlan_id:
              description:
                - The external network's vlan ID
              returned: When an external network is attached
              type: int
        trunk_id:
          description:
            - The parent network trunk's ID
          returned: When a parent network trunk is attached
          type: str
        trunk_networks:
          description:
            - A list of children trunk networks
          returned: When a parent network trunk is attached
          type: list
          elements: dict
          contains:
            name:
              description:
                - The child trunk's name
              returned: When a parent network trunk is attached
              type: str
            id:
              description:
                - The network's ID
              returned: When a parent network trunk is attached
              type: str
            vlan_id:
              description:
                - The network's vlan ID
              returned: When a parent network trunk is attached
              type: int
'''

from collections import defaultdict
from ansible_collections.openstack.cloud.plugins.module_utils.openstack import (
        OpenStackModule
)


class NodeNetworkInfoModule(OpenStackModule):
    argument_spec = dict(
        nodes=dict(type='list', elements='str'),
        network=dict(),
    )

    def run(self):
        self._prefetch_resources()
        node_network_info = self._get_node_network_info()
        node_networks = self._format_node_network_info(node_network_info)

        self.exit_json(node_networks=node_networks)

    def _prefetch_resources(self):
        self._networks_by_id = {
            network.id: network for network in self.conn.network.networks()
        }

        self._network_ports_by_id = {
            port.id: port for port in self.conn.network.ports()
        }

        ips = self.conn.network.ips()
        self._port_forwardings_by_internal_port_id = defaultdict(list)
        self._floating_ips_by_port_id = {}
        for ip in ips:
            for pfwd in self.conn.network.port_forwardings(ip):
                self._port_forwardings_by_internal_port_id[
                    pfwd.internal_port_id
                ].append(pfwd)
            else:
                self._floating_ips_by_port_id[pfwd.internal_port_id] = ip

    def _get_networks_from_port(self, network_port):
        parent_network = self._networks_by_id[network_port.network_id]

        if (self.params['network'] and (
                parent_network.name != self.params['network'] or
                parent_network.id != self.params['network'])):
            return None, [], [], None

        trunk_networks = []
        trunk_ports = []
        if network_port.trunk_details:
            subport_infos = network_port.trunk_details['sub_ports']
            for subport_info in subport_infos:
                subport = self._network_ports_by_id[subport_info['port_id']]
                trunk_network = self._networks_by_id[subport.network_id]

                trunk_ports.append(subport)
                trunk_networks.append(trunk_network)

        floating_network_id = getattr(
            self._floating_ips_by_port_id.get(network_port.id),
            'floating_network_id',
            None
        )
        floating_network = self._networks_by_id.get(floating_network_id, None)

        return parent_network, trunk_networks, trunk_ports, floating_network

    def _get_node_network_info(self):
        filter_nodes = set(self.params['nodes'])
        baremetal_nodes = self.conn.baremetal.nodes(details=True)

        node_networks = []
        for baremetal_node in baremetal_nodes:
            if (self.params['nodes'] and
                    baremetal_node.id not in filter_nodes and
                    baremetal_node.name not in filter_nodes):
                continue

            baremetal_ports = self.conn.baremetal.ports(
                details=True, node_id=baremetal_node.id)

            network_infos = []
            for baremetal_port in baremetal_ports:
                network_info = {
                    'baremetal_port_id': baremetal_port.id,
                    'mac_address': baremetal_port.address,
                    'network_ports': [],
                    'networks': {
                        'parent': None,
                        'trunks': [],
                        'floating': None,
                    },
                    'floating_ip': None,
                    'port_forwardings': [],
                }

                network_port = None
                network_port_id = baremetal_port.internal_info.get(
                    'tenant_vif_port_id', None)

                if network_port_id:
                    network_port = self._network_ports_by_id.get(
                        network_port_id, None)

                if network_port:
                    parent, trunks, trunk_ports, floating = \
                        self._get_networks_from_port(network_port)

                    if not parent:
                        continue

                    floating_ip = self._floating_ips_by_port_id.get(
                        network_port.id, None)
                    network_info['network_ports'].append(network_port)
                    network_info['network_ports'].extend(trunk_ports)
                    network_info['networks']['parent'] = parent
                    network_info['networks']['trunks'] = trunks
                    network_info['networks']['floating'] = floating
                    network_info['floating_ip'] = floating_ip
                    network_info['port_forwardings'] = (
                        self
                        ._port_forwardings_by_internal_port_id
                        .get(network_port.id, [])
                    )

                elif self.params['network']:
                    continue

                network_infos.append(network_info)

            if network_infos:
                node_networks.append({
                    'name': baremetal_node.name,
                    'id': baremetal_node.id,
                    'ports_info': network_infos,
                })

        return node_networks

    def _format_node_network_info(self, node_network_info):
        node_networks = []
        for info in node_network_info:
            node_network = {
                'name': info['name'],
                'id': info['id'],
            }

            node_ports = []
            for port_info in info['ports_info']:
                node_port = {
                    'baremetal_port_id': port_info['baremetal_port_id'],
                    'mac_address': port_info['mac_address'],
                }

                network_ports = port_info.get('network_ports')
                if network_ports:
                    network_port = network_ports[0]
                    node_port['network_port'] = {
                        'name': network_port.name,
                        'id': network_port.id,
                        'fixed_ips': [
                            ips['ip_address'] for ips in network_port.fixed_ips
                        ],
                    }

                networks = port_info.get('networks')
                if networks:
                    parent = networks.get('parent')
                    if parent:
                        node_port['network'] = {
                            'name': parent.name,
                            'id': parent.id,
                            'vlan_id': parent.provider_segmentation_id,
                        }

                        trunks = networks.get('trunks')
                        if trunks:
                            node_port['trunk_networks'] = [
                                {
                                    'name': trunk.name,
                                    'id': trunk.id,
                                    'vlan_id': trunk.provider_segmentation_id,
                                } for trunk in trunks
                            ]

                            details = network_port.get('trunk_details')
                            if details:
                                node_port['trunk_id'] = details['trunk_id']

                    floating = networks.get('floating')
                    if floating:
                        node_port['floating_network'] = {
                            'name': floating.name,
                            'id': floating.id,
                            'vlan_id': floating.provider_segmentation_id,
                        }

                        floating_ip = port_info.get('floating_ip')
                        if floating_ip:
                            node_port['floating_ip'] = {
                                'address': floating_ip.floating_ip_address,
                                'id': floating_ip.id
                            }

                        port_forwardings = port_info.get('port_forwardings')
                        if port_forwardings:
                            node_port['floating_ip']['port_forwardings'] = [
                                {
                                    'external_port': pfwd.external_port,
                                    'internal_port': pfwd.internal_port,
                                } for pfwd in port_forwardings
                            ]

                node_ports.append(node_port)

            node_network['ports_info'] = node_ports
            node_networks.append(node_network)

        return node_networks


def main():
    module = NodeNetworkInfoModule()
    module()


if __name__ == '__main__':
    main()

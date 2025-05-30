def mac_to_agent_name(v: list[str], agents) -> str | None:
    """Returns the name of the agent with matching MAC address"""

    target_addresses = set(v)
    for agent in agents:
        # Use set intersection
        interfaces = agent.get("status", {}) \
                          .get("inventory", {}) \
                          .get("interfaces", [])
        agent_addresses = {iface["macAddress"] for iface in interfaces}

        if target_addresses.intersection(agent_addresses):
            return agent['metadata']['name']

    return None


class FilterModule:
    def filters(self):
        return {
            "mac_to_agent_name": mac_to_agent_name,
        }

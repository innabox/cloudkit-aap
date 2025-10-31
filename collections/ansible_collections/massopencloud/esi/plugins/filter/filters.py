import json
import re

re_node_location = re.compile("moc-r([0-9]+)p([a-z])c([0-9]+)u([0-9]+)(-s(.*))?")


def extract_esi_location(v: str) -> dict[str, str]:
    mo = re_node_location.match(v.lower())
    if not mo:
        return {}

    return {
        "cabinet": mo.group(3),
        "pod": mo.group(2),
        "row": mo.group(1),
        "slot": mo.group(6),
        "u": mo.group(4),
    }


def match_agent_addresses(v: list[str], agents) -> str|None:
    for agent in agents:
        agent_addresses = [
            iface["macAddress"] for iface in agent.get("status", {}).get("inventory", {}).get("interfaces", []) ]
        if any(addr in agent_addresses for addr in v):
            return agent['metadata']['name']

    return None


class FilterModule:
    def filters(self):
        return {
            "extract_esi_location": extract_esi_location,
            "match_agent_addresses": match_agent_addresses,
        }


def test_extract_esi_location():
    samples = {
        "MOC-R4PAC24U35-S3A": {
            "cabinet": "24",
            "pod": "A",
            "row": "4",
            "slot": "3A",
            "u": "35",
        },
        "MOC-R8PAC23U26": {
            "cabinet": "23",
            "pod": "A",
            "row": "8",
            "slot": None,
            "u": "26",
        },
    }

    for name, want in samples.items():
        try:
            have = extract_esi_location(name)
            assert have == want
        except AssertionError:
            print(f"have = {have}")
            print(f"want = {want}")
            raise

#!/usr/bin/python

DOCUMENTATION = """
---
module: hosts
short_description: Query active Ethernet hosts per LAN port from a Fritz!Box
description:
  - Returns the list of currently active Ethernet hosts visible on each
    physical LAN port (ports 1-4) via the TR-064 X_AVM-DE_GetHostListPath
    service.
  - Uses the fritzconnection library.
options:
  host:
    description: Hostname or IP address of the Fritz!Box.
    required: true
    type: str
  username:
    description: Fritz!Box login username.
    required: false
    type: str
    default: ""
  password:
    description: Fritz!Box login password.
    required: false
    type: str
    no_log: true
    default: ""
  port:
    description: TR-064 port.
    required: false
    type: int
    default: 49000
  use_tls:
    description: Use TLS for the TR-064 connection.
    required: false
    type: bool
    default: false
  active_only:
    description: Only return currently active (online) hosts.
    required: false
    type: bool
    default: true
"""

EXAMPLES = """
- name: Gather Fritz!Box LAN port host assignments
  pschmitt.fritzbox.hosts:
    host: "{{ ansible_host }}"
    username: "{{ fritzbox_username }}"
    password: "{{ fritzbox_password }}"
"""

RETURN = """
ansible_facts:
  description: Facts gathered from the Fritz!Box.
  returned: always
  type: dict
  contains:
    fritzbox_lan_hosts:
      description: >
        Active Ethernet hosts per physical LAN port (ports 1-4).
        Each entry has: port (int 1-4), mac (upper-case), ip, name.
      type: list
      elements: dict
      sample:
        - port: 4
          mac: "D8:58:D7:00:3D:AB"
          ip: "10.178.0.5"
          name: "turris"
"""

from ansible.module_utils.basic import AnsibleModule

try:
    from fritzconnection.core.fritzconnection import FritzConnection
    from fritzconnection.core.exceptions import (
        FritzConnectionException,
        FritzAuthorizationError,
    )
    from fritzconnection.lib.fritzhosts import FritzHosts

    HAS_FRITZCONNECTION = True
except ImportError:
    HAS_FRITZCONNECTION = False

_LAN_PORT_MIN = 1
_LAN_PORT_MAX = 4


def main():
    module = AnsibleModule(
        argument_spec={
            "host": {"type": "str", "required": True},
            "username": {"type": "str", "default": ""},
            "password": {"type": "str", "default": "", "no_log": True},
            "port": {"type": "int", "default": 49000},
            "use_tls": {"type": "bool", "default": False},
            "active_only": {"type": "bool", "default": True},
        },
        supports_check_mode=True,
    )

    if not HAS_FRITZCONNECTION:
        module.fail_json(
            msg="The fritzconnection Python library is required. "
            "Install it via: pip install fritzconnection"
        )

    try:
        fc = FritzConnection(
            address=module.params["host"],
            port=module.params["port"],
            user=module.params["username"],
            password=module.params["password"],
            use_tls=module.params["use_tls"],
        )
        fh = FritzHosts(fc=fc)
        raw = fh.get_hosts_attributes()
    except FritzAuthorizationError as e:
        module.fail_json(msg=f"Authorization failed connecting to {module.params['host']}: {e}")
    except FritzConnectionException as e:
        module.fail_json(msg=f"Connection to {module.params['host']} failed: {e}")
    except Exception as e:
        module.fail_json(msg=f"Unexpected error: {e}")

    active_only = module.params["active_only"]
    lan_hosts = []
    for h in raw:
        if active_only and not h.get("Active"):
            continue
        if h.get("InterfaceType") != "Ethernet":
            continue
        lan_port = h.get("X_AVM-DE_Port")
        if lan_port is None or not (_LAN_PORT_MIN <= lan_port <= _LAN_PORT_MAX):
            continue
        mac = h.get("MACAddress", "")
        if not mac:
            continue
        lan_hosts.append({
            "port": lan_port,
            "mac": mac.upper(),
            "ip": h.get("IPAddress") or "",
            "name": h.get("HostName") or "",
        })

    module.exit_json(
        changed=False,
        ansible_facts={"fritzbox_lan_hosts": lan_hosts},
    )


if __name__ == "__main__":
    main()

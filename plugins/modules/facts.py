#!/usr/bin/python

DOCUMENTATION = """
---
module: facts
short_description: Gather facts from an AVM Fritz!Box via TR-064
description:
  - Connects to a Fritz!Box using the fritzconnection library (TR-064/SOAP)
    and returns device and WAN status as ansible_facts.
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
"""

EXAMPLES = """
- name: Gather Fritz!Box facts
  pschmitt.fritzbox.facts:
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
    fritzbox_modelname:
      description: Device model name.
      type: str
    fritzbox_system_version:
      description: Firmware version string.
      type: str
    fritzbox_is_connected:
      description: Whether the WAN link is connected.
      type: bool
    fritzbox_is_linked:
      description: Whether the DSL/physical link is up.
      type: bool
    fritzbox_device_uptime:
      description: Device uptime in seconds.
      type: int
    fritzbox_external_ip:
      description: Current WAN IPv4 address.
      type: str
    fritzbox_update_available:
      description: Whether a firmware update is available.
      type: bool
    fritzbox_upnp_enabled:
      description: Whether UPnP is enabled.
      type: bool
"""

from ansible.module_utils.basic import AnsibleModule

try:
    from fritzconnection.core.fritzconnection import FritzConnection
    from fritzconnection.core.exceptions import (
        FritzConnectionException,
        FritzAuthorizationError,
    )
    from fritzconnection.lib.fritzstatus import FritzStatus

    HAS_FRITZCONNECTION = True
except ImportError:
    HAS_FRITZCONNECTION = False


def main():
    module = AnsibleModule(
        argument_spec={
            "host": {"type": "str", "required": True},
            "username": {"type": "str", "default": ""},
            "password": {"type": "str", "default": "", "no_log": True},
            "port": {"type": "int", "default": 49000},
            "use_tls": {"type": "bool", "default": False},
        },
        supports_check_mode=True,
    )

    if not HAS_FRITZCONNECTION:
        module.fail_json(
            msg="The fritzconnection Python library is required. "
            "Install it via: pip install fritzconnection"
        )

    host = module.params["host"]
    username = module.params["username"]
    password = module.params["password"]
    port = module.params["port"]
    use_tls = module.params["use_tls"]

    try:
        fc = FritzConnection(
            address=host,
            port=port,
            user=username,
            password=password,
            use_tls=use_tls,
        )
        fs = FritzStatus(fc=fc)

        facts = {
            "fritzbox_modelname": fc.modelname,
            "fritzbox_system_version": fc.system_version,
            "fritzbox_is_connected": fs.is_connected,
            "fritzbox_is_linked": fs.is_linked,
            "fritzbox_device_uptime": fs.device_uptime,
            "fritzbox_external_ip": fs.external_ip,
            "fritzbox_update_available": fs.update_available,
            "fritzbox_upnp_enabled": fs.upnp_enabled,
        }

    except FritzAuthorizationError as e:
        module.fail_json(msg=f"Authorization failed connecting to {host}: {e}")
    except FritzConnectionException as e:
        module.fail_json(msg=f"Connection to {host} failed: {e}")
    except Exception as e:
        module.fail_json(msg=f"Unexpected error connecting to {host}: {e}")

    module.exit_json(changed=False, ansible_facts=facts)


if __name__ == "__main__":
    main()

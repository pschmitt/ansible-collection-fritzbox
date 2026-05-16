#!/usr/bin/python

from ansible.module_utils.basic import AnsibleModule

try:
    from fritzconnection.core.fritzconnection import FritzConnection
    from fritzconnection.core.exceptions import (
        FritzConnectionException,
        FritzAuthorizationError,
    )

    HAS_FRITZCONNECTION = True
except ImportError:
    HAS_FRITZCONNECTION = False


def main():
    module = AnsibleModule(
        argument_spec={
            "host": {"type": "str", "required": True},
            "port": {"type": "int", "default": 49000},
            "username": {"type": "str", "default": ""},
            "password": {"type": "str", "default": "", "no_log": True},
            "ip": {"type": "str", "default": None},
            "mask": {"type": "str", "default": None},
            "dhcp_enabled": {"type": "bool", "default": None},
            "dhcp_start": {"type": "str", "default": None},
            "dhcp_end": {"type": "str", "default": None},
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
    port = module.params["port"]
    username = module.params["username"]
    password = module.params["password"]
    desired_ip = module.params["ip"]
    desired_mask = module.params["mask"]
    desired_dhcp_enabled = module.params["dhcp_enabled"]
    desired_dhcp_start = module.params["dhcp_start"]
    desired_dhcp_end = module.params["dhcp_end"]
    use_tls = module.params["use_tls"]

    try:
        fc = FritzConnection(
            address=host,
            port=port,
            user=username,
            password=password,
            use_tls=use_tls,
        )

        info = fc.call_action("LANHostConfigManagement1", "GetInfo")
        current_ip = info.get("NewIPRouters", "")
        current_mask = info.get("NewSubnetMask", "")
        current_dhcp_enabled = info.get("NewDHCPServerEnable", False)
        current_dhcp_start = info.get("NewMinAddress", "")
        current_dhcp_end = info.get("NewMaxAddress", "")

    except FritzAuthorizationError as e:
        module.fail_json(msg=f"Authorization failed connecting to {host}: {e}")
    except FritzConnectionException as e:
        module.fail_json(msg=f"Connection to {host} failed: {e}")
    except Exception as e:
        module.fail_json(msg=f"Unexpected error connecting to {host}: {e}")

    changes = {}

    if desired_ip is not None and current_ip != desired_ip:
        changes["ip"] = (current_ip, desired_ip)

    if desired_mask is not None and current_mask != desired_mask:
        changes["mask"] = (current_mask, desired_mask)

    if desired_dhcp_enabled is not None and bool(current_dhcp_enabled) != bool(
        desired_dhcp_enabled
    ):
        changes["dhcp_enabled"] = (current_dhcp_enabled, desired_dhcp_enabled)

    if desired_dhcp_start is not None and current_dhcp_start != desired_dhcp_start:
        changes["dhcp_start"] = (current_dhcp_start, desired_dhcp_start)

    if desired_dhcp_end is not None and current_dhcp_end != desired_dhcp_end:
        changes["dhcp_end"] = (current_dhcp_end, desired_dhcp_end)

    if not changes:
        module.exit_json(changed=False)

    if module.check_mode:
        module.exit_json(changed=True, diff=changes)

    if "ip" in changes or "mask" in changes:
        module.fail_json(
            msg="Changing LAN IP or subnet mask via TR-064 is not supported. "
            "Please configure manually."
        )

    try:
        if "dhcp_start" in changes or "dhcp_end" in changes:
            new_start = desired_dhcp_start if desired_dhcp_start is not None else current_dhcp_start
            new_end = desired_dhcp_end if desired_dhcp_end is not None else current_dhcp_end
            fc.call_action(
                "LANHostConfigManagement1",
                "SetAddressRange",
                NewMinAddress=new_start,
                NewMaxAddress=new_end,
            )

        if "dhcp_enabled" in changes:
            fc.call_action(
                "LANHostConfigManagement1",
                "SetDHCPServerEnable",
                NewDHCPServerEnable=desired_dhcp_enabled,
            )

    except FritzAuthorizationError as e:
        module.fail_json(msg=f"Authorization failed applying changes to {host}: {e}")
    except FritzConnectionException as e:
        module.fail_json(msg=f"Connection to {host} failed while applying changes: {e}")
    except Exception as e:
        module.fail_json(msg=f"Unexpected error applying changes to {host}: {e}")

    module.exit_json(changed=True, diff=changes)


if __name__ == "__main__":
    main()

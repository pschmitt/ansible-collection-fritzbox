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
            "wlan_index": {"type": "int", "required": True},
            "enabled": {"type": "bool", "default": None},
            "ssid": {"type": "str", "default": None},
            "psk": {"type": "str", "default": None, "no_log": True},
            "global_enable": {"type": "bool", "default": None},
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
    wlan_index = module.params["wlan_index"]
    desired_enabled = module.params["enabled"]
    desired_ssid = module.params["ssid"]
    desired_psk = module.params["psk"]
    desired_global_enable = module.params["global_enable"]
    use_tls = module.params["use_tls"]

    if wlan_index not in (1, 2, 3):
        module.fail_json(msg=f"wlan_index must be 1, 2, or 3, got {wlan_index}")

    svc = f"WLANConfiguration{wlan_index}"

    try:
        fc = FritzConnection(
            address=host,
            port=port,
            user=username,
            password=password,
            use_tls=use_tls,
        )

        info = fc.call_action(svc, "GetInfo")
        current_enabled = info.get("NewEnable")
        current_ssid = info.get("NewSSID")

        current_psk = None
        if desired_psk is not None:
            keys = fc.call_action(svc, "GetSecurityKeys")
            current_psk = keys.get("NewKeyPassphrase")

        current_global_enable = None
        if desired_global_enable is not None and wlan_index == 1:
            current_global_enable = info.get("NewX_AVM-DE_WLANGlobalEnable")

    except FritzAuthorizationError as e:
        module.fail_json(msg=f"Authorization failed connecting to {host}: {e}")
    except FritzConnectionException as e:
        module.fail_json(msg=f"Connection to {host} failed: {e}")
    except Exception as e:
        module.fail_json(msg=f"Unexpected error connecting to {host}: {e}")

    changes = {}

    if desired_enabled is not None and bool(current_enabled) != bool(desired_enabled):
        changes["enabled"] = (current_enabled, desired_enabled)

    if desired_ssid is not None and current_ssid != desired_ssid:
        changes["ssid"] = (current_ssid, desired_ssid)

    if desired_psk is not None and current_psk != desired_psk:
        changes["psk"] = ("<redacted>", "<redacted>")

    if desired_global_enable is not None and wlan_index == 1:
        if bool(current_global_enable) != bool(desired_global_enable):
            changes["global_enable"] = (current_global_enable, desired_global_enable)

    if not changes:
        module.exit_json(changed=False)

    if module.check_mode:
        module.exit_json(changed=True, diff=changes)

    try:
        if "enabled" in changes:
            fc.call_action(svc, "SetEnable", NewEnable=desired_enabled)

        if "ssid" in changes:
            fc.call_action(svc, "SetSSID", NewSSID=desired_ssid)

        if "psk" in changes:
            fc.call_action(
                svc,
                "SetSecurityKeys",
                NewWEPKey0="",
                NewWEPKey1="",
                NewWEPKey2="",
                NewWEPKey3="",
                NewPreSharedKey="",
                NewKeyPassphrase=desired_psk,
            )

        if "global_enable" in changes and wlan_index == 1:
            fc.call_action(
                "WLANConfiguration1",
                "X_AVM-DE_SetWLANGlobalEnable",
                **{"NewX_AVM-DE_WLANGlobalEnable": desired_global_enable},
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

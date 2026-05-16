#!/usr/bin/python

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.pschmitt.fritzbox.plugins.module_utils.fritzbox import (
    HAS_REQUESTS,
    api_headers,
    get_sid,
)

try:
    import requests
except ImportError:
    pass


def _get_name(host, sid):
    resp = requests.get(
        f"https://{host}/api/v0/dino/misc/boxname",
        headers=api_headers(sid),
        verify=False,
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["name"]


def _set_name(host, sid, name, do_not_modify_ssids):
    resp = requests.put(
        f"https://{host}/api/v0/dino/misc/boxname",
        headers=api_headers(sid),
        json={"name": name, "doNotModifySSIDs": do_not_modify_ssids},
        verify=False,
        timeout=10,
    )
    resp.raise_for_status()


def main():
    module = AnsibleModule(
        argument_spec={
            "host": {"type": "str", "required": True},
            "username": {"type": "str", "default": ""},
            "password": {"type": "str", "default": "", "no_log": True},
            "name": {"type": "str", "required": True},
            "do_not_modify_ssids": {"type": "bool", "default": True},
        },
        supports_check_mode=True,
    )

    if not HAS_REQUESTS:
        module.fail_json(
            msg="The requests Python library is required. "
            "Install it via: pip install requests"
        )

    host = module.params["host"]
    username = module.params["username"]
    password = module.params["password"]
    desired_name = module.params["name"]
    do_not_modify_ssids = module.params["do_not_modify_ssids"]

    try:
        sid = get_sid(host, username, password)
        current_name = _get_name(host, sid)
    except Exception as e:
        module.fail_json(msg=f"Failed to read box name from {host}: {e}")

    if current_name == desired_name:
        module.exit_json(changed=False, name=current_name)

    diff = {"before": {"name": current_name}, "after": {"name": desired_name}}

    if module.check_mode:
        module.exit_json(changed=True, diff=diff)

    try:
        _set_name(host, sid, desired_name, do_not_modify_ssids)
    except Exception as e:
        module.fail_json(msg=f"Failed to set box name on {host}: {e}", diff=diff)

    module.exit_json(changed=True, diff=diff, name=desired_name)


if __name__ == "__main__":
    main()

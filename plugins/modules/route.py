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


def _get_routes(host, sid):
    r = requests.get(
        f"https://{host}/api/v0/generic/route/route",
        headers=api_headers(sid),
        verify=False,
        timeout=10,
    )
    r.raise_for_status()
    return r.json()


def _find_route(current_routes, network, netmask):
    for r in current_routes:
        if r.get("ipaddr") == network and r.get("netmask") == netmask:
            return r
    return None


def _route_needs_update(existing, desired):
    return (
        existing.get("gateway") != desired["gateway"]
        or (existing.get("activated") == "1") != desired.get("enabled", True)
    )


def main():
    module = AnsibleModule(
        argument_spec={
            "host": {"type": "str", "required": True},
            "username": {"type": "str", "default": ""},
            "password": {"type": "str", "default": "", "no_log": True},
            "routes": {
                "type": "list",
                "elements": "dict",
                "required": True,
                "options": {
                    "network": {"type": "str", "required": True},
                    "netmask": {"type": "str", "required": True},
                    "gateway": {"type": "str", "required": True},
                    "enabled": {"type": "bool", "default": True},
                },
            },
            "purge": {"type": "bool", "default": False},
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
    desired_routes = module.params["routes"]
    purge = module.params["purge"]

    try:
        sid = get_sid(host, username, password)
        current_routes = _get_routes(host, sid)
    except Exception as e:
        module.fail_json(msg=f"Failed to read static routes from {host}: {e}")

    headers = api_headers(sid)
    base_url = f"https://{host}/api/v0/generic/route/route"

    changed = False
    created = []
    updated = []

    for desired in desired_routes:
        network = desired["network"]
        netmask = desired["netmask"]
        gateway = desired["gateway"]
        enabled = desired.get("enabled", True)
        payload = {
            "ipaddr": network,
            "netmask": netmask,
            "gateway": gateway,
            "activated": "1" if enabled else "0",
        }

        existing = _find_route(current_routes, network, netmask)

        if existing is None:
            if not module.check_mode:
                r = requests.post(
                    base_url, headers=headers, json=payload, verify=False, timeout=10
                )
                r.raise_for_status()
            changed = True
            created.append(f"{network}/{netmask} via {gateway}")
        elif _route_needs_update(existing, desired):
            if not module.check_mode:
                uid = existing["UID"]
                r = requests.put(
                    f"{base_url}/{uid}",
                    headers=headers,
                    json=payload,
                    verify=False,
                    timeout=10,
                )
                r.raise_for_status()
            changed = True
            updated.append(f"{network}/{netmask} via {gateway}")

    deleted = []
    if purge:
        desired_keys = {(r["network"], r["netmask"]) for r in desired_routes}
        for existing in current_routes:
            key = (existing["ipaddr"], existing["netmask"])
            if key not in desired_keys:
                if not module.check_mode:
                    r = requests.delete(
                        f"{base_url}/{existing['UID']}",
                        headers=headers,
                        verify=False,
                        timeout=10,
                    )
                    r.raise_for_status()
                changed = True
                deleted.append(f"{existing['ipaddr']}/{existing['netmask']}")

    if not changed:
        module.exit_json(changed=False, routes=current_routes)

    module.exit_json(changed=True, created=created, updated=updated, deleted=deleted)


if __name__ == "__main__":
    main()

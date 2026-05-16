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


def _list_domains(host, sid):
    resp = requests.get(
        f"https://{host}/api/v0/generic/dns_excepted_domains",
        headers=api_headers(sid),
        verify=False,
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    # Response shape: {"domain": [{"name": "fritz.box", "UID": "domain6194"}, ...]}
    return {e["UID"]: e["name"] for e in data.get("domain", [])}


def _add_domain(host, sid, name):
    resp = requests.post(
        f"https://{host}/api/v0/generic/dns_excepted_domains/domain",
        headers=api_headers(sid),
        json={"name": name},
        verify=False,
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def _remove_domain(host, sid, uid):
    resp = requests.delete(
        f"https://{host}/api/v0/generic/dns_excepted_domains/domain/{uid}",
        headers=api_headers(sid),
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
            "domains": {
                "type": "list",
                "elements": "str",
                "required": True,
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
    desired = set(module.params["domains"])
    purge = module.params["purge"]

    try:
        sid = get_sid(host, username, password)
        current = _list_domains(host, sid)
    except Exception as e:
        module.fail_json(msg=f"Failed to read DNS rebind exceptions from {host}: {e}")

    current_names = set(current.values())
    to_add = desired - current_names
    to_remove = (
        {uid: name for uid, name in current.items() if name not in desired}
        if purge
        else {}
    )

    if not to_add and not to_remove:
        module.exit_json(changed=False, domains=sorted(current_names))

    diff = {
        "before": sorted(current_names),
        "after": sorted((current_names | to_add) - set(to_remove.values())),
    }

    if module.check_mode:
        module.exit_json(changed=True, diff=diff)

    try:
        for name in to_add:
            _add_domain(host, sid, name)
        for uid in to_remove:
            _remove_domain(host, sid, uid)
    except Exception as e:
        module.fail_json(
            msg=f"Failed to apply DNS rebind exceptions on {host}: {e}", diff=diff
        )

    module.exit_json(changed=True, diff=diff, domains=diff["after"])


if __name__ == "__main__":
    main()

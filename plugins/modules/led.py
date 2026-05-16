#!/usr/bin/python

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.pschmitt.fritzbox.plugins.module_utils.fritzbox import (
    HAS_REQUESTS,
    get_sid,
)

try:
    import requests
except ImportError:
    pass


def main():
    module = AnsibleModule(
        argument_spec={
            "host": {"type": "str", "required": True},
            "username": {"type": "str", "default": ""},
            "password": {"type": "str", "default": "", "no_log": True},
            "led_display": {"type": "int", "required": True, "choices": [0, 1, 2]},
            "dim_value": {"type": "int", "default": None},
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
    desired_led_display = module.params["led_display"]
    desired_dim_value = module.params["dim_value"]

    try:
        sid = get_sid(host, username, password)

        resp = requests.post(
            f"http://{host}/data.lua",
            data={"sid": sid, "page": "led", "xhrId": "all"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        led_settings = data.get("data", {}).get("ledSettings", {})
        current_led_display = int(led_settings.get("ledDisplay", -1))
        current_dim_value = int(led_settings.get("dimValue", 0))

    except Exception as e:
        module.fail_json(msg=f"Failed to read LED state from {host}: {e}")

    dim_value_to_apply = (
        desired_dim_value if desired_dim_value is not None else current_dim_value
    )

    led_changed = current_led_display != desired_led_display
    dim_changed = (
        desired_dim_value is not None and current_dim_value != desired_dim_value
    )

    if not led_changed and not dim_changed:
        module.exit_json(changed=False)

    if module.check_mode:
        module.exit_json(
            changed=True,
            diff={
                "led_display": (current_led_display, desired_led_display),
                "dim_value": (current_dim_value, dim_value_to_apply),
            },
        )

    try:
        resp = requests.post(
            f"http://{host}/data.lua",
            data={
                "sid": sid,
                "page": "led",
                "xhr": "1",
                "ledDisplay": desired_led_display,
                "dimValue": dim_value_to_apply,
                "apply": "",
            },
            timeout=10,
        )
        resp.raise_for_status()
        result = resp.json()
        if result.get("data", {}).get("apply") != "ok":
            module.fail_json(msg=f"LED apply did not return ok: {result}")
    except Exception as e:
        module.fail_json(msg=f"Failed to apply LED settings to {host}: {e}")

    module.exit_json(
        changed=True,
        led_display=desired_led_display,
        dim_value=dim_value_to_apply,
    )


if __name__ == "__main__":
    main()

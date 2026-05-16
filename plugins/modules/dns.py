#!/usr/bin/python

import base64
import hashlib
import hmac
import struct
import time
import urllib.parse

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.pschmitt.fritzbox.plugins.module_utils.fritzbox import (
    HAS_REQUESTS,
    get_sid,
)

try:
    import requests
except ImportError:
    pass


def _spa_post(host, sid, data):
    return requests.post(
        f"https://{host}/data.lua",
        headers={"Authorization": f"AVM-SID {sid}"},
        data={"sid": sid, **data},
        verify=False,
        timeout=10,
    )


def _tfa_post(host, sid, data):
    return requests.post(
        f"https://{host}/twofactor.lua",
        headers={"Authorization": f"AVM-SID {sid}"},
        data={"sid": sid, **data},
        verify=False,
        timeout=10,
    )


def _read_dns(host, sid):
    resp = _spa_post(host, sid, {"page": "dnsSrv", "xhrId": "all"})
    resp.raise_for_status()
    v = resp.json()["data"]["vars"]
    return {
        "v4_first": v["ipv4"]["firstdns"]["value"],
        "v4_second": v["ipv4"]["seconddns"]["value"],
        "v4_use_user_dns": v["ipv4"]["userdns"]["value"],
        "v6_first": v["ipv6"]["firstdns"]["value"],
        "v6_second": v["ipv6"]["seconddns"]["value"],
        "v6_use_user_dns": v["ipv6"]["userdns"]["value"],
        "public_enabled": "1" if v.get("public", {}).get("enabled") else "0",
        "dot_enabled": "1" if v.get("dot", {}).get("enabled") else "0",
        "dot_strict": "1" if v.get("dot", {}).get("strict") else "0",
        "dot_udp_fallback": "1" if v.get("dot", {}).get("udp_fallback") else "0",
        "dot_fqdn_list": v.get("dot", {}).get("fqdns", ""),
        "edns0_mac_and_hostname": (
            "1" if v.get("edns0", {}).get("mac_and_hostname") else "0"
        ),
    }


def _ip_octets(prefix, ip):
    parts = ip.split(".")
    return {f"{prefix}{i}": parts[i] for i in range(4)}


def _build_payload(current, desired_first, desired_second):
    return {
        "page": "dnsSrv",
        "xhr": "1",
        "apply": "true",
        "lang": "de",
        "ipv4_use_user_dns": "1",
        **_ip_octets("ipv4_user_firstdns", desired_first),
        **_ip_octets("ipv4_user_seconddns", desired_second),
        "ipv6_use_user_dns": current["v6_use_user_dns"],
        "ipv6_user_firstdns": current["v6_first"],
        "ipv6_user_seconddns": current["v6_second"],
        "public_enabled": current["public_enabled"],
        "edns0_mac_and_hostname": current["edns0_mac_and_hostname"],
        "dot_enabled": current["dot_enabled"],
        "dot_strict": current["dot_strict"],
        "dot_udp_fallback": current["dot_udp_fallback"],
        "dot_fqdn_list": current["dot_fqdn_list"],
    }


def _extract_totp_secret(totp_secret):
    if totp_secret.startswith("otpauth://"):
        parsed = urllib.parse.urlparse(totp_secret)
        params = urllib.parse.parse_qs(parsed.query)
        secrets = params.get("secret", [])
        if not secrets:
            raise Exception("No secret= found in otpauth URI")
        return secrets[0]
    return totp_secret


def _generate_totp(secret_str, digits=6, period=30):
    key = base64.b32decode(secret_str.upper().replace(" ", ""))
    counter = int(time.time()) // period
    msg = struct.pack(">Q", counter)
    digest = hmac.new(key, msg, hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return str(code % (10**digits)).zfill(digits)


def _apply_dns(host, sid, current, desired_first, desired_second, totp_secret):
    payload = _build_payload(current, desired_first, desired_second)

    resp = _spa_post(host, sid, payload)
    resp.raise_for_status()
    data = resp.json().get("data", {})
    apply_status = data.get("apply")

    if apply_status == "ok":
        return

    if apply_status != "twofactor":
        raise Exception(f"Unexpected apply response: {data}")

    twofactor_str = data.get("twofactor", "")
    if "starterror" in twofactor_str:
        code = twofactor_str.split(";")[1] if ";" in twofactor_str else ""
        if code == "92":
            raise Exception(
                "Fritz!Box 2FA is locked for 60 minutes after too many failed attempts. "
                "Wait before retrying."
            )
        _tfa_post(host, sid, {"tfa_cancel": ""})
        resp = _spa_post(host, sid, payload)
        resp.raise_for_status()
        data = resp.json().get("data", {})
        apply_status = data.get("apply")
        twofactor_str = data.get("twofactor", "")
        if apply_status != "twofactor" or "starterror" in twofactor_str:
            raise Exception(f"2FA unavailable after cancel: {data}")

    if not totp_secret:
        raise Exception(
            "Fritz!Box requires 2FA to change DNS settings. "
            "Provide totp_secret (bare base32 or otpauth:// URI)."
        )

    raw_secret = _extract_totp_secret(totp_secret)
    otp_code = _generate_totp(raw_secret)
    tfa_resp = _tfa_post(host, sid, {"tfa_googleauth": otp_code})
    tfa_resp.raise_for_status()
    tfa_data = tfa_resp.json()
    if tfa_data.get("err") == 1:
        raise Exception(f"TOTP rejected by Fritz!Box: {tfa_data}")

    for _ in range(30):
        time.sleep(1)
        poll_resp = _tfa_post(host, sid, {"tfa_active": ""})
        poll_resp.raise_for_status()
        poll = poll_resp.json()
        if poll.get("done"):
            if not poll.get("active"):
                raise Exception("2FA was denied or timed out")
            break
    else:
        raise Exception("2FA polling timed out after 30 seconds")

    resp2 = _spa_post(host, sid, payload)
    resp2.raise_for_status()
    data2 = resp2.json().get("data", {})
    if data2.get("apply") != "ok":
        raise Exception(f"Final DNS apply failed: {data2}")


def main():
    module = AnsibleModule(
        argument_spec={
            "host": {"type": "str", "required": True},
            "username": {"type": "str", "default": ""},
            "password": {"type": "str", "default": "", "no_log": True},
            "upstream_dns": {
                "type": "list",
                "elements": "str",
                "required": True,
            },
            "totp_secret": {"type": "str", "default": None, "no_log": True},
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
    desired_dns = module.params["upstream_dns"]
    totp_secret = module.params["totp_secret"]

    desired_first = desired_dns[0] if len(desired_dns) > 0 else ""
    desired_second = desired_dns[1] if len(desired_dns) > 1 else ""

    try:
        sid = get_sid(host, username, password)
        current = _read_dns(host, sid)
    except Exception as e:
        module.fail_json(msg=f"Failed to read DNS settings from {host}: {e}")

    if current["v4_first"] == desired_first and current["v4_second"] == desired_second:
        module.exit_json(
            changed=False,
            dns={"firstdns": current["v4_first"], "seconddns": current["v4_second"]},
        )

    diff = {
        "before": {"firstdns": current["v4_first"], "seconddns": current["v4_second"]},
        "after": {"firstdns": desired_first, "seconddns": desired_second},
    }

    if module.check_mode:
        module.exit_json(changed=True, diff=diff)

    try:
        _apply_dns(host, sid, current, desired_first, desired_second, totp_secret)
    except Exception as e:
        module.fail_json(
            msg=f"Failed to apply DNS settings to {host}: {e}", diff=diff
        )

    module.exit_json(
        changed=True,
        diff=diff,
        dns={"firstdns": desired_first, "seconddns": desired_second},
    )


if __name__ == "__main__":
    main()

import hashlib
import urllib3
import xml.etree.ElementTree as ET

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

try:
    import requests

    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


def get_sid(host, username, password):
    r = requests.get(f"http://{host}/login_sid.lua?version=2", timeout=10)
    root = ET.fromstring(r.text)
    challenge = root.find("Challenge").text
    parts = challenge.split("$")
    _, iter1, salt1, iter2, salt2 = parts
    h1 = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), bytes.fromhex(salt1), int(iter1)
    )
    h2 = hashlib.pbkdf2_hmac("sha256", h1, bytes.fromhex(salt2), int(iter2))
    r2 = requests.post(
        f"http://{host}/login_sid.lua?version=2",
        data={"username": username, "response": f"{salt2}${h2.hex()}"},
        timeout=10,
    )
    sid = ET.fromstring(r2.text).find("SID").text
    if sid == "0000000000000000":
        raise Exception("Authentication failed")
    return sid


def api_headers(sid):
    return {"Authorization": f"AVM-SID {sid}", "Content-Type": "application/json"}

# pschmitt.fritzbox

Ansible collection for managing AVM Fritz!Box routers.

## Modules

| Module | Description |
|--------|-------------|
| `pschmitt.fritzbox.facts` | Gather device and WAN facts via TR-064 |
| `pschmitt.fritzbox.lan` | Configure LAN IP and DHCP settings |
| `pschmitt.fritzbox.wlan` | Configure WLAN networks and global enable |
| `pschmitt.fritzbox.dns` | Configure upstream DNS servers (with 2FA support) |
| `pschmitt.fritzbox.dns_rebind` | Manage DNS rebind exception domains |
| `pschmitt.fritzbox.led` | Configure LED display mode |
| `pschmitt.fritzbox.name` | Set the Fritz!Box device name |
| `pschmitt.fritzbox.route` | Manage static routes |

## Requirements

- `requests` (for REST/SPA API modules)
- `fritzconnection` (for TR-064 modules: `facts`, `lan`, `wlan`)

## Installation

```bash
ansible-galaxy collection install git+https://github.com/pschmitt/ansible-collection-fritzbox.git
```

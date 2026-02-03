import subprocess
import re


WLAN_DEVICE = "wlan0"
AP_PROFILE_NAME = "AccessPopup"


def _run(cmd, timeout=15):
    """Run a shell command and return stdout."""
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=timeout
        )
        return result.stdout.strip(), result.returncode
    except subprocess.TimeoutExpired:
        return "", 1


def get_wifi_status():
    """Return current WiFi status: mode, ssid, ip address."""
    status = {"mode": None, "ssid": None, "ip": None}

    # Get active connection name on wlan0
    out, _ = _run(
        f"nmcli -t -f NAME,DEVICE connection show --active | grep {WLAN_DEVICE}"
    )
    if not out:
        return status

    active_name = out.split(":")[0]
    status["ssid"] = active_name

    # Check if AP or STA
    out, _ = _run(f'nmcli -t -f 802-11-wireless.mode connection show "{active_name}"')
    if out:
        mode_val = out.split(":")[-1].strip()
        if mode_val == "ap":
            status["mode"] = "AP"
        elif mode_val == "infrastructure":
            status["mode"] = "STA"

    # Get IP address
    out, _ = _run(
        f'nmcli -t -f IP4.ADDRESS connection show "{active_name}" | head -1'
    )
    if out:
        # Format is IP4.ADDRESS[1]:192.168.x.x/24
        ip_part = out.split(":")[-1]
        if "/" in ip_part:
            ip_part = ip_part.split("/")[0]
        status["ip"] = ip_part

    return status


def scan_networks():
    """Scan for nearby WiFi networks. Returns list of dicts with ssid, signal, security."""
    networks = []
    # Rescan
    _run(f"nmcli device wifi rescan ifname {WLAN_DEVICE}", timeout=10)

    # List available networks
    out, rc = _run(
        f"nmcli -t -f SSID,SIGNAL,SECURITY device wifi list ifname {WLAN_DEVICE}"
    )
    if rc != 0 or not out:
        return networks

    seen = set()
    for line in out.splitlines():
        parts = line.split(":")
        if len(parts) < 3:
            continue
        ssid = parts[0].strip()
        if not ssid or ssid == "--" or ssid in seen:
            continue
        seen.add(ssid)
        try:
            signal = int(parts[1])
        except ValueError:
            signal = 0
        security = parts[2] if len(parts) > 2 else ""
        networks.append({"ssid": ssid, "signal": signal, "security": security})

    # Sort by signal strength descending
    networks.sort(key=lambda x: x["signal"], reverse=True)
    return networks


def get_saved_profiles():
    """Return list of saved WiFi profile names (STA mode only)."""
    profiles = []
    out, _ = _run("nmcli -t -f NAME,TYPE connection show")
    if not out:
        return profiles
    for line in out.splitlines():
        parts = line.split(":")
        if len(parts) < 2:
            continue
        name = parts[0]
        conn_type = parts[1]
        if conn_type != "802-11-wireless":
            continue
        # Check if infrastructure (not AP)
        mode_out, _ = _run(
            f'nmcli -t -f 802-11-wireless.mode connection show "{name}"'
        )
        if mode_out and "infrastructure" in mode_out:
            profiles.append(name)
    return profiles


def connect_to_network(ssid, password=None):
    """Connect to a WiFi network. If a saved profile exists, use it. Otherwise create one."""
    # Stop the AccessPopup timer so it doesn't switch us back
    _run("sudo systemctl stop AccessPopup.timer")

    # Bring down current connection on wlan0
    out, _ = _run(
        f"nmcli -t -f NAME,DEVICE connection show --active | grep {WLAN_DEVICE}"
    )
    if out:
        active_name = out.split(":")[0]
        _run(f'nmcli connection down "{active_name}"')

    # Try connecting with saved profile first
    cmd_out, rc = _run(f'nmcli connection up "{ssid}"')
    if rc == 0:
        # Restart the timer so it can maintain the connection
        _run("sudo systemctl start AccessPopup.timer")
        return True, "Connected to " + ssid

    # No saved profile or connection failed, try with password
    if password:
        cmd_out, rc = _run(
            f'nmcli device wifi connect "{ssid}" password "{password}" ifname {WLAN_DEVICE}'
        )
        if rc == 0:
            _run("sudo systemctl start AccessPopup.timer")
            return True, "Connected to " + ssid
        return False, "Failed to connect: " + cmd_out

    return False, "No saved profile for this network. Please provide a password."


def switch_to_hotspot():
    """Switch from WiFi STA mode to the AccessPopup hotspot."""
    # Stop the timer
    _run("sudo systemctl stop AccessPopup.timer")

    # Bring down current connection on wlan0
    out, _ = _run(
        f"nmcli -t -f NAME,DEVICE connection show --active | grep {WLAN_DEVICE}"
    )
    if out:
        active_name = out.split(":")[0]
        _run(f'nmcli connection down "{active_name}"')

    # Check if AP profile exists
    out, _ = _run(f'nmcli -t -f NAME connection show | grep "^{AP_PROFILE_NAME}$"')
    if not out:
        # Create the AP profile
        _run(
            f'nmcli device wifi hotspot ifname {WLAN_DEVICE} con-name "{AP_PROFILE_NAME}" '
            f'ssid "{AP_PROFILE_NAME}" band bg channel 6 password "1234567890"'
        )
        _run(
            f'nmcli connection mod "{AP_PROFILE_NAME}" ipv4.method shared '
            f'ipv4.addr "192.168.50.5/24" ipv4.gateway "192.168.50.254"'
        )
        _run("nmcli con reload")

    # Activate the hotspot
    cmd_out, rc = _run(f'nmcli connection up "{AP_PROFILE_NAME}"')
    if rc == 0:
        # Restart the timer
        _run("sudo systemctl start AccessPopup.timer")
        return True, "Hotspot activated"

    return False, "Failed to activate hotspot: " + cmd_out


def forget_network(ssid):
    """Delete a saved WiFi profile."""
    cmd_out, rc = _run(f'nmcli connection delete "{ssid}"')
    if rc == 0:
        return True, f"Forgot network {ssid}"
    return False, "Failed to forget network: " + cmd_out

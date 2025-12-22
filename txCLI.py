"""
Telex Device - Command Line Interface

revised version:
- reacts to ESC+CLI OR dial 009
- provides status and basic control over the host system
"""
__author__      = "Jochen Krapf"
__revisor__     = "Wolfram Henkel"
__email__       = "jk@nerd2nerd.org"
__email2__      = "wolfhenk@wolfhenk.de"
__copyright__   = "Copyright 2020, JK"
__license__     = "GPL3"
__version__     = "2.3.1"



import logging
l = logging.getLogger("piTelex." + __name__)
import os

if os.name == 'nt':
    def get_shell_result(cmd: str) -> str:
        return "\r\r\n...ach bass emal uff, mir gehn nur uff linux...\r\r\n"

else:   # Linux and RPi
    import subprocess

    def get_shell_result(cmd: str) -> str:
        ret = subprocess.check_output(cmd, shell=True)
        ret = ret.decode("utf-8", "ignore") \
                 .replace('@', '?') \
                 .replace('#', '?') \
                 .replace('%', ' percent') \
                 .replace('\n', '\r\r\n')
        return ret


#######

def get_IP() -> str:
    """
    Legacy: returns one IP and hostname (kept for compatibility, currently unused).
    """
    import socket
    hostname = socket.gethostname()
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip_address = (s.getsockname()[0])
    except Exception:
        ip_address = '-'
    finally:
        s.close()
    return str(ip_address) + ' ' + hostname


#######

def get_IP_all() -> str:
    """
    Show all IPv4 addresses per interface (without lo), e.g.:
    eth0  192.168.x.y HOSTNAME
    wlan0 192.168.a.b HOSTNAME SSID
    """
    import subprocess
    import socket

    hostname = socket.gethostname()

    try:
        out = subprocess.check_output(
            "ip -o -4 addr show",
            shell=True,
            stderr=subprocess.DEVNULL
        ).decode("utf-8", "ignore")
    except Exception:
        return "NO IP"

    lines_out = []

    for line in out.splitlines():
        parts = line.split()
        if len(parts) < 4:
            continue

        iface = parts[1]
        if iface == 'lo':
            continue  # omit loopback

        cidr = parts[3]          # 192.168.3.150/24
        ip = cidr.split('/')[0]  # 192.168.3.150

        entry = f"{iface} {ip} {hostname}"

        if iface.startswith("wl") or "wlan" in iface:
            try:
                ssid = subprocess.check_output(
                    f"iwgetid {iface} -r",
                    shell=True,
                    stderr=subprocess.DEVNULL
                ).decode("utf-8", "ignore").strip()
                if ssid:
                    entry += f" {ssid}"
            except Exception:
                pass

        lines_out.append(entry)

    if not lines_out:
        return "NO IP"

    result = "\r\r\n".join(lines_out)
    result = result.replace('@', '?').replace('#', '?')
    return result


#######

def get_IP_external() -> str:
    """
    Show the external (public) IPv4 address, as far as it can be determined.
    """
    import subprocess

    commands = [
        "curl -s https://ifconfig.me",
        "curl -s https://api.ipify.org",
        "wget -qO- https://ifconfig.me",
        "wget -qO- https://api.ipify.org",
        "dig +short myip.opendns.com @resolver1.opendns.com"
    ]

    for cmd in commands:
        try:
            out = subprocess.check_output(
                cmd,
                shell=True,
                stderr=subprocess.DEVNULL
            ).decode("utf-8", "ignore").strip()
            if not out:
                continue
            ip = out.split()[0]
            ip = ip.replace('@', '?').replace('#', '?').replace('\n', '\r\r\n')
            return f"external ip-address is {ip}."
        except Exception:
            continue

    return "external ip-address can not be determined."


#######

def get_wlan_ip() -> str:
    """
    Show the IPv4 address of wlan0 without CIDR or '' if empty.
    """
    import subprocess
    try:
        ip = subprocess.check_output(
            "ip -4 addr show wlan0 | awk '/inet /{print $2}' | cut -d/ -f1",
            shell=True,
            stderr=subprocess.DEVNULL
        ).decode("utf-8", "ignore").strip()
        return ip
    except Exception:
        return ''


def get_WLAN_from_sudo(password: str) -> str:
    """
    Executes 'sudo iw wlan0 scan' and inspects SSIDs.

    Output format (one line per SSID):
        +++ SSID IP   for the active network (if wlan0 has an IP)
        --- SSID      for all other networks
    """
    import subprocess

    try:
        active_ssid = subprocess.check_output(
            "iwgetid -r",
            shell=True,
            stderr=subprocess.DEVNULL
        ).decode("utf-8", "ignore").strip()
    except Exception:
        active_ssid = ''

    wlan_ip = get_wlan_ip()

    proc = subprocess.Popen(
        ['sudo', '-S', 'iw', 'wlan0', 'scan'],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    out, err = proc.communicate((password + '\n').encode('utf-8'))

    if proc.returncode != 0:
        return "NO WLAN"

    scan_output = out.decode('utf-8', 'ignore')

    seen = set()
    lines = []

    for line in scan_output.splitlines():
        line = line.strip()
        if "SSID:" not in line:
            continue

        ssid = line.split("SSID:", 1)[1].strip().strip('"')
        if not ssid or ssid == "<hidden>":
            continue

        if ssid in seen:
            continue
        seen.add(ssid)

        is_active = bool(active_ssid and ssid == active_ssid)
        marker = "+++" if is_active else "---"

        entry = f"{marker} {ssid}"
        if is_active and wlan_ip:
            entry += f" {wlan_ip}"

        lines.append(entry)

    if not lines:
        return "NO WLAN"

    result = "\r\r\n".join(lines)
    result = result.replace('@', '?').replace('#', '?')
    return result


#######
# WPS / NetworkManager support
#######

WPS_ERR_OK               = 0
WPS_ERR_ILLEGAL_PASSWORD = 1
WPS_ERR_WPA_START        = 2
WPS_ERR_WPA_STATUS       = 3
WPS_ERR_WPS_NO_SIGNAL    = 4
WPS_ERR_WPS_TIMEOUT      = 5
WPS_ERR_WPA_CONF_READ    = 6
WPS_ERR_WPA_CONF_PARSE   = 7
WPS_ERR_NM_MODIFY        = 8
WPS_ERR_NM_ADD           = 9

WPS_ERROR_TEXT = {
    WPS_ERR_ILLEGAL_PASSWORD:
        "Error 1: no sudo password entered",
    WPS_ERR_WPA_START:
        "Error 2: WPS error: could not start wpa_supplicant",
    WPS_ERR_WPA_STATUS:
        "Error 3: WPS error: no connection to wpa_supplicant",
    WPS_ERR_WPS_NO_SIGNAL:
        "Error 4: WPS error: no active WPS signal found",
    WPS_ERR_WPS_TIMEOUT:
        "Error 5: WPS error: timeout, access point does not respond",
    WPS_ERR_WPA_CONF_READ:
        "Error 6: WPS error: could not read WPS configuration",
    WPS_ERR_WPA_CONF_PARSE:
        "Error 7: WPS error: SSID/password not readable from WPS configuration",
    WPS_ERR_NM_MODIFY:
        "Error 8: network error: could not update NetworkManager connection",
    WPS_ERR_NM_ADD:
        "Error 9: network error: could not create NetworkManager connection",
}


def sudo_needs_password() -> bool:
    """
    Returns True if sudo requires a password, False if it can run without
    (e.g. NOPASSWD or running as root).
    """
    import subprocess
    try:
        rc = subprocess.call(
            ["sudo", "-n", "true"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        # rc == 0 -> sudo runs without password
        # rc != 0 -> sudo would require a password
        return rc != 0
    except Exception:
        # be conservative on unexpected errors
        return True


def _wps_sudo_run(password: str, args, capture_output: bool = False):
    """
    Run a command via sudo for WPS handling.

    If a non-empty password is given, it is passed via -S.
    If password is empty (e.g. NOPASSWD setup), sudo is called without -S
    and without stdin input.
    """
    import subprocess

    if password:
        cmd = ["sudo", "-S"] + list(args)
        input_data = (password + "\n").encode("utf-8")
    else:
        cmd = ["sudo"] + list(args)
        input_data = None

    try:
        proc = subprocess.run(
            cmd,
            input=input_data,
            stdout=subprocess.PIPE if capture_output else subprocess.DEVNULL,
            stderr=subprocess.STDOUT if capture_output else subprocess.DEVNULL,
            check=False,
        )
    except Exception:
        return None
    return proc


def _sudo_schedule(password: str, shell_cmd: str) -> bool:
    """
    Start a sudo bash -c 'shell_cmd' process in the background (non-blocking for CLI).
    """
    import subprocess
    try:
        p = subprocess.Popen(
            ["sudo", "-S", "bash", "-c", shell_cmd],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            p.stdin.write((password + "\n").encode("utf-8"))
            p.stdin.close()
        except Exception:
            pass
        return True
    except Exception:
        return False


def wlan_wps_nm_sudo(password: str, iface: str = "wlan0", country: str = "DE"):
    import time
    import tempfile

    TIMEOUT_WPS = 120
    PING_TARGET = "8.8.8.8"
    PING_COUNT  = 3
    PING_TIMEOUT = 3

    # Only treat empty password as error if sudo actually requires one.
    if not password and sudo_needs_password():
        return (WPS_ERR_ILLEGAL_PASSWORD, "", "")

    tmp_conf = None

    def start_nm():
        _wps_sudo_run(password, ["systemctl", "start", "NetworkManager"])

    try:
        _wps_sudo_run(password, ["systemctl", "stop", "NetworkManager"])
        _wps_sudo_run(password, ["pkill", "wpa_supplicant"])
        time.sleep(1)

        fd, tmp_conf = tempfile.mkstemp(prefix="wps-wpa-", suffix=".conf")
        os.close(fd)
        with open(tmp_conf, "w", encoding="utf-8") as f:
            f.write("ctrl_interface=/run/wpa_supplicant\n")
            f.write("update_config=1\n")
            f.write("country=%s\n" % country)

        proc = _wps_sudo_run(password, ["wpa_supplicant", "-B", "-i", iface, "-c", tmp_conf])
        if not proc or proc.returncode != 0:
            start_nm()
            return (WPS_ERR_WPA_START, "", "")

        time.sleep(1)

        proc = _wps_sudo_run(password, ["wpa_cli", "-i", iface, "status"], capture_output=True)
        if (not proc) or proc.returncode != 0 or not proc.stdout:
            _wps_sudo_run(password, ["wpa_cli", "-i", iface, "terminate"])
            start_nm()
            return (WPS_ERR_WPA_STATUS, "", "")

        proc = _wps_sudo_run(password, ["wpa_cli", "-i", iface, "wps_pbc"], capture_output=True)
        if (not proc) or ("FAIL" in proc.stdout.decode("utf-8", "ignore").upper()):
            _wps_sudo_run(password, ["wpa_cli", "-i", iface, "terminate"])
            start_nm()
            return (WPS_ERR_WPS_NO_SIGNAL, "", "")

        ssid = ""
        deadline = time.time() + TIMEOUT_WPS
        while time.time() < deadline:
            proc = _wps_sudo_run(password, ["wpa_cli", "-i", iface, "status"], capture_output=True)
            if not proc or proc.returncode != 0 or not proc.stdout:
                break
            info = {}
            for line in proc.stdout.decode("utf-8", "ignore").splitlines():
                if "=" in line:
                    k, v = line.split("=", 1)
                    info[k.strip()] = v.strip()
            if info.get("wpa_state") == "COMPLETED":
                ssid = info.get("ssid", "")
                break
            time.sleep(2)

        if not ssid:
            _wps_sudo_run(password, ["wpa_cli", "-i", iface, "terminate"])
            start_nm()
            return (WPS_ERR_WPS_TIMEOUT, "", "")

        _wps_sudo_run(password, ["wpa_cli", "-i", iface, "save_config"])
        _wps_sudo_run(password, ["wpa_cli", "-i", iface, "terminate"])
        time.sleep(1)

        proc = _wps_sudo_run(password, ["cat", tmp_conf], capture_output=True)
        if not proc or proc.returncode != 0 or not proc.stdout:
            start_nm()
            return (WPS_ERR_WPA_CONF_READ, "", "")

        cfg_txt = proc.stdout.decode("utf-8", "ignore")
        ssid_cfg = ""
        psk_cfg  = ""
        for line in cfg_txt.splitlines():
            line = line.strip()
            if line.startswith("ssid="):
                v = line.split("=", 1)[1].strip()
                if v.startswith('"') and v.endswith('"') and len(v) >= 2:
                    v = v[1:-1]
                ssid_cfg = v
            elif line.startswith("psk="):
                v = line.split("=", 1)[1].strip()
                if v.startswith('"') and v.endswith('"') and len(v) >= 2:
                    v = v[1:-1]
                psk_cfg = v

        if not ssid_cfg or not psk_cfg:
            start_nm()
            return (WPS_ERR_WPA_CONF_PARSE, "", "")

        start_nm()
        time.sleep(2)

        con_name = ssid_cfg

        proc = _wps_sudo_run(
            password,
            ["nmcli", "-t", "-f", "NAME,TYPE", "connection", "show"],
            capture_output=True
        )
        has_con = False
        if proc and proc.stdout:
            for line in proc.stdout.decode("utf-8", "ignore").splitlines():
                name, _, typ = line.partition(":")
                if typ == "802-11-wireless" and name == con_name:
                    has_con = True
                    break

        if has_con:
            proc = _wps_sudo_run(password, [
                "nmcli", "connection", "modify", con_name,
                "connection.id", con_name,
                "802-11-wireless.ssid", ssid_cfg,
                "wifi-sec.key-mgmt", "wpa-psk",
                "wifi-sec.psk", psk_cfg,
                "connection.autoconnect", "yes",
            ])
            if not proc or proc.returncode != 0:
                return (WPS_ERR_NM_MODIFY, "", "")
        else:
            proc = _wps_sudo_run(password, [
                "nmcli", "connection", "add",
                "type", "wifi",
                "ifname", iface,
                "con-name", con_name,
                "ssid", ssid_cfg,
                "wifi-sec.key-mgmt", "wpa-psk",
                "wifi-sec.psk", psk_cfg,
                "connection.autoconnect", "yes",
            ])
            if not proc or proc.returncode != 0:
                return (WPS_ERR_NM_ADD, "", "")

        cfg_path = "/etc/NetworkManager/system-connections/%s.nmconnection" % con_name
        _wps_sudo_run(password, ["chmod", "600", cfg_path])
        _wps_sudo_run(password, ["nmcli", "connection", "reload"])
        _wps_sudo_run(password, ["nmcli", "device", "disconnect", iface])
        _wps_sudo_run(password, ["nmcli", "connection", "up", con_name])

        ip_now = "0.0.0.0"
        proc = _wps_sudo_run(password, ["ip", "-4", "addr", "show", iface], capture_output=True)
        if proc and proc.stdout:
            for line in proc.stdout.decode("utf-8", "ignore").splitlines():
                line = line.strip()
                if line.startswith("inet "):
                    ip_now = line.split()[1].split("/")[0]
                    break

        proc = _wps_sudo_run(password, [
            "ping", "-I", iface, "-c", str(PING_COUNT),
            "-W", str(PING_TIMEOUT), PING_TARGET
        ])
        if proc and proc.returncode != 0:
            act_name = None
            proc = _wps_sudo_run(password, [
                "nmcli", "-t", "-f", "NAME,DEVICE,TYPE",
                "connection", "show", "--active"
            ], capture_output=True)
            if proc and proc.stdout:
                for line in proc.stdout.decode("utf-8", "ignore").splitlines():
                    name, _, rest = line.partition(":")
                    dev, _, typ = rest.partition(":")
                    if typ == "802-11-wireless" and dev == iface:
                        act_name = name
                        break
            if act_name:
                p_act = 0
                p_proc = _wps_sudo_run(password, [
                    "nmcli", "-g", "connection.autoconnect-priority",
                    "connection", "show", act_name
                ], capture_output=True)
                if p_proc and p_proc.stdout:
                    try:
                        p_act = int(p_proc.stdout.decode("utf-8", "ignore").strip())
                    except ValueError:
                        p_act = 0

                min_other = None
                list_proc = _wps_sudo_run(password, [
                    "nmcli", "-t", "-f", "NAME,TYPE", "connection", "show"
                ], capture_output=True)
                if list_proc and list_proc.stdout:
                    for line in list_proc.stdout.decode("utf-8", "ignore").splitlines():
                        name, _, typ = line.partition(":")
                        if typ != "802-11-wireless" or name == act_name:
                            continue
                        pp = 0
                        p2 = _wps_sudo_run(password, [
                            "nmcli", "-g", "connection.autoconnect-priority",
                            "connection", "show", name
                        ], capture_output=True)
                        if p2 and p2.stdout:
                            try:
                                pp = int(p2.stdout.decode("utf-8", "ignore").strip())
                            except ValueError:
                                pp = 0
                        if min_other is None or pp < min_other:
                            min_other = pp

                if (min_other is not None) and (p_act >= min_other):
                    new_p = min_other - 1
                    _wps_sudo_run(password, [
                        "nmcli", "connection", "modify", act_name,
                        "connection.autoconnect-priority", str(new_p),
                    ])

        ssid_safe = ssid_cfg.replace('@', '?').replace('#', '?')
        ip_safe   = ip_now.replace('@', '?').replace('#', '?')
        return (WPS_ERR_OK, ssid_safe, ip_safe)

    finally:
        if tmp_conf and os.path.exists(tmp_conf):
            try:
                os.unlink(tmp_conf)
            except OSError:
                pass


#######

class CLI():
    def __init__(self, **params):
        self.params = params
        self.keyboard_mode = '<'
        self._wlan_wait_password = False

        self._wps_wait_password = False
        self._wps_wait_confirm = False
        self._wps_password = ""

        self._reboot_wait_password = False
        self._shutdown_wait_password = False

        self._lupd_wait_password = False

        self.id = 'CLI'

    def command(self, cmd_in: str) -> str:
                # waiting for REBOOT confirmation j/y
        if getattr(self, "_reboot_wait_password", False):
            ch = cmd_in.strip().lower()
            self._reboot_wait_password = False

            if ch not in ('j', 'y'):
                ans = "reboot aborted"
                ans += "\r\r\n: "
                ans += self.keyboard_mode
                return ans

            ok = _sudo_schedule("", "sleep 10; systemctl reboot")
            if not ok:
                ans = "reboot failed"
                ans += "\r\r\n: "
                ans += self.keyboard_mode
                return ans

            return 'BYE\r\n'

        # waiting for SHUTDOWN confirmation j/y
        if getattr(self, "_shutdown_wait_password", False):
            ch = cmd_in.strip().lower()
            self._shutdown_wait_password = False

            if ch not in ('j', 'y'):
                ans = "shutdown aborted"
                ans += "\r\r\n: "
                ans += self.keyboard_mode
                return ans

            ok = _sudo_schedule("", "sleep 10; systemctl poweroff")
            if not ok:
                ans = "shutdown failed"
                ans += "\r\r\n: "
                ans += self.keyboard_mode
                return ans

            return 'BYE\r\n'

        # waiting for LUPD confirmation j/y
        if getattr(self, "_lupd_wait_password", False):
            ch = cmd_in.strip().lower()
            self._lupd_wait_password = False

            if ch not in ('j', 'y'):
                ans = "linux update aborted"
            else:
                cmd = (
                    "DEBIAN_FRONTEND=noninteractive apt-get update && "
                    "DEBIAN_FRONTEND=noninteractive apt-get -y upgrade"
                )
                ok = _sudo_schedule("", cmd)
                if not ok:
                    ans = "linux update could not be started"
                else:
                    ans = "linux update started in background"

            ans += "\r\r\n: "
            ans += self.keyboard_mode
            return ans

        # waiting for WPS confirmation j/y
        if getattr(self, "_wps_wait_confirm", False):
            ch = cmd_in[0].lower() if cmd_in else ''

            self._wps_wait_confirm = False

            if ch in ('j', 'y'):
                code, ssid_safe, ip_safe = wlan_wps_nm_sudo("", iface="wlan0", country="DE")
                if code == WPS_ERR_OK:
                    if ip_safe == "0.0.0.0":
                        ans = f"connected to {ssid_safe}, IP unknown"
                    else:
                        ans = f"connected to {ssid_safe}, IP {ip_safe}"
                else:
                    errtxt = WPS_ERROR_TEXT.get(code, f"Error {code}: unknown error")
                    ans = errtxt
            else:
                ans = "WPS aborted"

            ans += "\r\r\n: "
            ans += self.keyboard_mode
            return ans

        ans = ''
        cmd = ''
        cmd_in = cmd_in.upper().strip()
        for c in cmd_in:
            if c in '<>':
                self.keyboard_mode = c
            else:
                cmd += c

        if cmd == 'WHOAMI':
            ans = '<<<\r\r\nPITELEX-CLI - INTERNAL COMMAND LINE INTERFACE\r\r\nHELP or ? FOR HELP.\r\r\n'

        elif cmd in ['KG', 'WRU']:
            ans = self.params.get('wru_id', 'NO')

        elif cmd == 'PING':
            try:
                ans = get_shell_result("ping -c 4 8.8.8.8")
            except Exception:
                ans = "PING FAILED 8.8.8.8"

        elif cmd == 'IP':
            ans = get_IP_all()

        elif cmd == 'PORT':
            devices = self.params.get('devices', None)
            if devices:
                for name, dev in devices.items():
                    if dev.get('enable') and dev.get('type') == 'i-Telex':
                        ans = str(dev.get('port', 'NO PORT'))

        elif cmd in ['DEV', 'DEVICES']:
            devices = self.params.get('devices', None)
            if devices:
                for name, dev in devices.items():
                    if dev.get('enable'):
                        ans += '\r\r\n{}: {}'.format(name, dev.get('type', 'UNKNOWN'))

        elif cmd == 'EXIT':
            return 'BYE\r\n'

        elif cmd == 'IPX':
            ans = get_IP_external()

        elif cmd == 'CPU':
            ans = get_shell_result(
                "top -bn1 | grep \"load average\" | awk '{printf \"CPU Load: %.2f percent\\n\", $(NF-2)}'"
            )

        elif cmd == 'MEM':
            ans = get_shell_result(
                "free -m | awk 'NR==2{printf \"Mem: %s/%sMB %.2f percent\\n\", $3,$2,$3*100/$2 }'"
            )

        elif cmd == 'DISK':
            ans = get_shell_result(
                "df -h / | awk 'NR==2{gsub(\"%\",\" percent\",$5); printf \"Disk: %s/%s %s\\n\", $3,$2,$5}'"
            )

        elif cmd == 'UPTIME':
            ans = get_shell_result("uptime -p")

        elif cmd == 'W':
            ans = get_shell_result("w -us")

        elif cmd == 'WLAN':
            ans = get_WLAN_from_sudo("")
            if ans == '':
                ans = '?'

        elif cmd == 'WPS':
            self._wps_wait_confirm = True
            ans = "WPS button on router pressed? (j/y)"
            ans += "\r\r\n-this may take up to 2 minutes...\r\r\n: "
            ans += self.keyboard_mode
            return ans

        elif cmd == 'REBOOT':
            self._reboot_wait_password = True
            ans = "reboot system? (j/y)"

        elif cmd == 'SHUTDOWN':
            self._shutdown_wait_password = True
            ans = "shutdown system? (j/y)"

        elif cmd == 'LUPD':
            self._lupd_wait_password = True
            ans = "start linux update? (j/y)"

        elif cmd in ['HELP', '?']:
            ans = (
                "\r\r\nAVAILABLE COMMANDS:\r\r\n"
                "HELP, ?        - show this help\r\r\n"
                "CPU            - show CPU load\r\r\n"
                "DEV, DEVICES   - list enabled devices\r\r\n"
                "DISK           - show root filesystem usage\r\r\n"
                "IP             - list local interfaces and IPv4 addresses\r\r\n"
                "IPX            - show external (WAN) IPv4 address\r\r\n"
                "KG, WRU        - show WRU ID\r\r\n"
                "LUPD           - linux system update (apt-get update/upgrade)\r\r\n"
                "MEM            - show memory usage\r\r\n"
                "PING           - ping 8.8.8.8, (4 packets)\r\r\n"
                "PORT           - show i-Telex port (if configured)\r\r\n"
                "UPTIME         - show system uptime\r\r\n"
                "W              - show logged in users\r\r\n"
                "WHOAMI         - identify this CLI\r\r\n"
                "WLAN           - scan WLAN networks\r\r\n"
                "WPS            - connect WLAN via WPS\r\r\n"
                "REBOOT         - reboot system\r\r\n"
                "SHUTDOWN       - shutdown system\r\r\n"
                "EXIT           - exit CLI"
            )

        if ans == '':
            ans = '?'
        ans += "\r\r\n: "
        ans += self.keyboard_mode
        return ans


       

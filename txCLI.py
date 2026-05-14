"""
Telex Device - Command Line Interface

revised version:
- reacts to ESC+CLI OR dial 009
- provides status and basic control over the host system
"""
__author__      = "Jochen Krapf (jk)"
__revisor__     = "Wolfram Henkel (wh)"
__revisor2      = "Rolf Obrecht (ro)"
__email__       = "jk@nerd2nerd.org"
__email2__      = "wolfhenk@wolfhenk.de"
__email3__      = "rolf.obrecht@web.de"
__copyright__   = "Copyright 2020, JK"
__license__     = "GPL3"
__version__     = "2.3.8"
__date__        = "2026-05-06"

"""
2.3.7 2026-05-05 (wh)
normalize J/Y confirmations:
- filter all non-letter characters from confirmation input
- accept semi-automatic teletype prefixes like "<j"
- applied to REBOOT, SHUTDOWN, RESTART and WPS confirmation

2.3.8 2026-05-06 (ro)
- translate "hessisch" to english :-)
- deactivate ifconfig.me in get_IP_external() for it delivers no IPv4 info
- group command help list by function, clarify CLI usage string
- start each answer with a new line
- change prompt from ':' to '+?'
- eliminate double CR's, this can be switched on by "double_wr": true in telex.json if needed
  and would result in 4x CR otherwise ...

2.3.9 2026-05-14 (ro)
- For the sake of peace, reinstate the Hessian error message :-)
- clarify system message after network restart
"""

import logging
l = logging.getLogger("piTelex." + __name__)
import os
import threading

if os.name == 'nt':
    def get_shell_result(cmd: str) -> str:
        return "\r\n... CLI commands require linux os...\r\n"

else:   # Linux and RPi
    import subprocess

    def get_shell_result(cmd: str) -> str:
        ret = subprocess.check_output(cmd, shell=True)
        ret = ret.decode("utf-8", "ignore") \
                 .replace('@', '?') \
                 .replace('#', '?') \
                 .replace('%', ' percent') \
                 .replace('\n', '\r\n')
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

    result = "\r\n".join(lines_out)
    result = result.replace('@', '?').replace('#', '?')
    return result


#######

def get_IP_external() -> str:
    """
    Show the external (public) IPv4 address, as far as it can be determined.
    """
    import subprocess

    commands = [
#        "curl -s https://ifconfig.me",  # only delivers IPv6-address
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
            ip = ip.replace('@', '?').replace('#', '?').replace('\n', '\r\n')
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
            entry += f"  /  {wlan_ip}"

        lines.append(entry)

    if not lines:
        return "NO WLAN"

    result = "\r\n".join(lines)
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

def _normalize_confirm_char(text: str) -> str:
    """
    Normalize confirmation input from semi-automatic teleprinters.
    Keep letters only and return the first one in lowercase.
    """
    for ch in text.lower():
        if 'a' <= ch <= 'z':
            return ch
    return ''

#######

class CLI():
    def __init__(self, **params):
        self.params = params
        self.keyboard_mode = '<'
        self._wlan_wait_password = False

        self._wps_wait_password = False
        self._wps_wait_confirm = False
        self._wps_password = ""
        self._wps_running = False
        self._wps_result = None
        self._wps_thread = None

        self._reboot_wait_password = False
        self._shutdown_wait_password = False
        self._restart_wait_password = False


        self.id = 'CLI'

    def _wps_worker(self):
        self._wps_result = wlan_wps_nm_sudo("", iface="wlan0", country="DE")

    def command(self, cmd_in: str) -> str:
                # waiting for REBOOT confirmation j/y
        if getattr(self, "_reboot_wait_password", False):
            ch = _normalize_confirm_char(cmd_in)
            self._reboot_wait_password = False

            if ch not in ('j', 'y'):
                ans = "\rreboot aborted"
                ans += "\r\n+? "
                ans += self.keyboard_mode
                return ans

            ok = _sudo_schedule("", "sleep 10; systemctl reboot")
            if not ok:
                ans = "\rreboot failed"
                ans += "\r\n+? "
                ans += self.keyboard_mode
                return ans

            return '\rBYE\r\n'

        # waiting for SHUTDOWN confirmation j/y
        if getattr(self, "_shutdown_wait_password", False):
            ch = _normalize_confirm_char(cmd_in)
            self._shutdown_wait_password = False

            if ch not in ('j', 'y'):
                ans = "\rshutdown aborted"
                ans += "\r\n+? "
                ans += self.keyboard_mode
                return ans

            ok = _sudo_schedule("", "sleep 10; systemctl poweroff")
            if not ok:
                ans = "\rshutdown failed"
                ans += "\r\n+? "
                ans += self.keyboard_mode
                return ans

            return '\rBYE\r\n'

        # waiting for RESTART confirmation j/y
        if getattr(self, "_restart_wait_password", False):
            ch = _normalize_confirm_char(cmd_in)
            self._restart_wait_password = False

            if ch not in ('j', 'y'):
                ans = "\rrestart aborted"
                ans += "\r\n+? "
                ans += self.keyboard_mode
                return ans

            ok = _sudo_schedule("", "sleep 10; systemctl restart pitelex.service")
            if not ok:
                ans = "\rrestart failed"
                ans += "\r\n+? "
                ans += self.keyboard_mode
                return ans

            return '\rBYE\r\n'

        # WPS is running in background. Return WAIT immediately after j/y.
        # While WPS is still active, every further CLI input returns WAIT.
        # When the worker has finished, the next CLI input returns the result.
        if getattr(self, "_wps_running", False):
            if self._wps_thread and self._wps_thread.is_alive():
                ans = "WAIT..."
            else:
                self._wps_running = False
                code, ssid_safe, ip_safe = self._wps_result or (WPS_ERR_WPA_STATUS, "", "")
                self._wps_result = None
                self._wps_thread = None

                if code == WPS_ERR_OK:
                    if ip_safe == "0.0.0.0":
                        ans = f"connected to {ssid_safe}, IP unknown"
                    else:
                        ans = f"connected to {ssid_safe}, IP {ip_safe}"
                else:
                    errtxt = WPS_ERROR_TEXT.get(code, f"Error {code}: unknown error")
                    ans = errtxt

            ans ="\r" + ans + "\r\n+? "
            ans += self.keyboard_mode
            return ans

        # waiting for WPS confirmation j/y
        # T68d and similar strip printers may need a pure CR after the long
        # WPS prompt to release the 68-character keyboard lock.
        # Ignore such line-end input here and keep waiting for j/y.
        if getattr(self, "_wps_wait_confirm", False):
            cmd_wait = cmd_in.strip()

            if not cmd_wait:
                ans += "\r\n+? "
                ans += self.keyboard_mode
                return ans

            self._wps_wait_confirm = False
            ch = _normalize_confirm_char(cmd_wait)

            if ch in ('j', 'y'):
                self._wps_running = True
                self._wps_result = None
                self._wps_thread = threading.Thread(target=self._wps_worker, daemon=True)
                self._wps_thread.start()
                ans = "WAIT"
            else:
                ans = "WPS aborted"

            ans ="\r" + ans + "\r\n+? "
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
            ans = "<<<\r\nPITELEX-CLI - INTERNAL COMMAND LINE INTERFACE\r\nTERMINATE EACH COMMAND WITH 'LF'\r\nENTER 'HELP' FOR A LIST OF AVAILABLE COMMANDS.\r\n"

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
                        ans += '\r{}: {}\r\n'.format(name, dev.get('type', 'UNKNOWN'))

        elif cmd == 'EXIT':
            return '\rBYE\r\n\n'

        elif cmd == 'IPX':
            ans = get_IP_external()

        elif cmd == 'CPU':
            ans = get_shell_result(
                "top -bn1 | grep \"load average\" | awk '{printf \"CPU Load: %.2f percent\", $(NF-2)}'"
            )

        elif cmd == 'MEM':
            ans = get_shell_result(
                "free -m | awk 'NR==2{printf \"Mem: %s/%sMB %.2f percent\", $3,$2,$3*100/$2 }'"
            )

        elif cmd == 'DISK':
            ans = get_shell_result(
                "df -h / | awk 'NR==2{gsub(\"%\",\" percent\",$5); printf \"Disk: %s/%s %s\", $3,$2,$5}'"
            )

        elif cmd == 'UPTIME':
            ans = get_shell_result("uptime -p").replace("\n","")

        elif cmd == 'W':
            ans = get_shell_result("w -us")

        elif cmd == 'WLAN':
            ans = get_WLAN_from_sudo("")
            if ans == '':
                ans = '?'

        elif cmd == 'WPS':
            self._wps_wait_confirm = True
            ans = "WPS button on router pressed? (y/n)"
            ans += "\r\n-this may take up to 2 minutes...\r\n+? "
            ans += self.keyboard_mode
            return ans

        elif cmd == 'REBOOT':
            self._reboot_wait_password = True
            ans = "reboot system? (y/n)"

        elif cmd == 'SHUTDOWN':
            self._shutdown_wait_password = True
            ans = "shutdown system? (y/n)"

        elif cmd == 'RESTART':
            self._restart_wait_password = True
            ans = "restart pitelex.service? (y/n)"

        elif cmd == 'RLNET':
            ok = _sudo_schedule("", "sleep 2; systemctl restart NetworkManager")
            if not ok:
                ans = "network reload failed"
            else:
                ans = "network reload started. use IP command to check for success"

        elif cmd in ['HELP', '?']:
            ans = (
                "\r\nAVAILABLE COMMANDS:\r\n"
                "HELP           - show this help\r\n"
                "EXIT           - exit CLI\r\n"
                "---- pitelex ----\r\n"
                "DEV, DEVICES   - list enabled devices\r\n"
                "KG, WRU        - show WRU ID\r\n"
                "PORT           - show i-Telex port (if configured)\r\n"
                "WHOAMI         - identify this CLI\r\n"
                "---- system info ----\r\n"
                "CPU            - show CPU load\r\n"
                "DISK           - show root filesystem usage\r\n"
                "MEM            - show memory usage\r\n"
                "UPTIME         - show system uptime\r\n"
                "IP             - list local interfaces and IPv4 addresses\r\n"
                "IPX            - show external (WAN) IPv4 address\r\n"
                "PING           - ping 8.8.8.8, (4 packets)\r\n"
                "W              - show logged in users\r\n"
                "WLAN           - scan for available WLAN networks\r\n"
                "---- system management ----\r\n"
                "RLNET          - restart NetworkManager\r\n"
                "WPS            - connect WLAN via WPS\r\n"
                "REBOOT         - reboot system\r\n"
                "RESTART        - restart pitelex.service\r\n"
                "SHUTDOWN       - shutdown system\r\n"
            )

        if ans == '':
            ans = '?'
        ans = "\r" + ans    
        ans += "\r\n+? "
        ans += self.keyboard_mode
        return ans

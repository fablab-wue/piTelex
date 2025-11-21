import logging
l = logging.getLogger("piTelex." + __name__)
import os

if os.name == 'nt':
    def get_shell_result(cmd:str) -> str:
        return "na"

else:   # Linux and RPi
    import subprocess
    def get_shell_result(cmd:str) -> str:
        ret = subprocess.check_output(cmd, shell = True )
        ret = ret.decode("utf-8", "ignore").replace('@', '?').replace('#', '?').replace('\n', '\r\n')
        return ret
        
##einige Sachen für testing veraendert von WolfHenk (2025)##

#######

def get_IP() -> str:
    import socket
    hostname = socket.gethostname()
    #ip_address = socket.gethostbyname(hostname)   # don't work - returns 127.0.1.1 on Raspian
    #ip_address_ex = socket.gethostbyname_ex(hostname)
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip_address = (s.getsockname()[0])
    except:
        ip_address = '-'
    finally:
        s.close()
    return str(ip_address) + ' ' + hostname

#######

def get_IP_all() -> str:
    """
    show all IPv4-adresses per interface (without lo), e.g.:
    eth0 192.168.x.y HOSTNAME
    wlan0 192.168.a.b HOSTNAME SSID
    """
    if os.name == 'nt':
        return "na"

    import subprocess
    import socket

    hostname = socket.gethostname()

    try:
        # ip -o -4 addr show -> each IP in a separate line
        out = subprocess.check_output(
            "ip -o -4 addr show",
            shell=True,
            stderr=subprocess.DEVNULL
        ).decode("utf-8", "ignore")
    except Exception:
        return "NO IP"

    lines_out = []

    for line in out.splitlines():
        # example line:
        # 2: eth0    inet 192.168.3.150/24 brd ... scope global eth0
        parts = line.split()
        if len(parts) < 4:
            continue

        iface = parts[1]
        if iface == 'lo':
            continue  # omit loopback

        cidr = parts[3]          # 192.168.3.150/24
        ip = cidr.split('/')[0]  # 192.168.3.150

        entry = f"{iface} {ip} {hostname}"

        # WLAN-Interface often has "wlan" or "wl" in its name
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
    Show the external (public) IPv4-address, as far as it can be determined
    """
    if os.name == 'nt':
        return "na"

    import subprocess

    # try different methods / tools
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
            # Only the first "word" matters
            ip = out.split()[0]
            ip = ip.replace('@', '?').replace('#', '?').replace('\n', '\r\n')
            return f"external ip-address is {ip}."
        except Exception:
            continue

    return "external ip-address can not be determined."

#######

def get_wlan_ip() -> str:
    """
    Show the IPv4 address of wlan0 without CIDR or '' if empty
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
    executes 'sudo iw wlan0 scan' and checks the SSIDs. The answer is formatted like:
          +++ SSID IP   für das aktive Netz
          --- SSID      für alle anderen
    """
    import subprocess

    # determine active WiFi SSID ermitteln – 'sudo' not needed
    try:
        active_ssid = subprocess.check_output(
            "iwgetid -r",
            shell=True,
            stderr=subprocess.DEVNULL
        ).decode("utf-8", "ignore").strip()
    except Exception:
        active_ssid = ''

    wlan_ip = get_wlan_ip()

    # sudo iw wlan0 scan *with* password at stdin
    proc = subprocess.Popen(
        ['sudo', '-S', 'iw', 'wlan0', 'scan'],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    out, err = proc.communicate((password + '\n').encode('utf-8'))

    if proc.returncode != 0:
        # wrong password or no permission / error
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

    result = "\r\n".join(lines)
    result = result.replace('@', '?').replace('#', '?')
    return result   

#######

class CLI():
    def __init__(self, **params):
        self.params = params
        self.keyboard_mode = '<'
        self._wlan_wait_password = False
        pass

    def command(self, cmd_in:str) -> str:
        # special case: waiting for the sudo password for WLAN
        if getattr(self, "_wlan_wait_password", False):
            # Password NOT uppercased, no special treatment of '<' / '>'
            password = cmd_in.strip()

            # Flag zurücksetzen
            self._wlan_wait_password = False

            ans = get_WLAN_from_sudo(password)
            if ans == '':
                ans = '?'
            ans += '\r\n: '
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
            ans = '<<<\r\nPITELEX-CLI'

        elif cmd in ['KG', 'WRU']:
            ans = self.params.get('wru_id', 'NO')

        #elif cmd in ['DEBUG']:
        #    ans = str(self.params.get('debug', 'NO'))

        #elif cmd.startswith('DEBUG='):
        #    level = int(cmd[6:])
        #    self.params['debug'] = level
        #    l.setLevel(level)
        #    ans = ' '

        elif cmd == 'PING':
            ans = 'PONG'

        elif cmd == 'IP':
            # all interfaces (IPv4 addresses)
            ans = get_IP_all()

        elif cmd == 'PORT':
            devices = self.params.get('devices', None)
            if devices:
                for name, dev in devices.items():
                    if dev['enable'] and dev['type'] == 'i-Telex':
                        ans = str(dev['port'])

        elif cmd in ['DEV', 'DEVICES']:
            devices = self.params.get('devices', None)
            if devices:
                for name, dev in devices.items():
                    if dev['enable']:
                        ans += '\r\n{}: {}'.format(name, dev['type'])

        elif cmd == 'EXIT':
            return 'BYE\r\n'   # magic word to exit CLI

        # Linux only commands
        # https://unix.stackexchange.com/questions/119126/command-to-display-memory-usage-disk-usage-and-cpu-load
        # https://www.cyberciti.biz/tips/top-linux-monitoring-tools.html

        elif cmd == 'IPX':
            # external (WAN-)IP, if detectable
            ans = get_IP_external()

        elif cmd == 'CPU':
            ans = get_shell_result("top -bn1 | grep load | awk '{printf \"CPU Load: %.2f\", $(NF-2)}'")

        elif cmd == 'MEM':
            ans = get_shell_result("free -m | awk 'NR==2{printf \"Mem: %s/%sMB %.2f%%\", $3,$2,$3*100/$2 }'")

        elif cmd == 'DISK':
            ans = get_shell_result("df -h | awk '$NF==\"/\"{printf \"Disk: %d/%dGB %s\", $3,$2,$5}'")

        elif cmd == 'UPTIME':
            ans = get_shell_result("uptime -p")

        elif cmd == 'W':
            ans = get_shell_result("w")
        
        elif cmd == 'WLAN':
            # beim nächsten Aufruf erwarten wir das sudo-passwort (im Klartext)
            self._wlan_wait_password = True
            ans = "password (only lowercase lettres and digits, no special characters)"

        if ans == '':
            ans = '?'
        ans += '\r\n: '
        ans += self.keyboard_mode
        return ans




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

class CLI():
    def __init__(self, **params):
        self.params = params
        self.keyboard_mode = '<'
        pass

    def command(self, cmd_in:str) -> str:
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
            ans = get_IP()

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
            ans = get_shell_result("hostname -I | cut -d' ' -f1")

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


        if ans == '':
            ans = '?'
        ans += '\r\n: '
        ans += self.keyboard_mode
        return ans
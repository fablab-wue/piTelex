import logging
l = logging.getLogger("piTelex." + __name__)

class CLI():
    def __init__(self, **params):
        self.params = params
        self.keyboard_mode = None
        pass

    def command(self, cmd_in:str) -> str:
        ans = ''
        cmd = ''
        cmd_in = cmd_in.upper().strip()
        for c in cmd_in:
            if c in '<>':
                self.keyboard_mode = c
                #print(c)
            else:
                cmd += c

        if cmd == 'WHOAMI':
            ans = '<<<\r\nPITELEX-CLI'

        elif cmd in ['KG', 'WRU']:
            ans = self.params.get('wru_id', 'NO')

        elif cmd in ['DEBUG']:
            ans = str(self.params.get('debug', 'NO'))

        elif cmd.startswith('DEBUG='):
            level = int(cmd[6:])
            self.params['debug'] = level
            l.setLevel(level)
            ans = ' '

        elif cmd == 'PING':
            ans = 'PONG'

        elif cmd == 'IP':
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
            ans = str(ip_address) + ' ' + hostname

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

        if ans == '':
            ans = '?'
        ans += '\r\n: '
        if self.keyboard_mode != '<':
            ans += '<'
        return ans
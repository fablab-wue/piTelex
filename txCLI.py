

class CLI():
    def __init__(self, **params):
        self.params = params
        pass

    def command(self, cmd:str) -> str:
        cmd = cmd.upper().strip()
        ans = ''

        if cmd == 'WHOAMI':
            ans = '\r\nPITELEX-CLI'

        elif cmd in ['KG', 'WRU']:
            ans = self.params.get('wru_id', 'NO')

        elif cmd in ['DEBUG']:
            ans = str(self.params.get('debug', 'NO'))

        elif cmd.startswith('DEBUG='):
            level = int(cmd[6:])
            self.params['debug'] = level
            ans = ' '

        elif cmd == 'PING':
            ans = 'PONG'

        elif cmd == 'IP':
            import socket
            hostname = socket.gethostname()
            ip_address = socket.gethostbyname(hostname)
            #ip_address_ex = socket.gethostbyname_ex(hostname)
            ans = str(ip_address) + ' ' + hostname

        elif cmd == 'EXIT':
            return 'BYE\r\n'   # magic word to exit CLI

        if ans == '':
            ans = '?'
        return ans+'\r\n: '
# Changes since release 2025-06

### Fix software WRU response
* Module: MCP
* Description:
  Reformat software WRU for better compatibility with Archive e-mail functionaltiy

### New module "babelfish" 
Babelfish allows automatic translation of incoming messages to a predefined language.<br>
See https://github.com/fablab-wue/piTelex/wiki/SW_DevBabelfish

### Fix unhandled exceptions
* Module: i-telex
* Description:
  Previously, it was possible in some cases that the socket connection is already closed when we want to send some data like 'der', 'occ',… Without catching this, the i-telex-server would die and the machine would not be reachable anymore.

  Now, this is catched and the server will still run after these exceptions.

### More commands for CLI 
* Module: txCLI (linux only)
* Description:
 CLI now takes the following commands:
<pre>
 "AVAILABLE COMMANDS:"
                "HELP, ?        - show this help"
                "CPU            - show CPU load"
                "DEV, DEVICES   - list enabled devices"
                "DISK           - show root filesystem usage"
                "IP             - list local interfaces and IPv4 addresses"
                "IPX            - show external (WAN) IPv4 address"
                "KG, WRU        - show WRU ID"
                "LUPD           - linux system update (apt-get update/upgrade)"
                "MEM            - show memory usage"
                "PING           - ping 8.8.8.8, (4 packets)"
                "PORT           - show i-Telex port (if configured)"
                "TUPD           - piTelex update from GitHub (stable)"
                "TUPD-T         - piTelex update from GitHub (testing)"
                "UPTIME         - show system uptime"
                "W              - show logged in users"
                "WHOAMI         - identify this CLI"
                "WLAN           - scan WLAN networks (requires sudo password)"
                "WPS            - connect WLAN via WPS (requires sudo password)"
                "REBOOT         - reboot system (requires sudo password)"
                "SHUTDOWN       - shutdown system (requires sudo password)"
                "EXIT           - exit CLI"
</pre>  

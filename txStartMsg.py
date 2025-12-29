#!/usr/bin/python3
"""
Telex Device - Startup message with IP, Internet and Backend (TNS/Centralex) information
"""

__author__      = "WolfHenk"
__programming_tool__ = "ChatGPT 5.1-thinking"
__email__       = "wolfhenk@wolfhenk.de"
__copyright__   = "2025"
__license__     = "GPL3"
__version__     = "0.1.1"

""" cleared for testing - WH - 2025-12-04-1000Z """

import os
import socket
import subprocess
import logging
import time

l = logging.getLogger("piTelex." + __name__)

import txBase
import txCode

try:
    import commentjson as cjson
except ImportError:
    cjson = None

ESC = "\x1b"
ESC_A = ESC + "A"
ESC_Z = ESC + "Z"


""" 
    for now, verbosit levels limited to 1-3 and 5, because the handling of TNS servers and centralex servers
    must be improved. Use of piTelex builtin defaults is not handled correctly, furthermore the defaults
    require to be replicated here. tis is a high danger for inconsistencies.
    (rowo 2025-12-29)
"""


class TelexStartMsg(txBase.TelexBase):
    """
    Sends exactly one startup message when the device is initialized.

    Controlled by the parameter 'verbosity' (1..5):

      1: only "TELEX READY" or "TELEX UP - NOT READY" + a few blank lines
      2: like 1 + external + internal IP addresses
      3: like 2 + "INTERNET CONNECTION OK/MISSING"
      4: like 3 + backend checks:
           - if 'centralex' is enabled in the i-Telex device: Centralex server from telex.json
           - otherwise: TNS servers (default list or tns_srv/tns_port from i-Telex)
      5: like 4 + two lines of RYRYRY...

    READY condition (always checked, independent of verbosity):

      - at least one internal IP address (no lo)
      - at least one reachable backend server:
          * Centralex (if enabled), or
          * TNS server

    If these conditions are not fulfilled:
      "TELEX UP - NOT READY"

    Motor start / stop:

      - In idle20Hz, when _state_counter == 2: ESC+A (motor on)
      - After a short delay: full message + ESC+Z
    """

    def __init__(self, **params):
        super().__init__()

        self.id = 'Sta'
        self.params = params
        self._rx_buffer = []

        # Verbosity from configuration
        v = params.get('verbosity', 2)
        try:
            v = int(v)
        except Exception:
            v = 2
        if v < 1:
            v = 1
        if v > 5:
            v = 5
        self.verbosity = v

        # Send state as in the Babelfish module
        self._processing = False
        self._state_counter = 0
        self._out_buffer = []

        # Prepare message (once at startup)
        self._prepare_message()

    # ---- internal helpers ----

    def _get_external_ip(self):
        """
        Try to determine the public IPv4 address.
        Returns 'UNKNOWN' if this is not possible.
        """
        if os.name == 'nt':
            return "UNKNOWN"

        cmds = [
            "curl -s https://api.ipify.org",
            "curl -s https://ifconfig.me",
            "wget -qO- https://api.ipify.org",
            "wget -qO- https://ifconfig.me",
            "dig +short myip.opendns.com @resolver1.opendns.com",
        ]

        for cmd in cmds:
            try:
                out = subprocess.check_output(
                    cmd,
                    shell=True,
                    stderr=subprocess.DEVNULL
                ).decode("utf-8", "ignore").strip()
                if not out:
                    continue
                ip = out.split()[0]
                ip = ip.replace('@', '?').replace('#', '?')
                return ip
            except Exception:
                continue

        return "UNKNOWN"

    def _get_internal_ips(self):
        """
        Return a list of lines like:
          ETH0 192.168.3.150 HOSTNAME
          WLAN0 192.168.3.135 HOSTNAME SSID
        (excluding lo)
        """
        if os.name == 'nt':
            return []

        try:
            out = subprocess.check_output(
                "ip -o -4 addr show",
                shell=True,
                stderr=subprocess.DEVNULL
            ).decode("utf-8", "ignore")
        except Exception:
            return []

        hostname = socket.gethostname()
        result_lines = []

        for line in out.splitlines():
            parts = line.split()
            if len(parts) < 4:
                continue

            iface = parts[1]
            if iface == "lo":
                continue

            cidr = parts[3]          # e.g. 192.168.3.150/24
            ip = cidr.split("/")[0]  # 192.168.3.150

            entry = f"{iface} {ip} {hostname}"

            # Extend WLAN interfaces with SSID if available
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

            result_lines.append(entry.upper().replace('@', '?').replace('#', '?'))

        return result_lines

    def _load_itelex_from_telexjson(self):
        """
        Read telex.json from the same directory as this module and
        return the i-Telex device block if present and enable==true.
        Otherwise None.

        Assumption: txStartMsg.py, telex.py and telex.json are in the same directory.
        """
        if cjson is None:
            l.warning("StartMsg: commentjson not available, cannot read telex.json for i-Telex")
            return None

        this_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(this_dir, "telex.json")

        if not os.path.isfile(config_path):
            l.warning("StartMsg: telex.json not found at %r", config_path)
            return None

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = cjson.load(f)
            l.info("StartMsg: using telex.json from %r", config_path)
        except Exception as e:
            l.warning("StartMsg: could not parse telex.json at %r: %s", config_path, e)
            return None

        devices = cfg.get("devices", {})
        itelex = None

        # Find i-Telex key in a robust way (i-Telex, i-telex, i_telex, ...)
        for key, val in devices.items():
            if isinstance(key, str) and key.replace("_", "-").lower() == "i-telex":
                itelex = val
                break

        if not itelex or not isinstance(itelex, dict):
            return None

        if not itelex.get("enable", True):
            return None

        return itelex

    def _get_backend_entries_from_config(self):
        """
        Determine, based on telex.json (i-Telex device),
        which backend servers should be tested.

        Return:
          (label, [(host, port), ...])

        label:
          "CENTRALEX", "TNS" or None
        """
        itelex = self._load_itelex_from_telexjson()
        if not itelex:
            return None, []

        centralex_active = bool(itelex.get("centralex", False))

        if centralex_active:
            host = str(itelex.get("centralex_srv", "")).strip()
            port = itelex.get("centralex_port", 49491)
            try:
                port = int(port)
            except Exception:
                port = 49491
            if port <= 0:
                port = 49491

            if not host:
                return "CENTRALEX", []
            return "CENTRALEX", [(host, port)]

        # TNS mode
        tns_param = itelex.get("tns_srv") or self.params.get("tns") or self.params.get("tns_srv")

        if not tns_param:
            host_list = [
                "tlnserv.teleprinter.net",
                "tlnserv2.teleprinter.net",
                "tlnserv3.teleprinter.net",
            ]
        else:
            host_list = []
            if isinstance(tns_param, str):
                for p in tns_param.split(","):
                    p = p.strip()
                    if p:
                        host_list.append(p)
            elif isinstance(tns_param, (list, tuple)):
                for p in tns_param:
                    s = str(p).strip()
                    if s:
                        host_list.append(s)

        default_port = itelex.get("tns_port", self.params.get("tns_port", 11811))
        try:
            default_port = int(default_port)
        except Exception:
            default_port = 11811
        if default_port <= 0:
            default_port = 11811

        entries = []
        for entry in host_list:
            host = entry
            port = default_port
            if ":" in entry:
                host, p = entry.rsplit(":", 1)
                host = host.strip()
                try:
                    port = int(p)
                except Exception:
                    port = default_port
            host = host.strip()
            if not host:
                continue
            entries.append((host, port))

        return "TNS", entries

    def _check_backend_connections(self):
        """
        Check connections to backend servers.

        Priority:
          1. CENTRALex server from i-Telex config if centralex=true
          2. Otherwise TNS servers (default list or tns_srv/tns_port)

        Return:
          (line_list, any_ok)

        Lines start with "CENTRALEX" or "TNS".
        """
        label, entries = self._get_backend_entries_from_config()

        lines = []
        any_ok = False

        if not label or not entries:
            lines.append("NO BACKEND CONFIGURED")
            return lines, any_ok

        for host, port in entries:
            status = "OK"
            try:
                with socket.create_connection((host, port), timeout=5):
                    status = "OK"
                    any_ok = True
            except Exception:
                status = "FAILED"

            line = f"{label} {host}:{port} {status}"
            lines.append(line.upper().replace('@', '?').replace('#', '?'))

        if not lines:
            lines.append("NO BACKEND CONFIGURED")

        return lines, any_ok

    def _prepare_message(self):
        """
        Build the complete text and store it as Baudot in _out_buffer.
        Called only once at startup.

        READY is only true if:
          - at least one internal IP address was found
          - at least one backend server is reachable
        """

        internal_ips = self._get_internal_ips()
        has_ip = bool(internal_ips)

        ext_ip = self._get_external_ip()
        internet_ok = bool(ext_ip and ext_ip != "UNKNOWN")

        backend_lines, backend_ok = self._check_backend_connections()

        ready = has_ip and backend_ok

        lines = []

        intro = time.strftime("%Y-%m-%d  %H:%M:%S", time.localtime())

        # Header
        if ready:
            header = "TELEX READY"
        else:
            header = "PITELEX UP - TELEX NOT READY"

        lines.append(" ")
        lines.append(f"{intro}: {header}")


        if self.verbosity >= 2:
            ext_ip_print = ext_ip if ext_ip else "UNKNOWN"
            lines.append("---")
            lines.append(f"MY EXTERNAL IP-ADDRESS IS {ext_ip_print}")
            lines.append("INTERNAL I HAVE")
            if internal_ips:
                lines.extend(internal_ips)
            else:
                lines.append("NO INTERNAL IP-ADDRESS")

        if self.verbosity >= 3:
            lines.append("---")
            if internet_ok:
                lines.append("INTERNET CONNECTION OK")
            else:
                lines.append("NO INTERNET CONNECTION")

        if self.verbosity >= 4:
            lines.append("---")
##### commented out, see above (rowo)
#            lines.extend(backend_lines)
            lines.append("backend checks not yet implemented")
##### commented out, see above (rowo)

        if self.verbosity >= 5:
            lines.append("---")
            lines.append("RYRYRYRYRYRYRYRYRYRYRYRYRYRYRYRYRYRYRYRYRYRYRYRYRYRYRYRYRYRYRYRYRYRY")
            lines.append("RYRYRYRYRYRYRYRYRYRYRYRYRYRYRYRYRYRYRYRYRYRYRYRYRYRYRYRYRYRYRYRYRYRY")

        if self.verbosity >= 2:
            lines.append("---")
            lines.append("(END OF DIAGNOSTICS)")
#        text = "\r\r\n\n\n\n\n".join(lines) + "\r\r\n\n\n\n\n"
        text = "\r\n".join(lines) + "\r\n\n\n"

        # convert to Baudot
        ba = txCode.BaudotMurrayCode.translate(text)

        # full message as list of characters
        self._out_buffer = list(ba)

        # Activate send state - motor start etc. is handled in idle20Hz
        self._processing = True
        self._state_counter = 0

        l.info(
            "Startup message prepared (verbosity=%d, ready=%s):\n%s",
            self.verbosity, ready, text
        )

    # ---- device interface ----

    def read(self) -> str:
        # similar to Babelfish: empty string if nothing is available
        return self._rx_buffer.pop(0) if self._rx_buffer else ''

    def write(self, a: str, source: str):
        # ignores incoming chars; this device only sends on startup
        return

    def idle(self):
        # nothing to do, we work via idle20Hz
        pass

    def idle20Hz(self):
        """
        Control motor start and output, similar to Babelfish:
          - first send ESC+A to MCP
          - short delay
          - then send the complete message + ESC+Z
        """
        if not self._processing:
            return

        self._state_counter += 1

        if self._state_counter == 2:
            # Motor start
            l.info("%s: Motor start (ESC+A) sent", self.id)
            self._rx_buffer.append(ESC_A)

        elif self._state_counter > 25:
            # full message + ESC+Z
            for ch in self._out_buffer:
                self._rx_buffer.append(ch)
            self._rx_buffer.append(ESC_Z)
            l.info("%s: Startup message completely sent", self.id)

            # Cleanup
            self._processing = False
            self._state_counter = 0
            self._out_buffer = []

    def idle2Hz(self):
        pass

    def exit(self):
        pass

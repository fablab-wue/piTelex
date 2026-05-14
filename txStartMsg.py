#!/usr/bin/python3
"""
Telex Device - Startup message with IP, Internet and Backend (TNS/Centralex) information
"""

__author__      = "WolfHenk"
__programming_tool__ = "ChatGPT 5.1-thinking"
__email__       = "wolfhenk@wolfhenk.de"
__copyright__   = "2025"
__license__     = "GPL3"
__version__     = "0.1.2"

"""
0.1.2 - 2026-05-10 - WH
- StartMsg no longer starts the printer directly with ESC+A.
- Uses MCP-controlled ESC+LT start and ESC+ST stop.
- Waits for ESC+AA before sending text.
- Adds rate-limited output with ESC+~<n> buffer feedback.
"""

import os
import socket
import subprocess
import logging
import time
import re

l = logging.getLogger("piTelex." + __name__)

import txBase
import txCode

try:
    import commentjson as cjson
except ImportError:
    cjson = None

ESC = "\x1b"
ESC_LT = ESC + "LT"
ESC_ST = ESC + "ST"
ESC_AA = ESC + "AA"

# Rate limited output. This does not change the physical line speed;
# it only controls how quickly this module feeds characters to the bus.
START_BAUD = 55.0
MIN_BAUD = 45.0
BITS_PER_CHAR = 7.5
TICK_HZ = 20.0

TARGET_LOAD = 7
LOAD_MIN = 4
LOAD_MAX = 10
LOAD_HARD_MAX = 14

START_TIMEOUT_TICKS = 10 * 20
DRAIN_TIMEOUT_TICKS = 5 * 20

TX_REQUEST_START = "request_start"
TX_WAIT_READY = "wait_ready"
TX_SENDING = "sending"
TX_WAIT_DRAIN = "wait_drain"


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

      - In idle20Hz, when _state_counter == 2: ESC+LT is sent to MCP.
      - MCP starts the printer path and broadcasts ESC+A.
      - StartMsg waits for ESC+AA before sending text.
      - Text is sent rate-limited; ESC+~<n> feedback regulates speed.
      - At the end, ESC+ST is sent so MCP terminates the session cleanly.
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

        # Send state as in the Babelfish module, but MCP-controlled.
        self._processing = False
        self._state_counter = 0
        self._out_buffer = []
        self._tx_state = TX_REQUEST_START
        self._start_wait_ticks = 0
        self._drain_wait_ticks = 0

        # Rate limiter / buffer control
        self._tx_baud = START_BAUD
        self._tx_accumulator = 0.0
        self._last_buffer_load = None
        self._buffer_seen = False
        self._buffer_report_age = 999
        self._tx_paused_by_buffer = False

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

        # Activate send state - printer start etc. is handled in idle20Hz
        self._processing = True
        self._state_counter = 0
        self._tx_state = TX_REQUEST_START
        self._start_wait_ticks = 0
        self._drain_wait_ticks = 0
        self._tx_baud = START_BAUD
        self._tx_accumulator = 0.0
        self._last_buffer_load = None
        self._buffer_seen = False
        self._buffer_report_age = 999
        self._tx_paused_by_buffer = False

        l.info(
            "Startup message prepared (verbosity=%d, ready=%s):\n%s",
            self.verbosity, ready, text
        )

    # ---- device interface ----

    def read(self) -> str:
        # similar to Babelfish: empty string if nothing is available
        return self._rx_buffer.pop(0) if self._rx_buffer else ''

    def write(self, a: str, source: str):
        """
        Listen for printer-ready and buffer feedback while sending.

        ESC+AA starts the actual text output after MCP has started
        the printer path. ESC+~<n> from any device is buffer feedback
        and regulates the output speed while StartMsg is sending.
        """
        if not a or ESC not in a:
            return

        for match in re.finditer(r"\x1b(~\d+|\^\d+|[A-Z]{1,3})", a):
            cmd = match.group(1)

            if cmd == "AA":
                if self._processing and self._tx_state == TX_WAIT_READY:
                    l.info("%s: printer ready (ESC+AA) received from %s", self.id, source)
                    self._tx_state = TX_SENDING
                    self._tx_baud = START_BAUD
                    self._tx_accumulator = 0.0
                continue

            if cmd.startswith("~"):
                if self._processing and self._tx_state in (TX_SENDING, TX_WAIT_DRAIN):
                    try:
                        self._update_rate_from_buffer(int(cmd[1:]))
                    except ValueError:
                        pass
                continue

    def _update_rate_from_buffer(self, load: int):
        """
        Adapt virtual output speed from ESC+~<n> buffer feedback.

        Rising buffer load slows down, falling load speeds up. There is
        deliberately no MAX_BAUD here. idle20Hz sends at most one char
        per tick, which limits practical output to about 150 baud.
        """
        if self._last_buffer_load is None:
            trend = 0
        else:
            # positive: buffer load is falling -> speed up
            # negative: buffer load is rising -> slow down
            trend = self._last_buffer_load - load

        self._last_buffer_load = load
        self._buffer_seen = True
        self._buffer_report_age = 0

        error = TARGET_LOAD - load
        correction = 1.2 * error + 1.0 * trend

        if load > LOAD_MAX:
            correction -= 3.0
        elif load < LOAD_MIN:
            correction += 3.0

        self._tx_baud = max(MIN_BAUD, self._tx_baud + correction)

        if load >= LOAD_HARD_MAX:
            self._tx_paused_by_buffer = True
            self._tx_accumulator = 0.0
        elif load <= LOAD_MAX:
            self._tx_paused_by_buffer = False

    def _send_rate_limited_char(self):
        """Send at most one character per idle20Hz tick."""
        if not self._out_buffer:
            return

        if self._tx_paused_by_buffer:
            self._tx_accumulator = 0.0
            return

        cps = self._tx_baud / BITS_PER_CHAR
        self._tx_accumulator += cps / TICK_HZ

        # Avoid bursts after pauses. One char per 20-Hz tick is the limit.
        self._tx_accumulator = min(self._tx_accumulator, 1.0)

        if self._tx_accumulator >= 1.0 and self._out_buffer:
            self._rx_buffer.append(self._out_buffer.pop(0))
            self._tx_accumulator -= 1.0

    def _finish_startmsg(self):
        self._rx_buffer.append(ESC_ST)
        l.info("%s: Startup message completely sent, ESC+ST queued", self.id)
        self._processing = False
        self._state_counter = 0
        self._out_buffer = []
        self._tx_state = TX_REQUEST_START
        self._tx_accumulator = 0.0
        self._tx_paused_by_buffer = False

    def _abort_startmsg(self, reason: str):
        l.warning("%s: Startup message aborted: %s", self.id, reason)
        self._rx_buffer.append(ESC_ST)
        self._processing = False
        self._state_counter = 0
        self._out_buffer = []
        self._tx_state = TX_REQUEST_START
        self._tx_accumulator = 0.0
        self._tx_paused_by_buffer = False

    def idle(self):
        # nothing to do, we work via idle20Hz
        pass

    def idle20Hz(self):
        """
        MCP-controlled startup output:
          - request local printer start with ESC+LT, not ESC+A
          - wait for ESC+AA
          - feed the prepared message with buffer-controlled braking
          - end with ESC+ST so MCP terminates the session cleanly
        """
        if not self._processing:
            return

        self._state_counter += 1

        if self._tx_state == TX_REQUEST_START:
            if self._state_counter >= 2:
                l.info("%s: Printer start request (ESC+LT) sent", self.id)
                self._rx_buffer.append(ESC_LT)
                self._tx_state = TX_WAIT_READY
                self._start_wait_ticks = 0
            return

        if self._tx_state == TX_WAIT_READY:
            self._start_wait_ticks += 1
            if self._start_wait_ticks > START_TIMEOUT_TICKS:
                self._abort_startmsg("printer did not answer with ESC+AA")
            return

        if self._tx_state == TX_SENDING:
            self._buffer_report_age += 1
            self._send_rate_limited_char()
            if not self._out_buffer:
                self._tx_state = TX_WAIT_DRAIN
                self._drain_wait_ticks = 0
            return

        if self._tx_state == TX_WAIT_DRAIN:
            self._buffer_report_age += 1
            self._drain_wait_ticks += 1

            if (not self._buffer_seen) or self._last_buffer_load == 0:
                self._finish_startmsg()
                return

            if self._drain_wait_ticks > DRAIN_TIMEOUT_TICKS:
                l.warning(
                    "%s: Drain timeout, last buffer load was %r",
                    self.id, self._last_buffer_load
                )
                self._finish_startmsg()

    def idle2Hz(self):
        pass

    def exit(self):
        pass

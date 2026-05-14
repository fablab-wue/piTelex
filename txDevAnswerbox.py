#!/usr/bin/python3
"""
Telex Device - Answerbox / Nightbox

Night-time printer emulation with schedule-controlled DTM / NTM,
message storage and replay of stored messages.

3.1.1 - 2026-05-10 - WH
- replay output now starts via ESC+LT, waits for ESC+AA, sends with
  throttling controlled by ESC+~<n> from any source, and ends via ESC+ST
- MCP is not changed; Answerbox uses the existing MCP-controlled printer path
"""
__author__      = "OpenAI"
__revisor__     = "Wolfram Henkel"
__license__     = "GPL3"
__version__     = "3.1.1"
__date__        = "2026-05-10"

import datetime
import logging
import os
import time
from collections import deque

l = logging.getLogger("piTelex." + __name__)

import txBase


ESC = "\x1b"

REPLAY_IDLE = "idle"
REPLAY_WAIT_AA = "wait_aa"
REPLAY_SENDING = "sending"
REPLAY_WAIT_DRAIN = "wait_drain"

START_BAUD = 55.0
MIN_BAUD = 45.0
BITS_PER_CHAR = 7.5
TICK_HZ = 20.0

TARGET_LOAD = 7
LOAD_MIN = 4
LOAD_MAX = 10
LOAD_HARD_MAX = 14


class TelexAnswerbox(txBase.TelexBase):
    """
    Three main areas:
    1. Time control (DTM / NTM, AT override, urgent override)
    2. Night communication (printer emulation, message capture, immediate replies)
    3. Replay for later output to the local printer path
    """

    def __init__(self, **params):
        super().__init__()

        self.id = params.get('id', 'Ans')
        self.loopback = False
        self.params = params

        # ------------------------------------------------------------------
        # 1. time control
        # ------------------------------------------------------------------
        self._weekly_schedule = params.get('weekly_schedule', {})
        self._mode_daytime = None
        self._forced_daytime = False
        self._urgent_daytime = False

        # DTM / NTM may only change while bus is in ZZ.
        # On startup piTelex is normally idle.
        self._zz_active = True

        # ------------------------------------------------------------------
        # 2. night communication
        # ------------------------------------------------------------------
        self._tx_queue = deque()
        self._capture_active = False
        self._current_msg = []
        self._current_urgent = False
        self._current_scan_len = 0
        self._last_rx_printable_ts = 0.0
        self._not_printed_state = 0

        urgent_words = params.get('urgent_words', ['=urgent=', '=eil=', '=blitz='])
        self._urgent_words = [w.lower() for w in urgent_words if w]
        self._urgent_scan_chars = int(params.get('urgent_scan_chars', 100) or 100)
        self._wru_id = self._load_global_wru_id()

        store_path = params.get('store_path', 'answerbox')
        if not store_path:
            store_path = 'answerbox'
        if not os.path.isabs(store_path):
            store_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), store_path)
        self._store_path = store_path
        os.makedirs(self._store_path, exist_ok=True)

        # ------------------------------------------------------------------
        # 3. replay
        # ------------------------------------------------------------------
        self._replay_active = False
        self._replay_state = REPLAY_IDLE
        self._replay_wait_counter = 0
        self._replay_ready_wait_counter = 0
        self._replay_drain_wait_counter = 0
        self._replay_delete_paths = []
        self._replay_payload = ''
        self._replay_tx_queue = deque()

        # Replay throttling. This regulates how fast Answerbox feeds the
        # MCP/printer path. It does not alter the physical baud rate of
        # any real teleprinter.
        self._replay_baud = START_BAUD
        self._replay_tx_accumulator = 0.0
        self._buffer_seen = False
        self._last_buffer_load = None
        self._buffer_report_age = 0
        self._replay_paused_by_buffer = False

        self._update_mode(force=True)

    # ==================================================================
    # public device interface
    # ==================================================================

    def read(self) -> str:
        if not self._tx_queue:
            return ''
        return self._tx_queue.popleft()

    def write(self, data:str, source:str):
        if source == self.id:
            return

        if len(data) > 1 and data[0] == '\x1b':
            self._handle_escape(data[1:], source)
            return

        if self._is_night_mode() and self._capture_active and len(data) == 1:
            self._handle_night_char(data)

    def idle20Hz(self):
        now = time.monotonic()

        if self._capture_active and self._not_printed_state != 0:
            if (now - self._last_rx_printable_ts) >= 0.5:
                self._queue_control('~0')
                self._not_printed_state = 0

        self._handle_replay_20hz()

    def idle2Hz(self):
        self._update_mode()

        if self._replay_active or self._capture_active or self._forced_daytime:
            return

        if not self._zz_active:
            return

        paths = self._list_store_files(urgent=True)
        if paths:
            self._start_replay([paths[0]], urgent=True)
            return

        if self._is_active_time() and self._mode_daytime:
            paths = self._list_store_files(urgent=False)
            if paths:
                self._start_replay(paths, urgent=False)

    # ==================================================================
    # 1. time control
    # ==================================================================

    def _desired_daytime(self, now=None) -> bool:
        if self._forced_daytime:
            return True
        if self._urgent_daytime:
            return True
        return self._is_active_time(now)

    def _update_mode(self, force:bool=False):
        desired = self._desired_daytime()

        if not force and (self._capture_active or self._replay_active):
            return

        if self._mode_daytime is None or desired != self._mode_daytime:
            if not self._zz_active:
                return

            self._mode_daytime = desired
            self._queue_control('DTM' if desired else 'NTM')

    def _is_night_mode(self) -> bool:
        return not bool(self._mode_daytime)

    def _is_active_time(self, now=None) -> bool:
        if now is None:
            now = datetime.datetime.now()

        day_cfg = self._weekly_schedule.get(self._day_key(now.weekday()))
        if day_cfg is None:
            day_cfg = self._weekly_schedule.get(self._day_key_short(now.weekday()), {})

        if isinstance(day_cfg, dict):
            windows = day_cfg.get('active', [])
        else:
            windows = day_cfg or []

        now_min = now.hour * 60 + now.minute
        for start_txt, end_txt in windows:
            start_min = self._parse_time(start_txt)
            end_min = self._parse_time(end_txt)
            if start_min is None or end_min is None:
                continue
            if start_min <= end_min:
                if start_min <= now_min < end_min:
                    return True
            else:
                if now_min >= start_min or now_min < end_min:
                    return True
        return False

    # ==================================================================
    # 2. night communication / printer emulation
    # ==================================================================

    def _handle_escape(self, cmd:str, source:str):
        if cmd == 'ZZ':
            self._zz_active = True

            if self._forced_daytime:
                self._forced_daytime = False

            self._update_mode(force=True)
            return

        # Buffer feedback is a bus-wide mechanism. It is deliberately not
        # tied to piT: during night operation Ans may be the virtual printer,
        # and other printer drivers may send ESC+~<n> as well.
        if cmd.startswith('~'):
            self._handle_buffer_feedback(cmd)
            return

        # WUP is a local wake-up request from piT for the AT key handling.
        # It must switch to daytime while Answerbox is still logically in ZZ,
        # so DTM can still be queued. Afterwards the local ZZ state is cleared,
        # but no additional ESC sequence is emitted here.
        if cmd == 'WUP' and self._is_night_mode() and self._zz_active:
            self._forced_daytime = True
            self._update_mode(force=True)
            self._zz_active = False
            return

        # These commands clearly leave the ZZ state.
        # ST is ignored here, because it is a stop request from hardware and
        # ZZ is expected shortly afterwards.
        if cmd in ('LT', 'PT', 'Z', 'A', 'AA', 'WB'):
            self._zz_active = False

        if cmd == 'AA':
            if self._replay_active and self._replay_state == REPLAY_WAIT_AA:
                self._start_replay_payload_output()
            return

        if cmd == 'A':
            if self._is_night_mode():
                self._start_capture()
                self._queue_control('AA')
            return

        if cmd == 'Z' and self._capture_active:
            self._finish_capture()
            return

    def _start_capture(self):
        self._capture_active = True
        self._current_msg = []
        self._current_urgent = False
        self._current_scan_len = 0
        self._last_rx_printable_ts = time.monotonic()
        self._not_printed_state = 0

    def _handle_night_char(self, ch:str):
        if len(ch) != 1:
            return

        self._mark_not_printed_active()

        if ch == '#':
            if self._wru_id:
                block = '\r\r\n' + self._wru_id + '\r\r\n'
                self._append_capture_text(block)
                self._queue_text(block)
            return

        self._append_capture_text(ch)

    def _append_capture_text(self, text:str):
        if not text:
            return

        self._current_msg.append(text)

        if self._current_scan_len >= self._urgent_scan_chars:
            return

        remaining = self._urgent_scan_chars - self._current_scan_len
        scan_part = text[:remaining]
        self._current_scan_len += len(scan_part)

        if (not self._current_urgent) and scan_part:
            scan_text = ''.join(self._current_msg)
            scan_text = scan_text[:self._urgent_scan_chars]
            scan_text = self._normalize_urgent_scan_text(scan_text)
            for word in self._urgent_words:
                if word and word in scan_text:
                    self._current_urgent = True
                    break

    def _mark_not_printed_active(self):
        self._last_rx_printable_ts = time.monotonic()
        if self._not_printed_state == 0:
            self._queue_control('~2')
            self._not_printed_state = 2

    def _finish_capture(self):
        if not self._capture_active:
            return

        self._capture_active = False

        if self._not_printed_state != 0:
            self._queue_control('~0')
            self._not_printed_state = 0

        text = ''.join(self._current_msg)
        self._current_msg = []
        self._current_scan_len = 0

        urgent = self._current_urgent
        self._current_urgent = False

        if not text:
            return

        if not urgent:
            scan_text = self._normalize_urgent_scan_text(text)
            for word in self._urgent_words:
                if word and word in scan_text:
                    urgent = True
                    break

        self._store_message(text, urgent=urgent)

        if urgent:
            self._urgent_daytime = True
            self._update_mode(force=True)

    # ==================================================================
    # 3. replay
    # ==================================================================

    def _start_replay(self, paths, urgent:bool):
        # Replay may only start in ZZ. Normal replay is limited to the
        # configured active time window. Urgent replay may also start outside
        # that window.
        if not self._zz_active:
            return

        if not urgent and not self._is_active_time():
            return

        texts = []
        delete_paths = []

        for path in paths:
            try:
                with open(path, 'r', encoding='utf-8', newline='') as f:
                    texts.append(f.read())
                delete_paths.append(path)
            except OSError as exc:
                l.error('Could not read answerbox message %r: %r', path, exc)

        if not texts:
            return

        if urgent:
            payload = '\r\r\n%% %% %%  % % %  %% %% %%\r\r\n' + texts[0] + '\r\r\n %% %% %%  % % %  %% %% %%\r\r\n'
            self._urgent_daytime = True
        else:
            parts = []
            last_index = len(texts) - 1
            for idx, text in enumerate(texts):
                parts.append(text)
                if idx < last_index:
                    parts.append('\r\r\n+++ NEXT +++\r\r\n')
                else:
                    parts.append('\r\r\n+++ LAST +++\r\r\n')
            payload = ''.join(parts)

        self._update_mode(force=True)

        self._replay_active = True
        self._replay_state = REPLAY_WAIT_AA
        self._replay_wait_counter = 0
        self._replay_ready_wait_counter = 0
        self._replay_drain_wait_counter = 0
        self._replay_delete_paths = delete_paths
        self._replay_payload = payload
        self._replay_tx_queue.clear()
        self._reset_replay_rate_control()

        # Replay is a self-writing operation. Do not start the printer by
        # sending ESC+A directly. Use MCP's existing local-test path: LT makes
        # MCP enter ACTIVE_INIT with broadcast, so MCP emits A and the active
        # printer answers AA. Only after AA do we feed text.
        self._queue_control('LT')

    def _finish_replay(self, delete_messages: bool = True):
        self._replay_active = False
        self._replay_state = REPLAY_IDLE
        self._replay_wait_counter = 0
        self._replay_ready_wait_counter = 0
        self._replay_drain_wait_counter = 0
        self._replay_payload = ''
        self._replay_tx_queue.clear()
        self._reset_replay_rate_control()

        if delete_messages:
            for path in self._replay_delete_paths:
                try:
                    os.unlink(path)
                except OSError as exc:
                    l.warning('Could not delete answerbox message %r: %r', path, exc)
        self._replay_delete_paths = []

        self._urgent_daytime = bool(self._list_store_files(urgent=True))

        self._update_mode(force=True)

    def _abort_replay(self, reason: str):
        l.warning('Answerbox replay aborted: %s', reason)
        # Release the MCP-controlled printer path if we already requested it.
        self._queue_control('ST')
        self._finish_replay(delete_messages=False)

    def _start_replay_payload_output(self):
        self._replay_tx_queue = deque(self._replay_payload)
        self._replay_payload = ''
        self._replay_state = REPLAY_SENDING
        self._replay_wait_counter = 0
        self._reset_replay_rate_control()
        l.info('Answerbox replay printer ready, starting throttled output')

    def _handle_replay_20hz(self):
        if not self._replay_active:
            return

        if self._replay_state == REPLAY_WAIT_AA:
            self._replay_ready_wait_counter += 1
            # MCP's no-printer fallback usually answers within 5 seconds if
            # enabled. Use a larger timeout so a slow machine still has room.
            if self._replay_ready_wait_counter > 240:  # 12 s at 20 Hz
                self._abort_replay('printer did not answer AA after LT')
            return

        if self._replay_state == REPLAY_SENDING:
            self._age_buffer_report()
            self._send_replay_char_limited()
            if not self._replay_tx_queue:
                self._replay_state = REPLAY_WAIT_DRAIN
                self._replay_drain_wait_counter = 0
            return

        if self._replay_state == REPLAY_WAIT_DRAIN:
            self._age_buffer_report()
            self._replay_drain_wait_counter += 1

            # Do not put ST before the last queued output character has been
            # handed to the bus.
            if self._tx_queue:
                return

            if self._can_finish_replay_output():
                self._queue_control('ST')
                self._finish_replay(delete_messages=True)

    def _handle_buffer_feedback(self, cmd: str):
        if not (self._replay_active and self._replay_state in (REPLAY_SENDING, REPLAY_WAIT_DRAIN)):
            return

        try:
            load = int(cmd[1:])
        except ValueError:
            return

        self._update_replay_rate_from_buffer(load)

    def _reset_replay_rate_control(self):
        self._replay_baud = START_BAUD
        self._replay_tx_accumulator = 0.0
        self._buffer_seen = False
        self._last_buffer_load = None
        self._buffer_report_age = 0
        self._replay_paused_by_buffer = False

    def _age_buffer_report(self):
        if self._buffer_seen:
            self._buffer_report_age += 1
            # If feedback goes stale, return towards the conservative start
            # speed and release any hard pause.
            if self._buffer_report_age > 40:
                if self._replay_baud > START_BAUD:
                    self._replay_baud -= min(0.5, self._replay_baud - START_BAUD)
                elif self._replay_baud < START_BAUD:
                    self._replay_baud += min(0.5, START_BAUD - self._replay_baud)
                self._replay_paused_by_buffer = False

    def _update_replay_rate_from_buffer(self, load: int):
        if self._last_buffer_load is None:
            trend = 0
        else:
            # Positive trend means the printer buffer is falling: feed faster.
            trend = self._last_buffer_load - load

        self._last_buffer_load = load
        self._buffer_seen = True
        self._buffer_report_age = 0

        error = TARGET_LOAD - load
        correction = 1.2 * error + 1.0 * trend
        self._replay_baud += correction

        if load >= LOAD_HARD_MAX:
            self._replay_paused_by_buffer = True
        elif load <= LOAD_MAX:
            self._replay_paused_by_buffer = False

        if load > LOAD_MAX:
            self._replay_baud -= 5.0
        elif load < LOAD_MIN:
            self._replay_baud += 5.0

        if self._replay_baud < MIN_BAUD:
            self._replay_baud = MIN_BAUD

    def _send_replay_char_limited(self):
        if not self._replay_tx_queue:
            return

        if self._replay_paused_by_buffer:
            self._replay_tx_accumulator = 0.0
            return

        cps = self._replay_baud / BITS_PER_CHAR
        self._replay_tx_accumulator += cps / TICK_HZ

        # No burst output. At 20 Hz this naturally caps the practical feed
        # rate at about 150 Baud.
        if self._replay_tx_accumulator > 1.0:
            self._replay_tx_accumulator = 1.0

        if self._replay_tx_accumulator >= 1.0 and self._replay_tx_queue:
            self._tx_queue.append(self._replay_tx_queue.popleft())
            self._replay_tx_accumulator -= 1.0

    def _can_finish_replay_output(self) -> bool:
        if self._buffer_seen:
            if self._last_buffer_load is not None and self._last_buffer_load <= 0:
                return True
            # Safety timeout for missing final ~0. Do not keep old messages
            # forever because one printer driver stopped reporting.
            return self._replay_drain_wait_counter > 120

        # No buffer feedback at all: use a conservative fixed drain delay.
        return self._replay_drain_wait_counter > 60

    # ==================================================================
    # helpers
    # ==================================================================

    def _store_message(self, text:str, urgent:bool=False):
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S-%f')[:-3]
        if urgent:
            filename = 'urgent_' + timestamp + '.txt'
        else:
            filename = timestamp + '.txt'
        path = os.path.join(self._store_path, filename)
        try:
            with open(path, 'w', encoding='utf-8', newline='') as f:
                f.write(text)
        except OSError as exc:
            l.error('Could not store answerbox message %r: %r', path, exc)
            return None
        return path

    def _list_store_files(self, urgent:bool=False):
        try:
            files = sorted(f for f in os.listdir(self._store_path) if f.lower().endswith('.txt'))
        except OSError as exc:
            l.warning('Could not list answerbox directory %r: %r', self._store_path, exc)
            return []

        if urgent:
            files = [f for f in files if f.startswith('urgent_')]
        else:
            files = [f for f in files if not f.startswith('urgent_')]

        return [os.path.join(self._store_path, f) for f in files]

    def _queue_control(self, cmd:str):
        if cmd == 'ZZ':
            self._zz_active = True
        elif cmd in ('LT', 'PT', 'Z', 'A', 'AA', 'WB'):
            self._zz_active = False

        self._tx_queue.append('\x1b' + cmd)

    def _queue_text(self, text:str):
        for ch in text:
            self._tx_queue.append(ch)

    def _normalize_urgent_scan_text(self, text:str) -> str:
        return text.lower().replace('<', '').replace('>', '')

    def _load_global_wru_id(self) -> str:
        config_file = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'telex.json')

        try:
            import commentjson as json_mod
        except Exception:
            import json as json_mod

        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                cfg = json_mod.load(f)
            return str(cfg.get('wru_id', '') or 'pitelex-answerbox')
        except Exception:
            return 'pitelex-answerbox'

    @staticmethod
    def _parse_time(text):
        try:
            hh, mm = text.split(':', 1)
            return int(hh) * 60 + int(mm)
        except Exception:
            return None

    @staticmethod
    def _day_key(index:int):
        return ('mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun')[index]

    @staticmethod
    def _day_key_short(index:int):
        return ('mo', 'di', 'mi', 'do', 'fr', 'sa', 'so')[index]

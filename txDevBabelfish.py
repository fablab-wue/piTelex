#!/usr/bin/python3
"""
Telex Device - Babelfish (Baf)

Babelfish module for piTelex. Passively listens to incoming i-Telex
traffic, translates the received text via OpenAI and prints the translation
locally through the existing MCP/printer path.

Version 1.2.6
- AI translates raw text only; BaF formats all teleprinter output itself.
- BaF uses a separate SKIP/TRANSLATE decision step before translation.
- Decision prompt uses only configured answerbox urgent_words and global wru_id
  from telex.json/txConfig. No hardcoded marker words are invented.
- BaF formats for teleprinter: AE/OE/UE, SZ, uppercase, 68 columns, WR/ZL.
- BaF prints through MCP without MCP changes: wait for MCP:ZZ, start with
  ESC+LT, wait for ESC+AA, stop with ESC+ST.
- ESC+~+number is buffer feedback from the bus. The sender is irrelevant
  (piT, Ans, MCP or any other printer-like device may send it).
- The cheerful service-teleprinter footer is intentional. It is suppressed
  only if BaF is in night mode and the current input contains a configured
  answerbox urgent marker within urgent_scan_chars.
"""

__author__ = "WolfHenk"
__programming_tool__ = "ChatGPT 5.5 Thinking"
__email__ = "wolfhenk@wolfhenk.de"
__copyright__ = "2025-2026"
__license__ = "GPL3"
__version__ = "1.2.6"

"""
Revision history
----------------
2026APR12 - UPDATED - WH
2026APR26 - prompts optimized - WH
2026MAY10 - 1.2.1 - Raw AI translation only. BaF performs teleprinter
            formatting and paced MCP-managed output. ESC+~ feedback is accepted
            from every source, not only piT. WH / ChatGPT
2026MAY10 - Footer prompt sharpened: one meaningful sentence from a cheerful
            service teleprinter translator, Sirius Cybernetics tone, then
            handled by the same teleprinter formatter as body text. WH / ChatGPT
2026MAY11 - 1.2.2 - Track ESC+NTM/ESC+DTM bus mode. Default is daytime.
            In night mode, BaF suppresses the cheerful footer. WH / ChatGPT
2026MAY11 - 1.2.3 - Add separate AI decision step before translation.
            Decision prompt uses configured answerbox urgent_words and global
            wru_id from telex.json/txConfig, without hardcoded marker words
            or example WRU IDs. WH / ChatGPT
2026MAY11 - 1.2.4 - Footer is no longer suppressed for every NTM/night output.
            It is suppressed only for night messages containing a configured
            answerbox urgent marker within urgent_scan_chars. WH / ChatGPT
2026MAY11 - 1.2.5 - Do not start local BaF printing immediately after MCP:Z.
            After translation has been prepared, wait for MCP:ZZ first, then
            request MCP-managed printer start via ESC+LT. WH / ChatGPT
2026MAY11 - 1.2.6 - Footer prompt shortened. The Sirius-Cybernetics-style
            closing remains intentional, but the model is now told to produce
            one concise sentence of about 12 to 20 words. WH / ChatGPT
"""

import logging
import re
import unicodedata
from collections import deque
from typing import Deque, List, Optional

import openai
import txConfig
import txCode
import txBase

l = logging.getLogger("piTelex." + __name__)

OPENAI_MODEL = 'gpt-5.1'
ESC = "\x1b"
ESC_A = ESC + "A"
ESC_LT = ESC + "LT"
ESC_ST = ESC + "ST"

WR = "\r\r"      # Wagenruecklauf, doppelt wegen T100-Zeitreserve
ZL = "\n"        # Zeilenvorschub

MAX_SEGMENT_SIZE = 50000
MAX_LINE_LEN = 68

IDLE_HZ = 20.0
BITS_PER_CHAR = 7.5
START_BAUD = 55.0
MIN_BAUD = 35.0

BUF_TARGET = 7
BUF_MIN = 4
BUF_MAX = 10
BUF_HARD_MAX = 14
BUF_REPORT_STALE_TICKS = int(2 * IDLE_HZ)
BUF_DRAIN_TIMEOUT_TICKS = int(10 * IDLE_HZ)
BUF_EMPTY_STABLE_TICKS = int(0.5 * IDLE_HZ)
PRINTER_READY_TIMEOUT_TICKS = int(8 * IDLE_HZ)
NO_BUF_END_WAIT_TICKS = int(1.5 * IDLE_HZ)

TX_IDLE = 0
TX_WAIT_MCP_IDLE = 5
TX_REQUEST_PRINTER = 10
TX_WAIT_PRINTER_READY = 20
TX_SEND_TEXT = 30
TX_WAIT_DRAIN = 40
TX_SEND_STOP = 50

ALLOWED_PRINTABLE = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 .,?:-/'()+=")

ESC_CLEAN_RE = re.compile(
    rb'\x1b(?:WELCOME|EXIT|DATE|FONT|CLI|TP[01]|AA|ZZ|AT|ST|LT|WB|PT|1T|NTM|DTM|~[0-9]+|\^[0-9]+|[AZI])'
)


class TelexBabelfish(txBase.TelexBase):
    def __init__(self, **params):
        self.coding = txConfig.CFG.get('coding', 0)
        super().__init__()
        self.id = params.get('id', 'Baf')
        self.target_lang = params.get('language', 'Deutsch')
        if (key := params.get('openai_api_key')):
            openai.api_key = key
        self.footer_fallback = params.get('footer_fallback', '')

        self._wru_id = str(txConfig.CFG.get('wru_id', '') or '').strip()
        self._operational_marker_words = self._load_operational_marker_words()
        self._urgent_scan_chars = self._load_urgent_scan_chars()

        # Default is daytime. Answerbox broadcasts NTM/DTM on the bus.
        self._night_mode = False

        # MCP idle means the line is really free. MCP:Z is not enough.
        self._mcp_idle = False

        self._rx_buffer: List[str] = []
        self._iTs_buffer = bytearray()
        self._session_open = False
        self._input_end_pending = False
        self._translation_active = False

        self._tx_state = TX_IDLE
        self._tx_queue: Deque[str] = deque()
        self._tx_timer = 0
        self._tx_baud = START_BAUD
        self._tx_accumulator = 0.0
        self._printer_ready_seen = False

        self._buf_load_seen = False
        self._last_buf_load: Optional[int] = None
        self._buf_report_age = BUF_REPORT_STALE_TICKS + 1
        self._tx_paused_by_buffer = False
        self._drain_wait_ticks = 0
        self._buf_empty_ticks = 0

        l.info(f"{self.id} initialized with model: {OPENAI_MODEL}")

    # ------------------------------------------------------------------
    # piTelex device interface

    def read(self) -> str:
        return self._rx_buffer.pop(0) if self._rx_buffer else ''

    def write(self, data: str, source: str):
        if source in (self.id, 'Baf'):
            return False

        tokens = self._extract_escape_tokens(data)
        self._handle_mode_tokens(tokens, source)
        self._handle_buffer_tokens(tokens, source)

        if source == 'iTs':
            if data != '\x1b^0':
                self._iTs_buffer.extend(data.encode('utf-8', 'replace'))
        elif source == 'MCP':
            self._handle_mcp_tokens(tokens)
        else:
            self._handle_generic_tokens(tokens, source)
        return None

    def idle20Hz(self):
        self._detect_input_session_start()

        if self._session_open and len(self._iTs_buffer) > MAX_SEGMENT_SIZE:
            l.error(f"{self.id}: Session aborted, ESC+Z missing at max segment size")
            self._reset_input_capture()

        if self._input_end_pending and not self._translation_active:
            self._process_finished_input_session()

        self._tick_output_state()

    # ------------------------------------------------------------------
    # ESC token handling

    @staticmethod
    def _extract_escape_tokens(data: str) -> List[str]:
        tokens: List[str] = []
        i = 0
        n = len(data)
        while i < n:
            if data[i] != ESC:
                i += 1
                continue

            rest = data[i + 1:]
            matched = None
            for tok in (
                'WELCOME', 'EXIT', 'DATE', 'FONT', 'CLI',
                'TP0', 'TP1', 'AA', 'ZZ', 'AT', 'ST', 'LT', 'WB', 'PT', '1T',
                'NTM', 'DTM', 'A', 'Z', 'I'
            ):
                if rest.startswith(tok):
                    matched = tok
                    break

            if matched is not None:
                tokens.append(matched)
                i += 1 + len(matched)
                continue

            if rest.startswith('~'):
                j = i + 2
                while j < n and data[j].isdigit():
                    j += 1
                tokens.append(data[i + 1:j])
                i = j
                continue

            if rest.startswith('^'):
                j = i + 2
                while j < n and data[j].isdigit():
                    j += 1
                tokens.append(data[i + 1:j])
                i = j
                continue

            if i + 1 < n:
                tokens.append(data[i + 1])
                i += 2
            else:
                i += 1
        return tokens

    def _handle_mcp_tokens(self, tokens: List[str]):
        for token in tokens:
            if token == 'ZZ':
                self._mcp_idle = True
                l.debug(f"{self.id}: MCP idle reported by ZZ")
                continue

            if token == 'Z':
                self._mcp_idle = False
                if self._session_open:
                    self._input_end_pending = True
                if self._tx_state in (TX_WAIT_PRINTER_READY, TX_SEND_TEXT, TX_WAIT_DRAIN):
                    l.warning(f"{self.id}: MCP sent Z during BaF output, aborting")
                    self._abort_output()
                continue

            if token in ('A', 'TP1', 'TP0'):
                self._mcp_idle = False
                if token == 'TP0' and self._tx_state in (TX_WAIT_PRINTER_READY, TX_SEND_TEXT, TX_WAIT_DRAIN):
                    l.warning(f"{self.id}: MCP sent TP0 during BaF output, aborting")
                    self._abort_output()
                continue

            if token == 'AA':
                if self._tx_state == TX_WAIT_PRINTER_READY:
                    l.info(f"{self.id}: Printer ready reported by MCP")
                    self._printer_ready_seen = True
                continue

    def _handle_generic_tokens(self, tokens: List[str], source: str):
        for token in tokens:
            if token == 'AA' and self._tx_state == TX_WAIT_PRINTER_READY:
                l.info(f"{self.id}: Printer ready reported by {source}")
                self._printer_ready_seen = True

    def _handle_mode_tokens(self, tokens: List[str], source: str):
        for token in tokens:
            if token == 'NTM':
                if not self._night_mode:
                    l.info(f"{self.id}: NTM received from {source}, night mode active")
                self._night_mode = True
            elif token == 'DTM':
                if self._night_mode:
                    l.info(f"{self.id}: DTM received from {source}, day mode active")
                self._night_mode = False

    def _handle_buffer_tokens(self, tokens: List[str], source: str):
        # ESC+~+number is the regulation signal. The source is deliberately
        # ignored. It can be piT, Ans, MCP or any other printer-like device.
        if self._tx_state not in (TX_SEND_TEXT, TX_WAIT_DRAIN):
            return
        for token in tokens:
            if not token.startswith('~'):
                continue
            try:
                load = int(token[1:])
            except ValueError:
                continue
            self._update_buffer_load(load, source)

    # ------------------------------------------------------------------
    # Config helpers

    def _load_operational_marker_words(self) -> List[str]:
        """
        Load only the urgent marker words registered in telex.json under
        devices.answerbox.urgent_words. No BaF-specific fallback words are
        added here. If answerbox or urgent_words is not configured, the list
        remains empty.
        """
        markers: List[str] = []
        try:
            devices = txConfig.CFG.get('devices', {}) or {}
            ans_cfg = devices.get('answerbox', {}) or {}
            urgent_words = ans_cfg.get('urgent_words', []) or []
            if isinstance(urgent_words, str):
                urgent_words = [urgent_words]
            for word in urgent_words:
                word = str(word).strip()
                if word and word not in markers:
                    markers.append(word)
        except Exception as e:
            l.warning(f"{self.id}: Could not load answerbox urgent_words: {e}")
        return markers

    def _load_urgent_scan_chars(self) -> int:
        try:
            devices = txConfig.CFG.get('devices', {}) or {}
            ans_cfg = devices.get('answerbox', {}) or {}
            value = int(ans_cfg.get('urgent_scan_chars', 100) or 100)
            return max(1, value)
        except Exception as e:
            l.warning(f"{self.id}: Could not load answerbox urgent_scan_chars: {e}")
            return 100

    @staticmethod
    def _format_prompt_list(items: List[str]) -> str:
        clean: List[str] = []
        for item in items:
            item = str(item).strip()
            if item and item not in clean:
                clean.append(item)
        if not clean:
            return "none configured"
        return ", ".join(repr(item) for item in clean)

    # ------------------------------------------------------------------
    # Prompts

    @staticmethod
    def build_translation_decision_prompt(target_lang: str, wru_id: str = '',
                                          marker_words: Optional[List[str]] = None) -> str:
        marker_text = TelexBabelfish._format_prompt_list(marker_words or [])
        wru_text = repr(wru_id) if wru_id else "none configured"
        return (
            f"You decide whether a teleprinter message needs translation. "
            f"The target language is {target_lang}. "
            f"Return exactly one word: SKIP or TRANSLATE. "
            f"Ignore teleprinter artefacts, station IDs, headers, footers, "
            f"former shift markers, and WRU/callsign lines. "
            f"The configured WRU/callsign for this station is: {wru_text}. "
            f"Also ignore these configured operational marker words when deciding "
            f"the language of the message: {marker_text}. "
            f"If no operational marker words are configured, do not invent any. "
            f"Configured marker words alone must not make you treat an otherwise "
            f"target-language message as foreign text. "
            f"A message is still considered to be in the target language if it "
            f"contains isolated foreign technical terms, names, abbreviations, "
            f"callsigns, product names, the configured WRU/callsign, or configured "
            f"operational marker words. "
            f"If the meaningful body text is already in {target_lang}, respond SKIP. "
            f"If there is no meaningful body text left after ignoring artefacts, "
            f"respond SKIP. "
            f"If the meaningful body text is not in {target_lang} and should be "
            f"translated, respond TRANSLATE. "
            f"Do not explain your decision."
        )

    @staticmethod
    def build_translation_prompt(target_lang: str, wru_id: str = '',
                                 marker_words: Optional[List[str]] = None) -> str:
        marker_text = TelexBabelfish._format_prompt_list(marker_words or [])
        wru_text = repr(wru_id) if wru_id else "none configured"
        return (
            f"You are a professional translator. "
            f"Translate the following message into {target_lang}. "
            f"Return only the translated text, with no explanations, notes, comments, "
            f"markdown, labels, or quotation marks around the whole answer. "
            f"Do not use emojis or decorative symbols. "
            f"Never translate the message into any language other than {target_lang}. "
            f"Ignore teleprinter artefacts such as WRU/callsigns, station IDs, "
            f"leading or trailing header/footer lines, and former shift markers. "
            f"The configured WRU/callsign for this station is: {wru_text}. "
            f"Also ignore these configured operational marker words as language "
            f"evidence: {marker_text}. "
            f"If no operational marker words are configured, do not invent any. "
            f"The text may contain dialect, slang, abbreviations, technical words, "
            f"product names, marker words, or jokes. "
            f"Do not over-interpret unclear wording. Translate what you can and leave "
            f"unknown tokens verbatim. "
            f"Respond with 'SKIP' only if, after ignoring teleprinter artefacts, "
            f"there is no translatable body text left at all. "
            f"If the remaining meaningful message is already in {target_lang}, "
            f"respond with 'SKIP'."
        )

    @staticmethod
    def build_footer_prompt(target_lang: str) -> str:
        return (
            f"You are an overly cheerful service teleprinter translator. "
            f"You have just translated a message and are sincerely delighted "
            f"that the user allowed you to help understand foreign text. "
            f"Write exactly one complete sentence. "
            f"The sentence must be short, friendly, deeply grateful, "
            f"mechanically polite, and slightly absurdly pleased about being useful, "
            f"in the spirit of the cheerful service devices of the "
            f"'Sirius Cybernetics Corporation' from Douglas Adams' "
            f"'The Hitchhiker's Guide to the Galaxy'. "
            f"Keep it concise. Aim for about 12 to 20 words. "
            f"Do not write a long or ornate sentence. "
            f"Do not use multiple sentences. "
            f"Do not use emojis, decorative symbols, exclamation marks, "
            f"markdown, labels, explanations, or quotation marks around the answer. "
            f"Do not mention doors, books, authors, characters, companies, or titles. "
            f"Respond strictly in {target_lang}. "
            f"Return only the one footer sentence."
        )

    def _default_footer(self) -> str:
        if self.footer_fallback:
            return self.footer_fallback
        lang = str(self.target_lang).lower()
        if 'deutsch' in lang or 'german' in lang:
            return "ICH BIN FREUDIG ERFOLGREICH FERTIG GEWORDEN."
        return "I AM DELIGHTED TO HAVE BEEN OF SERVICE."

    # ------------------------------------------------------------------
    # Text preparation

    @staticmethod
    def strip_wru_blocks(segment: bytes) -> bytes:
        return segment

    @staticmethod
    def strip_all_escape_sequences(segment: bytes) -> bytes:
        return ESC_CLEAN_RE.sub(b'', segment)

    @staticmethod
    def normalize_input_text(text: str) -> str:
        text = re.sub(r'\r\n|\n\r|\r|\n', '\n', text)
        text = text.replace('<', '').replace('>', '').replace('#', '')
        text = re.sub(r'[ \t]+', ' ', text)
        text = re.sub(r' *\n+ *', '\n', text)
        return text.strip()

    @staticmethod
    def normalize_line_endings(text: str) -> str:
        return re.sub(r'\r\n|\n\r|\r|\n', '\n', text)

    @staticmethod
    def sanitize_for_teleprinter(text: str) -> str:
        replacements = {
            'Ä': 'AE', 'Ö': 'OE', 'Ü': 'UE', 'ẞ': 'SZ',
            'ä': 'AE', 'ö': 'OE', 'ü': 'UE', 'ß': 'SZ',
            '„': "'", '“': "'", '”': "'", '"': "'",
            '’': "'", '‘': "'", '´': "'", '`': "'",
            '–': '-', '—': '-', '−': '-',
            '…': '...', '!': '.', '&': ' UND ', '@': ' AT ', '°': '', '\t': ' ',
        }
        for src, dst in replacements.items():
            text = text.replace(src, dst)
        text = unicodedata.normalize('NFKD', text)
        text = ''.join(ch for ch in text if not unicodedata.combining(ch))
        text = text.upper()

        out: List[str] = []
        last_space = False
        last_nl = False
        for ch in text:
            if ch in ('\n', '\r'):
                if not last_nl:
                    out.append('\n')
                last_space = False
                last_nl = True
                continue
            last_nl = False
            if ch in ALLOWED_PRINTABLE:
                if ch == ' ':
                    if not last_space:
                        out.append(ch)
                    last_space = True
                else:
                    out.append(ch)
                    last_space = False
            else:
                if not last_space:
                    out.append(' ')
                    last_space = True
        cleaned = ''.join(out)
        cleaned = re.sub(r' *\n *', '\n', cleaned)
        cleaned = re.sub(r' {2,}', ' ', cleaned)
        cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
        return cleaned.strip()

    @staticmethod
    def wrap_teleprinter_lines(text: str, width: int = MAX_LINE_LEN,
                               max_lines: Optional[int] = None) -> List[str]:
        text = TelexBabelfish.normalize_line_endings(text).strip()
        if not text:
            return []
        wrapped: List[str] = []
        for paragraph in re.split(r'\n+', text):
            paragraph = re.sub(r' +', ' ', paragraph).strip()
            if not paragraph:
                continue
            line = ''
            for word in paragraph.split(' '):
                if not word:
                    continue
                if len(word) > width:
                    if line:
                        wrapped.append(line)
                        line = ''
                    while len(word) > width:
                        wrapped.append(word[:width])
                        word = word[width:]
                    line = word
                    continue
                candidate = word if not line else f"{line} {word}"
                if len(candidate) <= width:
                    line = candidate
                else:
                    if line:
                        wrapped.append(line)
                    line = word
                if max_lines is not None and len(wrapped) >= max_lines:
                    return wrapped[:max_lines]
            if line:
                wrapped.append(line)
            if max_lines is not None and len(wrapped) >= max_lines:
                return wrapped[:max_lines]
        return wrapped[:max_lines] if max_lines is not None else wrapped

    @staticmethod
    def prepare_telex_lines(text: str, max_lines: Optional[int] = None) -> List[str]:
        return TelexBabelfish.wrap_teleprinter_lines(
            TelexBabelfish.sanitize_for_teleprinter(text), MAX_LINE_LEN, max_lines
        )

    @staticmethod
    def join_telex_lines(lines: List[str]) -> str:
        return (WR + ZL).join(lines)

    @staticmethod
    def compose_telex_text(body_lines: List[str], footer_lines: Optional[List[str]] = None) -> str:
        body = TelexBabelfish.join_telex_lines(body_lines)
        if footer_lines:
            footer = TelexBabelfish.join_telex_lines(footer_lines)
            return body + WR + ZL + ZL + footer if body else footer
        return body

    def call_openai(self, system_prompt: str, user_text: Optional[str] = None) -> str:
        messages = [{'role': 'system', 'content': system_prompt}]
        if user_text is not None:
            messages.append({'role': 'user', 'content': user_text})
        resp = openai.chat.completions.create(model=OPENAI_MODEL, messages=messages)
        content = resp.choices[0].message.content
        return content.strip() if content else ''

    # ------------------------------------------------------------------
    # Input session and translation

    def _detect_input_session_start(self):
        if self._session_open or self._tx_state != TX_IDLE:
            return
        needle = ESC_A.encode()
        if needle not in self._iTs_buffer:
            return
        start_idx = self._iTs_buffer.find(needle)
        self._iTs_buffer = self._iTs_buffer[start_idx + len(needle):]
        self._session_open = True
        self._input_end_pending = False
        l.info(f"{self.id}: Session started")

    def _process_finished_input_session(self):
        self._translation_active = True
        self._input_end_pending = False
        segment = self._iTs_buffer[:]
        self._iTs_buffer.clear()
        self._session_open = False
        try:
            self._prepare_translation_from_segment(segment)
        except Exception as e:
            l.error(f"{self.id}: Translation error: {e}")
            self._reset_input_capture()
        finally:
            self._translation_active = False

    def _decide_translation(self, text: str) -> str:
        decision = self.call_openai(
            self.build_translation_decision_prompt(
                self.target_lang,
                self._wru_id,
                self._operational_marker_words
            ),
            text
        ).strip().upper()

        if decision.startswith('SKIP'):
            return 'SKIP'
        if decision.startswith('TRANSLATE'):
            return 'TRANSLATE'
        return decision

    def _message_has_urgent_marker(self, text: str) -> bool:
        if not self._operational_marker_words:
            return False
        scan_text = text[:self._urgent_scan_chars].lower()
        for marker in self._operational_marker_words:
            if marker and marker.lower() in scan_text:
                return True
        return False

    def _prepare_translation_from_segment(self, segment: bytes):
        cleaned = self.strip_all_escape_sequences(self.strip_wru_blocks(segment))
        text = self.normalize_input_text(cleaned.decode('utf-8', 'replace'))
        l.info(f"{self.id}: Raw text bytes: {segment}")
        l.info(f"{self.id}: Payload received ({len(text)} characters)")
        l.info(f"{self.id}: Text to be translated: {text}")
        if not text:
            l.info(f"{self.id}: Translation skipped (empty payload after cleanup)")
            self._reset_input_capture()
            return

        decision = self._decide_translation(text)
        if decision == "SKIP":
            l.info(f"{self.id}: Translation skipped by decision prompt")
            self._reset_input_capture()
            return
        if decision != "TRANSLATE":
            l.warning(f"{self.id}: Invalid translation decision {decision!r}, translating anyway")

        translation = self.call_openai(
            self.build_translation_prompt(
                self.target_lang,
                self._wru_id,
                self._operational_marker_words
            ),
            text
        )
        if translation.strip().upper() == "SKIP":
            l.info(f"{self.id}: Translation skipped (SKIP detected)")
            self._reset_input_capture()
            return

        body_lines = self.prepare_telex_lines(translation)
        if not body_lines:
            l.info(f"{self.id}: Translation skipped (empty after cleanup)")
            self._reset_input_capture()
            return
        l.info(f"{self.id}: Translation prepared ({len(body_lines)} lines)")

        suppress_footer = self._night_mode and self._message_has_urgent_marker(text)
        if suppress_footer:
            l.info(f"{self.id}: Night urgent message, cheerful footer suppressed")
            footer_lines: List[str] = []
        else:
            footer_lines = self._prepare_footer_lines()

        full_text = self.compose_telex_text(body_lines, footer_lines)
        ba = txCode.BaudotMurrayCode.translate(full_text)
        self._start_output_queue(list(WR + ZL + ba + WR + ZL))

    def _prepare_footer_lines(self) -> List[str]:
        footer_text = ''
        try:
            footer_text = self.call_openai(self.build_footer_prompt(self.target_lang))
            l.info(f"{self.id}: Cheerful service closing sentence: {footer_text}")
        except Exception as e:
            l.warning(f"{self.id}: Footer AI failed, using fallback: {e}")
        if not footer_text:
            footer_text = self._default_footer()
        lines = self.prepare_telex_lines(footer_text)
        if not lines:
            lines = self.prepare_telex_lines(self._default_footer())
        return lines

    # ------------------------------------------------------------------
    # Output state machine

    def _start_output_queue(self, chars: List[str]):
        self._tx_queue = deque(chars)
        self._tx_state = TX_WAIT_MCP_IDLE
        self._tx_timer = 0
        self._tx_baud = START_BAUD
        self._tx_accumulator = 0.0
        self._printer_ready_seen = False
        self._buf_load_seen = False
        self._last_buf_load = None
        self._buf_report_age = BUF_REPORT_STALE_TICKS + 1
        self._tx_paused_by_buffer = False
        self._drain_wait_ticks = 0
        self._buf_empty_ticks = 0
        l.info(f"{self.id}: Output queued ({len(chars)} characters), waiting for MCP:ZZ")

    def _tick_output_state(self):
        if self._tx_state == TX_IDLE:
            return

        if self._tx_state == TX_WAIT_MCP_IDLE:
            if self._mcp_idle:
                l.info(f"{self.id}: MCP:ZZ seen, requesting MCP-managed printer start via LT")
                self._tx_state = TX_REQUEST_PRINTER
                self._tx_timer = 0
                return
            self._tx_timer += 1
            if self._tx_timer % int(5 * IDLE_HZ) == 0:
                l.info(f"{self.id}: Waiting for MCP:ZZ before local print output")
            return

        if self._tx_state == TX_REQUEST_PRINTER:
            self._rx_buffer.append(ESC_LT)
            self._mcp_idle = False
            self._tx_state = TX_WAIT_PRINTER_READY
            self._tx_timer = 0
            return

        if self._tx_state == TX_WAIT_PRINTER_READY:
            self._tx_timer += 1
            if self._printer_ready_seen:
                l.info(f"{self.id}: Printer ready, starting paced transmission")
                self._tx_state = TX_SEND_TEXT
                self._tx_timer = 0
                return
            if self._tx_timer > PRINTER_READY_TIMEOUT_TICKS:
                l.warning(f"{self.id}: Printer did not become ready, stopping output")
                self._rx_buffer.append(ESC_ST)
                self._reset_output_state()
                return

        elif self._tx_state == TX_SEND_TEXT:
            self._age_buffer_report()
            self._send_one_char_if_due()
            if not self._tx_queue:
                self._tx_state = TX_WAIT_DRAIN
                self._drain_wait_ticks = 0
                self._buf_empty_ticks = 0
                l.info(f"{self.id}: Text queue empty, waiting for printer buffer to drain")

        elif self._tx_state == TX_WAIT_DRAIN:
            self._age_buffer_report()
            self._drain_wait_ticks += 1
            if self._buf_load_seen and self._last_buf_load == 0:
                self._buf_empty_ticks += 1
            else:
                self._buf_empty_ticks = 0
            if self._buf_empty_ticks >= BUF_EMPTY_STABLE_TICKS:
                self._tx_state = TX_SEND_STOP
                return
            if not self._buf_load_seen and self._drain_wait_ticks >= NO_BUF_END_WAIT_TICKS:
                self._tx_state = TX_SEND_STOP
                return
            if self._drain_wait_ticks >= BUF_DRAIN_TIMEOUT_TICKS:
                l.warning(f"{self.id}: Printer buffer drain timeout, stopping anyway")
                self._tx_state = TX_SEND_STOP
                return

        elif self._tx_state == TX_SEND_STOP:
            l.info(f"{self.id}: Stopping MCP-managed printer session via ST")
            self._rx_buffer.append(ESC_ST)
            self._reset_output_state()

    def _update_buffer_load(self, load: int, source: str):
        old = self._last_buf_load
        self._last_buf_load = load
        self._buf_load_seen = True
        self._buf_report_age = 0
        trend = 0 if old is None else old - load
        error = BUF_TARGET - load
        correction = 1.2 * error + 1.4 * trend
        if load < BUF_MIN:
            correction += 4.0
        elif load > BUF_MAX:
            correction -= 5.0
        self._tx_baud += correction
        if self._tx_baud < MIN_BAUD:
            self._tx_baud = MIN_BAUD
        if load >= BUF_HARD_MAX:
            self._tx_paused_by_buffer = True
        elif load <= BUF_MAX:
            self._tx_paused_by_buffer = False
        l.debug(
            f"{self.id}: buffer load {load} from {source}, trend {trend}, "
            f"tx_baud {self._tx_baud:.1f}, paused {self._tx_paused_by_buffer}"
        )

    def _age_buffer_report(self):
        self._buf_report_age += 1
        if self._buf_report_age > BUF_REPORT_STALE_TICKS:
            if self._tx_baud > START_BAUD:
                self._tx_baud = max(START_BAUD, self._tx_baud - 0.5)
            elif self._tx_baud < START_BAUD:
                self._tx_baud = min(START_BAUD, self._tx_baud + 0.5)
            self._tx_paused_by_buffer = False

    def _send_one_char_if_due(self):
        if not self._tx_queue:
            return
        if self._tx_paused_by_buffer:
            self._tx_accumulator = 0.0
            return
        cps = self._tx_baud / BITS_PER_CHAR
        self._tx_accumulator += cps / IDLE_HZ
        if self._tx_accumulator > 1.0:
            self._tx_accumulator = 1.0
        if self._tx_accumulator >= 1.0:
            self._rx_buffer.append(self._tx_queue.popleft())
            self._tx_accumulator -= 1.0

    def _abort_output(self):
        self._rx_buffer.append(ESC_ST)
        self._reset_output_state()

    def _reset_output_state(self):
        self._tx_state = TX_IDLE
        self._tx_queue.clear()
        self._tx_timer = 0
        self._tx_baud = START_BAUD
        self._tx_accumulator = 0.0
        self._printer_ready_seen = False
        self._buf_load_seen = False
        self._last_buf_load = None
        self._buf_report_age = BUF_REPORT_STALE_TICKS + 1
        self._tx_paused_by_buffer = False
        self._drain_wait_ticks = 0
        self._buf_empty_ticks = 0

    def _reset_input_capture(self, keep_pending: bool = False):
        self._iTs_buffer.clear()
        self._session_open = False
        if not keep_pending:
            self._input_end_pending = False


def main():
    cfg = txConfig.CFG
    dev_cfg = cfg.get('devices', {}).get('babelfish', {})
    if dev_cfg.get('enable', False):
        TelexBabelfish(**dev_cfg)


if __name__ == '__main__':
    main()

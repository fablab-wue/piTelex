#!/usr/bin/python3
"""
Telex Device - Babelfish (Baf)
Version     : 1.0.0
Ersteller   : Wolfram (38718 wlfhnk d) mit KI-Assistant
Datum       : 2025-04-18

Babelfish-Modul für piTelex. Lauscht passiv auf den Datenstrom,
startet bei ESC+A von iTs, beendet bei ESC+Z von MCP,
filtert WRUs, übersetzt den Text via OpenAI und gibt ihn
über Telex zurück.
"""

import re
import time
import logging
import openai
import txConfig
import txCode
import txBase

l = logging.getLogger("piTelex." + __name__)

OPENAI_MODEL = 'gpt-4-turbo'
ESC = "\x1b"
ESC_A = ESC + "A"
ESC_Z = ESC + "Z"
MAX_SEGMENT_SIZE = 50000
WRU_BLOCK_REGEX = rb"#.{0,4}\n+.+\n+.{5,30}\n"

class TelexBabelfish(txBase.TelexBase):

    def __init__(self, **params):
        self.coding = txConfig.CFG.get('coding', 0)
        super().__init__()
        self.id = params.get('id', 'Baf')
        self.target_lang = params.get('language', 'Deutsch')
        if (key := params.get('openai_api_key')):
            openai.api_key = key
        self._iTs_buffer = bytearray()
        self._mcp_buffer = bytearray()
        self._processing = False
        self._translation = None
        self._out_buffer = []
        self._state_counter = 1
        self._rx_buffer = []
        self._last_pit_load = 0
        l.info(f"{self.id} initialized with model: {OPENAI_MODEL}")

    def read(self) -> str:
        return self._rx_buffer.pop(0) if self._rx_buffer else ''

    def write(self, data: str, source: str):
        if source == 'iTs':
            if data != '\x1b^0':
                self._iTs_buffer.extend(data.encode('utf-8', 'replace'))
        elif source == 'MCP':
            self._mcp_buffer.extend(data.encode('utf-8', 'replace'))
        elif source == 'piT' and data.startswith('\x1b~'):
            try:
                self._last_pit_load = int(data[2:])
            except ValueError:
                pass

    @staticmethod
    def strip_wru_blocks(segment: bytes) -> bytes:
        return re.sub(WRU_BLOCK_REGEX, b'', segment)

    @staticmethod
    def strip_all_escape_sequences(segment: bytes) -> bytes:
        return re.sub(rb'\x1b[\^~0-9A-Z]{1,3}', b'', segment)

    def idle20Hz(self):
        if not self._processing:
            if ESC_A.encode() in self._iTs_buffer:
                start = self._iTs_buffer.find(ESC_A.encode())
                self._iTs_buffer = self._iTs_buffer[start:]

                if len(self._iTs_buffer) > MAX_SEGMENT_SIZE:
                    l.error("Session aborted: ESC+Z missing at max segment size")
                    self._iTs_buffer.clear()
                    self._mcp_buffer.clear()
                    return

                if ESC_Z.encode() in self._mcp_buffer:
                    segment = self._iTs_buffer[:]
                    self._iTs_buffer.clear()
                    self._mcp_buffer.clear()

                    cleaned = self.strip_all_escape_sequences(self.strip_wru_blocks(segment))
                    cleaned = cleaned.replace(b'<', b'').replace(b'>', b'').replace(b'#', b'')
                    try:
                        text = cleaned.decode('utf-8', 'replace')
                        l.info(f"{self.id}: Payload received ({len(text)} characters)")
                        l.info(f"{self.id}: Text to be translated: {text}")

                        system_prompt = (
    f"You are an automatic translator."
    f"Translate the following message into {self.target_lang}."
    "The text might include dialects, slang or jokes."
    "Return only the pure translation, no explanations."
    "Break lines at word boundaries, each max 68 characters."
    "If the message is already in the target language or nonsense, reply with 'SKIP'."
    "Do not judge the meaning too strictly."
)

                        resp = openai.chat.completions.create(
                            model=OPENAI_MODEL,
                            messages=[
                                {'role': 'system', 'content': system_prompt},
                                {'role': 'user', 'content': text}
                            ]
                        )
                        self._translation = resp.choices[0].message.content.strip()
                        if self._translation.lower() == "skip":
                            l.info(f"{self.id}: Translation skipped (SKIP detected)")
                            self._processing = False
                            self._state_counter = 1
                            self._iTs_buffer.clear()
                            self._mcp_buffer.clear()
                            self._out_buffer.clear()
                            return

                        l.info(f"{self.id}: Translation received ({len(self._translation)} characters)")

                        abschluss_prompt = (
    f"Imagine you're an overly friendly teleprinter from 'Hitchhiker's Guide to the Galaxy'. "
    f"Thank the user for letting you help. "
    f"The line must sound overly cheerful, mechanical, and unnecessarily enthusiastic. "
    f"Only one single line. Never more than 68 characters – hard limit. Umlauts count as 2. "
    f"Use periods (.) instead of exclamation marks. Commas and question marks are allowed. "
    f"NEVER use exclamation marks (!), encoded symbols, or emojis. "
    f"Respond strictly in {self.target_lang}."
)
                        try:
                            footer_resp = openai.chat.completions.create(
                                model=OPENAI_MODEL,
                                messages=[
                                    {"role": "system", "content": abschluss_prompt}
                                ]
                            )
                            footer_line = footer_resp.choices[0].message.content
                            l.info(f"{self.id}: Closing line: {footer_line}")
                        except Exception as e:
                            footer_line = ""
                            l.warning(f"{self.id}: No emotional closing received: {e}")

                        full_text = self._translation + "\r\r\n\n" + footer_line
                        ba = txCode.BaudotMurrayCode.translate(full_text)
                        self._out_buffer = list('\r\n' + ba + '\r\n')
                        self._processing = True
                        self._state_counter = 1
                    except Exception as e:
                        l.error(f"{self.id}: Translation error: {e}")

        if self._processing:
            self._state_counter += 1
            if self._state_counter == 2:
                l.info(f"{self.id}: Motor start sent")
                self._rx_buffer.append(ESC_A)

            if self._state_counter > 25:
                for ch in self._out_buffer:
                    self._rx_buffer.append(ch)
                self._rx_buffer.append(ESC_Z)
                l.info(f"{self.id}: Transmission complete")
                self._processing = False
                self._translation = None
                self._state_counter = 1
                self._iTs_buffer.clear()
                self._mcp_buffer.clear()
                self._out_buffer.clear()

def main():
    cfg = txConfig.CFG
    dev_cfg = cfg.get('devices', {}).get('babelfish', {})
    if dev_cfg.get('enable', False):
        TelexBabelfish(**dev_cfg)

if __name__ == '__main__':
    main()

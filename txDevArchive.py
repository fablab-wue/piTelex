#!/usr/bin/env python3
"""
Telex Device - Archive all printed messages
"""
__author__      = "Björn Schließmann"
__license__     = "GPL3"

import datetime
import os
import re

import logging
l = logging.getLogger("piTelex." + __name__)

import txBase

# ASCII shifts (called "direction shifts" from here on out) for tagging
# inbound/outbound text
INBOUND =  "\x0e" # SI
OUTBOUND = "\x0f" # SO

# ANSI colour escape codes
ANSI_RED_FOREGROUND = "\x1b[31m"
ANSI_RESET = "\x1b[0m"

class TelexArchive(txBase.TelexBase):
    def __init__(self, **params):
        super().__init__()

        self.id = 'Arc'
        self.params = params

        self._current_msg = []
        # Internal states:
        # - 0: idle / startup
        # - 1: dialling
        # - 2: recording message
        self._state = 0
        # Direction of characters (for text colour):
        # - False: inbound
        # - True: outbound
        # - None: undefined
        self._direction_out = None
        # Number dialled (for discerning inbound/outbound connection)
        self._dial_number = None
        # Time when connection was made
        self._timestamp = None

        # The subdirectory to place archive files in is read from
        # configuration. Relative paths are taken relative to where piTelex
        # scripts are stored; absolute paths are just that.
        self.arclog_path = params.get("path", "archive")
        if not self.arclog_path:
            self.arclog_path = "archive"
        if not os.path.isabs(self.arclog_path):
            self.arclog_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), self.arclog_path)

        try:
            os.mkdir(self.arclog_path)
        except FileExistsError:
            pass
        l.info("Archiving in {!r}".format(self.arclog_path))

    def __del__(self):
        self.exit()
        super().__del__()

    def exit(self):
        pass

    def read(self) -> str:
        return ''

    def write(self, data:str, source:str):
        """
        telex.py main loop writes all data passing through piTelex to us by
        this method.
        """
        if len(data) > 1:
            # this is a command
            if data == "\x1bWB":
                # Dialling triggered
                if self._state <= 1:
                    # Prevent rogue WB commands from resetting us
                    self._state = 1
            elif data.startswith("\x1b#") and self._state == 1:
                # Dial command: record. The number dialled last will remain
                # (and should be the one that was successful)
                self._dial_number = data[2:]
            elif data == "\x1bA":
                if self._state >= 2:
                    l.warning("Redundant printer start command detected (ignored)")
                    return
                self._state = 2
                l.info("recording new message") # TODO debug
                self._timestamp = datetime.datetime.now()
            elif data == "\x1bZ":
                if self._state <= 0:
                    l.warning("Redundant printer stop command detected (ignored)")
                    return
                elif self._state >= 2:
                    self.save_msg()
                self._direction_out = None
                self._state = 0
        else:
            # this is data
            if self._state < 1:
                # printer not running -- don't save data
                return
            # Data direction: Everything from </> (i-Telex server/client
            # module) is inbound, rest outbound
            direction_out = source not in ['iTc', 'iTs']
            if not direction_out == self._direction_out:
                # Direction changed, need to insert direction shift
                self._current_msg.append(OUTBOUND if direction_out else INBOUND)
                self._direction_out = direction_out
            # Filter data
            # TODO others?
            data = data.lower()
            self._current_msg.append(data)

    def filename(self, wru="[unknown]", direction="with", timestamp=None) -> str:
        """
        Return filename for an archive file.

        Optionally:

        - incorporate WRU string (use generic name if not given)
        - also a direction for naming (from/to/with)
        - use a struct_time for the timestamp (else "now")
        """
        fn = {}

        if not timestamp:
            timestamp = datetime.datetime.now()
        fn["timestamp"] = timestamp.strftime("%Y-%m-%d %H.%M.%S.%f")[:-3]

        fn["title"] = "msg {} {}".format(direction, wru)

        return os.path.join(self.arclog_path, "{timestamp} {title}.txt".format(**fn))

    @classmethod
    def find_WRU_answer(cls, data, inbound=False) -> str:
        """
        Extract the first WRU answerback from data and return it (stripped from
        line breaks and special characters).

        WRU answerbacks are specified in ITU-T S.6 as follows:
        - 20 characters long
        - following sequence:
          1. letter or figure shift
          2. CR
          3. LF
          4.-19. 16 signals
          20. letter shift (optional)

        We identify the answerback code like so (proudly supported by re
        module):
        - Filter out all colour ESC sequences, shifts and CRs
        - Trigger on first WRU character (@ or #, see below).
        - After this, allow for up to 4 characters until one or more newlines.
        - After this, the match group begins -- record 5..30 characters until
          the next newline. (In theory, only 17; allow for longer answerbacks)

        The previous sermon is only valid for outbound connections,
        unfortunately. Incoming connections are typically done as follows (pure
        convention however):
        - The remote sends WRU, we send our WRU answer
        - The remote triggers his own WRU answer

        To overcome this in most cases, if inbound=True is given, don't record
        the line directly after WRU, but the next one after that. Also, trigger
        on inbound WRU character (#) instead of outbound (@).
        """
        # Filter out direction shifts
        data = re.sub(pattern=INBOUND+"|"+OUTBOUND, string=data, repl="")
        # Filter out letter/figure shift, CR and CR helper character
        data = re.sub(pattern="<|>|\r|❮", string=data, repl="")
        # Find WRU answerback match and return it
        try:
            if inbound:
                match = re.findall("#.{0,4}\n+.+\n+(.{5,30})\n", data)[0]
            else:
                match = re.findall("@.{0,4}\n+(.{5,30})\n", data)[0]
        except IndexError:
            l.info("No WRU answerback found")
            return None
        else:
            return match

    @classmethod
    def prettify(self, msg) -> str:
        """
        Post-process the message msg to make it visually pleasing when
        "catting" in console.

        Currently, the following is done:
        - Remove letter/figure shift.
        - Replace ASCII Shift-in/Shift-Out used to discern inbound/outbound
          characters by ANSI escape sequences for text colour change.
        - Replace piTelex internal WRU characters by Unicode character U+2720
          (✠).
        - Insert a "❮" character wherever isolated CRs may lead to
          overprinting, to make this obvious.
        """
        # Remove letter/figure shifts
        msg = re.sub(pattern="<|>", string=msg, repl="")

        # Replace @/# by ✠
        msg = re.sub(pattern="@", string=msg, repl="✠")
        msg = re.sub(pattern="#", string=msg, repl="✠")

        # If a CR could lead to overprinting, replace it with "❮". The
        # following conditions apply:
        # - Every CR must be followed by another CR or a newline,
        # - except there are no printable characters between it and the newline
        #   before it.
        # Examples see in prettify_cr_test.

        # 1. Replace multiple consecutive CRs by one
        msg = re.sub(pattern="\r+", string=msg, repl="\r")
        # 2. Delete rogue CRs at beginnings of lines, allowing for a single
        # unprintable direction shift if present
        msg = re.sub(pattern="^([{}]?)\r".format(INBOUND+OUTBOUND), string=msg, repl="\g<1>", flags=re.MULTILINE)
        # 3. Replace by "<" all CRs not followed by newline
        msg = re.sub(pattern="\r([^\n])", string=msg, repl="❮\g<1>")

        # Replace direction shifts by ANSI ESC sequences for colour change
        msg = re.sub(pattern=OUTBOUND, string=msg, repl=ANSI_RED_FOREGROUND)
        msg = re.sub(pattern=INBOUND, string=msg, repl=ANSI_RESET)

        # Add a ANSI_RESET to avoid messing up the console
        return msg+ANSI_RESET

    def save_msg(self) -> str:
        """
        Save the current message to file and get ready for the next. Return the
        file name.
        """
        msg = "".join(self._current_msg)
        self._current_msg = []

        if self._dial_number:
            # outbound connection
            direction = "to"
            wru = self.find_WRU_answer(msg, inbound=False)
        else:
            # inbound connection
            direction = "from"
            wru = self.find_WRU_answer(msg, inbound=True)

        # Fallback if no WRU answer found
        if not wru:
            if self._dial_number:
                wru = self._dial_number
            else:
                wru = "[unknown]"
        self._dial_number = None

        filename = self.filename(wru=wru, direction=direction, timestamp=self._timestamp)
        self._timestamp = None

        l.info("saving {}, length {}".format(filename, len(msg)))
        with open(filename, mode="w", encoding="utf-8", newline="") as f:
            f.write(msg)
        return filename

prettify_cr_test = """
\rOK: "Rogue" CR at beginning of line
\r\r\rOK: Multiple CRs at beginning of line
Test data\r
Test data\r\r\r
Last two lines also ok: CR(s) at line ending
Test data 1\rTest data 2, not OK: First part will be overprinted
\r\r\rtest1\rtest2\r\r\rtest3\r\r
The previous line should render as 'test1❮test2❮test3'
"""

prettify_lf_test = """There should come a single newline after this
\r\x0fHow far down am I?"""+OUTBOUND

wru_outbound_test = """12345678+<<<<<<<\r
>88.88.8888  88:88\r
@<\r
>12345678< example d<>\r
87654321 <ich d\r
\r
---message---\r
>\r
87654321 <ich d>@<\r
>12345678< example d<"""

wru_inbound_test = """<<<\r
88.88.8888  88:88\r
>>#<\r
>87654321< ich d<>\r
12345678< example d<<<\r\r
\r
---message---\r
\r
>#<\r
>87654321< ich d<>\r
12345678< example d<<<"""

def main():
    import sys
    files = sys.argv[1:]
    if not files:
        print("""txDevArchive prettifier
Usage: {} <filename>""".format(sys.argv[0]))
        return
    import io
    for f in files:
        with io.open(f, mode="r", encoding="utf-8", newline="") as msg:
            msg = msg.read()
            print(TelexArchive.prettify(msg))

if __name__ == "__main__":
    main()

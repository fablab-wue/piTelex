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
import smtplib
from email.mime.text import MIMEText

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

        # E-Mail Konfiguration (direkt aus der archive-Konfiguration)
        self.email_enabled = params.get("send_email", False)
        self.smtp_server = params.get("smtp_server")
        self.smtp_port = params.get("smtp_port")
        self.smtp_user = params.get("smtp_user")
        self.smtp_password = params.get("smtp_password")
        self.recipient = params.get("recipient")
        self.email_sender = params.get("email_sender", "noreply@example.com")

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
        #ATTENTION DO NOT react to Baf (Babelfish) it will be an endless loop....
        if source == 'Baf':
            return
        #this prevents Archive from endless loop by repeating Babelfish translations... WH

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

        fname = fname_orig = "{timestamp} {title}.txt".format(**fn)
        # Replace illegal characters by U+FFFD. GNU/Linux tolerates most of
        # these, but Windows doesn't. Use lowest common denominator.
        for c in '\0\\/:*?"<>|':
            fname = fname.replace(c, "\ufffd")
        if fname != fname_orig:
            l.warning("Filename contains unsafe characters, replaced (\"{}\" => \"{}\")".format(fname_orig, fname))
        return os.path.join(self.arclog_path, fname)

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
        """
        # Remove letter/figure shifts
        msg = re.sub(pattern="<|>", string=msg, repl="")

        # Replace @/# by ✠
        msg = re.sub(pattern="@", string=msg, repl="✠")
        msg = re.sub(pattern="#", string=msg, repl="✠")

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
            direction = "to"
            wru = self.find_WRU_answer(msg, inbound=False)
        else:
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

        l.info(f"Saving {filename}, length {len(msg)}")
        try:
            with open(filename, "w", encoding="utf-8", newline="") as f:
                f.write(msg)
        except OSError as e:
            l.error(f"OS error while writing file: {e}")

        # E-Mail senden, wenn aktiviert
        if self.email_enabled and direction == "from":
            self.send_email(wru, msg)

        return filename

    def send_email(self, wru: str, msg: str):
        """
        Sendet die eingehende Nachricht per E-Mail, falls aktiviert.
        """
        if not all([self.smtp_server, self.smtp_port, self.smtp_user, self.smtp_password, self.recipient]):
            l.error("E-Mail-Versand konfiguriert, aber unvollständige Daten")
            return

        subject = f"Telex von {wru}"
        filtered_msg = self.filter_email_text(msg)

        email_msg = MIMEText(filtered_msg, "plain", "utf-8")
        email_msg["Subject"] = subject
        email_msg["From"] = self.email_sender
        email_msg["To"] = self.recipient

        try:
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.sendmail(self.email_sender, self.recipient, email_msg.as_string())
            l.info(f"E-Mail mit Telex von {wru} gesendet an {self.recipient}")
        except Exception as e:
            l.error(f"Fehler beim Senden der E-Mail: {e}")

    @staticmethod
    def filter_email_text(text: str) -> str:
        """
        Erlaubt nur bestimmte Zeichen im E-Mail-Text, ersetzt alle anderen mit "".
        """
        allowed_chars = " abcdefghijklmnopqrstuvwxyz0123456789-+=:/()?.,'\n\r@°"
        return "".join(c if c in allowed_chars else "" for c in text.lower())

def main():
    import sys
    files = sys.argv[1:]
    if not files:
        print(f"""txDevArchive prettifier
Usage: {sys.argv[0]} <filename>""")
        return
    import io
    for f in files:
        with io.open(f, mode="r", encoding="utf-8", newline="") as msg:
            msg = msg.read()
            print(TelexArchive.prettify(msg))

if __name__ == "__main__":
    main()


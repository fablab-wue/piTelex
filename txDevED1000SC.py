#!/usr/bin/python3
"""
Telex Device - ED1000 Communication over Sound Card - Transmit Only

Articles:
https://www.allaboutcircuits.com/technical-articles/fsk-explained-with-python/
https://dsp.stackexchange.com/questions/29946/demodulating-fsk-audio-in-python
https://stackoverflow.com/questions/35759353/demodulating-an-fsk-signal-in-python#

Protocol:
https://wiki.telexforum.de/index.php?title=ED1000_Verfahren_(Teil_2)

"""
__author__      = "Jochen Krapf"
__email__       = "jk@nerd2nerd.org"
__copyright__   = "Copyright 2018, JK"
__license__     = "GPL3"
__version__     = "0.0.1"

from threading import Thread, Event
import time
import pyaudio
import math
import struct
#import scipy.signal.signaltools as sigtool
from scipy import signal
import numpy as np
import enum

import logging
l = logging.getLogger("piTelex." + __name__)
#l.setLevel(logging.DEBUG)

import txCode
import txBase

sample_f = 48000       # sampling rate, Hz, must be integer

# Set to plot receive filters' spectra
plot_spectrum = False

#######

class ST(enum.IntEnum):
    """
    Represent ED1000 teleprinter state.
    """
    # offline / startup
    OFFLINE = 1

    # online requested by ESC-WB/-A
    ONLINE_REQ = 2

    # online
    ONLINE = 3

    # offline requested by ESC-Z
    OFFLINE_REQ = 4

    # offline delay after buffer is empty
    OFFLINE_DELAY = 5

    # offline, wait for A level
    OFFLINE_WAIT = 6


class TelexED1000SC(txBase.TelexBase):
    def __init__(self, **params):
        super().__init__()

        self._mc = txCode.BaudotMurrayCode(loop_back=False)

        self.id = 'edS'
        self.params = params

        self._tx_buffer = []
        self._rx_buffer = []
        self._is_online = Event()
        self._ST_pressed = False
        # State of rx thread, governs most of the module operation (see class
        # ST)
        self._rx_state = ST.OFFLINE

        # Helper variables for printer feedback
        self._last_tx_buf_len = 0
        self._send_feedback = False

        self.recv_squelch = self.params.get('recv_squelch', 100)
        self.recv_debug = self.params.get('recv_debug', False)
        self.send_WB_pulse = self.params.get('send_WB_pulse', False)
        self.unres_threshold = self.params.get('unres_threshold', 100)

        recv_f0 = self.params.get('recv_f0', 2250)
        recv_f1 = self.params.get('recv_f1', 3150)
        recv_f = [recv_f0, recv_f1]
        self._recv_decode_init(recv_f)

        # Save how many characters have been printed per session
        self.printed_chars = 0

        # Track MCP active state for printer start feedback
        self._MCP_active = False

        self._run = True
        self._tx_thread = Thread(target=self.thread_tx, name='ED1000tx')
        self._tx_thread.start()
        self._rx_thread = Thread(target=self.thread_rx, name='ED1000rx')
        self._rx_thread.start()

    def __del__(self):
        super().__del__()


    def exit(self):
        self._run = False
        # Set online status to wake tx thread
        self._is_online.set()

    # =====

    def read(self) -> str:
        if self._rx_buffer:
            a = self._rx_buffer.pop(0)
            l.debug("read: {!r}".format(a))
            return a

    # -----

    def write(self, a:str, source:str):
        l.debug("write from {!r}: {!r}".format(source, a))
        if len(a) != 1:
            self._check_commands(a)
            return

        if a == '#':
            a = '@'   # ask teletype for hardware ID

        if a and self._is_online.is_set():
            self._tx_buffer.append(a)

    # =====

    def _check_commands(self, a:str):
        if a == '\x1bA':
            l.debug("received online command")
            self._tx_buffer.append('§A')   # signaling type A - connection
            self._MCP_active = True
            self._set_online(True)

        if a == '\x1bZ':
            l.debug("received offline command (ST pressed: {})".format(self._ST_pressed))
            self._MCP_active = False
            self._set_online(False)

        if a == '\x1bWB':
            l.debug("ready to dial")
            if self.send_WB_pulse:
                self._tx_buffer.append('§W')   # signaling type W - ready for dial
            self._set_online(True)

    # -----

    def _set_online(self, online:bool):
        if online:
            l.debug("set online")
            self._is_online.set()
        else:
            l.debug("set offline")
            self._is_online.clear()

    # =====

    def thread_tx(self):
        """Handler for sending tones."""

        devindex = self.params.get('devindex', None)
        baudrate = self.params.get('baudrate', 50)
        send_f0 = self.params.get('send_f0', 500)
        send_f1 = self.params.get('send_f1', 700)
        #send_f0 = self.params.get('recv_f0', 2250)   #debug
        #send_f1 = self.params.get('recv_f1', 3150)   #debug
        send_f = [send_f0, send_f1, (send_f0+send_f1)/2]
        zcarrier = self.params.get('zcarrier', False)

        Fpb = int(sample_f / baudrate + 0.5)   # Frames per bit
        Fpw = int(Fpb * 7.5 + 0.5)   # Frames per wave

        time.sleep(0.5)

        waves = []
        for i in range(3):
            samples=[]
            for n in range(Fpb):
                t = n / sample_f
                s = math.sin(t * 2 * math.pi * send_f[i])
                samples.append(int(s*32000))   # 16 bit
            waves.append(struct.pack('%sh' % Fpb, *samples))   # 16 bit

        audio = pyaudio.PyAudio()
        stream = audio.open(format=pyaudio.paInt16, channels=1, rate=sample_f, output=True, input=False, output_device_index=devindex, input_device_index=devindex)

        #a = stream.get_write_available()
        try:
            while self._run:
                # Going online: send Z
                if self._rx_state == ST.ONLINE_REQ:
                    l.debug("[tx] Sending Z level")
                    stream.write(waves[1], Fpb)   # blocking
                # Process buffer if we're online or going offline with nonempty
                # buffer. Critical for ASCII services that send faster than 50
                # Bd.
                elif ST.ONLINE <= self._rx_state <= ST.OFFLINE_REQ:
                    if self._tx_buffer:
                        a = self._tx_buffer.pop(0)
                        if len(a) == 1:
                            self.printed_chars += 1
                        l.debug("[tx] Sending {!r} (buffer length {})".format(a, len(self._tx_buffer)))
                        if a == '§W':   # signal WB (ready for dial)
                            bb = (0xF9FFFFFF,)   # 40ms pulse after 500ms pause, may be interpreted as 'V'
                            nbit = 32
                        elif a == '§A':   # signal A (online)
                            bb = (0xFFC0,)   # 140ms pulse
                            nbit = 16
                        elif a == '§L':   # transmit lock, to wait for WRU printing
                            # Send idle frequency for 20 characters, plus 1 for
                            # good measure: 7.5 bits * 21 = 157.5
                            # So wait for 158 bits.
                            nbit = 158
                            bb = ((2**nbit)-1,)
                        else:   # normal ANSI character
                            if a == '@':
                                # Teleprinter's WRU unit will trigger after
                                # this character -- lock further sending to
                                # prevent collisions
                                self._tx_buffer.insert(0, '§L')
                            bb = self._mc.encodeA2BM(a)
                            if not bb:
                                continue
                            nbit = 5

                        for b in bb:
                            mask = 1
                            wavecomp = bytearray()
                            for i in range(nbit):
                                bit = 1 if (b & mask) else 0
                                mask <<= 1
                                wavecomp.extend(waves[bit])   # data bit

                            if nbit == 5:
                                # Single Baudot character: add start and stop bits
                                wavecomp[0:0] = waves[0]   # start bit
                                wavecomp.extend(waves[1])
                                wavecomp.extend(waves[1])
                                # Limit send length (only 1.5 stop bits)
                                frames = Fpw   # 7.5 bits
                            else:
                                frames = len(wavecomp) // 2   # 16 bit words
                            stream.write(bytes(wavecomp), frames)   # blocking

                    else:   # nothing to send
                        l.debug("[tx] Online with empty tx buffer")
                        stream.write(waves[1], Fpb)   # blocking

                else:   # offline
                    if self._rx_state == ST.OFFLINE_DELAY:
                        l.debug("[tx] Going offline shortly")
                        # Wait out offline delay; write Z until then
                        while self._rx_state == ST.OFFLINE_DELAY:
                            stream.write(waves[1], Fpb)   # blocking

                    if zcarrier:
                        l.debug("[tx] Offline, sending A level")
                        stream.write(waves[0], Fpb)   # blocking
                    else:
                        l.debug("[tx] Offline, waiting")
                        # If there's absolutely nothing to do, block until
                        # we're going online again
                        self._is_online.wait()

                time.sleep(0.001)

        except Exception as e:
            print(e)

        finally:
            stream.stop_stream()
            stream.close()

    # =====

    def thread_rx(self):
        """Handler for receiving tones."""

        _bit_counter_0 = 0
        _bit_counter_1 = 0
        slice_counter = 0
        offline_delay_counter = 0
        quick_scanning = False

        devindex = self.params.get('devindex', None)
        baudrate = self.params.get('baudrate', 50)

        # One slice is a quarter of a bit or 5 ms
        FpS = int(sample_f / baudrate / 4 + 0.5)   # Frames per slice

        time.sleep(1.5)

        audio = pyaudio.PyAudio()
        stream = audio.open(format=pyaudio.paInt16, channels=1, rate=sample_f, output=False, input=True, frames_per_buffer=FpS, input_device_index=devindex)

        bit_last = None

        while self._run:
            # Executing the IIR filter for bit recognition takes a lot of CPU
            # power. Normally, we do it four times per bit or every 5 ms (once
            # per "slice", "quick scan").
            #
            # When offline, this is quite a waste. We'll read A level for a
            # long time without any benefit. So we lower scan interval to 1000
            # ms ("slow scan").
            #
            # When the operator presses AT, the teleprinter sends Z level.
            # We need to recognise this ASAP to maximise responsiveness. But we
            # also need to avoid recognising freak AT presses (e.g. when
            # plugging or unplugging the data line). To this end, we need to
            # establish a train of stable Z readings. To obtain this quickly,
            # after detecting the first Z, we switch to quick scan. From here
            # on, there are two possibilities:
            # - We read 20x Z: go online
            # - We read an A: go back to slow scan
            #
            # The responsiveness delay is about 2x scan interval. (The receive
            # IIR filter also seems to introduce a delay. In trials under
            # optimal circumstances, after pressing AT on the teleprinter,
            # it took the filter two cycles to recognise the change.)

            if quick_scanning or self._rx_state > ST.OFFLINE:
                pass
            else:
                self._is_online.wait(1)

            # Read audio input
            bdata = stream.read(FpS, exception_on_overflow=False)   # blocking
            data = np.frombuffer(bdata, dtype=np.int16)

            # Run FSK demodulation (bit detection)
            bit = self._recv_decode(data)

            if bit_last != bit and not (ST.ONLINE <= self._rx_state < ST.OFFLINE_DELAY):
                if bit is None:
                    l.debug("[rx] Squelch active, last bit {}, previous counter value: {}".format(
                        "Z" if bit_last else "A",
                        _bit_counter_1 if bit_last else _bit_counter_0
                        )
                    )
                elif bit_last is None:
                    l.debug("[rx] Squelch off, bit changed to {}, previous counter value: {}".format(
                        "Z" if bit else "A",
                        _bit_counter_0
                        )
                    )
                else:
                    l.debug("[rx] Bit changed to {}, previous counter value: {}".format(
                        "Z" if bit else "A",
                        _bit_counter_1 if bit_last else _bit_counter_0
                        )
                    )
                bit_last = bit

            # The purpose of these bit counters is to detect a stable level of
            # A or Z, which triggers state changes.
            if bit:
                _bit_counter_0 = 0
                _bit_counter_1 += 1
                if self._rx_state <= ST.OFFLINE:
                    if _bit_counter_1 == 1:
                        # First Z level detected; raise scanning rate to timely
                        # react to AT press
                        quick_scanning = True
                        l.debug("[rx] Enabling quick scanning")
            else:
                _bit_counter_0 += 1
                _bit_counter_1 = 0
                if quick_scanning:
                    # "A" level detected; disable quick scanning so that we scan
                    # the input signal less often (see above)
                    quick_scanning = False
                    l.debug("[rx] Disabling quick scanning")

            #l.debug("[rx] Bit counters: A:{}/Z:{}".format(_bit_counter_0, _bit_counter_1))

            # Main state machine tracking what the teleprinter hardware does.
            # Tx thread is slaved to this state.
            state_before = self._rx_state # Only for logging
            if self._rx_state <= ST.OFFLINE: # ====================
                if self._is_online.is_set():
                    self._rx_state = ST.ONLINE_REQ
                    # Online by external command: reset bit counters because we
                    # need a defined starting point for Z level recognition
                    _bit_counter_0 = 0
                    _bit_counter_1 = 0
                # Send ESC-AT after 20 consecutive Zs (100 ms + rest of
                # _is_online.wait delay, see above). Don't advance state;
                # ESC-AT will cause us to receive ESC-WB/ESC-A by txDevMCP and
                # this will toggle is_online. Use == 20 to ensure sending
                # ESC-AT only once.
                if _bit_counter_1 == 20:
                    l.info("[rx] Detected AT press")
                    self._rx_buffer.append('\x1bAT')
                    # Don't send printer start confirmation since AT was
                    # pressed.
            elif self._rx_state == ST.ONLINE_REQ: # ====================
                # Go online after 20 consecutive Zs.
                # - If we come here after ESC-AT, we fall through since
                #   _bit_counter_1 is already >= 20.
                # - If we come here by ESC-A from incoming connection, we
                #   properly wait for a stable Z reading.
                if _bit_counter_1 >= 20:
                    self._rx_state = ST.ONLINE
                    # Reset character recognition
                    slice_counter = 0
                # If the teleprinter doesn't switch to Z, but stays in A for at
                # least 100 scans (500 ms), detect it as unresponsive. This can
                # theoretically also happen if ST is pressed just at the right
                # moment, but this is very unlikely.
                #
                # This typically happens on an incoming connection, so don't
                # send ESC-ST because this would terminate it immediately. To
                # keep this transparent and allow fallback mechanisms like the
                # archive module to continue receiving, just set offline and
                # reset our internal state to ST.OFFLINE.
                if _bit_counter_0 == self.unres_threshold:
                    l.info("[rx] Detected unresponsive teleprinter")
                    self._set_online(False)
                    self._rx_state = ST.OFFLINE
                    _bit_counter_0 = 0
                    _bit_counter_1 = 0
                    if self._tx_buffer:
                        l.warning("[rx] Discarding tx buffer due to unresponsive teleprinter ({} characters)".format(len(self._tx_buffer)))
                        l.debug("[rx] tx buffer contents: {!r}".format(self._tx_buffer))
                        self._tx_buffer = []
            elif self._rx_state == ST.ONLINE: # ====================
                # Go offline on ESC-Z
                if not self._is_online.is_set():
                    self._rx_state = ST.OFFLINE_REQ
                # Send ESC-ST after 100 consecutive As (500 ms). Don't advance
                # state; ESC-ST will cause us to receive ESC-Z by txDevMCP and
                # this will toggle is_online. Use == 100 to ensure sending
                # ESC-ST only once.
                if _bit_counter_0 == 100:
                    l.info("[rx] Detected ST press")
                    self._rx_buffer.append('\x1bST')
                    self._ST_pressed = True
                    if self._tx_buffer:
                        l.warning("[rx] Discarding tx buffer due to ST press ({} characters)".format(len(self._tx_buffer)))
                        l.debug("[rx] tx buffer contents: {!r}".format(self._tx_buffer))
                        self._tx_buffer = []
            elif self._rx_state == ST.OFFLINE_REQ: # ====================
                # Write out tx buffer
                if not self._tx_buffer:
                    l.info("[rx] tx buffer empty, printed characters: {}".format(self.printed_chars))
                    self._rx_state = ST.OFFLINE_DELAY
                # ... but break on ST (if the operator wishes to go offline
                # immediately).
                # (If we reached this state by pressing ST, the buffer will be
                # empty and this point in code is not reached.  It wouldn't
                # matter though.)
                if _bit_counter_0 >= 100:
                    l.info("[rx] Detected ST press")
                    # Sending ST now probably won't be needed since _is_online
                    # has already been cleared.
                    self._rx_buffer.append('\x1bST')
                    self._ST_pressed = True
                    # Don't advance state since emptying the buffer now will
                    # trigger state ST.OFFLINE_DELAY on next loop (see above).
                    if self._tx_buffer:
                        l.warning("[rx] Discarding tx buffer due to ST press ({} characters)".format(len(self._tx_buffer)))
                        l.debug("[rx] tx buffer contents: {!r}".format(self._tx_buffer))
                        self._tx_buffer = []
            elif self._rx_state == ST.OFFLINE_DELAY: # ====================
                if self._ST_pressed:
                    # Skip delay if ST was pressed to improve responsiveness
                    self._ST_pressed = False
                    self._rx_state = ST.OFFLINE_WAIT
                offline_delay_counter += 1
                # Wait 3000 ms until switching to A level.
                if offline_delay_counter > 600:
                    self._rx_state = ST.OFFLINE_WAIT
                    offline_delay_counter = 0
                else:
                    if offline_delay_counter % 100 == 0:
                        l.debug("[rx] Offline delay running: {!r}/600".format(offline_delay_counter))
            elif self._rx_state >= ST.OFFLINE_WAIT: # ====================
                if _bit_counter_0 > 100:
                    self._rx_state = ST.OFFLINE
                    _bit_counter_0 = 0
                    _bit_counter_1 = 0
                    self.printed_chars = 0
                    l.debug("[rx] Received A level, offline confirmed")

            #l.debug("[rx] _is_online: {} bit: {}".format(self._is_online.is_set(), bit))
            if state_before != self._rx_state:
                l.info("[rx] State transition: {!s}=>{!s}".format(state_before, self._rx_state))

            # Suppress symbol recognition until we're in full online state.
            #
            # If we don't wait for a stable Z, we might spuriously decode one
            # of these symbols (start bit, 5x character bit, stop bits):
            #
            # ScccccSs
            # ========
            # AAAAAAZZ: NULL (~ in piTelex)
            # AAAAAZZZ: T
            # AAAAZZZZ: O
            # AAAZZZZZ: M
            # AAZZZZZZ: V
            # AZZZZZZZ: letter shift ([ in piTelex)
            #
            # We must not detect any A level that only results from the earlier
            # not-quite-online-yet state -- this would be the start bit
            # triggering one of the above characters. For the two possible ways
            # of going online this means:
            #
            # - AT is pressed: All ok, we've got a stable Z level already,
            #   that's why we went online in the first place.
            #
            # - Incoming connection: We send Z first, the teleprinter
            #   acknowledges this by switching from A to Z after some time.
            #
            # The second case is critical: We have to wait for the teleprinter
            # to send a Z; only after this we are online (_rx_state ==
            # ST.ONLINE). Turn off character recognition in later states
            # because the other endpoint is already disconnected; received data
            # would be useless. But ST operation always works independently.
            if not self._rx_state == ST.ONLINE: # online
                continue

            # Character recognition
            if slice_counter == 0:
                if not bit:   # found start step
                    symbol = 0
                    slice_counter = 1

            else:
                if slice_counter in (1, 2):   # middle of start step
                    if bit: # check if correct start bit
                        slice_counter = -1
                if slice_counter == 6:   # middle of step 1
                    if bit:
                        symbol |= 1
                if slice_counter == 10:   # middle of step 2
                    if bit:
                        symbol |= 2
                if slice_counter == 14:   # middle of step 3
                    if bit:
                        symbol |= 4
                if slice_counter == 18:   # middle of step 4
                    if bit:
                        symbol |= 8
                if slice_counter == 22:   # middle of step 5
                    if bit:
                        symbol |= 16
                if slice_counter == 26:   # middle of stop step
                    if not bit:
                        slice_counter = -5   # wrong stop bit!
                if slice_counter >= 28:   # end of stop step
                    slice_counter = 0
                    #print(symbol, val)   #debug
                    a = self._mc.decodeBM2A([symbol])
                    if a:
                        self._rx_buffer.append(a)
                    continue

                slice_counter += 1

            #time.sleep(0.001)


        stream.stop_stream()
        stream.close()

    # =====

    # IIR-filter
    def _recv_decode_init(self, recv_f):
        self._filters = []
        for i in range(2):
            f = recv_f[i]
            filter_bp = signal.iirfilter(4, [f/1.05, f*1.05], rs=40, btype='bandpass',
                        analog=False, ftype='butter', fs=sample_f, output='sos')
            self._filters.append(filter_bp)

        if not plot_spectrum:
            return

        import matplotlib.pyplot as plt
        plt.figure()
        plt.ylim(-100, 5)
        plt.xlim(0, 5500)
        plt.grid(True)
        plt.xlabel('Frequency (Hz)')
        plt.ylabel('Gain (dB)')
        plt.title('{}Hz, {}Hz'.format(recv_f[0], recv_f[1]))

        for i in range(2):
            f = recv_f[i]
            w, h = signal.sosfreqz(self._filters[i], 2000, fs=sample_f)
            plt.plot(w, 20*np.log10(np.abs(h)), label=str(f)+'Hz')
            plt.plot((f,f), (10, -100), color='red', linestyle='dashed')

        plt.plot((500,500), (10, -100), color='blue', linestyle='dashed')
        plt.plot((700,700), (10, -100), color='blue', linestyle='dashed')
        plt.show()

    # -----

    # IIR-filter
    def _recv_decode(self, data):
        val = [None, None]
        for i in range(2):
            fdata = signal.sosfilt(self._filters[i], data)
            fdata = np.abs(fdata)   # rectifier - instead of envelope curve
            val[i] = int(np.average(fdata))   # get energy for each frequency band

        bit = val[0] < val[1]   # compare energy of each frequency band
        if (val[0] + val[1]) < self.recv_squelch:   # no carrier
            bit = None

        if self.recv_debug:
            with open('recv_debug.log', 'a') as fp:
                line = '{},{}\n'.format(val[0], val[1])
                fp.write(line)

        return bit

    # =====

    # FIR-filter - not longer used
    def _recv_decode_init_FIR(self, recv_f):
        self._filters = []
        fbw = [(recv_f[1] - recv_f[0]) * 0.85, (recv_f[1] - recv_f[0]) * 0.8]
        for i in range(2):
            f = recv_f[i]
            filter_bp = signal.remez(80, [0, f-fbw[i], f, f, f+fbw[i], sample_f/2], [0,1,0], fs=sample_f, maxiter=100)
            self._filters.append(filter_bp)

        if not plot_spectrum:
            return

        import matplotlib.pyplot as plt
        plt.figure()
        plt.ylim(-60, 5)
        plt.xlim(0, 5500)
        plt.grid(True)
        plt.xlabel('Frequency (Hz)')
        plt.ylabel('Gain (dB)')
        plt.title('{}Hz, {}Hz'.format(recv_f[0], recv_f[1]))

        fbw = [(recv_f[1] - recv_f[0]) * 0.85, (recv_f[1] - recv_f[0]) * 0.8]
        for i in range(2):
            f = recv_f[i]
            w, h = signal.freqz(self._filters[i], [1], worN=2500)
            plt.plot(0.5*sample_f*w/np.pi, 20*np.log10(np.abs(h)))
            plt.plot((f,f), (10, -100), color='red', linestyle='dashed')

        plt.plot((500,500), (10, -100), color='blue', linestyle='dashed')
        plt.plot((700,700), (10, -100), color='blue', linestyle='dashed')
        plt.show()

    # -----

    # FIR-filter - not longer used
    def _recv_decode_FIR(self, data):
        val = [None, None]
        for i in range(2):
            fdata = signal.lfilter(self._filters[i], 1, data)
            fdata = np.abs(fdata)
            val[i] = np.average(fdata)

        bit = val[0] < val[1]
        if (val[0] + val[1]) < self.recv_squelch:   # no carrier
            bit = None
        return bit

    def idle2Hz(self):
        # Send printer start (ESC-AA) and buffer feedback (ESC-~)
        #
        # ESC-AA is sent as soon as the teleprinter is running and MCP is in
        # S_ACTIVE* state (i.e. ESC-A has been received; otherwise we'd cancel
        # dialling).
        #
        # ESC-~ communicates the current printer buffer length, i.e. the number
        # of characters that remain to be printed.
        printer_online = (ST.ONLINE <= self._rx_state <= ST.OFFLINE_REQ)
        if printer_online or self._send_feedback:
            tx_buf_len = len(self._tx_buffer)
            if (not self._send_feedback) and self._MCP_active:
                self._send_feedback = True
                # Confirm that we just came online
                self._rx_buffer.append('\x1bAA')
            elif self._last_tx_buf_len != tx_buf_len:
                # Normal feedback (when buffer changed)
                self._rx_buffer.append('\x1b~' + str(tx_buf_len))

            if not printer_online:
                # We went offline: turn off feedback
                self._send_feedback = False

            self._last_tx_buf_len = tx_buf_len

#######


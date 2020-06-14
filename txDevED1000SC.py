#!/usr/bin/python3
"""
Telex Device - ED1000 Communication over Sound Card - Transmit Only

Articles:
https://www.allaboutcircuits.com/technical-articles/fsk-explained-with-python/
https://dsp.stackexchange.com/questions/29946/demodulating-fsk-audio-in-python
https://stackoverflow.com/questions/35759353/demodulating-an-fsk-signal-in-python#

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
import matplotlib.pyplot as plt

import txCode
import txBase

sample_f = 48000       # sampling rate, Hz, must be integer

#######

class TelexED1000SC(txBase.TelexBase):
    def __init__(self, **params):
        super().__init__()

        self._mc = txCode.BaudotMurrayCode(loop_back=False)

        self.id = '='
        self.params = params

        self._tx_buffer = []
        self._rx_buffer = []
        self._is_online = Event()

        self.recv_squelch = self.params.get('recv_squelch', 100)
        self.recv_debug = self.params.get('recv_debug', False)

        recv_f0 = self.params.get('recv_f0', 2250)
        recv_f1 = self.params.get('recv_f1', 3150)
        recv_f = [recv_f0, recv_f1]
        self._recv_decode_init(recv_f)

        self.run = True
        self._tx_thread = Thread(target=self.thread_tx, name='ED1000tx')
        self._tx_thread.start()
        self._rx_thread = Thread(target=self.thread_rx, name='ED1000rx')
        self._rx_thread.start()



    def __del__(self):
        self.run = False

        super().__del__()


    def exit(self):
        self._run = False

    # =====

    def read(self) -> str:
        if self._rx_buffer:
            a = self._rx_buffer.pop(0)
            return a

    # -----

    def write(self, a:str, source:str):
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
            self._tx_buffer = []
            self._tx_buffer.append('§A')   # signaling type A - connection
            self._set_online(True)

        if a == '\x1bZ':
            self._tx_buffer = []
            self._set_online(False)

        if a == '\x1bWB':
            self._tx_buffer = []
            self._tx_buffer.append('§W')   # signaling type W - ready for dial
            self._set_online(True)

    # -----

    def _set_online(self, online:bool):
        if online:
            self._is_online.set()
        else:
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

            while self.run:
                if self._is_online.is_set():
                    if self._tx_buffer:
                        a = self._tx_buffer.pop(0)
                        if a == '§W':
                            bb = (0xF9FFFFFF,)
                            nbit = 32
                        elif a == '§A':
                            bb = (0xFFC0,)
                            nbit = 16
                        else:
                            bb = self._mc.encodeA2BM(a)
                            if not bb:
                                continue
                            nbit = 5
                        
                        for b in bb:
                            bits = [0]*nbit
                            mask = 1
                            for i in range(nbit):
                                if b & mask:
                                    bits[i] = 1
                                mask <<= 1
                            wavecomp = bytearray()
                            wavecomp.extend(waves[0])
                            for bit in bits:
                                wavecomp.extend(waves[bit])
                            wavecomp.extend(waves[1])
                            wavecomp.extend(waves[1])
 
                            if nbit == 5:
                                frames = Fpw   # 7.5 bits
                            else:
                                frames = len(wavecomp) // 2   # 16 bit words
                            stream.write(bytes(wavecomp), frames)   # blocking

                    else:   # nothing to send
                        stream.write(waves[1], Fpb)   # blocking

                else:   # offline
                    if zcarrier:
                        stream.write(waves[0], Fpb)   # blocking
                    else:
                        time.sleep(0.100)

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
        
        devindex = self.params.get('devindex', None)
        baudrate = self.params.get('baudrate', 50)

        FpS = int(sample_f / baudrate / 4 + 0.5)   # Frames per slice

        time.sleep(1.5)

        audio = pyaudio.PyAudio()
        stream = audio.open(format=pyaudio.paInt16, channels=1, rate=sample_f, output=False, input=True, frames_per_buffer=FpS, input_device_index=devindex)

        while self.run:
            bdata = stream.read(FpS, exception_on_overflow=False)   # blocking
            data = np.frombuffer(bdata, dtype=np.int16)

            bit = self._recv_decode(data)

            #if bit is None and self._is_online.is_set():
            #print(bit, val)

            if bit:
                _bit_counter_0 = 0
                _bit_counter_1 += 1
                if _bit_counter_1 == 20 and not self._is_online.is_set():   # 0.1sec
                    self._rx_buffer.append('\x1bAT')
            else:
                _bit_counter_0 += 1
                _bit_counter_1 = 0
                if _bit_counter_0 == 100:   # 0.5sec
                    self._rx_buffer.append('\x1bST')


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
                        slice_counter = -5
                        pass
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
            filter_bp = signal.iirfilter(4, [f/1.05, f*1.05], rs=40, btype='band',
                        analog=False, ftype='butter', fs=sample_f, output='sos')
            self._filters.append(filter_bp)

        return   # debug - remove to plot spectrum
    '''
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
        pass
    '''
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

        return
    '''
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
        pass
    '''

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

#######


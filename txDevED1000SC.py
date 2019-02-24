#!/usr/bin/python
"""
Telex Device - ED1000 Communication over Sound Card - Transmit Only
"""
__author__      = "Jochen Krapf"
__email__       = "jk@nerd2nerd.org"
__copyright__   = "Copyright 2018, JK"
__license__     = "GPL3"
__version__     = "0.0.1"

from threading import Thread
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

#######

class TelexED1000SC(txBase.TelexBase):
    def __init__(self, **params):
        super().__init__()

        self._mc = txCode.BaudotMurrayCode()

        self.id = '='
        self.params = params

        self._txb_buffer = []
        self._rxb_buffer = []
        self._carrier_counter = 0
        self._carrier_detected = False

        self.do_plot()

        self.run = True
        #self._tx_thread = Thread(target=self.thread_tx)
        #self._tx_thread.start()
        self._rx_thread = Thread(target=self.thread_rx)
        self._rx_thread.start()



    def __del__(self):
        self.run = False

        super().__del__()

    def do_plot(self):
        recv_f0 = self.params.get('recv_f0', 2250)
        recv_f1 = self.params.get('recv_f1', 3150)
        recv_f = [recv_f0, recv_f1]

        sample_f = 48000       # sampling rate, Hz, must be integer

        plt.figure()
        plt.ylim(-60, 5)
        plt.xlim(0, 5500)
        plt.grid(True)
        plt.xlabel('Frequency (Hz)')
        plt.ylabel('Gain (dB)')
        plt.title('{}Hz, {}Hz'.format(recv_f[0], recv_f[1]))

        filters = []
        fbw = [(recv_f[1] - recv_f[0]) * 0.85, (recv_f[1] - recv_f[0]) * 0.8]
        for i in range(2):
            f = recv_f[i]
            filter_bp = signal.remez(80, [0, f-fbw[i], f, f, f+fbw[i], sample_f/2], [0,1,0], fs=sample_f, maxiter=100)
            filters.append(filter_bp)

            w, h = signal.freqz(filters[i], [1], worN=2500)
            plt.plot(0.5*sample_f*w/np.pi, 20*np.log10(np.abs(h)))
            plt.plot((f,f), (10, -60), color='red', linestyle='dashed')

        plt.plot((500,500), (10, -60), color='blue', linestyle='dashed')
        plt.plot((700,700), (10, -60), color='blue', linestyle='dashed')
        plt.show()

    # =====

    def read(self) -> str:
        if self._rxb_buffer:
            b = self._rxb_buffer.pop(0)
            a = self._mc.decodeBM2A([b])
            return a


    def write(self, a:str, source:str):
        if len(a) != 1:
            return
            
        bb = self._mc.encodeA2BM(a)
        if bb:
            for b in bb:
                self._txb_buffer.append(b)

    # =====

    def thread_tx(self):
        """Handler for sending tones."""
        baudrate = self.params.get('baudrate', 50)
        send_f0 = self.params.get('send_f0', 500)
        send_f1 = self.params.get('send_f1', 700)
        #send_f0 = self.params.get('recv_f0', 2250)
        #send_f1 = self.params.get('recv_f1', 3150)
        send_f = [send_f0, send_f1]

        sample_f = 48000       # sampling rate, Hz, must be integer
        Fpb = int(sample_f / baudrate + 0.5)   # Frames per bit
        Fpw = int(Fpb * 7.5 + 0.5)   # Frames per wave

        audio = pyaudio.PyAudio()
        #stream = audio.open(format=pyaudio.paInt8, channels=1, rate=sample_f, output=True, input=False)
        stream = audio.open(format=pyaudio.paInt16, channels=1, rate=sample_f, output=True, input=False)
        #stream = audio.open(format=pyaudio.paFloat32, channels=1, rate=sample_f, output=True, input=False)

        #a = stream.get_write_available()

        waves = []
        for i in range(2):
            samples=[]
            for n in range(Fpb):
                t = n / sample_f
                s = math.sin(t * 2 * math.pi * send_f[i])
                samples.append(int(s*32000+0.5))   # 16 bit
                #samples.append(int(s*127+128.5))   # 8 bit
                #samples.append(s)   # float
            waves.append(struct.pack('%sh' % Fpb, *samples))   # 16 bit
            #waves.append(struct.pack('%sf' % Fpb, *samples))   # float


        while self.run:
            if self._txb_buffer:
                b = self._txb_buffer.pop(0)
                d1 = 1 if b & 1 else 0
                d2 = 1 if b & 2 else 0
                d3 = 1 if b & 4 else 0
                d4 = 1 if b & 8 else 0
                d5 = 1 if b & 16 else 0
                #print (b, d1, d2, d3, d4, d5)
                wavecomp = bytearray()
                wavecomp.extend(waves[0])
                wavecomp.extend(waves[d1])
                wavecomp.extend(waves[d2])
                wavecomp.extend(waves[d3])
                wavecomp.extend(waves[d4])
                wavecomp.extend(waves[d5])
                wavecomp.extend(waves[1])
                wavecomp.extend(waves[1])
                stream.write(bytes(wavecomp), Fpw)   # blocking

            else:   # nothing to send
                stream.write(waves[1], Fpb)   # blocking
        
            time.sleep(0.001)


        stream.stop_stream()  
        stream.close()

    # =====

    def thread_rx(self):
        """Handler for sending tones."""
        baudrate = self.params.get('baudrate', 50)
        recv_f0 = self.params.get('recv_f0', 2250)
        recv_f1 = self.params.get('recv_f1', 3150)
        recv_f = [recv_f0, recv_f1]

        slice_counter = 0

        sample_f = 48000       # sampling rate, Hz, must be integer
        Fps = int(sample_f / baudrate / 4 + 0.5)   # Frames per slice

        audio = pyaudio.PyAudio()
        stream = audio.open(format=pyaudio.paInt16, channels=1, rate=sample_f, output=False, input=True, frames_per_buffer=Fps)

        filters = []
        fbw = [(recv_f[1] - recv_f[0]) * 0.85, (recv_f[1] - recv_f[0]) * 0.8]
        for i in range(2):
            f = recv_f[i]
            filter_bp = signal.remez(80, [0, f-fbw[i], f, f, f+fbw[i], sample_f/2], [0,1,0], fs=sample_f, maxiter=100)
            filters.append(filter_bp)

        while self.run:
            bdata = stream.read(Fps, exception_on_overflow=False)   # blocking
            data = np.frombuffer(bdata, dtype=np.int16)

            val = [None, None]
            for i in range(2):
                fdata = signal.lfilter(filters[i], 1, data)
                fdata = np.abs(fdata)
                val[i] = np.average(fdata)

            bit = val[0] < val[1]
            carrier = (val[0] + val[1]) > 1000

            #print(val, bit)

            if carrier and self._carrier_counter < 100:
                self._carrier_counter += 1
                if self._carrier_counter == 100:
                    self._carrier_detected = True
            if not carrier and self._carrier_counter > 0:
                self._carrier_counter -= 1
                if self._carrier_counter == 0:
                    self._carrier_detected = False


            if slice_counter == 0:
                if not bit:   # found start step
                    symbol = 0
                    slice_counter = 1

            else:
                if slice_counter == 2:   # middle of start step
                    pass
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
                        #slice_counter = -10
                        pass
                if slice_counter >= 28:   # end of stop step
                    slice_counter = 0
                    #print(val, symbol)
                    self._rxb_buffer.append(val)
                    continue

                slice_counter += 1
        
            #time.sleep(0.001)


        stream.stop_stream()  
        stream.close()

#######


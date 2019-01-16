#!/usr/bin/python
"""
Telex ED1000 Communication over Sound Card - Transmit Only
"""
__author__      = "Jochen Krapf"
__email__       = "jk@nerd2nerd.org"
__copyright__   = "Copyright 2018, JK"
__license__     = "GPL3"
__version__     = "0.0.1"

import txCode
import txBase

import time
from threading import Thread
import pyaudio
import math
import struct

#######

class TelexED1000TxOnly(txBase.TelexBase):
    def __init__(self, **params):

        super().__init__()

        self._mc = txCode.BaudotMurrayCode()

        self.id = '"'
        self.params = params

        self._tx_buffer = []

        self.run = True
        self._tx_thread = Thread(target=self.thread_tx)
        self._tx_thread.start()


    def __del__(self):
        self.run = False

        super().__del__()
    
    # =====

    def read(self) -> str:
        return ''


    def write(self, a:str, source:str):
        if len(a) != 1:
            return
            
        bb = self._mc.encodeA2B(a)
        if bb:
            for b in bb:
                self._tx_buffer.append(b)

    # =====

    def thread_tx(self):
        """Handler for sending tones."""
        baudrate = self.params.get('baudrate', 50)
        f0 = self.params.get('f0', 500)
        f1 = self.params.get('f1', 700)
        freq = [f0, f1]

        fs = 44100       # sampling rate, Hz, must be integer
        Fpb = int(fs / baudrate + 0.5)   # Frames per bit
        Fpw = int(Fpb*7.5 + 0.5)   # Frames per wave

        audio = pyaudio.PyAudio()
        #stream = audio.open(format=pyaudio.paInt8, channels=1, rate=fs, output=True)
        stream = audio.open(format=pyaudio.paInt16, channels=1, rate=fs, output=True)
        #stream = audio.open(format=pyaudio.paFloat32, channels=1, rate=fs, output=True)

        a = stream.get_write_available()

        waves = []
        for i in range(2):
            samples=[]
            for n in range(Fpb):
                t = n / fs
                s = math.sin(t * 2 * math.pi * freq[i])
                samples.append(int(s*32000+0.5))   # 16 bit
                #samples.append(int(s*127+128.5))   # 8 bit
                #samples.append(s)   # float
            waves.append(struct.pack('%sh' % Fpb, *samples))   # 16 bit
            #waves.append(struct.pack('%sf' % Fpb, *samples))   # float


        while self.run:
            if self._tx_buffer:
                b = self._tx_buffer.pop(0)
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


#######


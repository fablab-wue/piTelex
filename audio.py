import pyaudio
import math
import struct

fs = 44100       # sampling rate, Hz, must be integer
baud = 50.0
Fpb = int(fs / baud + 0.5)   # Frames per bit
f0 = 500.0
f1 = 700.0
freq = [500.0, 700.0]

audio = pyaudio.PyAudio()
#stream = audio.open(format=pyaudio.paInt8, channels=1, rate=fs, output=True)
stream = audio.open(format=pyaudio.paFloat32, channels=1, rate=fs, output=True)


# 8 bit
a0=[]
a1=[]
for i in range(Fpb):
    t = i / fs
    s = math.sin(t * 2 * math.pi * f0)
    a0.append(int(s*127+128.5))
    s = math.sin(t * 2 * math.pi * f1)
    a1.append(int(s*127+128.5))

b0=bytes(a0)
b1=bytes(a1)

#float
waves = []
for i in range(2):
    samples=[]
    for n in range(Fpb):
        t = n / fs
        s = math.sin(t * 2 * math.pi * freq[i])
        samples.append(s)
    waves.append(struct.pack('%sf' % Fpb, *samples))


for i in range(50):
    stream.write(waves[1], Fpb)

stream.stop_stream()  
stream.close()  






stream.get_write_available()

for i in range(20):
    stream.write(waves[1], Fpb/10)
    time.sleep(0.05)
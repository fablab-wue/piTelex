#!/usr/bin/env python3

# List pyAudio devices
# Inspired by and adapted:
# https://stackoverflow.com/questions/36894315/how-to-select-a-specific-input-device-with-pyaudio

import pyaudio
p = pyaudio.PyAudio()
info = p.get_host_api_info_by_index(0)
numdevices = info.get('deviceCount')
print("=== pyAudio device list ===")
print("Device ID\toutputs\tinputs\tname")
for i in range(0, numdevices):
    dinf = p.get_device_info_by_host_api_device_index(0, i)
    name = dinf.get('name')
    inputs = dinf.get("maxInputChannels")
    outputs = dinf.get("maxOutputChannels")
    print(f"{i}\t\t{outputs}\t{inputs}\t{name}")

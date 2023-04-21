#!/usr/bin/python3
"""
Telex Device - KeyPad input for text shortcuts and test teletypes

Linux ONLY!

Tutorial:
https://python-evdev.readthedocs.io/en/latest/tutorial.html
"""
__author__      = "Jochen Krapf"
__email__       = "jk@nerd2nerd.org"
__copyright__   = "Copyright 2023, JK"
__license__     = "GPL3"
__version__     = "0.0.1"

import evdev   # sudo apt install python3-evdev
from threading import Thread

import logging
l = logging.getLogger("piTelex." + __name__)

import txBase

#######

class TelexKeyPad(txBase.TelexBase):
    def __init__(self, **params):
        super().__init__()

        self.id = 'KPd'
        self.params = params

        self._rx_buffer = []

        self._device = None

        self._show_key_name = self.params.get('show_key_name', False)
        device_name = self.params.get('device_name', 'KEYPAD').upper()


        # get list of all input devices
        devices = [evdev.InputDevice(path) for path in evdev.list_devices()]

        for device in devices:
            #print('path:', device.path, 'name:', device.name, 'phys:', device.phys)
            #print(device)
            text = "TelexKeyPad - device: {}".format(device)
            l.info(text)
            if self._show_key_name:
                print(text)

        # linux magic - event interfaces to spy keyboards and mice
        for device in devices:
            if device.name.upper().find(device_name) >= 0:
                self._device = evdev.InputDevice(device.path)
                text = 'TelexKeyPad - using keypad/keyboard: {}'.format(self._device)
                l.info(text)
                if self._show_key_name:
                    print(text)
                break
        else:   # no fitting device found
            text = 'TelexKeyPad - no keypad/keyboard found'
            l.error(text)
            if self._show_key_name:
                print(text)
            return

        # get all key-names which are available for this device
        self._keys = {}
        caps = self._device.capabilities(verbose=True)
        for group in caps:
            if group[1] == 1:   # id == 'EV_KEY'
                for name, id in caps[group]:
                    self._keys[id] = name

        # start spy in own thread
        self._thread = Thread(target=self.thread_keypad, name='KeyPad')
        self._thread.start()


    def __del__(self):
        super().__del__()

    # =====

    def read(self) -> str:
        if self._rx_buffer:
            return self._rx_buffer.pop(0)
        else:
            return ''


    def write(self, a:str, source:str):
        pass

    # =====

    def thread_keypad(self):
        LUT_keys = self.params.get('KEYS', {})
        LUT_replace_chars = {
            '\\': '\r',
            '_': '\n',
        }

        for ev in self._device.read_loop():
            if ev is None:
                break
            if ev.type == evdev.ecodes.EV_KEY and ev.value == 1:   # event=key and pressed
                key_name = self._keys.get(ev.code, None)

                if self._show_key_name:
                    print('<' + key_name + '>', end='', flush=True)

                text = LUT_keys.get(key_name.upper(), '')

                l.info('TelexKeyPad - key pressed: code={} key_name={} text="{}"'.format(ev.code, key_name, text))

                # scan text and filter escape sequences
                while text:
                    a = text[0]
                    text = text[1:]
                    if a == '{':
                        x = text.split('}', 1)
                        if len(x) > 1:
                            text = x[1]
                        else:
                            text = ''
                        self._rx_buffer.append('\x1b' + x[0])
                        continue

                    elif a in LUT_replace_chars:
                        a = LUT_replace_chars[a]

                    if a:
                        self._rx_buffer.append(a)

#######
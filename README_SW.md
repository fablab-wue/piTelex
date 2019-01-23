# Software

TODO...

<img src="img/SW_Modules.png" width="1330px">

## State Machine

The internal states are controlled by escape sequences. 

| ESC | Description |
| --- | --- |
| AT | User start outgoing call
| ST | User stop outgoing call
| LT | Locale
| A | Connected
| Z | Disconnected
| WB | Begin dialing
| #&lt;number&gt; | Dialing is finished, request IP-address, connecting


## USB-Serial-Adapter

Using an adapter board (or adapter cable - for V.10) based on the chip CH340 the device is detected as normal (virtual) serial interface. In Windows the device is shown as 'COMx'. In Linux it is shown as '/dev/ttyUSBx'.

With the Python library "PySerial" all necessary settings can be done to handle 50 baud, 5 data-bits and 1.5 stop-bits. Also, the handshake pins RTS and DTR can be set by this library.

## Raspberry Pi (RPi)

The build in UART of the RPi can’t handle 50 baud.

The correct timing can be formed jitter-free with the library “PiGPIO”. Receiving can be handled by asynchronous callbacks implemented in this library. With this also a Linux based computer like the RPi can handle precise and reliable timings.


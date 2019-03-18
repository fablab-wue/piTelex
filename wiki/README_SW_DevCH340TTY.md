# Device Module "CH340TTY"

TODO...

## Module Information

### System

| System | Comments |
| --- | --- |
| RPi | OK
| PC Linux | OK
| PC Windows | OK
| Mac | OK

### Dependencies

| Python<br>Module | Install | Anaconda |
| --- | --- | --- |
| pyserial | pip install pyserial | conda install pyserial

### Command Line Arguments

    -Y TTY
    --CH340TTY TTY

Example Windows: telex.py -Y COM3

Example Linux: telex.py -Y /dev/ttyUSB0

### Config File Parameter

| Param | Default | Description |
| :--- | --- | :--- |
| portname | '/dev/ttyUSB0' |
| baudrate | 50 |
| bytesize | 5 |
| stopbits | 1.5 |
| uscoding | False |
| loopback | None |
| loc_echo | False |

## Description

Using an adapter board (or adapter cable - for V.10) based on the chip CH340 the device is detected as normal (virtual) serial interface. In Windows the device is shown as 'COMx'. In Linux it is shown as '/dev/ttyUSBx'.

With the Python library "PySerial" all necessary settings can be done to handle 50 baud, 5 data-bits and 1.5 stop-bits. Also, the handshake pins RTS and DTR can be set by this library.

## Implementation

TODO
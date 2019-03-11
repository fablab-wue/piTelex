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

### Command Line

    -? <?>

### Config File Parameter

| Param | Description |
| :--- | :--- |
| TODO | TODO

## Description

Using an adapter board (or adapter cable - for V.10) based on the chip CH340 the device is detected as normal (virtual) serial interface. In Windows the device is shown as 'COMx'. In Linux it is shown as '/dev/ttyUSBx'.

With the Python library "PySerial" all necessary settings can be done to handle 50 baud, 5 data-bits and 1.5 stop-bits. Also, the handshake pins RTS and DTR can be set by this library.

## Implementation

TODO
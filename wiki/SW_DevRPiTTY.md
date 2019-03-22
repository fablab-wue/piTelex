# Device Module "RPiTTY"
TODO...

## Module Information

### System

| System | Comments |
| --- | --- |
| RPi | All boards with Raspian
| PC Linux | -
| PC Windows | -
| Mac | -

### Dependencies

| Python<br>Module | Install | Anaconda |
| --- | --- | --- |
| pigpio | pip install pigpio | conda install pigpio

### Command Line Arguments

    -G
    --RPiTTY

### Config File Parameter

| Param | Default | Description |
| :--- | --- | :--- |
| baudrate | 50 |
| bytesize | 5 |
| stopbits | 1.5 |
| pin_txd | 17 |
| pin_rxd | 27 |
| pin_fsg_ns | 6 | connected to rxd
| pin_rel | 22 |
| pin_dir | 11 |
| pin_oin | 10 |
| pin_opt | 9 |
| pin_sta | 12 |
| inv_rxd | False |
| inv_txd | False | not implemented yet
| uscoding | False |
| loopback | True |

## Description

The build in UART of the RPi can’t handle 50 baud.

The correct timing can be formed jitter-free with the library “PiGPIO”. Receiving can be handled by asynchronous callbacks implemented in this library. With this also a Linux based computer like the RPi can handle precise and reliable timings.

## Implementation

TODO
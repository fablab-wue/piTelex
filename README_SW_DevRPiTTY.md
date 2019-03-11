# Device Module "RPiTTY"
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
| pigpio | pip install pigpio | conda install pigpio

### Command Line

    -? <?>

### Config File Parameter

| Param | Description |
| :--- | :--- |
| TODO | TODO

## Description

The build in UART of the RPi can’t handle 50 baud.

The correct timing can be formed jitter-free with the library “PiGPIO”. Receiving can be handled by asynchronous callbacks implemented in this library. With this also a Linux based computer like the RPi can handle precise and reliable timings.

## Implementation

TODO
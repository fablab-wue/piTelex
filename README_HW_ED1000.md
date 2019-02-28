# Electronic for ED1000 Interface

<img src="img/ED1000.JPG" width="300px">

In old days a lot of electronic components are use to build a modulator and demodulator for Frequency-Shift-Keying (FSK).
Today most of the work can be done in software.

A (USB) sound card is used to play and record the carrier frequencies and 5 electronic components adapts the audio signal to teletype ED1000.

With this USB sound card adapter the teletype can be connected to a Windows-PC, a Linux-PC, a Mac (not tested) or a Raspberry Pi. A USB sound card is available in online shops for about 10€. Using a PC or laptop the build-in sound card can be used also.

### Connecting a PC Sound Card to ADo8

<img src="img/ED1000Schematic.png" width="300px">

### ADo8 Plug

| Pin |  Description |
| ---: | --- |
| 1 | Line a
| 2 | nc
| 3 | nc
| 4 | Line b
| 5 | Bridge to 6
| 6 | Bridge to 5
| 7 | nc / Paper-End-Switch
| 8 | nc / Paper-End-Switch

The line wires are used to send **and** receive at the same time like a MODEM on phone wires.

The bridge between pin 5 and 6 is for signaling a connected plug. May be high voltages can be used by teletype!

Some teletypes use a switch (relay) on pin 7 and 8 to signal paper end.

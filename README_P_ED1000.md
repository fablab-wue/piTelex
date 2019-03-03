# ED1000

> FOR FUTURE PLUGINS - NOT IMPLEMENTED YET

ED1000 is a technique to connect a teletype to a central office with 2 wires. A Frequency-Shift-Keying (FSK) is used to send and receive simultaniously. It is like a MODEM (V.21) but with different carrier frequencies.

## SEU-A/B Standard

### Definitions / Naming

| Type | Definition |
| --- | --- |
| A | Central Office, Switching Exchange, EDS, (PC Sound Card)
| B | Terminal Station, Teletype

Type 'B' is the normal configuration for a teletype. Some teletypes can be configured as type 'A' to be connected directly to another teletype.

### Levels and Frequencys

| SEU | Direction | Frq A<br>(space, 0) | Frq Z<br>(mark, 1) | Level | U rms * | U peak * |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| A | Send | 500Hz | 700Hz | -14.5dBm | 0.146V | 0.206V
| A | Receive | 2250Hz | 3150Hz | &ge;-34.0dBm | &ge;0.015V | &ge;0.022V
| B | Send | 2250Hz | 3150Hz | -9.0dBm | 0.275V | 0.389V
| B | Receive | 500Hz | 700Hz | &ge;-28.5dBm | &ge;0.029V | &ge;0.041V

*: at termination of 600Ohm

Seeing the lower frequencies as a bit value '0' and the higher as '1', the bit values can be used as from a TTL async. serial adapter.

### Max. Line Length

| Distance | Conductor Diameter |
| ---: | ---: |
| 20km | 0.8mm
| 14km | 0.6mm
| 10km | 0.4mm

### Max. Line Loss

| Direction |  Frequency Band | Loss |
| --- | ---: | ---: |
| A &rarr; B | 600Hz &pm; 100Hz | 14dB
| B &rarr; A | 2700Hz &pm; 450Hz | 25dB

## ADo8 Plug

It is common for ED1000 system to use an ADo8 plug.

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

The bridge between pin 5 and 6 is for signaling a connected plug. May be high voltages can be used by teletype to detect the bridge!

Some teletypes use a switch (relay) on pin 7 and 8 to signal paper end.

# Frequency Shift Keying (FSK)

<img src="img/ED1000FSK1.png" width="472px">

For signaling Z (logical 1) a high frequency is used (700Hz, 3150Hz). For signaling A (logical 0) a lower frequency is used (500Hz, 2250Hz). Both frequencies have the same amplitude.

<img src="img/ED1000FSK3.png" width="442px">

In frequency domain ...

<img src="img/ED1000FSK2.png" width="595px">

For sending a character the transmitter switches between the corresponding frequency with the giver baud rate.

For timing see: [Baudot-Murray-Code](/README_P_BMC.md)

# Protocol

## Outgoing Call

Idle mode ...

### Begin Call and Dialing

<img src="img/ED1000Call1.png" width="550px">

Pressing button AT on FSG...

### Connecting

<img src="img/ED1000Call3.png" width="240px">

On fail...

<img src="img/ED1000Call2.png" width="550px">

On success...

### Transmitting Content

<img src="img/ED1000Call4.png" width="550px">

Typing characters...

<img src="img/ED1000Call5.png" width="550px">

Transmitting without pause...

### Ending Call

<img src="img/ED1000Call6.png" width="240px">

Pressing button ST...

<img src="img/ED1000Call7.png" width="240px">

Ending by other side...

## Incoming Call

<img src="img/ED1000Incomming.png" width="550px">

## WRU (Wer da?)

<img src="img/ED1000WRU.png" width="550px">

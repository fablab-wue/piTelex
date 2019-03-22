# Electronic for Current-Loop Interface

## Overview of Modules

The Telex adapter hardware must source a constant (regulated) current of 40mA, switch the current for transmitting data and observe the current for receiving data from the Telex.

The current loop is specified in "TW39".

<img src="img/TelexOverview.png" width="466px">

To use a Telex as an USB-device you can use an USB-to-serial-TTL converter based on a CH340 chip (other chips from FTDI and Prolofic don't work at 50 baud, 5 data-bits, 1.5 stop-bits).

The commutate circuit (drawn in cyan) is optional and only needed when the telex is using a FSG. Without a FSG the cyan area can be removed.

<img src="img/TelexCH340.png" width="504px">

To use router and FSG functionality the adapter hardware can be connected directly to a Raspberry Pi.

<img src="img/TelexRPi.png" width="504px">

---

## Current Regulators

### Historic Current Loop

... hand trimmed potentiometer for each line

TODO

### Current Source and Regulator

To simplify the device an adjustable DC/DC boost converter board (from China) is used to get a voltage of 20...35V. The voltage regulator LM317 is used as a fixed current source to get the 40mA. The LM317 works as a linear regulator and must be mounted on a heat sink.

<img src="img/TelexCurrent.png" width="432px">

Note: The LM317 is designed for a maximal voltage of 35V. A higher voltage can damage the chip.

### Alternative Current Regulator

With 2 Transistors a current regulator is implemented with a voltage tolerance of 120 volt. The TIP47 works as a linear regulator and must be mounted on a heat sink.

<img src="img/TelexCurrent2.png" width="195px">

Note: At a supply voltage of 60V a continuous power of about 2W have to be handled by the TIP47 and its heat sink.

Note: The regulator can be combined with the transmitter. See examples below.

---

## Telex Transmitters

To send data to the Telex the current loop must be switched. A current of 40mA means High, an open loop (no current) means Low. The simplest way is to use a transistor switching to GND.

The following schematics switches to GND. This simplifies the circuit and reduce the voltage drop on the transistor to less than 1V. Other solutions with the switching transistor in the middle of the loop have a voltage drop of 5V to 10V.

### Telex Transmitter with Bipolar Transistor

The simplest way is to use a small NPN transistor.

<img src="img/TelexTXD.png" width="153px">

The transmitter has effectively no voltage drop on the current loop (< 0.2V). No heat sink or big transistor is needed.

### Telex Transmitter with FET Transistor

Alternatively, to a bipolar transistor a logic level FET can be used.

<img src="img/TelexTXDFET.png" width="167px">

---

## Telex Receivers

To get data from the Telex the current must be observed. A current of 40mA means High, an open loop (no current) means Low. 

### Telex Receiver with optocoupler

For galvanic decoupling an opto-coupler is used.

<img src="img/TelexRXD.png" width="309px">

As opto-coupler a LTV817 or PC817 is recommended. All other coupler with coupling factor > 50% should also work.

The receiver has a voltage drop on the current loop of about 2V.

---

## Telex Commutate (Option)

To signal the FSG (dialing and switching device) an established connection, the polarity of the current loop is reversed with a relay.

<img src="img/TelexCommutate.png" width="197px">

---

# Complete Examples

## TW39 Compact USB Interface

<img src="img/USB.JPG" width="160px">

This is the first approach with a USB to TTL adapter (middle), a DC/DC converter (bottom) and a self-made-board (top) for current regulator, reading and controlling the loop.

<img src="img/TelexUSB3.png" width="518px">

This can be used with a Windows-PC, Linux-PC, Mac (not tested) and Raspberry Pi.

Details at [Example_USB](Example_USB.md)

---

## TW39 High Voltage USB and Raspberry Pi Interface

<img src="img/pyTelexPCBt.png" width="157px">
<img src="img/pyTelexPCBb.png" width="157px">

<img src="img/TelexCurrentTXD3.png" width="476px">

This is designed for Raspberry Pi but with a CH340-serial-adapter this can be also used with a Windows-PC, Linux-PC, and Mac (not tested).

Details at [Example_RPi](Example_RPi.md)

---

# Power supply

All teletypes (with current loop interface) are designed for a current of 40mA. The receive unit (magnet coil) has a typical voltage drop of 15V. With the voltage drops in the interface circuits a power supply voltage of about 20V should do - in theory.

**BUT!** The switching speed of a magnet coil depends directly on intermediate circuit voltage - in this case the power supply voltage. On practical experience a intermediate circuit voltage should be at least 2x of the magnet coil voltage.

**ADDITIONAL BUT!** Most teletypes are used with a FSG (dialing device). This has also a relay in the current loop with an additional voltage drop. Some relay circuits (especially for "Wahlbereitschaft" = ready for dial) needs a very voltage (60V) to work as expected.

### Hands-on tests

Working supply voltages with interfaces above:

Lo15, T37, T68 without FSG: 24V

T100S with integrated FSG: 60V

**TODO** More Details...


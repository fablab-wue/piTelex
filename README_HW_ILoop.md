# Electronic for Current-Loop Interface

## Overview of Modules

The Telex adapter hardware have to source a constant (regulated) current of 40mA, switch the current for transmitting data and observe the current for receiving data from the Telex.

The current loop is specified in "TW39".

<img src="img/TelexOverview.png" width="466px">

To use a Telex as an USB-device you can use an USB-to-serial-TTL converter based on a CH340 chip (other chips from FTDI and Prolofic don't work at 50 baud, 5 data-bits, 1.5 stop-bits).

The commutate circuit (drawn in cyan) is optional and only needed when the telex is using a FSG. Without a FSG the cyan area can be removed.

<img src="img/TelexCH340.png" width="504px">

To use router and FSG functionality the adapter hardware can be connected directly to a Raspberry Pi.

<img src="img/TelexRPi.png" width="504px">

## Current Source and Regulator

To simplify the device an adjustable DC/DC boost converter board (from China) is used to get a voltage of 20...35V. The voltage regulator LM317 is used as a fixed current source to get the 40mA. The LM317 works as a linear regulator and must be mounted on a heat sink.

<img src="img/TelexCurrent.png" width="432px">

## Alternative Regulator

With 2 Transistors a current regulatir is implemented with a voltage tolerance of 120 volt. The TIP47 works as a linear regulator and must be mounted on a heat sink.

<img src="img/TelexCurrent2.png" width="195px">

## Telex Transmitter with Bipolar Transistor

To send data to the Telex the current loop has to be switched. A current of 40mA means High, an open loop (no current) means Low. The simplest way is to use a transistor switching to GND.

<img src="img/TelexTXD.png" width="153px">

The transmitter has effectively no voltage drop on the current loop (< 0.2V).

## Telex Transmitter with FET Transistor

Alternatively to a bipolar transistor a logic level FET can be used.

<img src="img/TelexTXDFET.png" width="167px">

## Telex Receiver

To get data from the Telex the current has to be observed. A current of 40mA means High, an open loop (no current) means Low. For galvanic decoupling an opto-coupler is used.

<img src="img/TelexRXD.png" width="309px">

As opto-coupler a LTV817 or PC817 is recommended. All other coupler with coupling factor > 50% should also work.

The receiver has a voltage drop on the current loop of about 2V.

## Telex Commutate (Option)

To signal the FSG a connection the voltage is pole changed with a relais.

<img src="img/TelexCommutate.png" width="197px">

# Complete Examples

## Compact USB Interface

<img src="img/USB.JPG" width="320px">

This is the first approach with a USB to TTL adapter (middle), a DC/DC converter (bottom) and a self-made-board (top) for current regulator, reading and contolling the loop.

<img src="img/TelexUSB3.png" width="518px">

## High Voltage Interface

<img src="img/pyTelexPCBt.png" width="314px">
<img src="img/pyTelexPCBb.png" width="314px">

The PCBs are ordered and will be assembled and tested in Feb. 2019

<img src="img/TelexCurrentTXD2.png" width="343px">

Note: If using a CH340-board with a RXD-LED, the LED have to be removed!

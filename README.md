<img src="img/Header.JPG" width="1024px">

# piTelex
**Control a historic Telex device with a Raspberry Pi in Python 3.**

The goal is to connect a historic telex device (teletype) with TW39 current loop to a modern Windows/Linux-PC (over USB) and/or a Raspberry Pi (over GPIO) with minimal hardware.

One part of the project is the hardware to adapt the current loop "TW39" to modern logic level ports.

The other part is the Python software to send and receive the serial data (50 baud, 5 data-bits) and decode the "CCITT-2" character set (also called "Baudot-Murray-Code" or "ITA2") to ASCII.

With the characters arrived in the PC/RPi the data can be routed to i-Telex, eMail or IRC. The telex can also be (miss-) used as printer or keyboard.

The software supports also a connection to an other i-Telex device over internet.

As side effect teletypes with V.10 inteface (like TeKaDe FS200) can also be connected to USB-adapter and handled by the software.

**The software and hardware is still in BETA state. First release is planned in 2019-03**

## Hardware

 * [Electronic for Current-Loop Interface](/README_HW_ILoop.md)
 * [Electronic for V.10 Interface](/README_HW_V10.md)

## Software

 * [Software](/README_SW.md)

## Protocol / Coding

 * [Baudot-Murray-Code = CCITT-2 = ITA2](/README_P_BMC.md)
 * [TW39 / TWM Transmission](/README_P_TW39.md)
 * [ED1000 Transmission](/README_P_ED1000.md)

## Additional Information

 * [Additional Information](/README_A.md)

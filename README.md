<img src="https://raw.githubusercontent.com/wiki/fablab-wue/piTelex/img/Header.JPG" width="1024px">

# <img src="piTelexLogo.png" width="42px">- piTelex

### Control a historic Telex device with a Raspberry Pi (or PC) in Python 3.

<img src="https://raw.githubusercontent.com/wiki/fablab-wue/piTelex/img/RPiTW39.JPG" width="200px" align="right">

The goal is to connect a historic telex device (teletype) with **TW39** protocol on a **current loop** to a modern **Windows/Linux-PC** (over USB) and/or a **Raspberry Pi** (over GPIO) with minimal hardware.

<img src="https://raw.githubusercontent.com/wiki/fablab-wue/piTelex/img/USB.JPG" width="200px" align="right">

One part of the project is the hardware to adapt the **current loop** for **TW39** to modern logic level ports.

The other part is the Python software to send and receive the serial data (50 baud, 5 data-bits) and decode the "**Baudot-Murray-Code**" character set (also called "CCITT-2" or "ITA2") to ASCII.

With the characters arrived in the PC/RPi the data can be routed to [i-Telex](https://www.i-telex.net), eMail or IRC. The telex can also be (miss-) used as printer or keyboard.

The software supports also a connection to an other [i-Telex](https://www.i-telex.net) device over internet.

<img src="https://raw.githubusercontent.com/wiki/fablab-wue/piTelex/img/V.10.JPG" width="200px" align="right">

As side effect teletypes with **V.10** inteface (like TeKaDe FS200 / FS220) can also be connected to USB-to-RS232-adapter with a DIY adapter cable. The protocol is completely handled by the software. (No FAG200 is needed)

<img src="https://raw.githubusercontent.com/wiki/fablab-wue/piTelex/img/ED1000SC.JPG" width="200px" align="right">

An other playground is the ED1000 interface used by (more) modern teletypes. It is based on frequency-shift-keying (FSK) and will be handled by a USB sound card, a few passive components and a lot of software.

> The software and hardware is still in BETA state. First test releases are out in the field...

[**For more informations see the WIKI pages**](https://github.com/fablab-wue/piTelex/wiki)

<img src="https://raw.githubusercontent.com/wiki/fablab-wue/piTelex/img/Header.JPG" width="1024px">

# <img src="piTelexLogo.png" width="42px">- piTelex

### Control a historic Telex device with a Raspberry Pi (or PC) in Python 3.

The goal is to connect a historic telex device (teletype) with **TW39** protocol on a **current loop** to a modern **Windows/Linux-PC** (over USB) and/or a **Raspberry Pi** (over GPIO) with minimal hardware.

One part of the project is the hardware to adapt the **current loop** for **TW39** to modern logic level ports.

The other part is the Python software to send and receive the serial data (50 baud, 5 data-bits) and decode the "**Baudot-Murray-Code**" character set (also called "CCITT-2" or "ITA2") to ASCII.

With the characters arrived in the PC/RPi the data can be routed to [i-Telex](https://www.i-telex.net), eMail or IRC. The telex can also be (miss-) used as printer or keyboard.

The software supports also a connection to an other [i-Telex](https://www.i-telex.net) device over internet.

As side effect teletypes with **V.10** inteface (like TeKaDe FS200) can also be connected to USB-adapter and handled by the software.

> The software and hardware is still in BETA state. First release is planned in 2019-03


> **For more informations see the WIKI pages**

---

### Examples

##### TW39 Compact USB Interface

<img src="https://raw.githubusercontent.com/wiki/fablab-wue/piTelex/img/USB.JPG" width="160px">

 ##### TW39 Raspberry Pi Interface

<img src="https://raw.githubusercontent.com/wiki/fablab-wue/piTelex/img/pyTelexPCBt.png" width="157px">
<img src="https://raw.githubusercontent.com/wiki/fablab-wue/piTelex/img/pyTelexPCBb.png" width="157px">

 ##### V.10 Interface for TeKaDe FS200Z / FS220Z

<img src="https://raw.githubusercontent.com/wiki/fablab-wue/piTelex/img/V.10.JPG" width="160px">

##### ED1000 Interface

    IN DEVELOPMENT

---

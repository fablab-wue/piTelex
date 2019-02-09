# Electronic for V.10 Interface

<img src="img/V.10.JPG" width="320px">

Some teletypes have an optional V.10 interface like the TeKaDe FS200Z / FS220Z. The V.10 definition is near to V.24 (RS-232) with a voltage limit of -6...6V.

Most modern UARTs and serial-adapters do not support 50 baud and/or 5 bits. **BUT!** The USB-to-serial-chip **CH340** does support it!

In online stores you find an adapter cable USB to RS-232 (not TTL) with a 9-pin Sub-D connector with this **CH340** chip (not FTDI, not Prolific, not CP210x). With this adapter you only have to solder an adapter to connect your teletype to your PC.

<img src="img/V10Adapter.png" width="250px">

Note: the gray cables are optional.

### Lines:
 * D1: Transmit data
 * D2: Receive data
 * Betr.b.: If Telex is powered up, the "Beriebsbereit" (German for "ready for use") is set to 5V.
 * S2: If LIN-button is pressed S2 is set to 5V and line communication is active.
 * M2: A rising edge (to 5V) on M2 make a beep sound.
 * ARQ: This is used to request a saved message from teletype (not used)
 * E*: Ground

### Platforms

With this USB adapter cable the teletype can be connected to a Windows-PC, a Linux-PC, a Mac (not tested) or a Raspberry Pi.

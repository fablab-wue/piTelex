# Example with ED1000 Compact USB Interface
TODO...

## Hardware

<img src="../img/V.10.JPG" width="320px">

All you need is a CH340-USB-adapter with RS232 level and a adapter cable.

### Schematics

<img src="../img/V10Adapter.png" width="300px">

---

## Software

For Installation see [SW_Install](/wiki/README_SW_Install.md)

This electronic is handles by the software module [CH340TTY](/wiki/README_SW_DevCH340TTY.md).

Start the program with arguments -Y TTY and -m V10 on Linux:
    
    telex -Y /dev/ttyUSB0 -m V10 -I 2342

or on Windows
    
    telex -Y COM3 -m V10 -I 2342

Note: The argument -I is to start the i-Telex [client](/wiki/README_SW_DevITelexClient.md) and [server](/wiki/README_SW_DevITelexSrv.md) at port 2342.

## ???

TODO
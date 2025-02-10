<img src="https://raw.githubusercontent.com/wiki/fablab-wue/piTelex/img/Header.JPG" width="1024px">

## Installation

### Hardware requirements

#### Teletype
* At least one functional Teletype 

    * "speaking" ITA2 

    * using one of the communication protocols 

        * line loop (single current 40mA), 
        * TW39
        * ED1000
        * V.10

* Optionally a CCU

#### Computer platforms
* RaspBerry Pi (all flavours with 40 pin GPIO, for TW39 a Pi Zero is sufficient)
* Other SBC (GPIO functionality not completely tested, but USB should work)
* PC hardware with free USB Port(s)

#### Additional hardware
* Hardware matching the selected connection to the computer (Raspi GPIO, USB) and matching the connection type of the teletype (TW39 with or w/o CCU, V10, ED1000)
* Hardware proposals and pcb layouts can be found under https://github.com/fablab-wue/piTelex.supplement

### Software requirements
* Debian based linux distro (RaspBerry Pi OS, debian, ubuntu, mint,...)
* or Windows (all flavours)
* Python3
* A few additional python3 modules (see Documentation)

### Documentation
Complete Docuemtation for installation and usage can be found at https://github.com/fablab-wue/piTelex/wiki

# Software Installation



## Raspberry Pi Zero (RPi)

* Download RASPBIAN image and flash to MicroSD card
  * See: https://www.raspberrypi.org/downloads/

* Boot the RPi (can take more than a minute at first time)

* For next steps you need command line on the RPi. Either direct with a monitor or establish a connection between the RPi and your PC with SSH. This can be done by different ways:

  1. Use HDMI-monitor and USB-keyboard

  1. Usa a USB to Ethernet adapter:
     * Use tools like nmap to find the IP address of the RPi in your local network.
     * Use SSH to connect to this IP
        Note: On Windows system use program Putty

  1. Usa a USB to Serial adapter with 3.3V TTL level:
     * Connect to RPi debug-serial pins TXD and RXD
     * Use SSH to connect to this tty
        Note: On Windows system use program Putty

  1. Change boot files on MicroSD card for headless NDIS (USB/Ethernet) connection:
     * See: http://www.circuitbasics.com/raspberry-pi-zero-ethernet-gadget/   or
      https://www.factoryforward.com/pi-zero-w-headless-setup-windows10-rndis-driver-issue-resolved/
     * Use SSH to connect to `raspberrypi.local`
        Note: On Windows system use program Putty
        Note: NDIS setup a network with address 169.254.*.*/16. It can take several minutes til the DNS entry is available
   
* Login with user `pi` and password `raspberry`

* Use `sudo raspi-config` to configure RPi system:
  * Set new password in menu `Change User Password`
  * Change device name in menu `Network Options` -> `Hostnames` (e.g. 'piTelex')
  * Set WIFI access to your local network. Set SSID and key in menu `Network Options` -> `WIFI`
  * Set Localization in menu `Localozation Options` -> `Change Locale`
  * Set Timezone in menu `Localization Options` -> `Timezone`
  * Disable SPI in menu `Interfacing Options` -> `SPI`
  * (optional) Enable I2C if needed in menu `Interfacing Options` -> `I2C`
  * (optional) Enable 1-Wire if needed in menu `Interfacing Options` -> `1-Wire`
  
* Update your RPi system with 
      
      sudo apt-get update
      sudo apt-get upgrade

* Install additional programs and libs with:
      
      sudo apt-get install python3 python3-pip
      sudo apt-get install pigpio
      sudo apt-get install git

* Start pigpio deamon with 
      
      sudo systemctl start pigpiod`
      sudo systemctl enable pigpiod`

* Install additional python libs with:
      
      sudo pip3 install pigpio

* Download piTelex repository from GITHUB with `git clone https://github.com/fablab-wue/piTelex.git`

* Make python file executable with `sudo chmod +x /home/pi/piTelex/telex.py`

* Test if telex program is working
  * Start telex with `/home/pi/piTelex/telex.py -G /more args/`
    Note: See args chapter below
  * Stop with Ctrl-C

* Prepare system to start clock program at startup. This can be done in different ways:
  1. Start with rc.local:
     * Edit rc.local with `sudo nano /etc/rc.local`
     * Add at end before `exit 0` `sudo /home/pi/piTelex/telex.py &`

  1. Start with crontab:
     * Edit system crontab file with `sudo crontab -e`
     * Add at end `@reboot /home/pi/piTelex/telex.py -G /more args/`
       Note: See args chapter below

* If all works, make a backup of the MicroSD card

---

## PC-Linux

* Install dependencies:

      sudo apt-get install python3 python3-pip git

    * If using USB-Serial-Adapter (TW39, TWM and V.10) additional install:   

          sudo pip install pyserial

    * If using USB-Sound-Card (ED1000) additional install:   

          sudo pip install pyaudio numpy scipy

* Install telex program:

      sudo git clone https://github.com/fablab-wue/piTelex

* Make python file executable with:

      sudo chmod +x /home/pi/piTelex/telex.py

* Test if telex program is working
  * Start telex with `/home/pi/piTelex/telex.py /more args/`
    Note: See args chapter below
  * Stop with Ctrl-C

* Prepare system to start clock program at startup. This can be done in different ways:
  1. Start with rc.local:
     * Edit rc.local with `sudo nano /etc/rc.local`
     * Add at end before `exit 0` `sudo /home/pi/piTelex/telex.py &`

  1. Start with crontab:
     * Edit system crontab file with `sudo crontab -e`
     * Add at end `@reboot /home/pi/piTelex/telex.py /more args/`
       Note: See args chapter below

---

## PC-Windows

TODO

---

## piTelex Arguments

| Environment / Hardware | args | args (long) |
| --- | --- | --- |
| RPi with piTelex-board | `-G` | `--RPi-TW39`
| with USB-Serial-Adapter (without dialing) | `-Y TTY` | `--tty TTY`
| with USB-Serial-Adapter to TW39 (pulse dial) | `-W TTY` | `--tty-TW39 TTY`
| with USB-Serial-Adapter to TWM (keypad dial) | `-M TTY` | `--tty-TWM TTY`
| with USB-Serial-Adapter to V.10 | `-V TTY` | `--tty-V10 TTY`
| with USB-Sound-Card to ED1000 | `-E` | `--audio-ED1000`

| Gateway | args | args (long) | Comments |
| --- | --- | --- | --- |
| i-Telex | `-I PORT` <br>`-I 0` | `--i-Telex PORT`<br>`--i-Telex 0` | for client and server at port *PORT*<br>for client only
| Telnet | `-T PORT` | `--telnet PORT` | for server at port *PORT*
| Eliza Chat Bot | `-Z` | `--eliza` | for demonstation and fun

| Option | args | args (long) | Comments |
| --- | --- | --- | --- |
| ID | `-k ID` | `--idID`<br>`--KG ID` | If your teletype has no ID-generator ('Kennungsgeber') you can add  this option to respond a given ID on WRU requests.
| Log to file | `-L FILE` | `--log FILE` | If you want to log all incoming and outgoing characters you can add this option.
| Save args | `-s` | `--save` | To save all args to txConfig.json file you can add this option. After that you don't have to type args at telex start.


TODO

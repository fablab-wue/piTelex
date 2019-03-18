# Software Installation

## [RPi only] Operatin System

 * Load newest Raspian image from [raspberrypi.org](https://www.raspberrypi.org/downloads/raspbian/)
 * Write image to SD-card (min. 8GB)
 * Connect RPi to HDMI-monitor and USB-keyboard
 * If the RPi has an Ethernet-Port, connect LAN-cable
 * Power up RPi
 * Login as 'pi' with password 'respberry'
 * Update operating system
       
       sudo apt-get update
       sudo apt-get upgrade

 * Start program raspi-conig ...
 
           sudo raspi-conig
 
 * ... and set / change:
    * User Password
    * Computer name
    * WiFi credentials
    * SPI off
    * I2C on
       
 
## [RPi and PC-Linux] Install Programs

 * Install programs and dependencies
     
       sudo apt-get install python3 python3-pip git
       sudo pip install pyserial
       [RPi only] sudo pip install pigpio

 * Install telex program
 
       sudo git clone https://github.com/fablab-wue/piTelex

 * Make telex program executable
 
       sudo ?

TODO

## [PC-Windows] Install Programs

TODO
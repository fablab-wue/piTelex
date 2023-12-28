Relay Watchdog
==============

This program is usefull if you do not want you telex to be on all the time (e.g. because it is LOUD!).

It listens on a socket (by default localhost port 22000) and when a client connects to it it will make sure the specified GPIO port (27 by default) is turned or kept high for the next specified number of seconds (300 by default).

If you connect a relay to the GPI port, you can use it to programatically switch on your telex when there is data to receive.

Usage
-----
```
usage: relay_watchdog.py [-h] [--host localhost] [-p 22000] [-d 300] [-g 27] [--pigpio hostname] [-v]
                         [-q]

Listen on a socket for connections and toggle a GPIO pin high for a certain amount of time

options:
  -h, --help            show this help message and exit
  --host localhost      IP address to listen on
  -p 22000, --port 22000
                        Port to listen on
  -d 300, --duration 300
                        Default time to keep the GPIO pin high for
  -g 27, --gpio 27      GPIO pin to toggle
  --pigpio hostname     Hostname of ip address of pigpiod
  -v, --verbose         Be (more) verbose
  -q, --quiet           Be quiet, only output errors
  ```
  
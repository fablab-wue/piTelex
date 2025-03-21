# List of changes relevant for daily use

## Changes compared to release 2025-02

###  Added centralex protocol
* Module: ITelexSrv, part ITelexCentralex
* Description:

i-telex stations require an IPv4 address in order to be reachable from the internet. For stations only equipped with an IPv6 address, the use of a centralex relay server may solve this problem.

See https://github.com/fablab-wue/piTelex/wiki/SW_DevITelexCentralex for details.

### E-Mail notification when a telex arrives
* Module: Archive
* Description:

    The archive module now can not only save incoming messages to an archive directory, but can also send the content of the message to an e-mail address.
    To achieve this, several new config file options have been added (see also the wiki page for the module)
    ```json
         "send_email": true,    				# notify via email when a telex has arrived
         "recipient": "recipient@targetdomain.domain",       # E-Mail address of recipient
         "email_sender": "sendername@provider.domain",       # E-Mail address of sender
         "smtp_server": "smtp.mailserver.org",               # FQDN or IP of mailserver
         "smtp_port": 587,					# TCP port at mailserver (often 25, 465, 587)
         "smtp_user": "username",		                # username at mail server
         "smtp_password": "VeryVerySecret"	                # password for username
    ```



---
## Changes compared to the release 2023-07 

###  New config file parameter `block_ascii`
* Module: ITelexSrv
* Description:

Added config file parameter 
````json
	"block_ascii" : true/false    # default true
````
to avoid port scans and such being printed at the TTY, if set to true. 

Hint: On an incoming ASCII-connection, the teleprinter may or may not be switched on for a few seconds, but printing is suppressed.



###  Added support for USB-Keypads
* Module: `Keypad` (new)
* Dependencies: python-evdev, Linux ONLY!
* Description:  

  Added device `keypad`, allows connection of a numeric keypad via usb
  KeyPad input for text shortcuts and test teletypes.


### Added a "hand type simulator"
* Module: MCP
* Description:
 
   Added a simulator for manual typing, i.e insert random delays between "keystrokes".
   Toggle on/off in Screen via `<ESC> T`.
   When enabled, prints "lorem ipsum" dummy text with pseudo random delay between keystrokes until disabled.
   To output the text to the teleprinter, first activate it by either dialling '009' or entering `<ESC> A`in `screen`.

### Added modes "AGT-TWM", "AGT-TW39"

* Module: RPiTTY
* Description:

  Introduce more specific modes `AGT-TW39`, `AGT-TWM` (module RPiTTY) for use with Ö-AGT's (will probably replace general mode `AGT` in a later version)

### Added LED_Z
* Module: RPiCtrl
* Description:

  Added config parameter 
  ```json
  "pin_LED_Z": 0    # integer > 0, default 0 
  ```
  which defines a connection pin for a LED which is lit in "Z" and "ZZ" mode.

### Added heartbeat function for LED_Z
* Module: RPiCtrl
* Description:

  Added config parameter
  ```
  "LED_Z_heartbeat": 6     # integer > 0, default 6
  ```
  which defines the pause in steps of 500ms between two flashes of LED_Z. A value of 0 means "no flashing".

  Used as indicator: as long as the system has heartbeat, piTelex is running and not "dead"...

  Flashing is only for ZZ mode! Z mode is always indicated by steady light of LED_Z.
  


### Switch off current loop in "ZZ" mode
* Module: RPiTTY
* Description:

  Added config file parameter 
  ```json
  "txd_powersave": true/false #default is false
  ```
  If set to true, loop current will be switched off in ZZ status. 

  Only useful for TW39/line current machines.

  Mostly useful in context with `"pin_power"` option of module RPiCtrl. 

  Especially useful for t68d machines; in standby, they pull a current of 5mA, but when mains is diconnected, raise it to 40mA, 
  which means unnecessary thermal loss.
  
### Added feature to insert text files into the character stream
* Module: MCP
* Description:

  Entering five or more subsequent `WR` (carriage return) at the telerpinter lets pitelex 
  interpret the following number from 0 to 9 as a file name located in the subdirectory 
  "read" of pitelex. The file must have the extension `.txt`.
  
  If the fie exists, pitelex will insert the contents of the file.
  

### TNS hosts now configurable
* Module: ITelex
* Description:

  Up to now, the TNS hostnames were hardcoded in the sources.
  The new config file option `tns_srv`, which defaults to

  ```json
  "tns_srv": ['tlnserv.teleprinter.net','tlnserv2.teleprinter.net','tlnserv3.teleprinter.net'],
  ```
  allows to configure the TNS hosts in telex.json. Under normal circumstances, there should be no need to change the default. But 
  piTelex' default mechanism of selecting a TNS host is rather rudimentary and cannot cope with nonexistent or faulty servers. In such cases, the list can be reduced to functional addresses.

### Configure the welcome message
* Module: MCP
* Description:

  When piTelex accepts a connection, it prints the welcome message which normally consists of a DateTime stamp.
  This is historically correct for the EDS system, earlier (TW39 et al) implementations did not print such a message at the beginning of the connection.
  The new config option
  
  ```json
  "welcome_msg" : true/false # default true
  ```
  allows to select whether the Timestamp is printed or not.
  

  
  

Device-ID|Parameter|Default|Type or range|Comment
------|---------|-------|-------------|-------
||||
-|wru\_id|[none]|string|Software-WRU-ID
-|debug|3|1 .... 5|Debug level (will be deprecated soon)
-|wru\_replace\_always|false|false / true|if true, always replace HW-WRU by $wru\_id
-|continue\_with\_no\_printer|true|false / true|if true, ignore missing / faulty printer device; if false, abort connections if teleprinter fails to start up
-|dial\_timeout|2.0|'+‘ / float (0.0...55.0)|idle time after last dialled digit to start dial process; if  ‚+‘, „plus-dialling“ selected, if ‚0‘, instant dialling is used (see documentation in txDevMCP.md)
-|wru\_fallback|||deprecated (replaced by wru\_replace\_always)
-|devices|{}|dict|Dictionary of device-node-IDs (modules)
||||
Archive|path|"archive"|string|path to archive directory
||||
CH340TTY|portname|"/dev/ttyUSB0"|string|serial port used
CH340TTY|baudrate|50|50, 75, 100|Baud rate
CH340TTY|bytesize|5|5 … 8|# of Databits
CH340TTY|stopbits|1.5|1, 1.5, 2|# of stopbits
CH340TTY|coding|0|0,1,2,3|0:ITA2=CCITT2, 1:US, 2:MKT2, 3:ZUSE (see txCode.md)
CH340TTY|loopback|true|false / true|if true, sent characters are removed from receive buffer
CH340TTY|loc\_echo|false|false / true|if true, echo back all characters received from teleprinter
CH340TTY|inverse\_dtr|false|false / true|If true, use inverted signal
CH340TTY|inverse\_rts|false|false / true|If true, use inverted signal
||||
ED1000SC|recv\_squelch|100|positive integer|Defines the power threshold below which the filter output for A/Z level is ignored; if needed, can be determined experimentally using helper script ED1000/squelch\_check.py (see docstring inside).
ED1000SC|recv\_debug|false|false / true|If true, output recv\_debug.log file inside which the repective filter power output levels for every sample are recorded. Use only for debugging (file will grow quickly).
ED1000SC|send\_WB\_pulse|false|false / true|If true, send pulse to signal ready-to-dial condition like with the current interface.
ED1000SC|unres\_threshold|100|positive integer|Duration in ms that piTelex waits for the teleprinter, after it started sending Z level, until the teleprinter returns the Z level to signal readiness state. Raise if the teleprinter needs more time to start up for special setups, e.g. when switching mains using ESC-TP0/TP1 commands.
ED1000SC|recv\_f0|2250|number|RX frequency 0 in Hz (A level)
ED1000SC|recv\_f1|3150|number|RX frequency 1 in Hz (Z level)
ED1000SC|devindex|null|null or positive integer (0 included)|pyaudio‘s device index for the intended audio device; use ED1000/audiotest.py to list currently available devices.
ED1000SC|baudrate|50|50, 75, 100|Baud rate
ED1000SC|send\_f0|500|number|TX frequency 0 in Hz (A level)
ED1000SC|send\_f1|700|number|TX frequency 1 in Hz (Z level)
ED1000SC|zcarrier|false|false / true|If true, piTelex will send continous A level in idle state. Most teleprinters don‘t need this.
||||
IRC|directed\_only|false|false / true|?
IRC|irc\_server|"irc.nerd2nerd.org"|string|Name or IPV4 address of IRC server
IRC|irc\_port|6697|1024 ... 65535|IP port of IRC server
IRC|irc\_nick|"telextest"|string|Nick name
IRC|irc\_channel|"#tctesting"|string|IRC Channel to use
||||
ITelexClient|tns\_port|11811|number|TCP port number of tns\_host (tns=“TeilNehmerServer“) 
ITelexClient|userlist|"userlist.csv"|string|filename of file containing speed dials, syntax see userlist.csv.sample
||||
ITelexSrv|port|2342|1024 ... 65535|TCP port number (ports <1024 are privileged and not accessible for normal users)
ITelexSrv|tns-dynip-number|0|positive integer|Initially 0 (disable dynamic IP update). Set to own i-Telex calling number to enable dynamic IP update – must be agreed on with i-Telex administrators.
ITelexSrv|number|0|positive integer|alias for tns-dynip-number, deprecated
ITelexSrv|tns-pin|None|positive integer < 65536|PIN for dynamic IP update; set according to i-Telex administrator‘s instructions
||||
Log|filename|"log.txt"|string|path to logfile
||||
News|newspath|"./news"|string|path to news file
News|print\_path|false|false / true|If true, reformat newspath suitable for printing; no functionality by now due to internal affairs…
||||
RPiCtrl|pin\_number\_switch|0|number|GPIO# of pin connected to number switch of FSG; if 0, use kbd dialling
RPiCtrl|inv\_number\_switch|true|false / true|If true, use inverted signal on pin
RPiCtrl|pin\_button\_1T|0|number|GPIO# of Single button (optional), press button 1T repeatedly to cycle through states Offline,  Active, WB
RPiCtrl|pin\_button\_AT|0|number|GPIO# of button AT (optional) Button connects to GND
RPiCtrl|pin\_button\_ST|0|number|GPIO# of button ST (optional) Button connects to GND
RPiCtrl|pin\_button\_LT|0|number|GPIO# of button LT (optional) Button connects to GND
RPiCtrl|pin\_button\_U1|0|number|GPIO# of button user1 (optional) Button connects to GND
RPiCtrl|text\_button\_U1|"RY"|string|cmd associated with button user1
RPiCtrl|pin\_button\_U2|0|number|GPIO# of button user2 (optional) Button connects to GND
RPiCtrl|text\_button\_U2|"RYRY ... RY"|string|Cmd associated with button user2
RPiCtrl|pin\_button\_U3|0|number|GPIO# of button user3 (optional) Button connects to GND
RPiCtrl|text\_button\_U3|"#" |string|Cmd associated with button user3
RPiCtrl|pin\_button\_U4|0|number|GPIO# of button user4 (optional) Button connects to GND
RPiCtrl|text\_button\_U4|"@"|string|Cmd associated with button user4
RPiCtrl|pin\_LED\_A|0|number|GPIO# of LED indicating state „A“ ; LED connects to GND (1kOhm in series!)
RPiCtrl|pin\_LED\_WB|0|number|GPIO# of LED indicating state „WB“ ; LED connects to GND  
RPiCtrl|pin\_LED\_WB\_A|0|number|GPIO# of LED indicating state „WB\_A“  ; LED connects to GND (1kOhm in series!)
RPiCtrl|pin\_LED\_status\_R|0|number|GPIO# of RED status LED ; LED connects to GND  (330Ohm in series!)
RPiCtrl|pin\_LED\_status\_G|0|number|GPIO# of GREEN status LED ; LED connects to GND  (330Ohm in series!)
RPiCtrl|pin\_power|0|number|GPIO# of pin used to switch off teletype power for power saving
RPiCtrl|inv\_power|false|false / true|If true, use inverted signal on pin
||||
RPiTTY|mode|"TW39"|"TW39" / "V10"|TW39 for all TTY‘s with high voltage current loop; V10 for machines with V.10 interface (mainly TeKaDe FS200 / FS220)
RPiTTY|baudrate|50|38 ... 50 … 200|Baud rate
RPiTTY|bytesize|5|5 … 8|# of databits
RPiTTY|stopbits|1.5|1 / 1.5 / 2|# of stopbits
RPiTTY|pin\_txd|17|number|GPIO# of TX-Data pin
RPiTTY|inv\_txd|false|false / true|If true, use inverted signal on TX-Data pin, not possible with PIGPIO
RPiTTY|pin\_dir|0|number|GPIO# of DIR pin. This pin is set to 1 on transmitting each byte for hardware loopback supression
RPiTTY|pin\_rxd|27|number|GPIO# of RX-Data pin
RPiTTY|inv\_rxd|false|false / true|If true, use inverted signal on RX-Data pin
RPiTTY|pin\_relay|22|number|GPIO# of relay coil pin; in non-FSG mode used to switch the line power of the teletype; in FSG mode, relay is used to invert the polarity of the current loop when a connection is established; see corresponding hardware description
RPiTTY|inv\_relay|false|false / true|If true, use inverted signal on pin
RPiTTY|pin\_power|0|number|GPIO# of pin used to switch off current loop
RPiTTY|inv\_power|false|false / true|If true, use inverted signal on pin
RPiTTY|pin\_number\_switch|6|number|GPIO# of pin connected to the number switch; typically wired to pin\_rxd. Use -1 if pin\_number\_switch in module RPiCtrl is used
RPiTTY|pin\_fsg\_ns|6|number|GPIO# of pin connected to the number switch; typically wired to pin\_rxd, deprecated
RPiTTY|inv\_number\_switch|false|false / true|If true, use inverted signal on pin
RPiTTY|use\_observe\_line|true|false / true|If true, monitor *pin\_observe\_line* for state changes of >0,5s
RPiTTY|pin\_observe\_line|[pin\_rxd]|number|GPIO# of pin to observe
RPiTTY|inv\_observe\_line|[inv\_rxd]|false / true|If true, use inverted signal on pin
RPiTTY|coding|0|0,1,2,3|0:ITA2=CCITT2, 1:US, 2:MKT2, 3:ZUSE (see txCode.md) 
RPiTTY|loopback|true|false / true|if true, sent characters are removed from receive buffer
RPiTTY|timing\_rxd|false|false / true|?
RPiTTY|WB\_pulse\_length|40|number|set length of WB pulse in milliseconds
RPiTTY|double\_WR|false|false / true|if true, add an extra \<CR\> to give the old machines more time to move to the start of the line
||||
Screen|show\_BuZi|true|false / true|If true, show special characters for Bu / Zi on Screen
Screen|show\_capital|false|false / true|if true, use capital letters on screen
Screen|show\_ctrl|true|false / true|if true, show control sequences on screen
Screen|show\_info|false|false / true|if true, show additional info on screen
Screen|show\_line|true|false / true|if true, show vertical border line „\|“ on screen
||||
ShellCmd|LUT|{}|dict|List of user defined commands to be executed in response to piTelex ESC commands; form: {„key1“: „cmd1“, „key2“: „cmd2“,..,..}. „cmd1“ will be executed after typing <ESC>key1<ENTER> a.s.o.. example: {„quick“: „echo the quick brown fox jumps“}; <ESC>quick<ENTER> gives the output „the quick brown fox jumps“; can be used for predefined commands like TP0/TP1 (turn off/on power for teleprinter)
||||
Terminal|portname|"/dev/ttyUSB0"|string|serial port used
Terminal|baudrate|300|number|Baud rate
Terminal|bytesize|8|number|# of Databits
Terminal|stopbits|1|1, 1.5, 2|# of stopbits
Terminal|parity|"NONE"|"NONE" / "ODD" / "EVEN"|parity bit
Terminal|loc\_echo|true|false / true|if true, echo back all characters
||||
Twitter|consumer\_key|||?
Twitter|consumer\_secret|||?
Twitter|access\_token\_key|||?
Twitter|access\_token\_secret|||?
Twitter|follow|||?
Twitter|track|||?
Twitter|languages|||?
Twitter|url|||?
Twitter|host|||?
Twitter|port|||?

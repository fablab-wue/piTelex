## Device StartMsg

### Description

Prints exactly one startup message after piTelex and the TTY device have been initialized, and checks wether

 - at least one internal IP address assigned (no local loopback)
 - at least one backend server can be reached:
      * Centralex (if enabled), or
      * TNS server



### Supported Operating Systems

Linux, RPi OS, MacOS, Windows

### Dependencies

none

### Command line parameters

none

### Config file option

| option name | type             | value | default | remark                                              |
| ----------- | ---------------- | ----- | ------- | --------------------------------------------------- |
| verbosity   | positive integer | 1..5  | 1       | verbosity of startup message, see description below |



The verbosity of the startup message can be controlled by the  option 'verbosity' (1..5):

| verbosity | startup message                                              |
| --------- | ------------------------------------------------------------ |
| 1         | only `TELEX READY` or `TELEX UP - NOT READY` + a few blank lines |
| 2         | like (1) + external + internal IP addresses                  |
| 3         | like (2) + `INTERNET CONNECTION OK/MISSING`                  |
| 4         | like (3) + backend checks:  <br />* if 'centralex' is enabled in the i-Telex device: Centralex server from telex.json<br/>* otherwise: TNS servers (default list or tns_srv/tns_port from i-Telex) |
| 5         | like (4) + two lines of `RYRYRY...`                            |

> NOTE: The backend diagnostics are missing up to now. Will be added in a future release.
> 
### Config file snippet

```JSON
"startmsg": {
      "type": "startmsg",
      "verbosity": 1, # 1 to 5
      "enable": true
    }
```

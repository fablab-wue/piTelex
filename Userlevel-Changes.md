## Changes compared to branch Experimental-22-01
This file will hopefully help to keep track of the  changes from the Experimental-branch, as far as the user level is concerned.
Before committing this branch to master, the official wiki documentation should be updated according to the entries in this file.

### Configuration Parameters

|commit No|Action  | Device | Parameter                          | type / range | default| comment|
|---------|--------|--------|------------------------------------|--------------|--------|---------|
|c061859  |Added   |Global  |power_off_delay                     | non-neg. int |20      | time in seconds from end-of-conection until switching off TTY power|
|c061859  |Added   |Global  |power_button_timeout                | non-neg. int | 300    | time in seconds from switching on TTY power by means of button PT until switch off PWR|
|67bf7ee  |fixed   |Global  |continue_with_no_printer           | false/true   |false   | bug for TW39-devices fixed|
|a5fc112  |Added   |RPiCtrl |pin_button_PT                       | non-neg. int | 0      | GPIO # of power button PT |
|24fd178  |Added   |RPiCtrl |pin_LED_LT                          | non-neg. int | 0      | GPIO # of LED indicating local mode |
|b25d15a  |Added   |RPiCtrl |delay_AT                            | non-neg. int | 0      | optional delay to make reactions to pressing `AT` more realistic|
|b25d15a  |Added   |RPiCtrl |delay_ST                            | non-neg. int | 0      | optional delay to make reactions to pressing `ST` more realistic|
|ed3ee79  |Deleted |Global  |verbose                             |              |        | unused
|         |Deleted |Global  |wru_fallback                        |              |        | replaced by `wru_replace_always`|
| 8059f3d |Deleted |ITelexSrv| number                            |              |        | replaced by `tns-dynip-number`
|ed3ee79  |Deleted |RPiTTY  | observe_rxd                        |              |        | replaced by `use_observe_line` `pin_observe_line`, `inv_observe_line`|
|9e4c76c  |Deleted |RPiTTY  |pin_fsg_ns                          |              |        | replaced by `pin_number_switch`|
|a8f40a9| Added|  ITelexSrv| tns_dynip_number |              |        | replace tns-dynip-number|
|a8f40a9| Added|  ITelexSrv| tns_pin       |              |        | replace tns-pin|
|a8f40a9| Deprecated|  ITelexSrv| tns-dynip-number |              |        | replaced by tns_dynip_number|
|a8f40a9| Deprecated|  ITelexSrv| tns-pin       |              |        | replaced by tns_pin|
|d856a4f| Added |Global| errorlog_level | NOTSET, DEBUG, INFO, WARN, ERROR, CRITICAL | INFO | verbosity of error log
|53de83a| Added | RPiCtrl | pin_wakeup  | non-neg. int | 0 | GPIO # pin for wake up from sleeping ZZ

###  Miscellaneous

#### 0796dd8: Add optional parameter DELAY for rss-feed

Timeout between two checks of a newsfeed can be specified by -t parameter of rssFileWrite,py; but the helper script rss-feed did not cope with this.
Now the delay can be specified in the newsfeed config file as third parameter separately for each feed. If no delay is given, it defaults to 10 seconds.
Must update page for rssFileWriter.py to reflect this.

#### Module RPiCtrl: Add option `nzz_observer_line` (default:false): Usage? --> ignore observing when sleeping

#### Module RPiTTY: Add modes 

`AGT` for Ö-AGT support  --> another sub mode for Lorenz TTY?

`TW39H` for H-Bridge HW Support

tbc...

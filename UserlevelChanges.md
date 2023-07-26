## List of changes relevant to the user in the  "testing" branch compared to the "master" branch 

###  New config file parameter `block_ascii`

* Module: ITelexSrv

* commit: https://github.com/fablab-wue/piTelex/commit/6c4ae196d4bc84fbcb5309b17ef936fdc4fdd2d3
   
* Description:
Added config file parameter `block_ascii` (boolean, default false) to avoid port scans and such being printed at the TTY, if set to true
Hint: On an incoming ASCII-connection, the teleprinter may or may not be switched on for a few seconds, but printing is suppressed.



###  Added support for USB-Keypads

* Module: Keypad (new)

* commit: https://github.com/fablab-wue/piTelex/commit/6d4ae6055ebb5265e21930b720c472887bea0845

* Dependencies: python-evdev, Linux ONLY!

* Description:  

  Added device "keypad", allows connection of a numeric keypad via usb
  KeyPad input for text shortcuts and test teletypes.

  Tutorial: https://python-evdev.readthedocs.io/en/latest/tutorial.html


### Added a "hand type simulator"

* Module: MCP
* commit: https://github.com/fablab-wue/piTelex/commit/6d4ae6055ebb5265e21930b720c472887bea0845
* Description:
 
   Added a simulator for manual typing, i.e insert random delays between "keystrokes".
   Toggle on/off in Screen via `<ESC> T`.
   When enabled, prints "lorem ipsum" dummy text with pseudo random delay between keystrokes until disabled.
   To output the text to the teleprinter, first activate it by either dialling '000' or entering `<ESC> A`in `screen`.

### Added modes "AGT-TWM", "AGT-TW39"

* Module: RPiTTY
* commit: https://github.com/fablab-wue/piTelex/commit/bda4629887ff94e56a51519ad4501a1df5fa2810
* Description:

  Introduce more specific modes `AGT-TW39`, `AGT-TWM` (module RPiTTY) for use with Ö-AGT's (will probably replace general mode `AGT` in a later version)

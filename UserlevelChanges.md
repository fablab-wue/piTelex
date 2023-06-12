## List of user level relevant changes in branch "testing" compared to master branch 

###  New config file parameter `block_ascii`

* Module: ITelexSrv

* commit: https://github.com/fablab-wue/piTelex/commit/6c4ae196d4bc84fbcb5309b17ef936fdc4fdd2d3
   
* Description:
Added config file parameter `block_ascii` (boolean, default false) to avoid port scans and such being printed at the TTY, if set to true



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
 
   Added "hand type simulator", i.e insert random delays between "keystrokes" if enabled.
   Enable/disable in Screen via `<ESC>T`. When enabled, TTY then prints "lorem ipsum" blind text.

### Added modes "AGT-TWM", "AGT-TW39"

* Module: RPiTTY
* commit: https://github.com/fablab-wue/piTelex/commit/bda4629887ff94e56a51519ad4501a1df5fa2810
* Description:
* 
   Introduce modes `AGT-TW39`, `AGT-TWM` (module RPiTTY) for use with Ö-AGT's

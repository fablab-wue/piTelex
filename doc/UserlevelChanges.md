# Changes since release 2025-06

### Fix software WRU response
* Module: MCP
* Description:
  Reformat software WRU for better compatibility with Archive e-mail functionaltiy

### New module "babelfish" 
Babelfish allows automatic translation of incoming messages to a predefined language.<br>
See https://github.com/fablab-wue/piTelex/wiki/SW_DevBabelfish

### Fix unhandled exceptions
* Module: i-telex
* Description:
  Previously, it was possible in some cases that the socket connection is already closed when we want to send some data like 'der', 'occ',… Without catching this, the i-telex-server would die and the machine would not be reachable anymore.

  Now, this is catched and the server will still run after these exceptions.

# Software

TODO...

## Modules

<img src="img/SW_Modules.png" width="1330px">

### Device Modules

| Module | Description | System | State |
| :--- | :--- | --- | --- |
| [Controller](README_SW_DevController.md) | Handling common tasks | all | RC
| [Screen](README_SW_DevScreen.md) | Type and display on screen | PC-W, PC-L | RC
| [Log](README_SW_DevLog.md) | Log to file | all | RC
| [CH340TTY](README_SW_DevCH340TTY.md) | TODO | all (USB) | BETA
| [RPiTTY](README_SW_DevRPiTTY.md) | TODO | RPi | ALPHA
| [ED1000](README_SW_DevED1000.md) | TODO | PC-W, PC-L | ALPHA
| [ITelexClient](README_SW_DevITelexClient.md) | TODO | all | BETA
| [ITelexSrv](README_SW_DevITelexSrv.md) | TODO | all | BETA
| [TelnetSrv](README_SW_DevTelnetSrv.md) | TODO | all | BETA
| [Eliza](README_SW_DevEliza.md) | TODO | all | BETA

## State Machine

The internal states are controlled by escape sequences. 

| ESC | Description |
| --- | --- |
| AT | User start outgoing call
| ST | User stop outgoing call
| LT | Locale
| A | Connected
| Z | Disconnected
| WB | Begin dialing
| #&lt;number&gt; | Dialing is finished, request IP-address, connecting


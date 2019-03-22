# Software

For Installation see [SW_Install](SW_Install.md)

TODO...

---

## Modules

<img src="img/SW_Modules.png" width="1330px">

### Device Modules

For more information on single module click on the link in the table.

| Module | Description | System | State |
| :--- | :--- | --- | --- |
| [Controller](SW_DevController.md) | Handling common tasks | all | RC
| [Screen](SW_DevScreen.md) | Type and display on screen | PC-W, PC-L | RC
| [Log](SW_DevLog.md) | Log to file | all | RC
| [CH340TTY](SW_DevCH340TTY.md) | TODO | all (USB) | BETA
| [RPiTTY](SW_DevRPiTTY.md) | TODO | RPi | ALPHA
| [ED1000](SW_DevED1000.md) | TODO | PC-W, PC-L | ALPHA
| [ITelexClient](SW_DevITelexClient.md) | TODO | all | BETA
| [ITelexSrv](SW_DevITelexSrv.md) | TODO | all | BETA
| [TelnetSrv](SW_DevTelnetSrv.md) | TODO | all | BETA
| [Eliza](SW_DevEliza.md) | TODO | all | BETA

---

## State Machine

The internal states are controlled by escape sequences. 

| ESC | Description |
| --- | --- |
| AT | User start outgoing call
| ST | User stop outgoing call
| LT | User set to Locale mode
| A | Connected
| Z | Disconnected
| WB | Begin dialing
| #&lt;number&gt; | Dialing is finished, request IP-address, connecting

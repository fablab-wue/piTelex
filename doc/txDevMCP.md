
### Error messages, based on r874 of i-Telex source and personal conversation
with Fred

##### Types:

- A: printed at the calling party during keyboard dial
- B: sent as reject packet payload by called party

   |Error|Type|Handled in|Description|
   |-----|----|----------|-----------|
   |bk   | A  |  iTxClient  | dial failure (called party not found in TNS) |
   |nc   | A  |  iTxClient  | cannot establish TCP connection to called party |
   |abs  | A  |             | line disabled |
   |abs  | B  |             | line disabled |
   |occ  | B  |  iTxSrv     | line occupied |
   |der  | B  |  iTxCommon  | derailed: line connected, but called teleprinter not starting up |
   |na   | B  |  iTxCommon  | called extension not allowed |

B type errors are handled in txDevITelexCommon.send_reject. It defaults to "abs", but this error isn't used yet.
Printer start feedback code follows, which enables us to check if the printer hardware has in fact been started. 
Every teleprinter module must support the `ESC-~` command, which is sent upon printer startup and after that about every 500 ms.

- Whenever `ESC-A` is sent, the teleprinter must be started. MCP starts a timer upon receipt (see above).

- When the teleprinter has been started, its module sends `ESC-~` on successful start, which cancels MCP's timer.

- If the teleprinter cannot be started, `ESC-~` must **not** be sent. When the timer runs out, MCP sends `ESC-Z` to terminate the start attempt.

NB: Ready-to-dial state `ESC-WB` is handled in a special way:

- In WB mode, the teleprinter
     - **must** be running at machines using keyboard dialling, but
     - must **not** be running at machines which use number switch dialling. 
       So don't require printer startup during WB, but remember if it does and skip timer activation in A state.

- No other modules depend on WB state yet, it's solely triggered by manual AT operation, so the relaxed monitoring for keyboard dialling machines should be ok. Feedback on the A state is crucial however, in case of incoming i-Telex connections.

This thread monitors the number-to-dial and initiates the dial command depending on the selected mode:

- **Instant dialling** is the classic dial method used in older piTelex versions. It's selected if the configured timeout is 0. In contrast to the other methods, dialling is tried after every entered digit, i.e. incrementally.

- **Timeout dialling** behaviour is based on i-Telex r874 (as documented in the comments at trunk/iTelex/iTelex. :4586) and simplified:

     1. After each digit, the local user list is searched in i-Telex. In piTelex, we don't, because in the current architecture it would complicate things         quite a bit.
     2. TNS server is queried if at least five digits have been dialled and no further digit is dialled for two seconds.
     3. If there is a positive result from a local or TNS query, try to establish a connection.
     4. Dialling is cancelled if a connection attempt in 3. failed or if nothing further is dialled for 15 seconds.

- **Plus dialling** simply waits for digits, cumulates them and dials after '+' has been entered.

    - The condition "five digits minimum" is fulfilled in `txDevITelexClient`.
    - change holds the return value of `dial_change.wait`: False if returning by timeout, True otherwise
    - Number empty or not in dial mode -- wait for next change and recheck afterwards.

- **Instant dialling**: Just try dialling on every digit, failing silently if number not found (`ESC-#!` instead of `ESC-#`, handled in `txDevITelexClient`).

NB: We keep `self._dial_number` here to allow **incremental dialling**. It is reset not inside this thread like with the other methods, but from the outside (on receipt of `ESC-A`).

Other dialling methods start here.

There is a number being dialled. This loop runs once for every dialled digit and checks if the dial condition is
fulfilled:

- '+' dialling: number complete when finished by +
- timeout dialling: number complete when timeout occurs

On dial, we break out of the loop and queue the dial command, which is executed by `txDevMCP`. For details see `txDevMCP.get_user`.

A change in `self._dial_number` has occurred:
- in + dial mode: Check if the last change was a plus, otherwise ignore; Remove trailing + and dial
- in timeout dial mode, just save the digit and continue

No change in dialled number: wait method timed out. This can only happen in timeout dialling mode and if at least one digit has been dialled. Dial now.

Before the next iteration, wait on the next change We've got a "go" for dialling, either by timeout or by +

TODO have dial command always print an error on fail...

README.txt
===========

piTelex CLI
Maintainer notes on differences between txCLI.py versions


Compared versions
-----------------
- txCLI.py version 2.3.1
- local file:     txCLI.py version 2.3.6

General assessment
------------------
The local file is not just a cosmetic edit. It is a functionally extended
variant of the testing-branch CLI, mainly in the interactive control flow.
Most of the technical base remains compatible, but several maintenance and
operator workflows were changed.

Main changes
------------

1. WPS handling changed from blocking to asynchronous

   In the testing branch, WPS is started synchronously after confirmation.
   The CLI is effectively busy until the WPS process finishes.

   In the local version, WPS was reworked to run in a background thread.
   Added internal state variables:

   - `_wps_running`
   - `_wps_result`
   - `_wps_thread`
   - `_wps_worker()`

   Behaviour:
   - after j/y confirmation, CLI returns `WAIT` immediately
   - later inputs return `WAIT` while WPS is still active
   - after completion, the next input returns the result

   This is the most important behavioural change.

2. WPS confirmation made more robust for strip printers

   The local version explicitly tolerates an empty CR while waiting for
   WPS confirmation. This is documented in code as useful for T68d and
   similar strip printers.

   Result:
   - a pure line end does not abort or mis-handle WPS confirmation
   - the CLI keeps waiting for a real j/y input

3. `LUPD` removed

   The testing branch still contains `LUPD`, which starts a Linux update
   sequence using `apt-get update && apt-get -y upgrade`.

   The local version removes this command entirely.

   Consequence:
   - the local CLI no longer performs distribution/package upgrades
   - this avoids long-running and risky remote update behaviour from CLI

4. New command `RESTART`

   The local version adds `RESTART`.

   Behaviour:
   - confirmation via j/y
   - then schedules `systemctl restart pitelex.service`
   - returns `BYE`

   This replaces the old update-oriented workflow with a service-oriented
   restart workflow.

5. New command `RLNET`

   The local version adds `RLNET`.

   Behaviour:
   - schedules `systemctl restart NetworkManager`
   - returns a short operator message
   - intended for controlled network reload without reboot

6. Constructor state updated accordingly

   Removed:
   - `_lupd_wait_password`

   Added:
   - `_restart_wait_password`
   - WPS thread state variables mentioned above

7. Help text adjusted

   The help output was updated to reflect the new command set.

   Differences:
   - `LUPD` removed
   - `RESTART` added
   - `RLNET` added
   - wording cleaned up accordingly

8. Minor text adjustments

   Example:
   - `WHOAMI` text changed from
     `HELP or ? FOR HELP.`
     to
     `WRITE HELP FOR HELP.`

   This is minor, but it is part of the visible operator behaviour.

What did NOT fundamentally change
---------------------------------
The following areas still follow the same overall line as in the testing branch:

- shell helper functions
- IP information commands
- external IP lookup
- WLAN scan handling
- WPS helper/error code structure
- basic command parser layout
- confirmation handling style for reboot/shutdown

So the local file should be understood as an incremental but meaningful
extension, not as a rewrite.

Operational effect
------------------
From a maintainer point of view, the local version shifts the CLI in a more
practical direction for teleprinter operation:

- less risk from remote package upgrades
- better WLAN/WPS usability on real teleprinter hardware
- explicit service restart option
- explicit network reload option
- non-blocking long-running WPS procedure

Recommendation for maintainers
------------------------------
Before merging into a shared branch, the following should be checked:

1. Whether asynchronous WPS behaviour is acceptable project-wide
2. Whether `LUPD` should really stay removed
3. Whether `RESTART` and `RLNET` fit the intended maintenance policy
4. Whether the WAIT/result behaviour is acceptable on all supported printers
5. Whether command documentation in other project texts needs updating

Short changelog form
--------------------
- version raised from 2.3.1 to 2.3.6
- WPS reworked to asynchronous background execution
- better WPS confirmation handling for strip printers
- removed `LUPD`
- added `RESTART`
- added `RLNET`
- adjusted help and status texts

End of file

Further changes of the file txCLI.py should be documented in the header of the file.

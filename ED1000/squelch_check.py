#!/usr/bin/env python3

"""
ED1000 squelch check

Motivation: There is crosstalk between ED1000 receive and send circuits. It
can, under some circumstances, happen that if there is no clear A or Z signal
reception from the teletypewriter (e.g. if it's disconnected temporarily),
phantom characters are received when data are sent to the teletypewriter at the
same time, mixing with the actually received characters.

To prevent this from happening, adjust the receive_squelch parameter of the
ED1000 module. It determines which minimal receive level is accepted as actual
data. To recognise valid data, the sum of A and Z levels must be bigger than
this threshold.

How to use:
1. Enable recv_debug option and restart piTelex, after which the recv_debug.log
   file is created, listing the reception level output of the A and Z
   recognition filters, separated by comma, one line per sample.

2. Collect some valid data, e.g. by dialling an automatic i-Telex service to
   receive some text.

3. After this, disconnect the teletypewriter signal cable and receive some more
   data, e.g. by "telnet <your-ip> <piTelex Port>", write some text and
   disconnect (CTRL-], q). If there is interfering crosstalk, the piTelex
   console should show garbled text. This step may be optional.

4. Execute "./squelch_check.py recv_debug.log". It shows a signal level
   histogram, i.e. the total signal level for "valid A" and "valid Z",
   respectively:
   - Samples recognised as A or Z are printed in different colours.
   - In total, for A and Z there should be one clearly defined cluster at the
     right end or in the middle. These are the "real", valid, samples.
   - To the right, there should be a high peak at 0 and some noise beside it.
     The high peak are the idle samples (where nothing is received), the noise
     on its right side is crosstalk.
   - There should be a lot of empty space between the right border of the
     crosstalk and the left border of the nearest valid cluster. Pick the
     approximate middle.

5. Set recv_squelch to this middle value and restart piTelex. Repeat step
   three; there should be no more garbled text.

Remarks:
- For a logarithmic frequency axis, pass "log" as additional argument.
- If there are no clearly defined "valid" clusters, try adjusting the capture
  volume for the microphone (e.g. with alsamixer). One way to check levels is
  to do "tail -f recv_debug.log", open the mixer in parallel and connect your
  teletypewriter. In quiescent state, it should send "A" signal continuously.
  Lower the microphone recording volume to zero; receive levels should drop to
  about zero. Then raise the volume step by step; levels should rise too. At
  some time, the level should max out, i.e. it raises no more even though you
  raise the volume. You should aim closely below this threshold for optimal
  reception.

TODO:
- A realtime plot would be nice.
"""

import sys
import matplotlib.pyplot as plt

def main(*argv):
    try:
        logfile = argv[1]
    except IndexError:
        print("Error: Must be called with recv_debug log file name. Exiting.")
        sys.exit(1)

    with open(logfile) as f:
        lines = f.readlines()
        f.close()

    # Create data lists
    values_sum_AZ_Z = []    # Sum A+Z for all A <  Z (recognised as Z)
    values_sum_AZ_A = []    # Sum A+Z for all A >= Z (recognised as A)

    # Insert all lines representing the received A, Z filter level, one line
    # being one sample each, into a list.
    for line in lines:
        line = line.strip()
        A, Z = line.split(",")
        A = int(A)
        Z = int(Z)
        if A < Z:
            # Z level recognised
            values_sum_AZ_Z.append(A+Z)
        else:
            # A level recognised
            values_sum_AZ_A.append(A+Z)

    # Plot the values
    plt.hist(values_sum_AZ_A, bins=100, alpha = 0.8, label = "A")
    plt.hist(values_sum_AZ_Z, bins=100, alpha = 0.8, label = "Z")

    # Enable log frequency axis
    if "log" in argv:
        plt.yscale('log', nonposy='clip')
    plt.title("Receive level histogram")
    plt.xlabel("level")
    plt.ylabel("frequency")
    plt.legend(loc='upper right')
    plt.show()

if __name__ == "__main__":
    main(*sys.argv)

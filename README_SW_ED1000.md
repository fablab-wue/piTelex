# Software Plugin ED1000

## Plugin Information

### System

| System | Comments |
| --- | --- |
| RPi | unknown
| PC Linux | unknown
| PC Windows | in Develpment
| Mac | unknown


### Dependencies

| Python<br>Module | Install | Anaconda |
| --- | --- | --- |
| pyaudio | pip install pyaudio | conda install pyaudio
| numpy | ? | -included-
| scypy | ? | -included-



## Implementation Details

> In development:

### Using IIR-Filter

<img src="img/ED1000IIR.png" width="300px">

 * Slice samples in 5ms pieces
 * Filter each slice for 2250HZ and 3150Hz:

       filter_bp = signal.iirfilter(4, [f/1.05, f*1.05], rs=40, btype='band',
                    analog=False, ftype='butter', fs=sample_f, output='sos')

 * Get average of abs() per slice per frequency
 * Compare values of both frequencies to get bit value (0/1)

 ### Using FFT...

TODO...

 ...

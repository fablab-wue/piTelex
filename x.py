import RPi.GPIO as GPIO

# Set up the GPIO channels - one input and one output
GPIO.setmode(GPIO.BCM)
GPIO.setup(11, GPIO.IN, pull_up_down = GPIO.PUD_UP)
#
GPIO.setup(12, GPIO.OUT)

# Input from GPIO 11
value = GPIO.input(11)

# Output to GPIO 12
GPIO.output(12, GPIO.HIGH)

==

import pigpio # http://abyz.co.uk/rpi/pigpio/python.html

pi = pigpio.pi()

# Set up the GPIO channels - one input and one output
#
pi.set_mode(11, pigpio.INPUT)
pi.set_pull_up_down(11, pigpio.PUD_UP)
pi.set_mode(12, pigpio.OUTPUT)

# Input from GPIO 11
value = pi.read(11)

# Output to GPIO 12
pi.write(12, 1)

==================================================
GPIO In/Out (Sleep)

import pigpio # http://abyz.co.uk/rpi/pigpio/python.html

pi = pigpio.pi()

while True:
    pi.write(pin_a, 1)
    pi.write(pin_b, 1)

    time.sleep(0.003)   # :-(

    pi.write(pin_a, 0)

    time.sleep(0.002)   # :-(

    pi.write(pin_b, 0)

    time.sleep(0.005)   # :-(

=============================================
GPIO Wave

pi = pigpio.pi()

wave = [
    pigpio.pulse(1<<pin_a | 1<<pin_b, 0, 3000),
    pigpio.pulse(0, 1<<pin_a, 0, 2000),
    pigpio.pulse(0, 1<<pin_b, 0, 5000),
    ]
pi.wave_add_generic(wave)

wid = pi.wave_create() # commit waveform
pi.wave_send_repeat(wid) # transmit waveform

do_work()

=============================================
GPIO Wave Serial

pi = pigpio.pi()

wpi.wave_add_serial(pin_txd, BAUD, 'Hallo', 0, DATABITS, STOPBITSx2)

wid = pi.wave_create() # commit waveform
pi.wave_send_once(wid) # transmit waveform

while pi.wave_tx_busy():
    do_work()

???pi.wave_delete(wid)

count, data = pi.bb_serial_read(pin_rxd)

=============================================
GPIO Callback

pi.set_mode(pin_dial, pigpio.INPUT)
pi.set_pull_up_down(pin_dial, pigpio.PUD_UP)
pi.set_glitch_filter(pin_dial, 1000)   # 1ms
pi.set_watchdog(pin_dial, 150)   # 150ms

pi.callback(pin_dial, pigpio.FALLING_EDGE, callback_dial)

def callback_dial(gpio, level, tick):
    if level == pigpio.TIMEOUT:   # watchdog timeout
        print(dial_count)
        dial_count = 0
    else:
        dial_count += 1

=============================================
PWM

pi.set_mode(pin_pwm, pigpio.OUTPUT)

pi.set_PWM_frequency(pin_pwm, 1000)   # 1kHz
pi.set_PWM_range(pin_pwm, 100)

pi.set_PWM_dutycycle(pin_pwm, 0)
pi.set_PWM_dutycycle(pin_pwm, 50)
pi.set_PWM_dutycycle(pin_pwm, 100)

=============================================
I2C

h = pi.i2c_open(1, 0x53)

pi.i2c_write_device(h, 0x55)
data = pi.i2c_read_byte(h)

pi.i2c_write_byte_data(h, 0x1d, 0xAA)
data = pi.i2c_read_byte_data(h, 0x1d)

pi.i2c_write_block_data(h, 0x1C, [1,2,3,4,5])
(b, data) = pi.i2c_read_i2c_block_data(h, 0x1D, 5)

=============================================
SPI

h = pi.spi_open(1, 50000)

(b, data) = pi.spi_xfer(h, [1,128,0])

(b, data) = pi.spi_xfer(h, '\x01\x80\x00')

=============================================
Remote

#Shell auf RPi mit Namen 'myRPi'
>sudo pigpiod

#Python auf PC
pi = pigpio.pi('myRPi')   # oder '10.23.42.66'

pi.set_mode(11, pigpio.INPUT)
pi.set_mode(12, pigpio.OUTPUT)

value = pi.read(11)
pi.write(12, 1)

=============================================
Spezial

pi = pigpio.pi()

pi.set_mode(12, pigpio.OUTPUT)
pi.set_mode(13, pigpio.OUTPUT)
pi.set_mode(14, pigpio.OUTPUT)

pi.set_bank_1(1<<12 | 1<<13 | 1<<14)

pi.clear_bank_1(1<<12 | 1<<13 | 1<<14)

=============================================

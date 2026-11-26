# SPDX-FileCopyrightText: 2026 Mikey Sklar for Adafruit Industries
#
# SPDX-License-Identifier: Unlicense

"""HDMI audio test: color bars plus a steady 440 Hz tone on the monitor's speakers.

Wire the board's I2S output into the adapter's I2S header. On the Metro
ESP32-P4: A0 to BCK, A1 to LRC, A2 to DIN. No MCLK is needed. Turn the
adapter's DDC switch off, and use a monitor input with audio: DVI inputs carry
no sound. The bridge is set up for 48 kHz audio.

The video timing is the 720p mode from ``lt8912b_720p.py``.
"""

import array
import math
import time

import audiobusio
import audiocore
import board
import busio
import displayio
import framebufferio
import mipidsi
import vectorio

import adafruit_lt8912b

displayio.release_displays()

# Set this to the bridge's reset pin, or None if it is not connected.
RESET_PIN = getattr(board, "DSI_RESET", None)

SAMPLE_RATE = 48_000  # The bridge is set up for 48 kHz.
TONE_FREQUENCY = 440
TONE_CYCLES = 11  # 11 cycles of 440 Hz fill exactly 1200 samples at 48 kHz.
VOLUME = 0.25

# LT8912B vendor 1280x720 preset: 80 MHz, 1800x741 totals, 59.98 Hz.
WIDTH = 1280
HEIGHT = 720
PIXEL_CLOCK_FREQUENCY = 80_000_000
NUM_LANES = 2

i2c = busio.I2C(board.SCL, board.SDA)
bus = mipidsi.Bus(minimum_frequency=PIXEL_CLOCK_FREQUENCY * 24 // NUM_LANES, num_lanes=NUM_LANES)
bridge = adafruit_lt8912b.LT8912B(
    bus,
    i2c,
    reset=RESET_PIN,
    width=WIDTH,
    height=HEIGHT,
    hsync_pulse_width=32,
    hsync_back_porch=80,
    hsync_front_porch=408,
    vsync_pulse_width=5,
    vsync_back_porch=13,
    vsync_front_porch=3,
    pixel_clock_frequency=PIXEL_CLOCK_FREQUENCY,
    hsync_positive=True,
    vsync_positive=True,
    vic=0,  # Custom timing: the totals differ from CEA-861 VIC 4.
    aspect_ratio=2,  # 16:9
)
display = framebufferio.FramebufferDisplay(bridge, auto_refresh=True)

# Draw eight vertical color bars.
colors = (0xFFFFFF, 0xFFFF00, 0x00FFFF, 0x00FF00, 0xFF00FF, 0xFF0000, 0x0000FF, 0x000000)
palette = displayio.Palette(len(colors))
for index, color in enumerate(colors):
    palette[index] = color
group = displayio.Group()
bar_width = bridge.width // len(colors)
for index in range(len(colors)):
    group.append(
        vectorio.Rectangle(
            pixel_shader=palette,
            width=bar_width,
            height=bridge.height,
            x=index * bar_width,
            y=0,
            color_index=index,
        )
    )
display.root_group = group

# Switch the bridge to HDMI and turn on its I2S input.
bridge.audio_enabled = True

# One loop of a 440 Hz sine wave, played over and over.
length = SAMPLE_RATE * TONE_CYCLES // TONE_FREQUENCY
peak = int(32767 * VOLUME)
sine = array.array(
    "h", (int(peak * math.sin(2 * math.pi * TONE_CYCLES * i / length)) for i in range(length))
)
tone = audiocore.RawSample(sine, sample_rate=SAMPLE_RATE)

audio = audiobusio.I2SOut(bit_clock=board.A0, word_select=board.A1, data=board.A2)
audio.play(tone, loop=True)

print("Color bars and a 440 Hz tone should now be playing.")
print("HDMI cable connected:", bridge.hot_plug_detected)

while True:
    time.sleep(1)

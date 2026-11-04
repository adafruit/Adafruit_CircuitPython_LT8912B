# SPDX-FileCopyrightText: 2026 Scott Shawcroft for Adafruit Industries
#
# SPDX-License-Identifier: Unlicense

"""1080p30 output on the LT8912B bridge.

Connect the bridge's I2C control pins to the board's default SCL/SDA. CEA-861
1080p30 uses a 74.25 MHz pixel clock, but the ESP32-P4 DSI host can only make
pixel clocks that divide 240 or 160 MHz. This uses 80 MHz (240/3) and moves the
extra pixels into the horizontal back porch: 2370 by 1125 totals scan at 30.00
Hz and 33.76 kHz per line, matching CEA 1080p30's rates.

With two DSI lanes and RGB888, 80 MHz needs 960 Mbps per lane, within the
ESP32-P4's 1.5 Gbps per-lane limit.

See ``lt8912b_720p.py`` for the 720p60 alternative.
"""

import time

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

# CEA-861 1080p30 with 170 extra pixels in the horizontal back porch.
WIDTH = 1920
HEIGHT = 1080
HSYNC_PULSE_WIDTH = 44
HSYNC_BACK_PORCH = 318
HSYNC_FRONT_PORCH = 88
VSYNC_PULSE_WIDTH = 5
VSYNC_BACK_PORCH = 36
VSYNC_FRONT_PORCH = 4
PIXEL_CLOCK_FREQUENCY = 80_000_000
VIC = 0  # Custom timing: the totals differ from CEA-861 VIC 34.
ASPECT_RATIO = 2  # 16:9

H_TOTAL = WIDTH + HSYNC_FRONT_PORCH + HSYNC_PULSE_WIDTH + HSYNC_BACK_PORCH
V_TOTAL = HEIGHT + VSYNC_FRONT_PORCH + VSYNC_PULSE_WIDTH + VSYNC_BACK_PORCH

# Run two DSI lanes at no less than the rate RGB888 needs. The bus picks a
# PHY rate close to that minimum.
NUM_LANES = 2
MINIMUM_LANE_BIT_RATE = PIXEL_CLOCK_FREQUENCY * 24 // NUM_LANES

print("Line rate:", PIXEL_CLOCK_FREQUENCY // H_TOTAL, "Hz")
print("Refresh rate:", PIXEL_CLOCK_FREQUENCY // (H_TOTAL * V_TOTAL), "Hz")

i2c = busio.I2C(board.SCL, board.SDA)

bus = mipidsi.Bus(minimum_frequency=MINIMUM_LANE_BIT_RATE, num_lanes=NUM_LANES)

# The bridge configures itself, then starts DSI video.
bridge = adafruit_lt8912b.LT8912B(
    bus,
    i2c,
    reset=RESET_PIN,
    width=WIDTH,
    height=HEIGHT,
    hsync_pulse_width=HSYNC_PULSE_WIDTH,
    hsync_back_porch=HSYNC_BACK_PORCH,
    hsync_front_porch=HSYNC_FRONT_PORCH,
    vsync_pulse_width=VSYNC_PULSE_WIDTH,
    vsync_back_porch=VSYNC_BACK_PORCH,
    vsync_front_porch=VSYNC_FRONT_PORCH,
    pixel_clock_frequency=PIXEL_CLOCK_FREQUENCY,
    hsync_positive=True,
    vsync_positive=True,
    vic=VIC,
    aspect_ratio=ASPECT_RATIO,
)

display = framebufferio.FramebufferDisplay(bridge, auto_refresh=True)

# Draw eight vertical color bars on the HDMI/DVI output.
palette = displayio.Palette(8)
colors = (
    0xFFFFFF,  # white
    0xFFFF00,  # yellow
    0x00FFFF,  # cyan
    0x00FF00,  # green
    0xFF00FF,  # magenta
    0xFF0000,  # red
    0x0000FF,  # blue
    0x000000,  # black
)
for index, color in enumerate(colors):
    palette[index] = color

group = displayio.Group()
bar_width = bridge.width // len(colors)
for index in range(len(colors)):
    left = index * bar_width
    right = (index + 1) * bar_width if index < len(colors) - 1 else bridge.width
    group.append(
        vectorio.Rectangle(
            pixel_shader=palette,
            width=right - left,
            height=bridge.height,
            x=left,
            y=0,
            color_index=index,
        )
    )
display.root_group = group

print("1080p30 color bars displayed. HDMI cable connected:", bridge.hot_plug_detected)

while True:
    time.sleep(1)

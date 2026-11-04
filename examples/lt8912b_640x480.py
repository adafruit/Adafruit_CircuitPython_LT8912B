# SPDX-FileCopyrightText: 2026 Scott Shawcroft for Adafruit Industries
#
# SPDX-License-Identifier: Unlicense

"""Standard 640x480 output on the LT8912B bridge.

Connect the bridge's I2C control pins to the board's default SCL/SDA. This
example targets the VESA DMT 640x480 mode, but the ESP32-P4 cannot produce its
25.175 MHz pixel clock: the DSI host divides a fixed 240 MHz source, so only
240/N pixel clocks exist and 25.175 MHz would round to 24 MHz (57 Hz, which
many monitors reject). 26.667 MHz is 240/9 exactly, so the surplus pixels go
into the vertical back porch instead: 800x556 keeps DMT's horizontal timing
and totals, and scans at 59.95 Hz.
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

# 640x480 at ~60 Hz with DMT's horizontal timing. The vertical back porch
# absorbs the 31 extra lines needed to keep the refresh rate at the 26.667 MHz
# clock the DSI host can actually generate.
WIDTH = 640
HEIGHT = 480
HSYNC_PULSE_WIDTH = 96
HSYNC_BACK_PORCH = 48
HSYNC_FRONT_PORCH = 16
VSYNC_PULSE_WIDTH = 2
VSYNC_BACK_PORCH = 64
VSYNC_FRONT_PORCH = 10
PIXEL_CLOCK_FREQUENCY = 26_666_667
VIC = 0  # Custom timing: the totals differ from CEA-861 VIC 1.
ASPECT_RATIO = 1  # 4:3

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
print("DSI lane rate:", bus.frequency // 1_000_000, "Mbps")

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
    hsync_positive=False,
    vsync_positive=False,
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

print("640x480 color bars displayed. HDMI cable connected:", bridge.hot_plug_detected)

while True:
    time.sleep(1)

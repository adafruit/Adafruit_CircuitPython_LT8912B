# SPDX-FileCopyrightText: 2026 Scott Shawcroft for Adafruit Industries
#
# SPDX-License-Identifier: Unlicense

"""Simple test for the LT8912B MIPI DSI to HDMI/DVI bridge.

Connect the bridge's I2C control pins to the board's default SCL/SDA. This
example uses a fixed 800 x 480 DVI mode. See ``lt8912b_edid.py`` to use the
monitor's preferred EDID timing instead.
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

# The ESP32-P4 has two DSI data lanes. 480 Mbps per lane is exactly what
# RGB888 at 40 MHz needs over two lanes, so the stream is continuous (byte
# clock = 1.5x pixel clock) and the link runs as slowly as it can.
LANE_BIT_RATE = 480_000_000
NUM_LANES = 2

# Fixed 800 x 480 mode at ~60 Hz. The DSI host can only make 240/N pixel
# clocks, so this uses 40 MHz (240/6) and puts the extra 270 pixels in the
# horizontal back porch: 1270 x 525 scans at 59.99 Hz and 31.5 kHz per line.
WIDTH = 800
HEIGHT = 480
HSYNC_PULSE_WIDTH = 48
HSYNC_BACK_PORCH = 310
HSYNC_FRONT_PORCH = 112
VSYNC_PULSE_WIDTH = 3
VSYNC_BACK_PORCH = 29
VSYNC_FRONT_PORCH = 13
PIXEL_CLOCK_FREQUENCY = 40_000_000

H_TOTAL = WIDTH + HSYNC_FRONT_PORCH + HSYNC_PULSE_WIDTH + HSYNC_BACK_PORCH
V_TOTAL = HEIGHT + VSYNC_FRONT_PORCH + VSYNC_PULSE_WIDTH + VSYNC_BACK_PORCH

print("Line rate:", PIXEL_CLOCK_FREQUENCY // H_TOTAL, "Hz")
print("Refresh rate:", PIXEL_CLOCK_FREQUENCY // (H_TOTAL * V_TOTAL), "Hz")

i2c = busio.I2C(board.SCL, board.SDA)

# Create the DSI bus first so its PHY is powered while the bridge is programmed.
dsi_bus = mipidsi.Bus(frequency=LANE_BIT_RATE, num_lanes=NUM_LANES)

bridge = adafruit_lt8912b.LT8912B(
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
    lanes=NUM_LANES,
)

# An empty init sequence is correct: the LT8912B is a bridge, not a DSI panel.
# Display's constructor starts DPI scanout once the bridge is configured.
panel = mipidsi.Display(
    dsi_bus,
    b"",
    width=WIDTH,
    height=HEIGHT,
    hsync_pulse_width=HSYNC_PULSE_WIDTH,
    hsync_back_porch=HSYNC_BACK_PORCH,
    hsync_front_porch=HSYNC_FRONT_PORCH,
    vsync_pulse_width=VSYNC_PULSE_WIDTH,
    vsync_back_porch=VSYNC_BACK_PORCH,
    vsync_front_porch=VSYNC_FRONT_PORCH,
    pixel_clock_frequency=PIXEL_CLOCK_FREQUENCY,
    color_depth=24,
)

display = framebufferio.FramebufferDisplay(panel, auto_refresh=True)

# Scanout is live now, so start the bridge's output clock loop at the
# configured pixel clock instead of the vendor table's 29 MHz default.
bridge.seed_output_clock()

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
bar_width = panel.width // len(colors)
for index in range(len(colors)):
    left = index * bar_width
    right = (index + 1) * bar_width if index < len(colors) - 1 else panel.width
    group.append(
        vectorio.Rectangle(
            pixel_shader=palette,
            width=right - left,
            height=panel.height,
            x=left,
            y=0,
            color_index=index,
        )
    )
display.root_group = group

print("Color bars displayed. HDMI cable connected:", bridge.get_hpd())

while True:
    time.sleep(1)

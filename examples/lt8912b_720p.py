# SPDX-FileCopyrightText: 2026 Scott Shawcroft for Adafruit Industries
#
# SPDX-License-Identifier: Unlicense

"""Standard 720p60 output on the LT8912B bridge.

Connect the bridge's I2C control pins to the board's default SCL/SDA. This is
1280x720 at 60 Hz, but not with CEA-861's 74.25 MHz pixel clock: the ESP32-P4
DSI host divides a fixed 240 MHz source, so 74.25 MHz becomes 80 MHz and the
CEA totals would scan at 64.6 Hz. HDMI sinks usually only accept CEA refresh
rates, so this uses 80 MHz (240/3, also 160/2) with the LT8912B vendor preset
totals 1800x741, which scans at 59.98 Hz and 44.4 kHz per line. With two DSI
lanes and RGB888, 80 MHz needs about 960 Mbps per lane, within the ESP32-P4's
1.5 Gbps per-lane limit. 1080p60 would need about 1920 Mbps per lane.

See ``lt8912b_1080p30.py`` for the 1080p30 alternative, and
``lt8912b_640x480.py`` for a low-bandwidth mode.
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

# 960 Mbps makes the DSI byte clock exactly 1.5x the pixel clock, so the
# stream is continuous and the bridge's FIFO loop has nothing to chase. This
# is the vendor's 720p configuration.
LANE_BIT_RATE = 960_000_000
NUM_LANES = 2

# LT8912B vendor 1280x720 preset: 80 MHz, 1800x741 totals, 59.98 Hz.
WIDTH = 1280
HEIGHT = 720
HSYNC_PULSE_WIDTH = 32
HSYNC_BACK_PORCH = 80
HSYNC_FRONT_PORCH = 408
VSYNC_PULSE_WIDTH = 5
VSYNC_BACK_PORCH = 13
VSYNC_FRONT_PORCH = 3
PIXEL_CLOCK_FREQUENCY = 80_000_000
VIC = 0  # Custom timing: the totals differ from CEA-861 VIC 4.
ASPECT_RATIO = 2  # 16:9

H_TOTAL = WIDTH + HSYNC_FRONT_PORCH + HSYNC_PULSE_WIDTH + HSYNC_BACK_PORCH
V_TOTAL = HEIGHT + VSYNC_FRONT_PORCH + VSYNC_PULSE_WIDTH + VSYNC_BACK_PORCH

print("Required lane rate:", PIXEL_CLOCK_FREQUENCY * 24 // NUM_LANES, "bps per lane")
print("Lane rate:", LANE_BIT_RATE // 1_000_000, "Mbps per lane")
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
    hsync_positive=True,
    vsync_positive=True,
    vic=VIC,
    aspect_ratio=ASPECT_RATIO,
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

# Scanout is live now, so start the bridge's output clock loop at the real
# pixel clock instead of the vendor table's 29 MHz default.
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

# get_input_timing() reports the H/V period the receiver measures and
# get_hpd() the monitor's hot-plug state, which are the two quickest ways to
# tell a DSI problem from an HDMI one.
print(
    "720p60 color bars displayed. MIPI input:",
    bridge.get_input_timing(),
    "HPD:",
    bridge.get_hpd(),
)

while True:
    time.sleep(1)

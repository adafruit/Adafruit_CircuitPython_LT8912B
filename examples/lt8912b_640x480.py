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

If the image shears partway down the frame, the bridge's output clock is
slightly off the DSI input rate; ``bridge.seed_output_clock(hold=True)`` pins
it at 26.667 MHz instead of tracking the stream.
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

# 320 Mbps per lane is exactly what RGB888 at 26.667 MHz needs over two
# lanes, so the stream is continuous (byte clock = 1.5x pixel clock) and the
# link runs as slowly as it can.
LANE_BIT_RATE = 320_000_000
NUM_LANES = 2

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

print("Required lane rate:", PIXEL_CLOCK_FREQUENCY * 24 // NUM_LANES, "bps per lane")
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
    hsync_positive=False,
    vsync_positive=False,
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

print("640x480 color bars displayed. HDMI cable connected:", bridge.get_hpd())

while True:
    time.sleep(1)

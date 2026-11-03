# SPDX-FileCopyrightText: 2026 Scott Shawcroft for Adafruit Industries
#
# SPDX-License-Identifier: Unlicense

"""Standard 1080p30 output on the LT8912B bridge.

Connect the bridge's I2C control pins to the board's default SCL/SDA. This uses
CEA-861 VIC 34 exactly: 1920x1080 at 30 Hz with a 74.25 MHz pixel clock, 2200
by 1125 totals, 33.75 kHz per line. 74.25 MHz is not a division of the ESP32-P4
port's fixed 240 MHz DPI source, so ``mipidsi`` programs the audio PLL to 74.25
MHz instead; the constructor prints ``mipidsi: APLL 74 MHz / 1`` when it does.

With two DSI lanes and RGB888, 74.25 MHz needs about 891 Mbps per lane, within
the ESP32-P4's 1.5 Gbps per-lane limit. 1080p60 needs 148.5 MHz, which is above
the APLL's 125 MHz ceiling, so it is not available.

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

# 891 Mbps per lane is exactly what RGB888 at 74.25 MHz needs over two lanes,
# so the stream is continuous (byte clock = 1.5x pixel clock).
LANE_BIT_RATE = 891_000_000
NUM_LANES = 2

# CEA-861 VIC 34: 1920x1080p30.
WIDTH = 1920
HEIGHT = 1080
HSYNC_PULSE_WIDTH = 44
HSYNC_BACK_PORCH = 148
HSYNC_FRONT_PORCH = 88
VSYNC_PULSE_WIDTH = 5
VSYNC_BACK_PORCH = 36
VSYNC_FRONT_PORCH = 4
PIXEL_CLOCK_FREQUENCY = 74_250_000
VIC = 34
ASPECT_RATIO = 2  # 16:9

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

print("1080p30 color bars displayed. HDMI cable connected:", bridge.get_hpd())

while True:
    time.sleep(1)

# SPDX-FileCopyrightText: 2026 Scott Shawcroft for Adafruit Industries
#
# SPDX-License-Identifier: Unlicense

"""Use the monitor's preferred EDID timing with the LT8912B bridge.

Connect the bridge's I2C control pins to the board's default SCL/SDA. If the
adapter has a DDC switch, turn it on so the monitor's EDID EEPROM is visible at
0x50. The example falls back to 800 x 480 when no usable EDID timing is found
or when the preferred mode exceeds the DSI bandwidth.

The DSI host cannot produce most EDID pixel clocks. It divides a fixed 240 MHz
source, so 74.25 MHz becomes 80 MHz and 25.175 MHz becomes 24 MHz. The example
absorbs that rounding in the horizontal back porch so the refresh rate the
EDID asks for is preserved; only the blanking changes.

The DDC switch connects the display's own I2C pins to the bridge's control bus
while it is on. Some HDMI display boards expose a programming interface at the
bridge's 0x48-0x4A addresses, so if the bridge behaves oddly with the switch
on, read the EDID, then switch DDC off and rerun with the printed timing
hard-coded.
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

# The ESP32-P4 has two DSI data lanes. 960 Mbps per lane leaves headroom for
# RGB888 output up to about 80 MHz pixel clock.
LANE_BIT_RATE = 960_000_000
NUM_LANES = 2

FALLBACK_TIMING = {
    "width": 800,
    "height": 480,
    "hsync_pulse_width": 48,
    "hsync_back_porch": 310,
    "hsync_front_porch": 112,
    "vsync_pulse_width": 3,
    "vsync_back_porch": 29,
    "vsync_front_porch": 13,
    "pixel_clock_frequency": 40_000_000,
    "hsync_positive": False,
    "vsync_positive": False,
    "vic": 0,
    "aspect_ratio": 0,
}

# Set False to pass the EDID porches through unchanged. That keeps the totals
# a picky sink may expect, at the cost of shifting its refresh rate by the
# clock rounding error.
RETIME_TIMING = True

# mipidsi's DSI host derives the DPI pixel clock from a fixed 240 MHz source
# (PLL_F240M), and ESP-IDF rounds the requested clock to the nearest divider.
DPI_CLOCK_SOURCE = 240_000_000


def achievable_clock(clock):
    """Return the pixel clock the DSI host will really generate."""
    return DPI_CLOCK_SOURCE // round(DPI_CLOCK_SOURCE / clock)


def totals(timing):
    """Return the horizontal and vertical totals for a timing dict."""
    h_total = (
        timing["width"]
        + timing["hsync_front_porch"]
        + timing["hsync_pulse_width"]
        + timing["hsync_back_porch"]
    )
    v_total = (
        timing["height"]
        + timing["vsync_front_porch"]
        + timing["vsync_pulse_width"]
        + timing["vsync_back_porch"]
    )
    return h_total, v_total


def retime(timing):
    """Move clock rounding into the back porch so the refresh rate survives.

    Returns ``None`` when the rounded clock cannot reproduce the timing.
    """
    h_total, v_total = totals(timing)
    clock = achievable_clock(timing["pixel_clock_frequency"])
    refresh = timing["pixel_clock_frequency"] / (h_total * v_total)
    back_porch = timing["hsync_back_porch"] + round(clock / (refresh * v_total)) - h_total
    if back_porch < 0 or back_porch > 0xFFFF:
        return None
    timing = dict(timing)
    timing["pixel_clock_frequency"] = clock
    timing["hsync_back_porch"] = back_porch
    return timing


i2c = busio.I2C(board.SCL, board.SDA)

# Read the monitor's preferred mode before talking to the bridge. The EDID
# EEPROM lives at 0x50 and may be on a separate DDC bus on some adapters.
timing = adafruit_lt8912b.read_edid_timing(i2c)
requested = timing
if timing is not None and RETIME_TIMING:
    timing = retime(timing)
if timing is None:
    print("No usable EDID timing, using the 800x480 fallback")
    timing = FALLBACK_TIMING
elif timing["pixel_clock_frequency"] * 24 > LANE_BIT_RATE * NUM_LANES:
    print("EDID mode exceeds the DSI bandwidth, using the 800x480 fallback")
    timing = FALLBACK_TIMING
else:
    edid_h, edid_v = totals(requested)
    print(
        f"EDID timing: {requested['width']}x{requested['height']} at "
        f"{requested['pixel_clock_frequency'] / 1_000_000:.2f} MHz, "
        f"{edid_h}x{edid_v}, "
        f"{requested['pixel_clock_frequency'] / (edid_h * edid_v):.2f} Hz"
    )
    h_total, v_total = totals(timing)
    print(
        f"Sending {timing['pixel_clock_frequency'] / 1_000_000:.2f} MHz, "
        f"{h_total}x{v_total}, "
        f"{timing['pixel_clock_frequency'] / (h_total * v_total):.2f} Hz"
    )

# Create the DSI bus first so its PHY is powered while the bridge is programmed.
dsi_bus = mipidsi.Bus(frequency=LANE_BIT_RATE, num_lanes=NUM_LANES)

bridge = adafruit_lt8912b.LT8912B(i2c, reset=RESET_PIN, **timing, lanes=NUM_LANES)

# An empty init sequence is correct: the LT8912B is a bridge, not a DSI panel.
# Display's constructor starts DPI scanout once the bridge is configured.
panel = mipidsi.Display(
    dsi_bus,
    b"",
    width=timing["width"],
    height=timing["height"],
    hsync_pulse_width=timing["hsync_pulse_width"],
    hsync_back_porch=timing["hsync_back_porch"],
    hsync_front_porch=timing["hsync_front_porch"],
    vsync_pulse_width=timing["vsync_pulse_width"],
    vsync_back_porch=timing["vsync_back_porch"],
    vsync_front_porch=timing["vsync_front_porch"],
    pixel_clock_frequency=timing["pixel_clock_frequency"],
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

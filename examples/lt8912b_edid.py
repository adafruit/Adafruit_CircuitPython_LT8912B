# SPDX-FileCopyrightText: 2026 Scott Shawcroft for Adafruit Industries
#
# SPDX-License-Identifier: Unlicense

"""Use the monitor's preferred EDID timing with the LT8912B bridge.

Connect the bridge's I2C control pins to the board's default SCL/SDA. If the
adapter has a DDC switch, turn it on so the monitor's EDID EEPROM is visible at
0x50. The example falls back to 800 x 480 when no usable EDID timing is found
or when the preferred mode exceeds the DSI bandwidth.

The DSI host makes the pixel clock by dividing a fixed 240 MHz source, so
74.25 MHz becomes 80 MHz and 25.175 MHz becomes 24 MHz. Monitors that check
the refresh rate may then show nothing. The example absorbs that rounding in
the horizontal back porch so the refresh rate the EDID asks for is preserved;
only the blanking changes.

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

# The ESP32-P4 has two DSI data lanes. Limit the EDID mode to 960 Mbps per
# lane, which covers RGB888 output up to an 80 MHz pixel clock.
MAX_LANE_BIT_RATE = 960_000_000
NUM_LANES = 2

# The monitor's EDID EEPROM, reached over the HDMI DDC pins.
EDID_ADDRESS = 0x50


def read_edid(i2c):
    """Read the 128-byte EDID base block, or return ``None`` on failure."""
    data = bytearray(128)
    while not i2c.try_lock():
        pass
    try:
        i2c.writeto_then_readfrom(EDID_ADDRESS, b"\x00", data)
    except OSError:
        return None
    finally:
        i2c.unlock()
    return data


def parse_edid_timing(data):  # noqa: PLR0911
    """Decode the preferred detailed timing from an EDID 1.3/1.4 base block.

    Only digital, progressive modes with separate sync are supported. Returns
    a dict of ``LT8912B`` timing keyword arguments, or ``None``.
    """
    if data is None or bytes(data[0:8]) != b"\x00\xff\xff\xff\xff\xff\xff\x00":
        return None
    # Checksum, version 1, revision 3 or 4.
    if sum(data[0:128]) & 0xFF or data[18] != 1 or not 3 <= data[19] <= 4:
        return None
    # Digital input with a preferred timing in the first detailed descriptor.
    if not (data[20] & 0x80) or not (data[24] & 0x02):
        return None

    dtd = data[54:72]
    clock_10khz = dtd[0] | (dtd[1] << 8)
    flags = dtd[17]
    # Reject interlaced, stereo, borders and anything but digital separate sync.
    if not clock_10khz or flags & 0xE1 or (flags & 0x18) != 0x18 or dtd[15] or dtd[16]:
        return None

    width = dtd[2] | ((dtd[4] & 0xF0) << 4)
    h_blank = dtd[3] | ((dtd[4] & 0x0F) << 8)
    height = dtd[5] | ((dtd[7] & 0xF0) << 4)
    v_blank = dtd[6] | ((dtd[7] & 0x0F) << 8)
    hsync_front_porch = dtd[8] | ((dtd[11] & 0xC0) << 2)
    hsync_pulse_width = dtd[9] | ((dtd[11] & 0x30) << 4)
    vsync_front_porch = (dtd[10] >> 4) | ((dtd[11] & 0x0C) << 2)
    vsync_pulse_width = (dtd[10] & 0x0F) | ((dtd[11] & 0x03) << 4)

    if not width or not height:
        return None
    if not 1 <= hsync_pulse_width <= 255 or not 1 <= vsync_pulse_width <= 255:
        return None
    if (
        h_blank < hsync_front_porch + hsync_pulse_width
        or v_blank < vsync_front_porch + vsync_pulse_width
    ):
        return None

    return {
        "width": width,
        "height": height,
        "hsync_pulse_width": hsync_pulse_width,
        "hsync_back_porch": h_blank - hsync_front_porch - hsync_pulse_width,
        "hsync_front_porch": hsync_front_porch,
        "vsync_pulse_width": vsync_pulse_width,
        "vsync_back_porch": v_blank - vsync_front_porch - vsync_pulse_width,
        "vsync_front_porch": vsync_front_porch,
        "pixel_clock_frequency": clock_10khz * 10_000,
        "hsync_positive": bool(flags & 0x02),
        "vsync_positive": bool(flags & 0x04),
    }


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
timing = parse_edid_timing(read_edid(i2c))
requested = timing
if timing is not None and RETIME_TIMING:
    timing = retime(timing)
if timing is None:
    print("No usable EDID timing, using the 800x480 fallback")
    timing = FALLBACK_TIMING
elif timing["pixel_clock_frequency"] * 24 > MAX_LANE_BIT_RATE * NUM_LANES:
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

# RGB888 needs 24 bits per pixel across the lanes. Base the minimum on the
# pixel clock the DSI host will really generate, which can be rounded.
actual_pixel_clock = achievable_clock(timing["pixel_clock_frequency"])
minimum_lane_bit_rate = actual_pixel_clock * 24 // NUM_LANES
bus = mipidsi.Bus(minimum_frequency=minimum_lane_bit_rate, num_lanes=NUM_LANES)
print(f"DSI lane rate: {bus.frequency / 1_000_000:.2f} Mbps")

# The bridge configures itself, then starts DSI video.
bridge = adafruit_lt8912b.LT8912B(bus, i2c, reset=RESET_PIN, **timing)

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

print("Color bars displayed. HDMI cable connected:", bridge.hot_plug_detected)

while True:
    time.sleep(1)

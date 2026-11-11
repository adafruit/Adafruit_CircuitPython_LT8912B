# SPDX-FileCopyrightText: 2026 Scott Shawcroft for Adafruit Industries
# SPDX-FileCopyrightText: 2023-2026 Espressif Systems (Shanghai) CO LTD
# SPDX-FileCopyrightText: 2026 Adafruit Industries
#
# SPDX-License-Identifier: Apache-2.0
# Register initialization tables are adapted from Espressif's
# esp_lcd_lt8912b and Adafruit's Adafruit_LT8912B under the Apache License,
# Version 2.0. See NOTICE and LICENSES/Apache-2.0.txt.
"""
`adafruit_lt8912b`
================================================================================

CircuitPython driver for the LT8912B MIPI DSI to HDMI/DVI bridge.

`LT8912B` is a ``mipidsi.Display`` that also configures the bridge over I2C.

* Author(s): Scott Shawcroft

Implementation Notes
--------------------

**Hardware:**

* Adafruit LT8912B MIPI DSI to HDMI/DVI bridge adapter
  (https://github.com/adafruit/Adafruit_LT8912B)

**Software and Dependencies:**

* Adafruit CircuitPython firmware for the supported boards, with
  ``mipidsi.Display.pixel_clock_frequency`` and ``low_power_blanking``, and
  ``mipidsi.Bus.minimum_frequency``, ``frequency`` and ``num_lanes``:
  https://circuitpython.org/downloads

* Adafruit's Bus Device library:
  https://github.com/adafruit/Adafruit_CircuitPython_BusDevice
"""

import time

import digitalio
import mipidsi
from adafruit_bus_device.i2c_device import I2CDevice
from micropython import const

__version__ = "0.0.0+auto.0"
__repo__ = "https://github.com/adafruit/Adafruit_CircuitPython_LT8912B.git"

# The bus treats rates within 1 kHz of its minimum as meeting it.
_BUS_FREQUENCY_TOLERANCE = const(1_000)

# I2C addresses of the bridge's three register banks.
_I2C_MAIN = const(0x48)
_I2C_DSI = const(0x49)
_I2C_AVI = const(0x4A)

# MAIN bank registers
_MAIN_MIPI_RESET = const(0x03)
_MAIN_DDS_RESET = const(0x05)
_MAIN_TX_CONTROL = const(0x33)
_MAIN_SYNC_POLARITY = const(0xAB)
_MAIN_HDMI_MODE = const(0xB2)
_MAIN_HPD_STATUS = const(0xC1)

# DSI bank registers
_DSI_LANES = const(0x13)
_DSI_H_SYNC = const(0x18)
_DSI_V_SYNC = const(0x19)
_DSI_H_ACTIVE = const(0x1C)
_DSI_FIFO_BUFFER_LENGTH = const(0x2F)
_DSI_H_TOTAL = const(0x34)
_DSI_V_TOTAL = const(0x36)
_DSI_V_BACK_PORCH = const(0x38)
_DSI_V_FRONT_PORCH = const(0x3A)
_DSI_H_BACK_PORCH = const(0x3C)
_DSI_H_FRONT_PORCH = const(0x3E)
_DSI_DDS_FREQUENCY = const(0x4E)
_DSI_DDS_CONTROL = const(0x51)

# AVI bank registers
_AVI_CHECKSUM = const(0x43)

# Vendor initialization tables as flat (register, value) pairs.
_MAIN_INIT = (
    b"\x02\xf7\x08\xff\x09\xff\x0a\xff\x0b\x7c\x0c\xff"  # Digital clock enable
    b"\x31\xe1\x32\xe1\x33\x0c\x37\x00\x38\x22\x60\x82"  # TX analog
    b"\x39\x45\x3a\x00\x3b\x00"  # CBUS analog
    b"\x44\x31\x55\x44\x57\x01\x5a\x02"  # HDMI PLL analog
    b"\x3e\xd6\x3f\xd4\x41\x3c"  # MIPI analog: no P/N swap, EQ, control
)
_DSI_INIT_START = (
    b"\x10\x01"  # Termination enable
    b"\x11\x10"  # Settle
)
_DSI_INIT_END = (
    b"\x14\x00"  # Debug mux
    b"\x15\x00"  # No lane swap
    b"\x1a\x03"  # H shift
    b"\x1b\x03"  # V shift
    # DDS: frequency word, full/empty thresholds, timer and trend coefficients
    b"\x4e\x93\x4f\x3e\x50\x29\x51\x80\x1e\x4f\x1f\x5e\x20\x01\x21\x2c"
    b"\x22\x01\x23\xfa\x24\x00\x25\xc8\x26\x00\x27\x5e\x28\x01\x29\x2c"
    b"\x2a\x01\x2b\xfa\x2c\x00\x2d\xc8\x2e\x00\x42\x64\x43\x00\x44\x04"
    b"\x45\x00\x46\x59\x47\x00\x48\xf2\x49\x06\x4a\x00\x4b\x72\x4c\x45"
    b"\x4d\x00\x52\x08\x53\x00\x54\xb2\x55\x00\x56\xe4\x57\x0d\x58\x00"
    b"\x59\xe4\x5a\x8a\x5b\x00\x5c\x34"
    b"\x51\x00"  # Release DDS control
    b"\x70\x00"  # Disable the internal test pattern
)
_MAIN_LVDS_BYPASS = (
    b"\x44\x30"  # LVDS power up
    b"\x51\x05"
    b"\x50\x24"  # CP = 50 uA
    b"\x51\x2d"  # Pixel clock reference, second-order PLL
    b"\x52\x04"
    b"\x69\x0e"
    b"\x69\x8e"
    b"\x6a\x00"
    b"\x6c\xb8"
    b"\x6b\x51"
    b"\x04\xfb"  # Core PLL reset
    b"\x04\xff"
    b"\x7f\x00"  # Disable scaler
    b"\xa8\x13"  # VESA format
    b"\x44\x31"  # LVDS output off
)
_AVI_AUDIO_OFF = (
    b"\x06\x00"  # Stop audio acquisition
    b"\x07\x00"  # Disable audio clock regeneration
    b"\x34\x52"  # Disable I2S input
    b"\x3c\x40"  # Disable audio/null packets
)


class LT8912B(mipidsi.Display):
    """LT8912B MIPI DSI to HDMI/DVI bridge.

    This resets the bridge and configures it for the given timing, then starts
    DSI video. Use it with `framebufferio.FramebufferDisplay` like any other
    ``mipidsi.Display``. The framebuffer is always RGB888.

    :param ~mipidsi.Bus bus: DSI bus connected to the bridge. Create it with a
        ``minimum_frequency`` of at least 24 times the pixel clock divided by
        the number of lanes. The bridge checks the rate the bus actually runs
        at, which can be higher.
    :param ~busio.I2C i2c: I2C bus connected to the bridge.
    :param int width: Active horizontal pixels.
    :param int height: Active vertical lines.
    :param int hsync_pulse_width: Horizontal sync width, 1 to 255 pixels.
    :param int hsync_back_porch: Horizontal back porch in pixels.
    :param int hsync_front_porch: Horizontal front porch in pixels.
    :param int vsync_pulse_width: Vertical sync width, 1 to 255 lines.
    :param int vsync_back_porch: Vertical back porch in lines.
    :param int vsync_front_porch: Vertical front porch in lines.
    :param int pixel_clock_frequency: Pixel clock in Hz.
    :param ~microcontroller.Pin reset: Optional active-low reset pin.
    :param bool hsync_positive: True for positive horizontal sync.
    :param bool vsync_positive: True for positive vertical sync.
    :param int vic: AVI video code, 0 to 127. 0 for custom timing.
    :param int aspect_ratio: AVI aspect ratio: 0 unspecified, 1 4:3, 2 16:9.
    :param kwargs: Other ``mipidsi.Display`` arguments, such as ``rotation``.
    :raises ValueError: If a parameter is out of range, the bus is too slow for
        the pixel clock, or the bridge does not respond on I2C.
    """

    def __init__(  # noqa: PLR0913, PLR0917
        self,
        bus,
        i2c,
        *,
        width,
        height,
        hsync_pulse_width,
        hsync_back_porch,
        hsync_front_porch,
        vsync_pulse_width,
        vsync_back_porch,
        vsync_front_porch,
        pixel_clock_frequency,
        reset=None,
        hsync_positive=False,
        vsync_positive=False,
        vic=0,
        aspect_ratio=0,
        **kwargs,
    ):
        h_total = width + hsync_front_porch + hsync_pulse_width + hsync_back_porch
        v_total = height + vsync_front_porch + vsync_pulse_width + vsync_back_porch
        if h_total > 0xFFFF or v_total > 0xFFFF:
            raise ValueError("horizontal or vertical total does not fit in 16 bits")
        if not 1 <= hsync_pulse_width <= 255:
            raise ValueError("hsync_pulse_width must be between 1 and 255")
        if not 1 <= vsync_pulse_width <= 255:
            raise ValueError("vsync_pulse_width must be between 1 and 255")
        if not 0 <= vic <= 127:
            raise ValueError("vic must be between 0 and 127")
        if not 0 <= aspect_ratio <= 2:
            raise ValueError("aspect_ratio must be 0, 1, or 2")

        # Configure the bridge before starting DSI video.
        self._main = I2CDevice(i2c, _I2C_MAIN)
        self._dsi = I2CDevice(i2c, _I2C_DSI)
        self._avi = I2CDevice(i2c, _I2C_AVI)

        self._reset_pin = None
        if reset is not None:
            self._reset_pin = digitalio.DigitalInOut(reset)
            self._reset_pin.switch_to_output(value=True)

        self._reset()

        # Stop the transmitter while reconfiguring.
        self._write_bit(self._main, _MAIN_TX_CONTROL, 1, False)

        self._write(self._main, _MAIN_INIT)
        self._write(self._dsi, _DSI_INIT_START)
        self._write(self._dsi, bytes((_DSI_LANES, bus.num_lanes % 4)))  # 0 means 4 lanes
        self._write(self._dsi, _DSI_INIT_END)
        # The vendor table seeds the DDS at 29 MHz; use the pixel clock.
        self._seed_output_clock(pixel_clock_frequency)

        timing = (
            (_DSI_H_TOTAL, h_total),
            (_DSI_V_TOTAL, v_total),
            (_DSI_V_BACK_PORCH, vsync_back_porch),
            (_DSI_V_FRONT_PORCH, vsync_front_porch),
            (_DSI_H_BACK_PORCH, hsync_back_porch),
            (_DSI_H_FRONT_PORCH, hsync_front_porch),
        )
        sequence = bytearray(
            (
                _DSI_H_SYNC,
                hsync_pulse_width,
                _DSI_V_SYNC,
                vsync_pulse_width,
                _DSI_H_ACTIVE,
                width & 0xFF,
                _DSI_H_ACTIVE + 1,
                width >> 8,
                _DSI_FIFO_BUFFER_LENGTH,
                0x0C,
            )
        )
        for register, value in timing:
            sequence.extend((register, value & 0xFF, register + 1, value >> 8))
        self._write(self._dsi, sequence)

        self._write_bit(self._main, _MAIN_SYNC_POLARITY, 1, hsync_positive)
        self._write_bit(self._main, _MAIN_SYNC_POLARITY, 0, vsync_positive)

        self._write_infoframe(vic, aspect_ratio)
        self._reset_receiver()
        self._write(self._main, _MAIN_LVDS_BYPASS)
        self._write(self._avi, _AVI_AUDIO_OFF)
        self._write_bit(self._main, _MAIN_HDMI_MODE, 0, False)  # DVI
        self._write_bit(self._main, _MAIN_TX_CONTROL, 1, True)

        # Start DSI video only now. The lanes stay in high speed mode, so the
        # bridge's receiver must be ready for the one start of transmission.
        super().__init__(
            bus,
            b"",
            width=width,
            height=height,
            hsync_pulse_width=hsync_pulse_width,
            hsync_back_porch=hsync_back_porch,
            hsync_front_porch=hsync_front_porch,
            vsync_pulse_width=vsync_pulse_width,
            vsync_back_porch=vsync_back_porch,
            vsync_front_porch=vsync_front_porch,
            pixel_clock_frequency=pixel_clock_frequency,
            color_depth=24,
            # The bridge regenerates the pixel clock from the DSI clock and
            # loses lock if the lanes drop to low power during blanking.
            low_power_blanking=False,
            **kwargs,
        )

        # RGB888 needs 24 bits per pixel spread across the lanes.
        needed = (self.pixel_clock_frequency * 24 + bus.num_lanes - 1) // bus.num_lanes
        if bus.frequency + _BUS_FREQUENCY_TOLERANCE < needed:
            self.deinit()
            raise ValueError(
                f"bus runs at {bus.frequency}, below the {needed} needed for this pixel clock"
            )

        # Seed again from the real clock now that the DDS has video to track.
        self._seed_output_clock(self.pixel_clock_frequency)

    def _reset(self):
        """Pulse the reset pin if there is one, otherwise send a software reset."""
        if self._reset_pin is not None:
            self._reset_pin.value = False
            time.sleep(0.01)
            self._reset_pin.value = True
            time.sleep(0.01)
            return
        with self._main:
            self._main.write(bytes((0x01,)))
        time.sleep(0.02)

    def deinit(self):
        """Stop the display and release the reset pin."""
        if self._reset_pin is not None:
            self._reset_pin.deinit()
            self._reset_pin = None
        super().deinit()

    @property
    def hot_plug_detected(self):
        """True when the HDMI hot-plug detect line is high."""
        return bool(self._read_byte(self._main, _MAIN_HPD_STATUS) & 0x80)

    def _seed_output_clock(self, pixel_clock_frequency):
        """Start the output clock generator (DDS) at the pixel clock."""
        dds = int(pixel_clock_frequency / 1_000_000 * 0x16C16)
        self._write(
            self._dsi,
            bytes(
                (
                    _DSI_DDS_CONTROL,
                    0x80,
                    _DSI_DDS_FREQUENCY,
                    dds & 0xFF,
                    _DSI_DDS_FREQUENCY + 1,
                    (dds >> 8) & 0xFF,
                    _DSI_DDS_FREQUENCY + 2,
                    (dds >> 16) & 0xFF,
                    _DSI_DDS_CONTROL,
                    0x00,
                )
            ),
        )

    def _write_infoframe(self, vic, aspect_ratio):
        """Write the AVI infoframe: RGB, picture aspect ratio and VIC."""
        # The checksum also covers the 82 02 0D header.
        aspect = aspect_ratio << 4 | 0x08
        payload = ((0x5F - aspect - vic) & 0xFF, 0x10, aspect, 0, vic) + (0,) * 9
        infoframe = bytearray()
        for index, value in enumerate(payload):
            infoframe.extend((_AVI_CHECKSUM + index, value))
        self._write(self._avi, infoframe)

    def _reset_receiver(self):
        """Reset the MIPI receiver and the DDS."""
        self._write(self._main, bytes((_MAIN_MIPI_RESET, 0x7F)))
        time.sleep(0.01)
        self._write(self._main, bytes((_MAIN_MIPI_RESET, 0xFF, _MAIN_DDS_RESET, 0xFB)))
        time.sleep(0.01)
        self._write(self._main, bytes((_MAIN_DDS_RESET, 0xFF)))

    @staticmethod
    def _write(device, sequence):
        """Write a flat sequence of (register, value) pairs."""
        with device:
            for index in range(0, len(sequence), 2):
                device.write(sequence, start=index, end=index + 2)

    @staticmethod
    def _read_byte(device, register):
        buffer = bytearray(1)
        with device:
            device.write_then_readinto(bytes((register,)), buffer)
        return buffer[0]

    def _write_bit(self, device, register, bit, value):
        mask = 1 << bit
        current = self._read_byte(device, register) & ~mask
        self._write(device, bytes((register, current | (mask if value else 0))))

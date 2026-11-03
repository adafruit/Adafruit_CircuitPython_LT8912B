# SPDX-FileCopyrightText: 2026 Scott Shawcroft for Adafruit Industries
# SPDX-FileCopyrightText: 2023-2026 Espressif Systems (Shanghai) CO LTD
# SPDX-FileCopyrightText: 2026 Adafruit Industries
#
# SPDX-License-Identifier: MIT AND Apache-2.0
# Register initialization tables are adapted from Espressif's
# esp_lcd_lt8912b and Adafruit's Adafruit_LT8912B under the Apache License,
# Version 2.0. See NOTICE and LICENSES/Apache-2.0.txt.
"""
`adafruit_lt8912b`
================================================================================

CircuitPython driver for the LT8912B MIPI DSI to HDMI/DVI bridge.

The LT8912B is configured over I2C and then fed video by a MIPI DSI host, such
as the ESP32-P4. This driver only handles the I2C configuration (and optional
EDID reading); pixels are sent through the ``mipidsi`` module.

* Author(s): Scott Shawcroft

Implementation Notes
--------------------

**Hardware:**

* Adafruit LT8912B MIPI DSI to HDMI/DVI bridge adapter
  (https://github.com/adafruit/Adafruit_LT8912B)

**Software and Dependencies:**

* Adafruit CircuitPython firmware for the supported boards:
  https://circuitpython.org/downloads

* Adafruit's Bus Device library:
  https://github.com/adafruit/Adafruit_CircuitPython_BusDevice
"""

import time

import digitalio
from adafruit_bus_device.i2c_device import I2CDevice

__version__ = "0.0.0+auto.0"
__repo__ = "https://github.com/adafruit/Adafruit_CircuitPython_LT8912B.git"

# Fixed I2C addresses of the LT8912B register banks.
I2C_MAIN = 0x48
I2C_DSI = 0x49
I2C_AVI = 0x4A

# Display EDID EEPROM, separate from the bridge register banks.
EDID_ADDRESS = 0x50

_EDID_BLOCK_SIZE = 128
_EDID_VERSION = 18
_EDID_REVISION = 19
_EDID_INPUT = 20
_EDID_FEATURES = 24
_EDID_DTD = 54
_EDID_DIGITAL = 0x80
_EDID_PREFERRED = 0x02
_EDID_SYNC_TYPE = 0x18
_EDID_UNSUPPORTED = 0xE1
_EDID_HSYNC_POS = 0x02
_EDID_VSYNC_POS = 0x04

# MAIN bank registers used outside of the initialization tables.
_MAIN_MIPI_RESET = 0x03
_MAIN_DDS_RESET = 0x05
_MAIN_TX_CONTROL = 0x33
_MAIN_SYNC_POLARITY = 0xAB
_MAIN_HDMI_MODE = 0xB2
_MAIN_HPD_STATUS = 0xC1
_MAIN_H_SYNC_WIDTH = 0x9C
_MAIN_V_SYNC_WIDTH = 0x9E

# DSI bank registers used for the video timing.
_DSI_H_SYNC = 0x18
_DSI_V_SYNC = 0x19
_DSI_H_ACTIVE = 0x1C
_DSI_FIFO_BUFFER_LENGTH = 0x2F
_DSI_DDS_FREQUENCY = 0x4E
_DSI_DDS_CONTROL = 0x51
_DSI_PATTERN_ENABLE = 0x70
_DSI_H_TOTAL = 0x34
_DSI_V_TOTAL = 0x36
_DSI_V_BACK_PORCH = 0x38
_DSI_V_FRONT_PORCH = 0x3A
_DSI_H_BACK_PORCH = 0x3C
_DSI_H_FRONT_PORCH = 0x3E

# AVI bank infoframe registers.
_AVI_CHECKSUM = 0x43

# Ordered vendor initialization tables, stored as flat (register, value)
# byte strings to keep the frozen module small. These are retained from
# Espressif's esp_lcd_lt8912b driver and Adafruit's Arduino port.
_MAIN_DIGITAL_CLOCK = bytes(
    (
        0x02,
        0xF7,  # Digital clock enable.
        0x08,
        0xFF,
        0x09,
        0xFF,
        0x0A,
        0xFF,
        0x0B,
        0x7C,
        0x0C,
        0xFF,
    )
)
_MAIN_TX_ANALOG = bytes(
    (
        0x31,
        0xE1,  # Tx analog.
        0x32,
        0xE1,
        0x33,
        0x0C,
        0x37,
        0x00,
        0x38,
        0x22,
        0x60,
        0x82,
    )
)
_MAIN_CBUS_ANALOG = bytes((0x39, 0x45, 0x3A, 0x00, 0x3B, 0x00))  # Cbus analog.
_MAIN_HDMI_PLL = bytes(
    (
        0x44,
        0x31,  # HDMI PLL analog.
        0x55,
        0x44,
        0x57,
        0x01,
        0x5A,
        0x02,
    )
)
_MAIN_MIPI_ANALOG = bytes(
    (
        0x3E,
        0xD6,  # No MIPI P/N swap.
        0x3F,
        0xD4,  # EQ.
        0x41,
        0x3C,  # MIPI analog control.
    )
)
_DSI_BASIC_START = bytes(
    (
        0x10,
        0x01,  # Termination enable.
        0x11,
        0x10,  # Settle.
    )
)
_DSI_BASIC_END = bytes(
    (
        0x14,
        0x00,  # Debug mux.
        0x15,
        0x00,  # No lane swap.
        0x1A,
        0x03,  # H shift 3.
        0x1B,
        0x03,  # V shift 3.
    )
)
_DSI_DDS_CONFIG = bytes(
    (
        0x4E,
        0x93,  # strm_sw_freq_word[7:0]
        0x4F,
        0x3E,  # strm_sw_freq_word[15:8]
        0x50,
        0x29,  # strm_sw_freq_word[23:16]
        0x51,
        0x80,  # [0]=strm_sw_freq_word[24]
        0x1E,
        0x4F,
        0x1F,
        0x5E,  # full_value
        0x20,
        0x01,
        0x21,
        0x2C,  # full_value1
        0x22,
        0x01,
        0x23,
        0xFA,  # full_value2
        0x24,
        0x00,
        0x25,
        0xC8,  # full_value3
        0x26,
        0x00,
        0x27,
        0x5E,  # empty_value
        0x28,
        0x01,
        0x29,
        0x2C,  # empty_value1
        0x2A,
        0x01,
        0x2B,
        0xFA,  # empty_value2
        0x2C,
        0x00,
        0x2D,
        0xC8,  # empty_value3
        0x2E,
        0x00,
        0x42,
        0x64,  # tmr_set[7:0]: 100 us
        0x43,
        0x00,  # tmr_set[15:8]
        0x44,
        0x04,  # Timer step and following DDS tuning coefficients.
        0x45,
        0x00,
        0x46,
        0x59,
        0x47,
        0x00,
        0x48,
        0xF2,
        0x49,
        0x06,
        0x4A,
        0x00,
        0x4B,
        0x72,
        0x4C,
        0x45,
        0x4D,
        0x00,
        0x52,
        0x08,  # Trend step and following DDS tuning coefficients.
        0x53,
        0x00,
        0x54,
        0xB2,
        0x55,
        0x00,
        0x56,
        0xE4,
        0x57,
        0x0D,
        0x58,
        0x00,
        0x59,
        0xE4,
        0x5A,
        0x8A,
        0x5B,
        0x00,
        0x5C,
        0x34,
        0x51,
        0x00,  # Release DDS control.
    )
)
_MAIN_LVDS_BYPASS = bytes(
    (
        0x44,
        0x30,  # LVDS power up for bypass configuration.
        0x51,
        0x05,
        0x50,
        0x24,  # CP=50 uA.
        0x51,
        0x2D,  # Pixel clock reference, second-order passive LPF PLL.
        0x52,
        0x04,  # loopdiv=0; use second-order PLL.
        0x69,
        0x0E,  # CP_PRESET_DIV_RATIO.
        0x69,
        0x8E,
        0x6A,
        0x00,
        0x6C,
        0xB8,  # RGD_CP_SOFT_K_EN, RGD_CP_SOFT_K[13:8].
        0x6B,
        0x51,
        0x04,
        0xFB,  # Core PLL reset.
        0x04,
        0xFF,
        0x7F,
        0x00,  # Disable scaler.
        0xA8,
        0x13,  # VESA format (0x33 would select JEIDA).
        0x44,
        0x31,  # Disable LVDS output; use the HDMI/DVI transmitter only.
    )
)
_AVI_AUDIO_OFF = bytes(
    (
        0x06,
        0x00,  # Stop audio acquisition.
        0x07,
        0x00,  # Disable audio clock regeneration.
        0x34,
        0x52,  # Disable I2S input.
        0x3C,
        0x40,  # Disable audio/null packet insertion.
    )
)


class LT8912B:
    """LT8912B MIPI DSI to HDMI/DVI bridge.

    The chip exposes three fixed I2C register banks at 0x48, 0x49, and 0x4A.
    Creating this object asks `I2CDevice` to probe all three addresses, so a
    ``ValueError`` is raised if the bridge is not connected or is held in
    reset. Probing verifies I2C acknowledgements, not silicon identity. The
    bridge is configured for the given video timing as part of construction.

    :param ~busio.I2C i2c: I2C bus connected to the bridge control pins.
    :param ~microcontroller.Pin reset: Optional active-low reset pin. When
        provided, it is driven low then high during initialization.
    :param int width: Active horizontal pixels; must be positive.
    :param int height: Active vertical lines; must be positive.
    :param int hsync_pulse_width: Horizontal sync width, 1 to 255 pixel clocks.
    :param int hsync_back_porch: Horizontal back porch in pixel clocks.
    :param int hsync_front_porch: Horizontal front porch in pixel clocks.
    :param int vsync_pulse_width: Vertical sync width, 1 to 255 lines.
    :param int vsync_back_porch: Vertical back porch in lines.
    :param int vsync_front_porch: Vertical front porch in lines.
    :param int pixel_clock_frequency: Positive source pixel clock in Hz.
    :param bool hsync_positive: True for positive horizontal sync polarity.
    :param bool vsync_positive: True for positive vertical sync polarity.
    :param int vic: AVI video code, 0 to 127; 0 for custom timing.
    :param int aspect_ratio: AVI aspect: 0 unspecified, 1 is 4:3, 2 is 16:9.
    :param int lanes: Number of DSI data lanes, 1 to 4, without lane or P/N
        swapping.
    :raises ValueError: If the bridge does not acknowledge at 0x48, 0x49, or
        0x4A.
    """

    def __init__(  # noqa: PLR0913, PLR0917
        self,
        i2c,
        *,
        reset=None,
        width=800,
        height=480,
        hsync_pulse_width=48,
        hsync_back_porch=40,
        hsync_front_porch=112,
        vsync_pulse_width=3,
        vsync_back_porch=29,
        vsync_front_porch=13,
        pixel_clock_frequency=31_500_000,
        hsync_positive=False,
        vsync_positive=False,
        vic=0,
        aspect_ratio=0,
        lanes=2,
    ):
        self._width = width
        self._height = height
        self._hsync_pulse_width = hsync_pulse_width
        self._hsync_back_porch = hsync_back_porch
        self._hsync_front_porch = hsync_front_porch
        self._vsync_pulse_width = vsync_pulse_width
        self._vsync_back_porch = vsync_back_porch
        self._vsync_front_porch = vsync_front_porch
        self._pixel_clock_frequency = pixel_clock_frequency
        self._hsync_positive = hsync_positive
        self._vsync_positive = vsync_positive
        self._vic = vic
        self._aspect_ratio = aspect_ratio
        self._h_total = width + hsync_front_porch + hsync_pulse_width + hsync_back_porch
        self._v_total = height + vsync_front_porch + vsync_pulse_width + vsync_back_porch
        self._validate(lanes)

        self._main = I2CDevice(i2c, I2C_MAIN)
        self._dsi = I2CDevice(i2c, I2C_DSI)
        self._avi = I2CDevice(i2c, I2C_AVI)

        self._reset_pin = None
        if reset is not None:
            self._reset_pin = digitalio.DigitalInOut(reset)
            self._reset_pin.switch_to_output(value=True)
        self.reset()
        self._configure(lanes)

    def reset(self):
        """Reset the bridge, then wait for it to come back.

        With a reset pin this pulses it low for 10 ms. The Raspberry Pi MIPI
        DSI pinout has no reset line, so without a pin this falls back to the
        vendor driver's software reset, a bare write of ``0x01`` to the main
        bank. Reset discards configuration; create a new `LT8912B` afterward
        to configure the bridge again.
        """
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
        """Release the reset pin, if one was configured."""
        if self._reset_pin is not None:
            self._reset_pin.deinit()
            self._reset_pin = None

    def _configure(self, lanes):
        """Configure RGB888 DSI reception and enable video-only DVI output.

        The constructor calls this automatically. Create the ``mipidsi.Bus``
        before this object, then create the ``mipidsi.Display`` afterward so
        scanout starts once the bridge is ready.

        :param int lanes: Number of DSI data lanes, 1 to 4, without lane or
            P/N swapping.
        :raises OSError: If an I2C transaction fails.
        """

        # Stop the transmitter while changing timing so a partially updated
        # mode is not displayed.
        self.enable_output(False)

        self._write_sequence(self._main, _MAIN_DIGITAL_CLOCK)
        self._write_sequence(self._main, _MAIN_TX_ANALOG)
        self._write_sequence(self._main, _MAIN_CBUS_ANALOG)
        self._write_sequence(self._main, _MAIN_HDMI_PLL)
        self._write_sequence(self._main, _MAIN_MIPI_ANALOG)

        # Vendor encoding: 00=4, 01=1, 02=2, 03=3 lanes.
        lane_code = 0 if lanes == 4 else lanes
        self._write_sequence(self._dsi, _DSI_BASIC_START)
        self._write_sequence(self._dsi, bytes((0x13, lane_code)))
        self._write_sequence(self._dsi, _DSI_BASIC_END)
        self._write_sequence(self._dsi, _DSI_DDS_CONFIG)
        # Clear the test pattern enable so a soft reload after
        # show_test_pattern() starts from DSI video again.
        self._write_byte(self._dsi, _DSI_PATTERN_ENABLE, 0x00)
        # The vendor table seeds the DDS at 29 MHz, which is far from most
        # modes and leaves the FIFO loop to slew the output clock from there.
        self._write_dds_frequency()
        self._write_timing()

        # Sync polarity occupies only bits 1:0. Preserve the other fields.
        self._write_bits(self._main, _MAIN_SYNC_POLARITY, self._hsync_positive, shift=1)
        self._write_bits(self._main, _MAIN_SYNC_POLARITY, self._vsync_positive, shift=0)

        # AVI header is 82 02 0D. PB1=10 selects RGB with active-format
        # information; PB2 has the picture aspect in bits 5:4 and active
        # aspect "same as picture". Checksum=0x5F-PB2-PB4, modulo 256.
        aspect = self._aspect_ratio * 16 + 0x08
        checksum = (0x5F - aspect - self._vic) & 0xFF
        payload = (checksum, 0x10, aspect, 0, self._vic, 0, 0, 0, 0, 0, 0, 0, 0, 0)
        infoframe = bytearray(len(payload) * 2)
        for index, value in enumerate(payload):
            infoframe[index * 2] = _AVI_CHECKSUM + index
            infoframe[index * 2 + 1] = value
        self._write_sequence(self._avi, infoframe)

        self._reset_receiver()
        self._write_sequence(self._main, _MAIN_LVDS_BYPASS)
        self._write_sequence(self._avi, _AVI_AUDIO_OFF)
        self.set_hdmi(False)
        self.enable_output(True)

    def set_hdmi(self, enabled=True):
        """Select HDMI signaling or DVI signaling without enabling audio.

        :param bool enabled: True selects HDMI; False selects DVI.
        """
        self._write_bits(self._main, _MAIN_HDMI_MODE, enabled, shift=0)

    def enable_output(self, enabled=True):
        """Enable or disable the HDMI/DVI transmitter.

        :param bool enabled: True to transmit video; False to stop it.
        """
        self._write_bits(self._main, _MAIN_TX_CONTROL, enabled, shift=1)

    def seed_output_clock(self, hold=False):
        """Re-seed the output clock generator from the configured pixel clock.

        The FIFO loop inherits the seed written at construction time and can
        drift while there is no DSI video to track. Call this once
        ``mipidsi`` scanout is running to start the loop at the right
        frequency instead of the vendor table's 29 MHz default.

        :param bool hold: True pins the generator at the pixel clock instead
            of releasing it to the FIFO loop. Use it when the DSI host's pixel
            clock is exact, to rule the feedback loop out as a source of
            jitter.
        :raises OSError: If an I2C transaction fails.
        """
        self._write_dds_frequency(hold=hold)

    def _write_dds_frequency(self, hold=False):
        """Program the DDS word from the pixel clock, optionally holding it.

        Passing ``hold=True`` keeps the clock generator on the programmed
        frequency instead of releasing it to the FIFO loop, which is what the
        internal test pattern needs.
        """
        dds = int(self._pixel_clock_frequency / 1_000_000 * 0x16C16)
        self._write_sequence(
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
                )
            ),
        )
        if not hold:
            self._write_byte(self._dsi, _DSI_DDS_CONTROL, 0x00)

    def show_test_pattern(self):
        """Draw the bridge's internal color-bar pattern instead of DSI video.

        The LT8912B generates the pattern itself, so it separates the HDMI
        transmitter from the MIPI DSI receiver: bars on screen mean the
        transmitter, clock generation and cable are fine and the DSI input is
        the problem. This mirrors the vendor driver's ``ENABLE_TEST_PATTERN``
        sequence. Call it after construction and do not start ``mipidsi``
        scanout while the pattern is active. Create a new `LT8912B` to return
        to pass-through video.

        :raises OSError: If an I2C transaction fails.
        """
        # DE starts after the sync plus back porch, in the pattern generator's
        # own counters.
        de_delay = self._hsync_pulse_width + self._hsync_back_porch
        de_top = self._vsync_pulse_width + self._vsync_back_porch
        # The pattern clock does not come from the FIFO loop, so hold the DDS
        # at the pixel clock instead of releasing it.
        self._write_sequence(
            self._dsi,
            bytes(
                (
                    0x72,
                    0x12,
                    0x73,
                    de_delay & 0xFF,
                    0x74,
                    de_delay >> 8,
                    0x75,
                    de_top & 0xFF,
                    0x76,
                    self._width & 0xFF,  # DE count, low byte.
                    0x77,
                    self._height & 0xFF,  # DE lines, low byte.
                    0x78,
                    (((self._height >> 8) & 0x0F) << 4) | ((self._width >> 8) & 0x0F),
                    0x79,
                    self._h_total & 0xFF,
                    0x7A,
                    self._v_total & 0xFF,
                    0x7B,
                    (((self._v_total >> 8) & 0x0F) << 4) | ((self._h_total >> 8) & 0x0F),
                    0x7C,
                    self._hsync_pulse_width & 0xFF,
                    0x7D,
                    (((self._hsync_pulse_width >> 8) & 0x03) << 6)
                    | (self._vsync_pulse_width & 0x3F),
                    _DSI_PATTERN_ENABLE,
                    0x80,  # Pattern enable.
                    0x71,
                    0x51,
                    0x42,
                    0x12,
                    0x1E,
                    0x67,  # Select the pattern clock and HDMI output.
                )
            ),
        )
        self._write_dds_frequency(hold=True)

    def get_hpd(self):
        """Read the HDMI hot-plug detect input.

        :return: True if HPD is high.
        :rtype: bool
        """
        return bool(self._read_bits(self._main, _MAIN_HPD_STATUS, shift=7))

    @property
    def hot_plug_detected(self):
        """True when the bridge reports an HDMI hot-plug detect."""
        return self.get_hpd()

    def get_input_timing(self):
        """Read the H/V period the DSI receiver measures on its input.

        The vendor driver labels these as the input sync widths, but a locked
        receiver reports the measured periods: V matches the programmed V
        total, and H uses a finer unit (18004 for an 1800 pixel total). A zero
        H value means no MIPI video input, which is how the vendor detects a
        missing stream. Compare the values against the configured timing to
        tell a bad DSI stream from a bad HDMI output.

        :return: The ``(h, v)`` pair the receiver measures, or ``None`` when
            it reports no input.
        :rtype: tuple or None
        """
        hsync = self._read_byte(self._main, _MAIN_H_SYNC_WIDTH)
        hsync |= self._read_byte(self._main, _MAIN_H_SYNC_WIDTH + 1) << 8
        if not hsync:
            return None
        vsync = self._read_byte(self._main, _MAIN_V_SYNC_WIDTH)
        vsync |= self._read_byte(self._main, _MAIN_V_SYNC_WIDTH + 1) << 8
        return (hsync, vsync)

    def get_dds_status(self):
        """Read the vendor's DDS debug registers in the DSI bank.

        The vendor driver polls these four bytes and calls the output clock
        stable when byte 2 is ``0xD2`` and byte 1 is between ``0xD1`` and
        ``0xFE``. Values that change between reads mean the FIFO loop is still
        hunting for a frequency.

        :return: The raw values of ``0x0C`` through ``0x0F``, in order.
        :rtype: tuple
        """
        return tuple(self._read_byte(self._dsi, 0x0C + index) for index in range(4))

    def _validate(self, lanes):
        if lanes < 1 or lanes > 4:
            raise ValueError("lanes must be between 1 and 4")
        if self._width <= 0 or self._height <= 0:
            raise ValueError("width and height must be positive")
        if (
            self._hsync_front_porch < 0
            or self._hsync_back_porch < 0
            or self._vsync_front_porch < 0
            or self._vsync_back_porch < 0
        ):
            raise ValueError("porches must be non-negative")
        if self._h_total > 0xFFFF or self._v_total > 0xFFFF:
            raise ValueError("horizontal or vertical total does not fit in 16 bits")
        if self._hsync_pulse_width < 1 or self._hsync_pulse_width > 255:
            raise ValueError("hsync_pulse_width must be between 1 and 255")
        if self._vsync_pulse_width < 1 or self._vsync_pulse_width > 255:
            raise ValueError("vsync_pulse_width must be between 1 and 255")
        if self._pixel_clock_frequency <= 0:
            raise ValueError("pixel_clock_frequency must be positive")
        if self._vic < 0 or self._vic > 127:
            raise ValueError("vic must be between 0 and 127")
        if self._aspect_ratio < 0 or self._aspect_ratio > 2:
            raise ValueError("aspect_ratio must be 0, 1, or 2")

    @staticmethod
    def _write_sequence(device, sequence):
        buffer = bytearray(2)
        with device:
            for index in range(0, len(sequence), 2):
                buffer[0] = sequence[index]
                buffer[1] = sequence[index + 1]
                device.write(buffer)

    def _write_byte(self, device, register, value):
        self._write_sequence(device, bytes((register, value)))

    @staticmethod
    def _write_bits(device, register, value, *, shift=0, width=1):
        mask = ((1 << width) - 1) << shift
        buffer = bytearray(1)
        with device:
            device.write_then_readinto(bytes((register,)), buffer)
            buffer[0] = (buffer[0] & ~mask) | ((int(bool(value)) << shift) & mask)
            device.write(bytes((register, buffer[0])))

    @staticmethod
    def _read_byte(device, register):
        buffer = bytearray(1)
        with device:
            device.write_then_readinto(bytes((register,)), buffer)
        return buffer[0]

    @staticmethod
    def _read_bits(device, register, *, shift=0, width=1):
        buffer = bytearray(1)
        with device:
            device.write_then_readinto(bytes((register,)), buffer)
        return (buffer[0] >> shift) & ((1 << width) - 1)

    def _write_timing(self):
        values = bytes(
            (
                _DSI_H_SYNC,
                self._hsync_pulse_width & 0xFF,
                _DSI_V_SYNC,
                self._vsync_pulse_width & 0xFF,
                _DSI_H_ACTIVE,
                self._width & 0xFF,
                _DSI_H_ACTIVE + 1,
                (self._width >> 8) & 0xFF,
                _DSI_FIFO_BUFFER_LENGTH,
                0x0C,  # FIFO buffer length 12.
                _DSI_H_TOTAL,
                self._h_total & 0xFF,
                _DSI_H_TOTAL + 1,
                (self._h_total >> 8) & 0xFF,
                _DSI_V_TOTAL,
                self._v_total & 0xFF,
                _DSI_V_TOTAL + 1,
                (self._v_total >> 8) & 0xFF,
                _DSI_V_BACK_PORCH,
                self._vsync_back_porch & 0xFF,
                _DSI_V_BACK_PORCH + 1,
                (self._vsync_back_porch >> 8) & 0xFF,
                _DSI_V_FRONT_PORCH,
                self._vsync_front_porch & 0xFF,
                _DSI_V_FRONT_PORCH + 1,
                (self._vsync_front_porch >> 8) & 0xFF,
                _DSI_H_BACK_PORCH,
                self._hsync_back_porch & 0xFF,
                _DSI_H_BACK_PORCH + 1,
                (self._hsync_back_porch >> 8) & 0xFF,
                _DSI_H_FRONT_PORCH,
                self._hsync_front_porch & 0xFF,
                _DSI_H_FRONT_PORCH + 1,
                (self._hsync_front_porch >> 8) & 0xFF,
            )
        )
        self._write_sequence(self._dsi, values)

    def _reset_receiver(self):
        self._write_byte(self._main, _MAIN_MIPI_RESET, 0x7F)
        time.sleep(0.01)
        self._write_byte(self._main, _MAIN_MIPI_RESET, 0xFF)
        self._write_byte(self._main, _MAIN_DDS_RESET, 0xFB)
        time.sleep(0.01)
        self._write_byte(self._main, _MAIN_DDS_RESET, 0xFF)


def read_edid_timing(i2c, *, address=EDID_ADDRESS):
    """Read the preferred timing from the display's EDID EEPROM.

    :param ~busio.I2C i2c: I2C bus connected to the display's DDC pins. This
        may be a different bus than the bridge control bus.
    :param int address: EDID EEPROM address, 0x50 by default.
    :return: A dict of `LT8912B` timing keyword arguments, or ``None`` if no
        usable preferred timing was found.
    :rtype: dict or None
    """
    try:
        device = I2CDevice(i2c, address)
        data = bytearray(_EDID_BLOCK_SIZE)
        with device:
            device.write_then_readinto(bytes((0,)), data)
    except (OSError, ValueError):
        return None
    return parse_edid_timing(data)


def parse_edid_timing(data):  # noqa: PLR0911
    """Decode the preferred detailed timing from an EDID base block.

    The first 128-byte block is validated and decoded. Extension blocks and
    alternate descriptors are ignored.

    :param ~circuitpython_typing.ReadableBuffer data: Buffer containing at
        least one complete EDID base block.
    :return: A dict of `LT8912B` timing keyword arguments, or ``None`` if the
        data is not a supported EDID 1.3/1.4 preferred timing.
    :rtype: dict or None
    """
    if len(data) < _EDID_BLOCK_SIZE:
        return None
    header = (0x00, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0x00)
    if tuple(data[0:8]) != header:
        return None
    checksum = 0
    for index in range(_EDID_BLOCK_SIZE):
        checksum += data[index]
    if (
        checksum & 0xFF
        or data[_EDID_VERSION] != 1
        or data[_EDID_REVISION] < 3
        or data[_EDID_REVISION] > 4
    ):
        return None
    if not (data[_EDID_INPUT] & _EDID_DIGITAL) or not (data[_EDID_FEATURES] & _EDID_PREFERRED):
        return None

    dtd = _EDID_DTD
    clock_10khz = data[dtd] | (data[dtd + 1] << 8)
    flags = data[dtd + 17]
    if (
        not clock_10khz
        or flags & _EDID_UNSUPPORTED
        or (flags & _EDID_SYNC_TYPE) != _EDID_SYNC_TYPE
        or data[dtd + 15] != 0
        or data[dtd + 16] != 0
    ):
        return None

    width = data[dtd + 2] | ((data[dtd + 4] & 0xF0) << 4)
    h_blank = data[dtd + 3] | ((data[dtd + 4] & 0x0F) << 8)
    height = data[dtd + 5] | ((data[dtd + 7] & 0xF0) << 4)
    v_blank = data[dtd + 6] | ((data[dtd + 7] & 0x0F) << 8)
    hsync_front_porch = data[dtd + 8] | ((data[dtd + 11] & 0xC0) << 2)
    hsync_pulse_width = data[dtd + 9] | ((data[dtd + 11] & 0x30) << 4)
    vsync_front_porch = (data[dtd + 10] >> 4) | ((data[dtd + 11] & 0x0C) << 2)
    vsync_pulse_width = (data[dtd + 10] & 0x0F) | ((data[dtd + 11] & 0x03) << 4)

    if not width or not height:
        return None
    if (
        not hsync_pulse_width
        or hsync_pulse_width > 255
        or not vsync_pulse_width
        or vsync_pulse_width > 255
    ):
        return None
    # Check blanking before subtraction so malformed data cannot underflow.
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
        "hsync_positive": bool(flags & _EDID_HSYNC_POS),
        "vsync_positive": bool(flags & _EDID_VSYNC_POS),
        "vic": 0,
        "aspect_ratio": 0,
    }

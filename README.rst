Introduction
============


.. image:: https://readthedocs.org/projects/adafruit-circuitpython-lt8912b/badge/?version=latest
    :target: https://docs.circuitpython.org/projects/lt8912b/en/latest/
    :alt: Documentation Status


.. image:: https://raw.githubusercontent.com/adafruit/Adafruit_CircuitPython_Bundle/main/badges/adafruit_discord.svg
    :target: https://adafru.it/discord
    :alt: Discord


.. image:: https://github.com/adafruit/Adafruit_CircuitPython_LT8912B/workflows/Build%20CI/badge.svg
    :target: https://github.com/adafruit/Adafruit_CircuitPython_LT8912B/actions
    :alt: Build Status


.. image:: https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json
    :target: https://github.com/astral-sh/ruff
    :alt: Code Style: Ruff

CircuitPython driver for the LT8912B MIPI DSI to HDMI/DVI bridge. The bridge is
configured over I2C and then fed video through a MIPI DSI host, such as the
ESP32-P4. Pixel data is sent by the ``mipidsi`` module; the LT8912B cannot send
pixels over I2C.

The driver also includes an EDID preferred-timing decoder, so the bridge and
the DSI host can be configured to match the connected monitor.


Dependencies
=============
This driver depends on:

* `Adafruit CircuitPython <https://github.com/adafruit/circuitpython>`_
* `Bus Device <https://github.com/adafruit/Adafruit_CircuitPython_BusDevice>`_

Please ensure all dependencies are available on the CircuitPython filesystem.
This is easily achieved by downloading
`the Adafruit library and driver bundle <https://circuitpython.org/libraries>`_
or individual libraries can be installed using
`circup <https://github.com/adafruit/circup>`_.



This driver works with Adafruit's LT8912B MIPI DSI to HDMI/DVI adapter.

`Purchase one from the Adafruit shop <https://www.adafruit.com/>`_

Installing from PyPI
=====================
.. note:: This library is not available on PyPI yet. Install documentation is included
   as a standard element. Stay tuned for PyPI availability!

.. todo:: Remove the above note if PyPI version is/will be available at time of release.

On supported GNU/Linux systems like the Raspberry Pi, you can install the driver locally `from
PyPI <https://pypi.org/project/adafruit-circuitpython-lt8912b/>`_.
To install for current user:

.. code-block:: shell

    pip3 install adafruit-circuitpython-lt8912b

To install system-wide (this may be required in some cases):

.. code-block:: shell

    sudo pip3 install adafruit-circuitpython-lt8912b

To install in a virtual environment in your current project:

.. code-block:: shell

    mkdir project-name && cd project-name
    python3 -m venv .venv
    source .env/bin/activate
    pip3 install adafruit-circuitpython-lt8912b

Installing to a Connected CircuitPython Device with Circup
==========================================================

Make sure that you have ``circup`` installed in your Python environment.
Install it with the following command if necessary:

.. code-block:: shell

    pip3 install circup

With ``circup`` installed and your CircuitPython device connected use the
following command to install:

.. code-block:: shell

    circup install adafruit_lt8912b

Or the following command to update an existing version:

.. code-block:: shell

    circup update

Usage Example
=============

The ESP32-P4 has two DSI data lanes, so use an RGB888 pixel format and keep the
pixel clock within the lane bandwidth. Configure the bridge before creating the
``mipidsi.Display`` so the DSI host does not start scanout early. The
constructor asks `I2CDevice` to probe the bridge's three I2C addresses and
raises ``ValueError`` if any of them does not respond.

.. code-block:: python

    import board
    import busio
    import mipidsi
    import adafruit_lt8912b

    i2c = busio.I2C(board.SCL, board.SDA)

    lanes = 2
    bus = mipidsi.Bus(frequency=480_000_000, num_lanes=lanes)

    bridge = adafruit_lt8912b.LT8912B(
        i2c,
        width=800,
        height=480,
        hsync_pulse_width=48,
        hsync_back_porch=310,
        hsync_front_porch=112,
        vsync_pulse_width=3,
        vsync_back_porch=29,
        vsync_front_porch=13,
        pixel_clock_frequency=40_000_000,
        lanes=lanes,
    )

    panel = mipidsi.Display(
        bus,
        b"",  # No DSI panel init sequence: the LT8912B is a bridge.
        width=800,
        height=480,
        hsync_pulse_width=48,
        hsync_back_porch=310,
        hsync_front_porch=112,
        vsync_pulse_width=3,
        vsync_back_porch=29,
        vsync_front_porch=13,
        pixel_clock_frequency=40_000_000,
        color_depth=24,
    )

See ``examples/lt8912b_simpletest.py`` for a fixed-timing color-bar example,
``examples/lt8912b_720p.py`` and ``examples/lt8912b_1080p30.py`` for standard
CEA-861 modes, ``examples/lt8912b_640x480.py`` for a low-bandwidth mode, and
``examples/lt8912b_edid.py`` for one that uses the monitor's preferred EDID
timing.

Bridge Control
==============

The constructor configures the bridge, so the object is ready to use as soon
as it exists. It also resets the bridge: it pulses the ``reset`` pin when one
is given, and otherwise sends the vendor driver's software reset, because the
Raspberry Pi MIPI DSI pinout has no reset line and an unreset bridge keeps its
previous mode and test-pattern state.

``set_hdmi(enabled)`` selects HDMI signalling instead of the default DVI
signalling, and ``enable_output(enabled)`` gates the transmitter. ``get_hpd()``
and its ``hot_plug_detected`` property report the monitor's hot-plug line.

``get_input_timing()`` returns the H/V period the DSI receiver measures, or
``None`` when no MIPI video is arriving, which separates a DSI problem from an
HDMI one. ``get_dds_status()`` returns the vendor's four DDS debug bytes; a
changing value means the output clock loop is still hunting.

``seed_output_clock(hold=False)`` re-seeds the output clock from the pixel
clock after ``mipidsi`` scanout starts, which is when the FIFO loop has
something to track. Pass ``hold=True`` to pin the clock at the pixel clock
instead. ``show_test_pattern()`` draws the bridge's internal pattern from a
held clock, which isolates the HDMI transmitter from the DSI input; re-create
the object to return to pass-through video.

EDID Timing
===========

``read_edid_timing(i2c)`` reads the display at 0x50 and returns a dict of
``LT8912B`` timing keyword arguments, or ``None`` when no supported preferred
timing is found. ``examples/lt8912b_edid.py`` shows how to pass the result to
the bridge and ``mipidsi.Display``, with an 800x480 fallback. If the adapter
has a DDC switch, turn it on before reading EDID. Some monitors expose an
RTD266x programming interface at the bridge's 0x48-0x4A addresses; hold the
bridge in reset while reading EDID if those addresses conflict.

``parse_edid_timing(data)`` decodes a base block that has already been read.
Both functions support the first preferred detailed timing in EDID 1.3/1.4:
progressive digital video with separate H/V sync and no stereo or borders. The
caller must check the DSI host's bandwidth and memory limits before applying
the returned timing. ``examples/lt8912b_edid.py`` also folds the DPI clock
rounding into the horizontal back porch so the monitor's refresh rate survives
the 240/N divider.

Standard Timings
================

The ESP32-P4 DSI PHY supports up to 1.5 Gbps per lane. With two lanes and
RGB888 output (24 bits per pixel), each lane carries 12 bits per pixel, so a
960 Mbps lane rate covers pixel clocks up to 80 MHz. The 720p60 example uses
80 MHz (960 Mbps per lane) and the 1080p30 example uses the CEA 74.25 MHz
(891 Mbps per lane). 1080p60 would need 148.5 MHz, which is about 1782 Mbps per
lane and also above the fractional clock generator's ceiling. 640x480 needs
only about 320 Mbps per lane, so it is a useful check when a monitor rejects
the larger modes.

Watch the pixel clock, not just the resolution. The DSI host makes the DPI
pixel clock by dividing a fixed source, 240 MHz for the default ``mipidsi``
configuration, and ESP-IDF rounds to the nearest integer divider. Current
firmware falls back to the fractional audio PLL when that divider is more than
0.5% off, which reaches any clock up to 125 MHz exactly, so 25.175 MHz and
74.25 MHz are both available; ``mipidsi`` prints an ``APLL`` line when it takes
that path. On firmware without the fallback only 240/N clocks exist, and
standard clocks run a few percent fast or slow: 25.175 MHz becomes 24 MHz and
74.25 MHz becomes 80 MHz, which turns 59.94 Hz into 57.1 Hz and 64.6 Hz.
Monitors that validate the pixel clock or the refresh rate then show nothing or
blink. The examples either use a clock the host can generate or compensate the
blanking totals, and the LT8912B vendor presets do the same (their 720p60
preset uses 80 MHz with 1800x741 totals).

``examples/lt8912b_720p.py`` shows 1280x720 at 60 Hz. CEA-861's 74.25 MHz clock
becomes 80 MHz on the P4, so the example uses 80 MHz (240/3) with the LT8912B
vendor preset totals of 1800x741, which scans at 59.98 Hz::

    width=1280, height=720
    hsync_front_porch=408, hsync_pulse_width=32, hsync_back_porch=80
    vsync_front_porch=3, vsync_pulse_width=5, vsync_back_porch=13
    pixel_clock_frequency=80_000_000
    vic=0, aspect_ratio=2  # 16:9

``examples/lt8912b_1080p30.py`` uses CEA-861 VIC 34 exactly: 74.25 MHz,
2200x1125, 30.00 Hz and 33.75 kHz per line, which ``mipidsi`` generates with
the fractional clock generator::

    width=1920, height=1080
    hsync_front_porch=88, hsync_pulse_width=44, hsync_back_porch=148
    vsync_front_porch=4, vsync_pulse_width=5, vsync_back_porch=36
    pixel_clock_frequency=74_250_000
    hsync_positive=True, vsync_positive=True
    vic=34, aspect_ratio=2  # 16:9

``examples/lt8912b_640x480.py`` shows 640x480 at ~60 Hz. The DSI host cannot
generate the DMT 25.175 MHz pixel clock, so the example uses 26.667 MHz
(240/9) and moves the surplus lines into the vertical back porch, which keeps
DMT's horizontal timing and totals at a 59.95 Hz refresh::

    width=640, height=480
    hsync_front_porch=16, hsync_pulse_width=96, hsync_back_porch=48
    vsync_front_porch=10, vsync_pulse_width=2, vsync_back_porch=64
    pixel_clock_frequency=26_666_667
    hsync_positive=False, vsync_positive=False
    vic=0, aspect_ratio=1  # 4:3

Documentation
=============
API documentation for this library can be found on `Read the Docs <https://docs.circuitpython.org/projects/lt8912b/en/latest/>`_.

For information on building library documentation, please check out
`this guide <https://learn.adafruit.com/creating-and-sharing-a-circuitpython-library/sharing-our-docs-on-readthedocs#sphinx-5-1>`_.

Credits and License
===================

The register initialization tables are adapted from `Espressif's
esp_lcd_lt8912b driver <https://github.com/espressif/esp-bsp/tree/master/components/lcd/esp_lcd_lt8912b>`_
and Adafruit's `Arduino LT8912B library <https://github.com/adafruit/Adafruit_LT8912B>`_.
Those portions remain under the Apache License, Version 2.0. See `NOTICE` and
`LICENSES/Apache-2.0.txt`. The Python interface and EDID decoder are MIT
licensed. Dependencies retain their own licenses.

Contributing
============

Contributions are welcome! Please read our `Code of Conduct
<https://github.com/adafruit/Adafruit_CircuitPython_LT8912B/blob/HEAD/CODE_OF_CONDUCT.md>`_
before contributing to help this project stay welcoming.

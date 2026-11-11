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


Dependencies
=============
This driver depends on:

* `Adafruit CircuitPython <https://github.com/adafruit/circuitpython>`_ with
  ``mipidsi.Display.pixel_clock_frequency`` and ``low_power_blanking``, and
  ``mipidsi.Bus.minimum_frequency``, ``frequency`` and ``num_lanes``
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

``LT8912B`` is a ``mipidsi.Display``. It configures the bridge over I2C and
then starts RGB888 video on the DSI bus with the same timing. The constructor
raises ``ValueError`` if the bridge does not respond on I2C. Create the bus
with a ``minimum_frequency`` of at least 24 times the pixel clock divided by
the number of lanes. The PHY may run faster than that minimum, so the bridge
checks the rate the bus actually uses, available as ``bus.frequency``.

.. code-block:: python

    import board
    import busio
    import framebufferio
    import mipidsi
    import adafruit_lt8912b

    i2c = busio.I2C(board.SCL, board.SDA)
    bus = mipidsi.Bus(minimum_frequency=480_000_000, num_lanes=2)

    bridge = adafruit_lt8912b.LT8912B(
        bus,
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
    )
    display = framebufferio.FramebufferDisplay(bridge)

See ``examples/lt8912b_simpletest.py`` for a fixed-timing color-bar example,
``examples/lt8912b_720p.py`` and ``examples/lt8912b_1080p30.py`` for standard
CEA-861 modes, ``examples/lt8912b_640x480.py`` for a low-bandwidth mode, and
``examples/lt8912b_edid.py`` for one that uses the monitor's preferred EDID
timing.

Bridge Control
==============

The constructor resets and configures the bridge. It pulses the ``reset`` pin
when one is given and otherwise sends a software reset.

``hot_plug_detected`` is True when a monitor is connected.

EDID Timing
===========

``examples/lt8912b_edid.py`` reads the monitor's preferred timing from its
EDID EEPROM at 0x50 and passes it to ``mipidsi.Display`` and ``LT8912B``, with
an 800x480 fallback. If the adapter has a DDC switch, turn it on before reading
EDID. The example also folds the DPI clock rounding into the horizontal back
porch so the monitor's refresh rate survives the 240/N divider.

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
Those portions remain under the Apache License, Version 2.0. See `NOTICE <https://github.com/adafruit/Adafruit_CircuitPython_LT8912B/blob/main/NOTICE>` and
`LICENSES/Apache-2.0.txt <https://github.com/adafruit/Adafruit_CircuitPython_LT8912B/blob/main/LICENSES/Apache-2.0.txt>`. The Python interface is MIT licensed. Dependencies
retain their own licenses.

Contributing
============

Contributions are welcome! Please read our `Code of Conduct
<https://github.com/adafruit/Adafruit_CircuitPython_LT8912B/blob/HEAD/CODE_OF_CONDUCT.md>`_
before contributing to help this project stay welcoming.

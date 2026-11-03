Simple test
------------

Ensure your device works with this simple test.

.. literalinclude:: ../examples/lt8912b_simpletest.py
    :caption: examples/lt8912b_simpletest.py
    :linenos:

EDID timing
-----------

Read the monitor's preferred mode and fall back to 800 x 480 when needed.

.. literalinclude:: ../examples/lt8912b_edid.py
    :caption: examples/lt8912b_edid.py
    :linenos:

Standard 720p60 timing
----------------------

Use CEA-861 720p60 timings for a standard 1280x720 output.

.. literalinclude:: ../examples/lt8912b_720p.py
    :caption: examples/lt8912b_720p.py
    :linenos:

Standard 1080p30 timing
-----------------------

Use CEA-861 1080p30 timings for a standard 1920x1080 output.

.. literalinclude:: ../examples/lt8912b_1080p30.py
    :caption: examples/lt8912b_1080p30.py
    :linenos:

Standard 640x480 timing
-----------------------

Use CEA-861 VIC 1 / VESA DMT 640x480 timings for a low-bandwidth test mode.

.. literalinclude:: ../examples/lt8912b_640x480.py
    :caption: examples/lt8912b_640x480.py
    :linenos:

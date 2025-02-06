suplalite
=========

A lightweight implementation of SUPLA server and devices in Python.

Note: this project is not affiliated with SUPLA or Zamel -- this is not an "official" library.

suplalite.server
----------------

Library providing a lightweight implementation of supla-server and supla-cloud.

Provides just enough to coordinate a collection of SUPLA devices and clients on a local network.

This implementation does *not* require/provide:
 - A MySQL database
 - supla-cloud web interface
 - Logging of historical sensor data
 - Dynamic registration of devices
 - Authentication of clients

Configuration of the server is static, i.e. devices must be configured before starting the
server. Clients do not need to be registed. Any client is allowed.

See `examples/server.py` for an example.

suplalite.device
----------------

Provides functionality necessary to create a SUPLA device using Python.

Currently supports the following kinds of channel:
 * Relay/switch
 * Temperature sensor
 * Humidity sensor
 * General purpose measurement

See `examples/device.py` for an example.

suplalite
=========

A lightweight implementation of SUPLA server and devices in Python.

Install using `pip install suplalite`

Note: this project is not affiliated with SUPLA or Zamel -- this is not an "official" library.

suplalite.server
----------------

Provides a lightweight implementation of supla-server and supla-cloud.
Has just enough functionality to coordinate a set of SUPLA devices and
clients on a local network. Use over the public internet is not recommended.

This implementation does *not* require/provide:
 - A MySQL database
 - supla-cloud web interface
 - Logging of historical sensor data
 - Dynamic registration of devices
 - Authentication of clients

Configuration of the server is static, i.e. devices must be configured before starting the
server. Clients registration is not required -- any client is allowed to connect.

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

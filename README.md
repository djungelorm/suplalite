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

Configuration of the server is static, i.e. devices must be configured before starting the
server. The server listens on three ports: a plain port for devices, a TLS-secured port for
devices and clients, and an HTTPS REST API port. TLS requires a certificate and key file.

Client authentication is supported via email and password.

See `examples/server.py` for an example.

suplalite.device
----------------

Provides functionality necessary to create a SUPLA device using Python.
Supports both plain and TLS-secured connections to the server.

Currently supports the following kinds of channel:
 - Relay/switch
 - Temperature sensor
 - Humidity sensor
 - Temperature and humidity sensor
 - General purpose measurement
 - Dimmer
 - RGB dimmer
 - RGBW dimmer

See `examples/device.py` for an example.

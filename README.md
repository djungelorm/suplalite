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

Devices are taken from the static configuration and cannot be added at runtime: a
device is accepted only if its GUID is configured and its manufacturer id, product
id and channels match that configuration. The email and authentication key it
registers with are *not* checked, so anything that knows a configured GUID can
register as that device -- devices are identified, not authenticated. Client registration, in
contrast, always succeeds -- any client that can reach the port is registered and
served, and the email and password it registers with are not checked.

Both are deliberate divergences from supla-server, which validates the device
authentication key and gates client registration on a window enabled through
supla-cloud; suplalite has neither a stored key to compare against nor any such
registration state, and always reports registration as disabled. Because of this
the server should only be exposed on a trusted network.

Email and password are checked for superuser authorization, which a client needs in
order to change device configuration.

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

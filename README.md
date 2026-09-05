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

See `examples/server.py` for an example.

### Authentication

supla-server admits a new device or client during a registration window that the user
opens through supla-cloud. suplalite has no such window: everything allowed to connect
is listed in the static configuration, and registration otherwise behaves as it does in
supla-server with the window permanently closed. A peer that is not configured is
rejected with `REGISTRATION_DISABLED`, one whose credentials do not match with
`BAD_CREDENTIALS`.

**Devices** authenticate with their GUID and AuthKey, both given to
`state.add_device()`. The device must also present the channels it was configured with.

**Clients** authenticate in whichever of the SUPLA app's two sign-in modes they use:

 - *Access identifier* -- the app sends an access id and password, configured with
   `state.add_access_id()`. Both are chosen by you, so this mode needs no discovery
   step and survives the app being reinstalled.
 - *Email* -- the app sends an email address along with a GUID and AuthKey it generated
   itself, configured with `state.add_client()`. Because the app invents the GUID and
   AuthKey, they cannot be known in advance: let the client try to register once, then
   copy them out of the warning the server logs when it rejects it. They change if the
   app is reinstalled. The password field of this message is not used.

Either can be turned off with `Server(..., device_auth=False)` or `client_auth=False`,
which accepts any device that is configured and any client at all. This is reasonable
on a trusted local network and is how versions before 2.0 behaved.

A failed registration is answered and then held open for `auth_failure_delay` seconds
(2 by default) before the connection is closed, as supla-server does.

Superuser authorization is separate from registration and unchanged: a client sends the
email and password given to `Server()`, and needs to have done so before it can change
device configuration.

Two things to be aware of, both of which make the server logs sensitive:

 - Rejecting a client logs the AuthKey it sent. That is deliberate -- it is the only way
   to learn what an app generated -- but it means log files hold client credentials.
 - An `EventId.REQUEST` event handler receives whole decoded messages, registration
   messages included, so anything logging them logs credentials too.

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

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

By default a device is accepted if its GUID and channels match the configuration, and
any client at all is accepted. That is reasonable on a trusted local network, and is
what earlier versions did.

Devices and clients can instead be made to authenticate, with
`Server(..., device_auth=True, client_auth=True)`. supla-server admits a new peer during
a registration window that the user opens through supla-cloud; suplalite has no such
window, so everything allowed to connect is listed in the static configuration and
registration otherwise behaves as it does in supla-server with the window permanently
closed. A peer that is not configured is rejected with `REGISTRATION_DISABLED`, one
whose credentials do not match with `BAD_CREDENTIALS`.

**Devices** authenticate with their GUID and AuthKey, both given to `state.add_device()`.
With `device_auth=True` every configured device needs an AuthKey, and the server refuses
to start if one does not have it.

**Clients** authenticate in whichever of the SUPLA app's two sign-in modes they use:

 - *Access identifier* -- the app sends an access id and password, configured with
   `state.add_access_id()`. Both are chosen by you, so this mode needs no discovery
   step and survives the app being reinstalled.
 - *Email* -- the app sends an email address along with a GUID and AuthKey it generated
   itself, configured with `state.add_client_credentials()`. Because the app invents the
   GUID and AuthKey, they cannot be known in advance: let the client try to register
   once, then copy them out of the warning the server logs when it rejects it. They
   change if the app is reinstalled. The password field of this message is not used.

A failed registration is answered and then held open for `auth_failure_delay` seconds
(2 by default) before the connection is closed, as supla-server does. This applies
whether or not authentication is enabled, since a device can still be rejected for
presenting an unknown GUID or the wrong channels.

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

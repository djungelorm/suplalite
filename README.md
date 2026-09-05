suplalite
=========

A lightweight implementation of SUPLA server and devices in Python.

Install using `pip install suplalite`

Note: this project is not affiliated with SUPLA or Zamel. It is not an "official" library.

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

Devices and clients authenticate when you turn it on:

```python
server = Server(..., device_auth=True, client_auth=True)
```

Both settings default to `False`. The server then accepts a device whose GUID and
channels match the configuration, and accepts any client. That suits a trusted local
network.

Everything allowed to connect is listed in the static configuration. An unconfigured
peer is rejected with `REGISTRATION_DISABLED`, and a wrong credential with
`BAD_CREDENTIALS`.

#### Devices

A device authenticates with the GUID and AuthKey you give to `state.add_device()`:

```python
server.state.add_device("test", guid, authkey=authkey)
```

With `device_auth=True` every configured device needs an AuthKey. The server raises a
`ValueError` at start up when one is missing.

#### Clients

The SUPLA app signs in with an access identifier or with an email address. Configure
whichever mode the app uses.

An access identifier is an access id and a password, both chosen by you:

```python
server.state.add_access_id(1, "access-id-password")
```

Email mode sends an email address, a GUID and an AuthKey. The app generates the GUID
and AuthKey itself, so let the client register once and read them from the warning the
server logs:

```python
server.state.add_client_credentials("email@email.com", guid, authkey)
```

Reinstalling the app changes the GUID and AuthKey. The password field of this message
is unused.

#### Failed Registrations

A failed registration is answered, then held open for `auth_failure_delay` seconds
(2 by default). This applies with authentication turned off, as a device is still
rejected for an unknown GUID or the wrong channels.

Rejecting a client logs the AuthKey it sent, so you can copy it into the configuration.
An `EventId.REQUEST` event handler also receives whole decoded registration messages.
Both put client credentials in your logs.

#### Superuser Authorization

Superuser authorization is separate from registration. A client sends the email and
password you give to `Server()`, and must do so before it can change device
configuration.

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

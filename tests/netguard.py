"""Block non-loopback network access so 'offline' tests prove they need no internet."""
import socket

LOCAL = {"127.0.0.1", "::1", "localhost", "0.0.0.0", ""}  # loopback is allowed (asyncio self-pipes on Windows)


def block_network(monkeypatch):
    real_connect, real_gai = socket.socket.connect, socket.getaddrinfo

    def connect(self, address, *a, **k):
        host = address[0] if isinstance(address, tuple) else None
        if host is not None and host not in LOCAL:
            raise RuntimeError(f"network blocked in offline test: {host}")
        return real_connect(self, address, *a, **k)

    def gai(host, *a, **k):
        if host not in LOCAL and host is not None:
            raise RuntimeError(f"DNS blocked in offline test: {host}")
        return real_gai(host, *a, **k)

    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(socket, "getaddrinfo", gai)

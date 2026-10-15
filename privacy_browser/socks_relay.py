"""Relay SOCKS5 lokal tanpa autentikasi -> proxy SOCKS upstream.

- SOCKS5 + username/password: Chromium tidak mendukung SOCKS5 dengan autentikasi,
  jadi relay ini yang melakukan login ke proxy asli.
- SOCKS4: Chromium me-resolve DNS SOCKS4 di komputer lokal (DNS bocor), jadi
  browser bicara SOCKS5 ke relay dan relay meneruskannya sebagai SOCKS4a.

Browser diarahkan ke 127.0.0.1:<port acak>. DNS selalu di-resolve di sisi proxy
(hostname diteruskan apa adanya).
"""
from __future__ import annotations

import asyncio


async def _pipe(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        while True:
            data = await reader.read(65536)
            if not data:
                break
            writer.write(data)
            await writer.drain()
    except (ConnectionError, asyncio.CancelledError, OSError):
        pass
    finally:
        try:
            writer.close()
        except Exception:
            pass


async def _read_addr(reader: asyncio.StreamReader, atyp: int) -> bytes:
    if atyp == 1:
        return await reader.readexactly(4)
    if atyp == 3:
        ln = await reader.readexactly(1)
        return ln + await reader.readexactly(ln[0])
    if atyp == 4:
        return await reader.readexactly(16)
    raise ValueError(f"ATYP tidak dikenal: {atyp}")


class SocksRelay:
    def __init__(self, host: str, port: int, username: str, password: str, upstream: str = "socks5"):
        self.host, self.port_up = host, port
        self.username, self.password = username, password
        self.upstream = upstream  # "socks5" | "socks4"
        self.server: asyncio.base_events.Server | None = None
        self.port = 0

    async def start(self) -> int:
        self.server = await asyncio.start_server(self._handle, "127.0.0.1", 0)
        self.port = self.server.sockets[0].getsockname()[1]
        return self.port

    async def close(self) -> None:
        if self.server:
            self.server.close()
            try:
                await asyncio.wait_for(self.server.wait_closed(), 2)
            except Exception:
                pass
            self.server = None

    async def _handle(self, cr: asyncio.StreamReader, cw: asyncio.StreamWriter) -> None:
        uw = None
        try:
            ver, n = await cr.readexactly(2)
            await cr.readexactly(n)
            if ver != 5:
                cw.close()
                return
            cw.write(b"\x05\x00")
            await cw.drain()

            req = await cr.readexactly(4)  # VER CMD RSV ATYP
            addr = await _read_addr(cr, req[3])
            port = await cr.readexactly(2)

            ur, uw = await asyncio.wait_for(asyncio.open_connection(self.host, self.port_up), 20)
            if self.upstream == "socks4":
                reply = await self._connect_socks4(ur, uw, req, addr, port)
            else:
                reply = await self._connect_socks5(ur, uw, req, addr, port)
            cw.write(reply)
            await cw.drain()
            if reply[1] != 0:
                raise ConnectionError(f"Proxy menolak koneksi (kode {reply[1]})")

            await asyncio.gather(_pipe(cr, uw), _pipe(ur, cw))
        except Exception:
            try:
                cw.write(b"\x05\x01\x00\x01\x00\x00\x00\x00\x00\x00")
            except Exception:
                pass
            for w in (cw, uw):
                if w:
                    try:
                        w.close()
                    except Exception:
                        pass

    async def _connect_socks5(self, ur, uw, req: bytes, addr: bytes, port: bytes) -> bytes:
        uw.write(b"\x05\x02\x00\x02")
        await uw.drain()
        sel = await ur.readexactly(2)
        if sel[1] == 0x02:
            u, p = self.username.encode(), self.password.encode()
            uw.write(b"\x01" + bytes([len(u)]) + u + bytes([len(p)]) + p)
            await uw.drain()
            auth = await ur.readexactly(2)
            if auth[1] != 0:
                raise PermissionError("Autentikasi proxy ditolak")
        elif sel[1] != 0x00:
            raise PermissionError("Proxy tidak menerima metode autentikasi")

        uw.write(req + addr + port)
        await uw.drain()
        rep = await ur.readexactly(4)
        bnd = await _read_addr(ur, rep[3])
        bport = await ur.readexactly(2)
        return rep + bnd + bport

    async def _connect_socks4(self, ur, uw, req: bytes, addr: bytes, port: bytes) -> bytes:
        """Terjemahkan CONNECT SOCKS5 ke SOCKS4a (hostname di-resolve oleh proxy)."""
        fail = lambda code: b"\x05" + bytes([code]) + b"\x00\x01" + bytes(6)  # noqa: E731
        if req[1] != 0x01:
            return fail(0x07)  # hanya CONNECT
        user = self.username.encode() + b"\x00"
        if req[3] == 1:      # IPv4
            msg = b"\x04\x01" + port + addr + user
        elif req[3] == 3:    # hostname -> SOCKS4a
            msg = b"\x04\x01" + port + b"\x00\x00\x00\x01" + user + addr[1:] + b"\x00"
        else:                # IPv6 tidak didukung SOCKS4
            return fail(0x08)
        uw.write(msg)
        await uw.drain()
        rep = await ur.readexactly(8)
        if rep[1] != 0x5A:
            return fail(0x05)
        return b"\x05\x00\x00\x01" + rep[4:8] + rep[2:4]

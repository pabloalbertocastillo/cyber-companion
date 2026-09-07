"""Owner-only bounded local protocol; clients cannot publish sensor facts."""
from __future__ import annotations
import asyncio
import os
import socket
import struct
from pathlib import Path
from uuid import uuid4
from .core.validation import decode, encode
from .settings import runtime_dir

VERSION = "cc.ipc/1"


class Server:
    def __init__(self, handler):
        self.handler = handler
        self.clients = 0
        self.tasks = set()

    async def connection(self, reader, writer):
        task = asyncio.current_task()
        self.tasks.add(task)
        accepted = False
        try:
            credentials = writer.get_extra_info("socket").getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12)
            _, uid, _ = struct.unpack("3i", credentials)
            if uid != os.getuid() or self.clients >= 8:
                return
            self.clients += 1
            accepted = True
            while True:
                request_id = None
                try:
                    line = await asyncio.wait_for(reader.readline(), 5)
                    if not line:
                        break
                    request = decode(line)
                    if type(request) is not dict or set(request) != {"version", "id", "method", "params"}:
                        raise ValueError("invalid request envelope")
                    request_id = request["id"]
                    if request["version"] != VERSION or type(request_id) is not str or len(request_id) > 64:
                        raise ValueError("unsupported protocol or request ID")
                    if type(request["method"]) is not str or type(request["params"]) is not dict:
                        raise ValueError("invalid method/parameters")
                    result = await self.handler(request["method"], request["params"])
                    response = {"id": request_id, "result": result}
                except (ValueError, TypeError, KeyError) as error:
                    response = {"id": request_id, "error": {"code": "invalid_request", "message": str(error)[:200]}}
                try:
                    frame = encode(response)
                except ValueError:
                    frame = encode({"id": request_id, "error": {"code": "response_too_large", "message": "El resultado excede el límite local."}})
                writer.write(frame + b"\n")
                await asyncio.wait_for(writer.drain(), 3)
        except (OSError, asyncio.TimeoutError, ConnectionError):
            pass
        finally:
            if accepted:
                self.clients -= 1
            self.tasks.discard(task)
            writer.close()
            try:
                await writer.wait_closed()
            except OSError:
                pass

    async def close(self):
        for task in list(self.tasks):
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)


def call(method: str, params: dict | None = None, path: Path | None = None, timeout: float = 4) -> dict:
    path = path or runtime_dir() / "control.sock"
    request = {"version": VERSION, "id": uuid4().hex, "method": method, "params": params or {}}
    with socket.socket(socket.AF_UNIX) as sock:
        sock.settimeout(timeout)
        sock.connect(str(path))
        sock.sendall(encode(request) + b"\n")
        stream = sock.makefile("rb")
        response = decode(stream.readline(65537))
    if type(response) is not dict or response.get("id") != request["id"]:
        raise ValueError("invalid daemon response")
    if "error" in response:
        raise ValueError(response["error"]["message"])
    return response["result"]

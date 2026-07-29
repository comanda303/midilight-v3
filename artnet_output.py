from __future__ import annotations
import socket
import struct

def build_artnet_packet(universe: int, data: bytes) -> bytes:
    if len(data) % 2 != 0:
        data = data + b'\x00'
    return (
        b'Art-Net\x00'
        + struct.pack('<H', 0x5000)
        + struct.pack('>H', 14)
        + b'\x00'
        + b'\x00'
        + struct.pack('B', universe & 0xFF)
        + struct.pack('B', (universe >> 8) & 0x7F)
        + struct.pack('>H', len(data))
        + data
    )

class ArtNetSender:
    def __init__(self, ip: str, port: int = 6454):
        self._ip = ip
        self._port = port
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def send(self, universe: int, data: bytes) -> None:
        pkt = build_artnet_packet(universe, data)
        self._sock.sendto(pkt, (self._ip, self._port))

    def close(self) -> None:
        self._sock.close()

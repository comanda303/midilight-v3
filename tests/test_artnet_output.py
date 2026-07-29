import struct
from artnet_output import build_artnet_packet, ArtNetSender

def test_packet_header():
    pkt = build_artnet_packet(0, bytes(512))
    assert pkt[:8] == b'Art-Net\x00'

def test_packet_opcode():
    pkt = build_artnet_packet(0, bytes(512))
    opcode = struct.unpack_from('<H', pkt, 8)[0]
    assert opcode == 0x5000

def test_packet_universe():
    pkt = build_artnet_packet(3, bytes(512))
    sub_uni = pkt[14]
    assert sub_uni == 3

def test_packet_length_field():
    data = bytes(100)
    pkt = build_artnet_packet(0, data)
    length = struct.unpack_from('>H', pkt, 16)[0]
    assert length == 100

def test_packet_data():
    data = bytes([0xAB] * 10)
    pkt = build_artnet_packet(0, data)
    assert pkt[18:28] == data

def test_packet_odd_length_padded():
    data = bytes(5)
    pkt = build_artnet_packet(0, data)
    assert len(pkt) == 18 + 6  # padded to even

def test_artnet_sender_instantiation():
    sender = ArtNetSender('127.0.0.1', 6454)
    sender.close()

"""Gayatri School OS — Edge Hardware Protocol & Framing (Phase 07).

Explicit packet protocol with header framing, field bounds, and CRC-16 checksums.
Prevents unverified, malformed, or corrupt packet ingestion from hardware lines.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import Optional

# Framing constants
FRAME_HEADER = 0xAA55
CMD_PUNCH_RECORD = 0x01
CMD_HEARTBEAT = 0x02
CMD_ACK = 0x06
CMD_NAK = 0x15


def crc16_ccitt(data: bytes) -> int:
    """Calculate CRC-16-CCITT checksum."""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = (crc << 1) ^ 0x1021
            else:
                crc = crc << 1
            crc &= 0xFFFF
    return crc


@dataclass
class HardwarePunchFrame:
    user_id: str
    punch_type: str
    punch_time: str
    verification_type: str
    sequence_num: int = 1


def pack_punch_frame(frame: HardwarePunchFrame) -> bytes:
    """Encode punch frame into structured binary packet:
    [Header 2B][Cmd 1B][Seq 2B][PayloadLen 2B][Payload (UTF-8)][CRC16 2B]
    """
    payload_str = f"{frame.user_id}|{frame.punch_type}|{frame.punch_time}|{frame.verification_type}"
    payload_bytes = payload_str.encode("utf-8")
    payload_len = len(payload_bytes)

    header_cmd_seq_len = struct.pack(">H B H H", FRAME_HEADER, CMD_PUNCH_RECORD, frame.sequence_num, payload_len)
    body = header_cmd_seq_len + payload_bytes
    crc = crc16_ccitt(body)
    return body + struct.pack(">H", crc)


def unpack_punch_frame(packet: bytes) -> HardwarePunchFrame:
    """Decode binary packet, validating header, length, and CRC16 checksum."""
    if len(packet) < 9:
        raise ValueError(f"Packet too short: {len(packet)} bytes (minimum 9 required)")

    header, cmd, seq, payload_len = struct.unpack(">H B H H", packet[:7])
    if header != FRAME_HEADER:
        raise ValueError(f"Invalid frame header: 0x{header:04X} (expected 0x{FRAME_HEADER:04X})")

    if cmd != CMD_PUNCH_RECORD:
        raise ValueError(f"Unsupported command code: 0x{cmd:02X}")

    expected_len = 7 + payload_len + 2
    if len(packet) != expected_len:
        raise ValueError(f"Length mismatch: packet has {len(packet)} bytes, expected {expected_len}")

    body = packet[:-2]
    expected_crc = struct.unpack(">H", packet[-2:])[0]
    calculated_crc = crc16_ccitt(body)

    if calculated_crc != expected_crc:
        raise ValueError(f"Checksum mismatch: calculated 0x{calculated_crc:04X}, packet has 0x{expected_crc:04X}")

    payload_bytes = packet[7 : 7 + payload_len]
    payload_str = payload_bytes.decode("utf-8")
    parts = payload_str.split("|")
    if len(parts) != 4:
        raise ValueError(f"Malformed payload content: expected 4 fields, got {len(parts)}")

    return HardwarePunchFrame(
        user_id=parts[0],
        punch_type=parts[1],
        punch_time=parts[2],
        verification_type=parts[3],
        sequence_num=seq,
    )

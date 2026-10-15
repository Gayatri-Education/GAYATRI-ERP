"""Gayatri School OS — Simulated Biometric Hardware Driver (Phase 07).

Provides high-fidelity emulation of hardware biometric terminals for automated testing:
- Valid punch reading
- Device disconnection simulation
- Hardware read timeout simulation
- Checksum corruption and framing error simulation
"""

from __future__ import annotations

import collections
from typing import Deque, Optional

from central_platform.edge.drivers.base import (
    AbstractBiometricDriver,
    HardwareDeviceError,
    HardwareTimeoutError,
)
from central_platform.edge.protocol import (
    HardwarePunchFrame,
    pack_punch_frame,
    unpack_punch_frame,
)


class SimulatedBiometricDriver(AbstractBiometricDriver):
    """Simulator driver for deterministic hardware testing."""

    def __init__(self, device_id: str = "SIM-BIO-01"):
        self.device_id = device_id
        self._connected: bool = True
        self._punch_queue: Deque[HardwarePunchFrame] = collections.deque()
        self._simulate_timeout: bool = False
        self._simulate_corrupt_next: bool = False
        self._sequence_counter: int = 1

    @property
    def is_simulated(self) -> bool:
        return True

    @property
    def driver_name(self) -> str:
        return "SimulatedBiometricDriver"

    def connect(self) -> bool:
        self._connected = True
        return True

    def disconnect(self) -> None:
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected

    def trigger_disconnect(self) -> None:
        """Simulate hardware unplug / wire disconnect."""
        self._connected = False

    def trigger_timeout_once(self) -> None:
        """Simulate a single hardware read timeout."""
        self._simulate_timeout = True

    def trigger_corrupt_packet_once(self) -> None:
        """Simulate a line noise / packet checksum error."""
        self._simulate_corrupt_next = True

    def inject_punch(
        self,
        user_id: str,
        punch_type: str = "CHECK_IN",
        punch_time: str = "2026-10-15T08:30:00Z",
        verification_type: str = "FINGERPRINT",
    ) -> HardwarePunchFrame:
        """Queue a simulated sensor punch."""
        frame = HardwarePunchFrame(
            user_id=user_id,
            punch_type=punch_type,
            punch_time=punch_time,
            verification_type=verification_type,
            sequence_num=self._sequence_counter,
        )
        self._sequence_counter += 1
        self._punch_queue.append(frame)
        return frame

    def read_punch(self, timeout_sec: float = 1.0) -> Optional[HardwarePunchFrame]:
        """Read next punch, validating framing and simulating any triggered faults."""
        if not self._connected:
            raise HardwareDeviceError(f"Biometric hardware '{self.device_id}' is disconnected.")

        if self._simulate_timeout:
            self._simulate_timeout = False
            raise HardwareTimeoutError("Hardware bus read timed out.")

        if self._simulate_corrupt_next:
            self._simulate_corrupt_next = False
            # Corrupt CRC byte in encoded packet
            dummy_frame = HardwarePunchFrame("corrupt", "CHECK_IN", "time", "FINGERPRINT", 99)
            raw = bytearray(pack_punch_frame(dummy_frame))
            raw[-1] ^= 0xFF  # Invert last checksum byte
            unpack_punch_frame(bytes(raw))  # Will raise ValueError("Checksum mismatch...")

        if not self._punch_queue:
            return None

        frame = self._punch_queue.popleft()
        # Verify through binary encode-decode round-trip
        packet = pack_punch_frame(frame)
        return unpack_punch_frame(packet)

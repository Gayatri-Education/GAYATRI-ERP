"""Gayatri School OS — Abstract Biometric Hardware Driver (Phase 07)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from central_platform.edge.protocol import HardwarePunchFrame


class HardwareDeviceError(Exception):
    """Raised when physical hardware or communications failure occurs."""
    pass


class HardwareTimeoutError(HardwareDeviceError):
    """Raised when hardware I/O times out without response."""
    pass


class AbstractBiometricDriver(ABC):
    """Abstract interface for biometric hardware drivers (USB, Serial, Ethernet)."""

    @abstractmethod
    def connect(self) -> bool:
        """Establish connection to hardware unit."""
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """Close connection to hardware unit."""
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        """Check whether hardware unit is currently connected."""
        pass

    @abstractmethod
    def read_punch(self, timeout_sec: float = 1.0) -> Optional[HardwarePunchFrame]:
        """Read a single punch from the device buffer. Returns None if buffer empty."""
        pass

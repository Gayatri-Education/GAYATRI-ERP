"""GGUF binary format inspection and validation tooling (Phase 09).

Implements Master Plan Phase 09 requirement 09.6:
- Binary magic header verification (b'GGUF' / 0x46554747)
- Format version decoding
- Tensor count and metadata key-value count extraction
- File size boundary checks
- Structural header validity without requiring full llama.cpp native dependencies
"""

from __future__ import annotations

import os
import struct
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass
class GGUFValidationResult:
    """Structured inspection report for a quantized GGUF file."""
    is_valid: bool
    magic: str = ""
    version: int = 0
    tensor_count: int = 0
    metadata_kv_count: int = 0
    file_size_bytes: int = 0
    file_size_mb: float = 0.0
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class GGUFValidator:
    """Lightweight, deterministic binary validator for GGUF model artifacts."""

    GGUF_MAGIC = b"GGUF"  # 0x46554747 little-endian

    @classmethod
    def validate_file(cls, file_path: Path | str) -> GGUFValidationResult:
        """Inspect the header of a file to verify GGUF format validity."""
        p = Path(file_path)
        if not p.exists():
            return GGUFValidationResult(
                is_valid=False,
                error=f"Model file does not exist: {p}",
            )

        if not p.is_file():
            return GGUFValidationResult(
                is_valid=False,
                error=f"Target path is not a file: {p}",
            )

        file_size = p.stat().st_size
        file_size_mb = round(file_size / (1024 * 1024), 2)

        # Minimum GGUF header size is 24 bytes (magic 4, version 4, tensor_count 8, metadata_kv_count 8)
        if file_size < 24:
            return GGUFValidationResult(
                is_valid=False,
                file_size_bytes=file_size,
                file_size_mb=file_size_mb,
                error=f"File too small to be a valid GGUF container ({file_size} bytes)",
            )

        try:
            with open(p, "rb") as f:
                header = f.read(24)

            magic = header[:4]
            if magic != cls.GGUF_MAGIC:
                return GGUFValidationResult(
                    is_valid=False,
                    magic=magic.decode("latin1", errors="replace"),
                    file_size_bytes=file_size,
                    file_size_mb=file_size_mb,
                    error=f"Invalid magic bytes {magic!r}. Expected {cls.GGUF_MAGIC!r}",
                )

            version = struct.unpack("<I", header[4:8])[0]
            if version not in (1, 2, 3):
                return GGUFValidationResult(
                    is_valid=False,
                    magic="GGUF",
                    version=version,
                    file_size_bytes=file_size,
                    file_size_mb=file_size_mb,
                    error=f"Unsupported GGUF version {version}. Expected version 1, 2, or 3.",
                )

            tensor_count = struct.unpack("<Q", header[8:16])[0]
            metadata_kv_count = struct.unpack("<Q", header[16:24])[0]

            return GGUFValidationResult(
                is_valid=True,
                magic="GGUF",
                version=version,
                tensor_count=tensor_count,
                metadata_kv_count=metadata_kv_count,
                file_size_bytes=file_size,
                file_size_mb=file_size_mb,
                error=None,
            )

        except Exception as exc:
            return GGUFValidationResult(
                is_valid=False,
                file_size_bytes=file_size,
                file_size_mb=file_size_mb,
                error=f"Header decoding error: {exc}",
            )

    @classmethod
    def create_mock_gguf(
        cls,
        dest_path: Path | str,
        version: int = 3,
        tensor_count: int = 150,
        metadata_kv_count: int = 25,
    ) -> Path:
        """Utility helper to write a syntactically valid GGUF header for testing."""
        p = Path(dest_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        header = struct.pack("<4sIQQ", cls.GGUF_MAGIC, version, tensor_count, metadata_kv_count)
        with open(p, "wb") as f:
            f.write(header)
            # Add dummy padding
            f.write(b"\x00" * 1024)
        return p

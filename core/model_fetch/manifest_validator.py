"""Model Manifest Validator & Registry Integration (Phase 09 & Phase 13).

Ensures model deployment consistency by validating model_manifest.json
against runtime configuration, schema definitions, and model artifact health.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import logging
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger("gayatri.model.validator")

# Core required keys for Phase 13/16 compatibility
REQUIRED_MANIFEST_KEYS = {
    "model_id",
    "display_name",
    "provider",
    "local_path",
    "download_source",
    "quantization",
    "context_length",
    "architecture",
    "parameter_count",
    "chat_template",
    "capabilities",
    "hardware_requirements",
    "language_support",
    "version",
    "checksum",
    "license",
}

# Extended canonical keys required by Phase 09 specification
PHASE09_CANONICAL_KEYS = {
    "artifact_path",
    "format",
    "prompt_template",
    "context_window",
    "streaming",
    "resource_profile",
}


class ModelManifestValidationError(ValueError):
    """Raised when model manifest is missing, malformed, or inconsistent."""
    pass


def load_and_validate_manifest(manifest_path: Path | str | None = None) -> dict[str, Any]:
    """Load model_manifest.json and validate required keys and consistency.

    Supports both original schema and Phase 09 unified canonical fields.
    """
    if manifest_path is None:
        manifest_path = Path("model_manifest.json")
    else:
        manifest_path = Path(manifest_path)

    if not manifest_path.exists():
        raise ModelManifestValidationError(f"Model manifest file not found at '{manifest_path}'.")

    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as e:
        raise ModelManifestValidationError(f"Failed to parse model manifest JSON: {e}")

    # Validate baseline required keys
    missing = REQUIRED_MANIFEST_KEYS - set(data.keys())
    if missing:
        raise ModelManifestValidationError(f"Model manifest is missing required keys: {missing}")

    # Validate context length / window
    ctx_len = data.get("context_length") or data.get("context_window")
    if not isinstance(ctx_len, int) or ctx_len <= 0:
        raise ModelManifestValidationError(f"Invalid context_length in manifest: {data.get('context_length')}")

    # Normalize canonical alias fields if absent
    if "artifact_path" not in data and "local_path" in data:
        data["artifact_path"] = data["local_path"]
    if "prompt_template" not in data and "chat_template" in data:
        data["prompt_template"] = data["chat_template"]
    if "context_window" not in data and "context_length" in data:
        data["context_window"] = data["context_length"]
    if "resource_profile" not in data and "hardware_requirements" in data:
        data["resource_profile"] = data["hardware_requirements"]
    if "format" not in data:
        data["format"] = "gguf"
    if "streaming" not in data:
        data["streaming"] = True

    logger.info(f"Model manifest validated successfully: {data['model_id']} ({data['architecture']})")
    return data


def get_active_manifest() -> dict[str, Any]:
    """Return the active model manifest parsed from root or config location."""
    from core.config import BASE_DIR
    candidates = [
        Path("model_manifest.json"),
        BASE_DIR / "model_manifest.json",
    ]
    for p in candidates:
        if p.exists():
            return load_and_validate_manifest(p)
    return load_and_validate_manifest()


def verify_model_checksum(file_path: Path | str, expected_sha256: str) -> bool:
    """Verify SHA-256 checksum of a model file."""
    p = Path(file_path)
    if not p.is_file():
        return False
    hasher = hashlib.sha256()
    with open(p, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest().lower() == expected_sha256.lower()


@dataclass
class ModelIntegrityResult:
    """Structured result of model manifest artifact integrity verification (Section 11 / P0-02)."""
    model_id: str
    model_path: str
    expected_sha256: str
    actual_sha256: str
    size: int
    format: str
    valid: bool
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "MODEL_ID": self.model_id,
            "MODEL_PATH": self.model_path,
            "EXPECTED_SHA256": self.expected_sha256,
            "ACTUAL_SHA256": self.actual_sha256,
            "SIZE": self.size,
            "FORMAT": self.format,
            "VALID": self.valid,
            "ERROR": self.error,
        }

    def format_cli(self) -> str:
        lines = [
            f"MODEL_ID: {self.model_id}",
            f"MODEL_PATH: {self.model_path}",
            f"EXPECTED_SHA256: {self.expected_sha256}",
            f"ACTUAL_SHA256: {self.actual_sha256}",
            f"SIZE: {self.size}",
            f"FORMAT: {self.format}",
            f"VALID: {self.valid}",
        ]
        if self.error:
            lines.append(f"ERROR: {self.error}")
        return "\n".join(lines)


_MANIFEST_CHECKSUM_CACHE: dict[tuple[str, float, int], str] = {}


def verify_model_manifest(
    manifest_path: Path | str | None = None,
    model_path: Path | str | None = None,
    use_cache: bool = True,
) -> ModelIntegrityResult:
    """Verify integrity of the local model artifact against model_manifest.json.

    Returns ModelIntegrityResult containing MODEL_ID, MODEL_PATH, EXPECTED_SHA256,
    ACTUAL_SHA256, SIZE, FORMAT, and VALID status (Section 11 / P0-02).
    """
    try:
        manifest = load_and_validate_manifest(manifest_path) if manifest_path else get_active_manifest()
    except Exception as exc:
        return ModelIntegrityResult(
            model_id="unknown",
            model_path=str(model_path or ""),
            expected_sha256="",
            actual_sha256="",
            size=0,
            format="gguf",
            valid=False,
            error=f"Failed to load manifest: {exc}",
        )

    model_id = str(manifest.get("model_id", "unknown"))
    expected_sha256 = str(manifest.get("checksum") or "").strip().lower()
    fmt = str(manifest.get("format", "gguf"))

    # Resolve target model artifact path
    resolved_path: Path | None = None
    if model_path is not None:
        p = Path(model_path)
        if not p.is_absolute():
            from core.config import BASE_DIR
            if (BASE_DIR / p).exists():
                resolved_path = (BASE_DIR / p).resolve()
            elif p.exists():
                resolved_path = p.resolve()
            else:
                resolved_path = (BASE_DIR / p).resolve()
        else:
            resolved_path = p.resolve()
    else:
        # Check active model path from core.config
        try:
            from core.config import get_active_model_path, BASE_DIR
            active_p = get_active_model_path()
            if active_p.exists():
                resolved_path = active_p.resolve()
            else:
                # Fallback to local_path / artifact_path in manifest
                manifest_local = manifest.get("artifact_path") or manifest.get("local_path")
                if manifest_local:
                    manifest_p = Path(manifest_local)
                    if (BASE_DIR / manifest_p).exists():
                        resolved_path = (BASE_DIR / manifest_p).resolve()
                    else:
                        resolved_path = (BASE_DIR / manifest_p).resolve()
                else:
                    resolved_path = active_p.resolve()
        except Exception:
            resolved_path = Path("models/qwen2.5-0.5b-instruct-q4_k_m.gguf").resolve()

    if resolved_path is None or not resolved_path.is_file():
        return ModelIntegrityResult(
            model_id=model_id,
            model_path=str(resolved_path or model_path or ""),
            expected_sha256=expected_sha256,
            actual_sha256="",
            size=0,
            format=fmt,
            valid=False,
            error=f"Model artifact file not found at '{resolved_path}'.",
        )

    actual_size = resolved_path.stat().st_size
    if actual_size == 0:
        return ModelIntegrityResult(
            model_id=model_id,
            model_path=str(resolved_path),
            expected_sha256=expected_sha256,
            actual_sha256="",
            size=0,
            format=fmt,
            valid=False,
            error=f"Model artifact file at '{resolved_path}' is empty (0 bytes).",
        )

    if not expected_sha256:
        return ModelIntegrityResult(
            model_id=model_id,
            model_path=str(resolved_path),
            expected_sha256="",
            actual_sha256="",
            size=actual_size,
            format=fmt,
            valid=False,
            error="Manifest does not define an authoritative checksum.",
        )

    # Compute or retrieve cached SHA-256
    cache_key = (str(resolved_path), resolved_path.stat().st_mtime, actual_size)
    if use_cache and cache_key in _MANIFEST_CHECKSUM_CACHE:
        actual_sha256 = _MANIFEST_CHECKSUM_CACHE[cache_key]
    else:
        hasher = hashlib.sha256()
        with open(resolved_path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        actual_sha256 = hasher.hexdigest().lower()
        if use_cache:
            _MANIFEST_CHECKSUM_CACHE[cache_key] = actual_sha256

    is_valid = (actual_sha256 == expected_sha256)
    err = None if is_valid else f"Checksum mismatch: expected '{expected_sha256}', got '{actual_sha256}'"

    return ModelIntegrityResult(
        model_id=model_id,
        model_path=str(resolved_path),
        expected_sha256=expected_sha256,
        actual_sha256=actual_sha256,
        size=actual_size,
        format=fmt,
        valid=is_valid,
        error=err,
    )


if __name__ == "__main__":
    manifest_arg = sys.argv[1] if len(sys.argv) > 1 else None
    model_arg = sys.argv[2] if len(sys.argv) > 2 else None
    try:
        res = verify_model_manifest(manifest_arg, model_arg)
        print(res.format_cli())
        sys.exit(0 if res.valid else 1)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(2)


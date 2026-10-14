"""Dataset validation, contamination detection, SHA-256 provenance, and decontamination tooling (Phase 09).

Implements Master Plan Phase 09 requirements (QA-013, QA-014):
- JSONL parsing integrity
- Required field validation (messages list with system/user/assistant roles)
- Empty or truncated record detection
- Exact duplicate detection
- Train/Validation prompt leakage / contamination detection
- Automated split decontamination
- Cryptographic SHA-256 checksum computation
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger("gayatri.training.dataset_validator")


@dataclass
class DatasetValidationReport:
    """Comprehensive validation metrics for a single or paired dataset split."""
    is_valid: bool
    total_examples: int = 0
    valid_examples: int = 0
    corrupt_lines: int = 0
    duplicate_examples: int = 0
    empty_records: int = 0
    sha256_checksum: str = ""
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    prompt_leakage_count: int = 0
    contaminated_prompts: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class DatasetValidator:
    """Rigorous validator and decontaminator for Gayatri SLM training datasets."""

    VALID_ROLES: Set[str] = {"system", "user", "assistant"}

    @classmethod
    def compute_sha256(cls, file_path: Path | str) -> str:
        """Compute cryptographic SHA-256 hash of a file for provenance verification."""
        p = Path(file_path)
        if not p.is_file():
            return ""
        hasher = hashlib.sha256()
        with open(p, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        return hasher.hexdigest()

    @classmethod
    def validate_split(cls, file_path: Path | str) -> DatasetValidationReport:
        """Validate a single JSONL dataset split for structural and schema integrity."""
        p = Path(file_path)
        if not p.exists():
            return DatasetValidationReport(
                is_valid=False,
                errors=[f"Dataset file does not exist: {p}"],
            )

        total = 0
        valid = 0
        corrupt = 0
        empty = 0
        duplicates = 0
        errors: List[str] = []
        warnings: List[str] = []
        seen_prompts: Set[str] = set()

        sha256 = cls.compute_sha256(p)

        with open(p, "r", encoding="utf-8") as f:
            for line_no, raw_line in enumerate(f, start=1):
                total += 1
                line = raw_line.strip()
                if not line:
                    empty += 1
                    errors.append(f"Line {line_no}: Empty line encountered.")
                    continue

                try:
                    record = json.loads(line)
                except json.JSONDecodeError as exc:
                    corrupt += 1
                    errors.append(f"Line {line_no}: JSON decode error ({exc}).")
                    continue

                if not isinstance(record, dict) or "messages" not in record:
                    corrupt += 1
                    errors.append(f"Line {line_no}: Missing required top-level key 'messages'.")
                    continue

                messages = record["messages"]
                if not isinstance(messages, list) or len(messages) < 2:
                    corrupt += 1
                    errors.append(f"Line {line_no}: 'messages' must be a list containing at least 2 entries (user & assistant).")
                    continue

                # Verify each message turn
                turn_valid = True
                prompt_key_parts = []
                for turn_no, turn in enumerate(messages):
                    if not isinstance(turn, dict) or "role" not in turn or "content" not in turn:
                        turn_valid = False
                        errors.append(f"Line {line_no}, turn {turn_no}: Malformed turn missing 'role' or 'content'.")
                        break
                    role = turn["role"]
                    content = str(turn.get("content", "")).strip()
                    if role not in cls.VALID_ROLES:
                        turn_valid = False
                        errors.append(f"Line {line_no}, turn {turn_no}: Invalid role '{role}'. Expected one of {cls.VALID_ROLES}.")
                        break
                    if not content:
                        turn_valid = False
                        errors.append(f"Line {line_no}, turn {turn_no}: Empty content for role '{role}'.")
                        break
                    if role in ("system", "user"):
                        prompt_key_parts.append(f"{role}:{content}")

                if not turn_valid:
                    corrupt += 1
                    continue

                # Check duplicate prompt
                prompt_sig = "|".join(prompt_key_parts)
                if prompt_sig in seen_prompts:
                    duplicates += 1
                    warnings.append(f"Line {line_no}: Duplicate prompt detected.")
                else:
                    seen_prompts.add(prompt_sig)

                valid += 1

        is_valid = (corrupt == 0 and empty == 0 and valid > 0)
        return DatasetValidationReport(
            is_valid=is_valid,
            total_examples=total,
            valid_examples=valid,
            corrupt_lines=corrupt,
            empty_records=empty,
            duplicate_examples=duplicates,
            sha256_checksum=sha256,
            errors=errors,
            warnings=warnings,
        )

    @classmethod
    def check_contamination(
        cls, train_path: Path | str, val_path: Path | str
    ) -> Tuple[int, List[str]]:
        """Identify prompt overlap between training and validation datasets.
        
        Returns:
            Tuple of (contamination_count, list_of_contaminated_prompts).
        """
        train_prompts: Set[str] = set()
        p_train = Path(train_path)
        if p_train.exists():
            with open(p_train, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                        msgs = rec.get("messages", [])
                        prompt_parts = [f"{m.get('role')}:{m.get('content', '').strip()}" for m in msgs if m.get("role") in ("system", "user")]
                        if prompt_parts:
                            train_prompts.add("|".join(prompt_parts))
                    except Exception:
                        pass

        contaminated: List[str] = []
        p_val = Path(val_path)
        if p_val.exists():
            with open(p_val, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                        msgs = rec.get("messages", [])
                        prompt_parts = [f"{m.get('role')}:{m.get('content', '').strip()}" for m in msgs if m.get("role") in ("system", "user")]
                        sig = "|".join(prompt_parts)
                        if sig in train_prompts:
                            contaminated.append(sig)
                    except Exception:
                        pass

        return len(contaminated), contaminated

    @classmethod
    def decontaminate_splits(
        cls,
        train_path: Path | str,
        val_path: Path | str,
        clean_val_path: Path | str,
    ) -> int:
        """Filter out contaminated examples from the validation split, writing a sanitized file.
        
        Returns:
            Number of contaminated examples pruned.
        """
        train_prompts: Set[str] = set()
        p_train = Path(train_path)
        with open(p_train, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                    msgs = rec.get("messages", [])
                    prompt_parts = [f"{m.get('role')}:{m.get('content', '').strip()}" for m in msgs if m.get("role") in ("system", "user")]
                    if prompt_parts:
                        train_prompts.add("|".join(prompt_parts))
                except Exception:
                    pass

        p_val = Path(val_path)
        p_clean = Path(clean_val_path)
        pruned_count = 0

        with open(p_val, "r", encoding="utf-8") as f_in, open(p_clean, "w", encoding="utf-8") as f_out:
            for line in f_in:
                line_str = line.strip()
                if not line_str:
                    continue
                try:
                    rec = json.loads(line_str)
                    msgs = rec.get("messages", [])
                    prompt_parts = [f"{m.get('role')}:{m.get('content', '').strip()}" for m in msgs if m.get("role") in ("system", "user")]
                    sig = "|".join(prompt_parts)
                    if sig in train_prompts:
                        pruned_count += 1
                        continue
                    f_out.write(line_str + "\n")
                except Exception:
                    f_out.write(line_str + "\n")

        return pruned_count

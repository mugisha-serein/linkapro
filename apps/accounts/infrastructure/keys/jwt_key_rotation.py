from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


@dataclass(slots=True)
class JWTKeyRotationManager:
    """
    File-backed RSA key rotation helper.

    Infrastructure-only:
    - manages cryptographic key material on disk
    - maintains version metadata
    - does NOT participate in authentication logic
    """

    keys_dir: Path | None = None
    current_private_key_name: str = "jwt_private.pem"
    current_public_key_name: str = "jwt_public.pem"
    metadata_filename: str = "jwt_key_versions.json"
    key_size: int = 4096

    def __post_init__(self) -> None:
        self.keys_dir = self.keys_dir or self._default_keys_dir()
        self.keys_dir.mkdir(parents=True, exist_ok=True)

    # -------------------------
    # PUBLIC API
    # -------------------------
    def generate_key_pair(self, version: int | None = None) -> dict[str, Any]:
        current_version = self.get_current_version()
        new_version = version if version is not None else current_version + 1

        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=self.key_size,
        )
        public_key = private_key.public_key()

        private_bytes = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )

        public_bytes = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )

        # atomic write
        private_path = self._atomic_write(self._private_version_path(new_version), private_bytes)
        public_path = self._atomic_write(self._public_version_path(new_version), public_bytes)

        # update metadata safely
        self._update_metadata(new_version)

        # update current links (no silent fallback)
        self._update_current_link(self.current_private_key_name, private_path)
        self._update_current_link(self.current_public_key_name, public_path)

        return {
            "version": new_version,
            "status": "generated",
        }

    def rotate(self, keep_versions: int = 2) -> dict[str, Any]:
        """
        Rotation is NOT transactional across filesystem,
        but follows strict order:
        generate → persist → metadata → cleanup
        """
        result = self.generate_key_pair()
        self.cleanup_old_keys(keep_versions=keep_versions)
        return result

    def cleanup_old_keys(self, keep_versions: int = 2) -> dict[str, list[int]]:
        versions = sorted(self._discover_versions())
        keep = set(versions[-keep_versions:]) if keep_versions > 0 else set()

        removed: list[int] = []

        for version in versions:
            if version in keep:
                continue

            self._safe_delete(self._private_version_path(version))
            self._safe_delete(self._public_version_path(version))
            removed.append(version)

        metadata = self._read_metadata()
        metadata["valid_versions"] = sorted(keep)

        if keep:
            metadata["current_version"] = max(keep)

        self._write_metadata_atomic(metadata)

        return {"removed_versions": removed, "kept_versions": sorted(keep)}

    def get_current_version(self) -> int:
        metadata = self._read_metadata()

        current_version = metadata.get("current_version")
        if isinstance(current_version, int):
            return current_version

        versions = self._discover_versions()
        return max(versions) if versions else 0

    def get_all_valid_public_keys(self) -> dict[int, str]:
        metadata = self._read_metadata()
        valid_versions = metadata.get("valid_versions") or self._discover_versions()

        result: dict[int, str] = {}

        for version in sorted(set(valid_versions)):
            path = self._public_version_path(version)
            if path.exists():
                result[version] = path.read_text(encoding="utf-8")

        return result

    # -------------------------
    # INTERNAL SAFETY LAYER
    # -------------------------
    def _atomic_write(self, path: Path, data: bytes) -> Path:
        tmp_path = path.with_suffix(".tmp")
        tmp_path.write_bytes(data)
        os.replace(tmp_path, path)  # atomic on most OS
        return path

    def _safe_delete(self, path: Path) -> None:
        if path.exists():
            path.unlink()

    def _write_metadata_atomic(self, metadata: dict[str, Any]) -> None:
        path = self._metadata_path()
        tmp_path = path.with_suffix(".tmp")

        tmp_path.write_text(
            json.dumps(metadata, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        os.replace(tmp_path, path)

    def _update_metadata(self, new_version: int) -> None:
        metadata = self._read_metadata()

        metadata["current_version"] = new_version

        valid = set(metadata.get("valid_versions", []))
        valid.add(new_version)
        metadata["valid_versions"] = sorted(valid)

        history = metadata.get("history", [])
        history.append(new_version)
        metadata["history"] = history[-10:]  # bounded history

        self._write_metadata_atomic(metadata)

    def _update_current_link(self, link_name: str, target_path: Path) -> None:
        link_path = self.keys_dir / link_name

        if link_path.exists() or link_path.is_symlink():
            link_path.unlink()

        # NO silent fallback (security decision)
        os.symlink(target_path.name, link_path)

    # -------------------------
    # DISCOVERY
    # -------------------------
    def _discover_versions(self) -> list[int]:
        versions: set[int] = set()

        for path in self.keys_dir.glob("jwt_private_v*.pem"):
            v = self._extract_version(path.name)
            if v is not None:
                versions.add(v)

        for path in self.keys_dir.glob("jwt_public_v*.pem"):
            v = self._extract_version(path.name)
            if v is not None:
                versions.add(v)

        metadata = self._read_metadata()

        for v in metadata.get("valid_versions", []):
            if isinstance(v, int):
                versions.add(v)

        if isinstance(metadata.get("current_version"), int):
            versions.add(metadata["current_version"])

        return sorted(versions)

    def _extract_version(self, filename: str) -> int | None:
        if filename.startswith("jwt_private_v"):
            prefix = "jwt_private_v"
        elif filename.startswith("jwt_public_v"):
            prefix = "jwt_public_v"
        else:
            return None

        try:
            return int(filename.removeprefix(prefix).removesuffix(".pem"))
        except ValueError:
            return None

    # -------------------------
    # METADATA
    # -------------------------
    def _metadata_path(self) -> Path:
        return self.keys_dir / self.metadata_filename

    def _read_metadata(self) -> dict[str, Any]:
        path = self._metadata_path()

        if not path.exists():
            return {"current_version": 0, "valid_versions": [], "history": []}

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {"current_version": 0, "valid_versions": [], "history": []}

        return data if isinstance(data, dict) else {}

    # -------------------------
    # PATHS
    # -------------------------
    def _private_version_path(self, version: int) -> Path:
        return self.keys_dir / f"jwt_private_v{version}.pem"

    def _public_version_path(self, version: int) -> Path:
        return self.keys_dir / f"jwt_public_v{version}.pem"

    def _default_keys_dir(self) -> Path:
        return Path(__file__).resolve().parents[4] / "keys"
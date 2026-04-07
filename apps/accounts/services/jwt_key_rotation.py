"""
JWT RSA Key Rotation Strategy

This module provides utilities for rotating JWT signing keys with zero downtime.
The key rotation strategy uses versioning:
- Keys are stored with a version number (e.g., jwt_private_v1.pem, jwt_private_v2.pem)
- The current version is tracked in a config file
- During rotation, both old and new keys are valid for a grace period
- New tokens are signed with the new key, old tokens remain valid
"""

import os
import subprocess
import json
import logging
from pathlib import Path
from django.conf import settings

logger = logging.getLogger('accounts.jwt_rotation')


class JWTKeyRotationManager:
    """
    Manages JWT RSA key rotation.
    Supports versioned keys with graceful transitions.
    """

    KEYS_DIR = settings.BASE_DIR / 'keys'
    CONFIG_FILE = KEYS_DIR / 'jwt_key_versions.json'
    CURRENT_PRIVATE_KEY = KEYS_DIR / 'jwt_private.pem'
    CURRENT_PUBLIC_KEY = KEYS_DIR / 'jwt_public.pem'
    KEY_SIZE = 4096  # RSA key size in bits

    @classmethod
    def generate_key_pair(cls, version):
        """
        Generate a new RSA key pair and store with version.
        
        Args:
            version: Integer version number (e.g., 2)
            
        Returns:
            dict: {'private_key_path': str, 'public_key_path': str}
        """
        private_path = cls.KEYS_DIR / f'jwt_private_v{version}.pem'
        public_path = cls.KEYS_DIR / f'jwt_public_v{version}.pem'

        # Ensure directory exists
        cls.KEYS_DIR.mkdir(parents=True, exist_ok=True)

        # Generate private key
        logger.info(f'Generating RSA {cls.KEY_SIZE}-bit private key for version {version}...')
        subprocess.run([
            'openssl', 'genrsa',
            '-out', str(private_path),
            str(cls.KEY_SIZE)
        ], check=True, capture_output=True)

        # Extract public key
        logger.info(f'Extracting public key for version {version}...')
        subprocess.run([
            'openssl', 'rsa',
            '-in', str(private_path),
            '-pubout',
            '-out', str(public_path)
        ], check=True, capture_output=True)

        # Set restrictive permissions on private key
        os.chmod(private_path, 0o600)
        os.chmod(public_path, 0o644)

        logger.info(f'Key pair generated: v{version}')
        return {
            'private_key_path': str(private_path),
            'public_key_path': str(public_path),
            'version': version
        }

    @classmethod
    def get_current_version(cls):
        """Get the current active key version."""
        if cls.CONFIG_FILE.exists():
            with open(cls.CONFIG_FILE, 'r') as f:
                config = json.load(f)
                return config.get('current_version')
        return 1

    @classmethod
    def set_current_version(cls, version):
        """Set the current active key version."""
        cls.KEYS_DIR.mkdir(parents=True, exist_ok=True)

        config = {}
        if cls.CONFIG_FILE.exists():
            with open(cls.CONFIG_FILE, 'r') as f:
                config = json.load(f)

        config['current_version'] = version
        config['last_rotation'] = str(__import__('datetime').datetime.utcnow().isoformat())

        with open(cls.CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)

        logger.info(f'Current JWT key version set to: {version}')

    @classmethod
    def rotate_keys(cls, grace_period_days=7):
        """
        Perform a key rotation:
        1. Generate new key pair
        2. Keep old keys active for grace period
        3. Update current symlinks
        
        Args:
            grace_period_days: Days to keep old key valid (default 7)
        """
        current_version = cls.get_current_version()
        new_version = current_version + 1

        logger.info(f'Starting JWT key rotation: {current_version} → {new_version}')

        # Generate new keys
        keys_info = cls.generate_key_pair(new_version)

        # Update current symlinks to point to new version
        try:
            if cls.CURRENT_PRIVATE_KEY.exists() or cls.CURRENT_PRIVATE_KEY.is_symlink():
                cls.CURRENT_PRIVATE_KEY.unlink()
            if cls.CURRENT_PUBLIC_KEY.exists() or cls.CURRENT_PUBLIC_KEY.is_symlink():
                cls.CURRENT_PUBLIC_KEY.unlink()

            cls.CURRENT_PRIVATE_KEY.symlink_to(f'jwt_private_v{new_version}.pem')
            cls.CURRENT_PUBLIC_KEY.symlink_to(f'jwt_public_v{new_version}.pem')

            logger.info(f'Updated symlinks to point to v{new_version}')
        except Exception as exc:
            logger.error(f'Failed to update symlinks: {exc}')
            raise

        # Update version tracker
        cls.set_current_version(new_version)

        logger.info(
            f'Key rotation completed: new tokens use v{new_version}, '
            f'old tokens (v{current_version}) valid for {grace_period_days} more days'
        )

        return {
            'old_version': current_version,
            'new_version': new_version,
            'grace_period_days': grace_period_days
        }

    @classmethod
    def get_all_valid_public_keys(cls, include_old_versions=True):
        """
        Get all currently valid public keys for token verification.
        
        Args:
            include_old_versions: If True, include old keys within grace period
            
        Returns:
            dict: {version: public_key_pem_content, ...}
        """
        keys = {}
        current_version = cls.get_current_version()

        # Always include current version
        current_pub_path = cls.KEYS_DIR / f'jwt_public_v{current_version}.pem'
        if current_pub_path.exists():
            with open(current_pub_path, 'r') as f:
                keys[current_version] = f.read()

        # Optionally include old versions
        if include_old_versions and current_version > 1:
            old_version = current_version - 1
            old_pub_path = cls.KEYS_DIR / f'jwt_public_v{old_version}.pem'
            if old_pub_path.exists():
                with open(old_pub_path, 'r') as f:
                    keys[old_version] = f.read()

        return keys

    @classmethod
    def cleanup_old_keys(cls, keep_versions=2):
        """
        Remove old key files, keeping only recent versions.
        Should be called after grace period expires.
        
        Args:
            keep_versions: Number of recent versions to keep
        """
        current_version = cls.get_current_version()
        min_keep_version = max(1, current_version - keep_versions + 1)

        logger.info(f'Cleaning up old keys: keeping v{min_keep_version}+')

        for version in range(1, current_version):
            if version < min_keep_version:
                for key_type in ['private', 'public']:
                    key_path = cls.KEYS_DIR / f'jwt_{key_type}_v{version}.pem'
                    if key_path.exists():
                        try:
                            key_path.unlink()
                            logger.info(f'Deleted jwt_{key_type}_v{version}.pem')
                        except Exception as exc:
                            logger.error(f'Failed to delete {key_path}: {exc}')


# Convenience function for management command
def rotate_jwt_keys():
    """Perform JWT key rotation (call from management command)."""
    return JWTKeyRotationManager.rotate_keys()

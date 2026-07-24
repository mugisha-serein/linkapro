# Vault Deployment Layout

This directory contains the deployment image wrapper and non-secret runtime layout for LinkaPro Vault.

- `Dockerfile`: pinned official Vault image wrapper.
- `config/vault.hcl`: Vault server configuration with Raft storage, TCP listener, and TLS file paths.
- `scripts/entrypoint.sh`: container entrypoint that starts Vault server with the committed config.

Runtime-only paths referenced by the config:

- `/vault/data`: Raft storage data directory.
- `/vault/tls/tls.crt`: TLS certificate.
- `/vault/tls/tls.key`: TLS private key.
- `/vault/tls/ca.crt`: TLS CA certificate.

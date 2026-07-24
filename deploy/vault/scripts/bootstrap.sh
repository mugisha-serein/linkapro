#!/usr/bin/env bash
set -euo pipefail

TRANSIT_MOUNT="transit"
TRANSIT_KEY="linkapro-payments-kek"
APPROLE_MOUNT="approle"
ROLE_NAME="payments-app"
POLICY_NAME="linkapro-encryption"

require_env() {
  local name="$1"
  if [[ -z "${!name:-}" ]]; then
    echo "Missing required environment variable: ${name}" >&2
    exit 1
  fi
}

require_command() {
  local name="$1"
  if ! command -v "${name}" >/dev/null 2>&1; then
    echo "Missing required command: ${name}" >&2
    exit 1
  fi
}

require_env "VAULT_ADDR"
require_env "VAULT_TOKEN"
require_command "vault"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
POLICY_FILE="${SCRIPT_DIR}/../policies/${POLICY_NAME}.hcl"

if [[ ! -f "${POLICY_FILE}" ]]; then
  echo "Policy file not found: ${POLICY_FILE}" >&2
  exit 1
fi

echo "Bootstrapping Vault encryption prerequisites at ${VAULT_ADDR}"
echo "The privileged bootstrap token is required but will not be printed."

SECRETS_JSON="$(vault secrets list -format=json)"
if grep -q "\"${TRANSIT_MOUNT}/\"" <<<"${SECRETS_JSON}"; then
  echo "Transit secrets engine already enabled at ${TRANSIT_MOUNT}/"
else
  vault secrets enable -path="${TRANSIT_MOUNT}" transit
fi

if vault read -format=json "${TRANSIT_MOUNT}/keys/${TRANSIT_KEY}" >/dev/null 2>&1; then
  echo "Transit key ${TRANSIT_KEY} already exists"
else
  vault write -f "${TRANSIT_MOUNT}/keys/${TRANSIT_KEY}"
fi

AUTH_JSON="$(vault auth list -format=json)"
if grep -q "\"auth/${APPROLE_MOUNT}/\"" <<<"${AUTH_JSON}"; then
  echo "AppRole auth already enabled at auth/${APPROLE_MOUNT}/"
else
  vault auth enable "${APPROLE_MOUNT}"
fi

vault policy write "${POLICY_NAME}" "${POLICY_FILE}"

vault write "auth/${APPROLE_MOUNT}/role/${ROLE_NAME}" \
  token_policies="${POLICY_NAME}" \
  token_ttl="15m" \
  token_max_ttl="1h" \
  secret_id_ttl="24h" \
  secret_id_num_uses="1"

ROLE_ID="$(vault read -field=role_id "auth/${APPROLE_MOUNT}/role/${ROLE_NAME}/role-id")"
SECRET_ID="$(vault write -f -field=secret_id "auth/${APPROLE_MOUNT}/role/${ROLE_NAME}/secret-id")"

echo "Role ID:"
echo "${ROLE_ID}"
echo
echo "Secret ID generated. Store it in the deployment secret manager immediately."
echo "It is shown once below and is not written to any repo file:"
echo "${SECRET_ID}"

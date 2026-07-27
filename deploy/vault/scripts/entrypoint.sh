#!/bin/sh
set -eu

exec vault server -config=/vault/config/vault.hcl "$@"

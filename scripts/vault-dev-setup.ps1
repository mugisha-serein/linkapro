$env:VAULT_ADDR = "http://127.0.0.1:8200"

vault secrets enable transit
vault write -f transit/keys/linkapro-payments-kek

vault auth enable approle
vault policy write payments-policy payments-policy.hcl
vault write auth/approle/role/payments-app `
    token_policies="payments-policy" `
    token_ttl=1h `
    token_max_ttl=4h

vault read auth/approle/role/payments-app/role-id
vault write -f auth/approle/role/payments-app/secret-id
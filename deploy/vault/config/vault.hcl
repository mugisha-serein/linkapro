storage "raft" {
  path    = "/vault/data"
  node_id = "linkapro-vault-1"
}

listener "tcp" {
  address            = "0.0.0.0:8200"
  tls_disable        = 0
  tls_cert_file      = "/vault/tls/tls.crt"
  tls_key_file       = "/vault/tls/tls.key"
  tls_client_ca_file = "/vault/tls/ca.crt"
}

disable_mlock = true

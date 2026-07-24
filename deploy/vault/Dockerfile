FROM hashicorp/vault:1.18.4

USER root

COPY --chown=vault:vault config/vault.hcl /vault/config/vault.hcl
COPY --chown=vault:vault scripts/entrypoint.sh /usr/local/bin/linkapro-vault-entrypoint.sh
RUN chmod 0555 /usr/local/bin/linkapro-vault-entrypoint.sh

USER vault

ENTRYPOINT ["/usr/local/bin/linkapro-vault-entrypoint.sh"]

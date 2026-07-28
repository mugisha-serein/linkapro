"""UUID generator implementation for identity application ports."""

import uuid

from application.identity.shared.ports.id_generator import IdGenerator


class UuidGenerator(IdGenerator):
    def new_id(self) -> uuid.UUID:
        return uuid.uuid4()


__all__ = ["UuidGenerator"]

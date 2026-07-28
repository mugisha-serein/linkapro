"""Base identity entity behavior."""


class Entity:
    id: object

    def __eq__(self, other: object) -> bool:
        if other.__class__ is not self.__class__:
            return False
        return getattr(other, "id", None) == self.id

    def __hash__(self) -> int:
        return hash((self.__class__, self.id))

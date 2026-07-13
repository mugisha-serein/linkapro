from __future__ import annotations

from typing import Mapping, Protocol, Sequence, TypeAlias

ProfileCompletionErrors: TypeAlias = Mapping[str, Sequence[str]]

class VendorProfileCompletionProvider(Protocol):
    def get_profile_completion_errors(self, profile: object) -> ProfileCompletionErrors: ...

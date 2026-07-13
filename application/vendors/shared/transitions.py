from __future__ import annotations

from typing import Callable


class TransitionExecutorMixin:
    def _execute_transition(
        self,
        *,
        authorize: Callable[[], None],
        loader: Callable,
        expected_version: int,
        transition: Callable,
        to_dto: Callable,
    ):
        authorize()
        aggregate = loader()
        self._assert_expected_version(aggregate.id, aggregate.version, expected_version)
        original_version = aggregate.version
        transition(aggregate)
        return self._save_if_changed(aggregate, original_version, to_dto)

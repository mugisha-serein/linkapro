"""Identity event consumers are wired through IdentityDomainEventOutbox.

This module remains importable from ``IdentityConfig.ready()`` for app startup
compatibility, but identity aggregate side effects should be added to
``tasks.identity_domain_events`` so the outbox is the single live event
mechanism for the identity domain.
"""

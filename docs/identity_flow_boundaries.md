# Identity Flow Boundaries

This note records the current architecture decision for identity flows. It is a
scoping guide for future layer-2 and layer-3 work; it is not a migration plan.

## Decision

Identity flows are not required to move wholesale into `application/identity/`.
The application layer owns identity domain state transitions and domain-event
creation. The Django identity app owns HTTP/security infrastructure when the
flow depends on DRF serializers, throttles, cookies, CSRF checks, one-time token
records, email-delivery audit records, session tables, or cache-backed challenge
state.

Identity aggregate side effects use `IdentityDomainEventOutbox` as the single
live event mechanism. Do not add a second signal-based identity event path.

## Application-Owned Flows

These flows should keep their business rules in `application/identity/`, with
Django views acting as adapters:

- Self-registration and registration role validation.
- Password login decisioning and authenticated session token issuance.
- OAuth login/linking once the provider identity has been validated.
- Authenticated password change.
- Email verification state changes.
- Profile name updates.
- User deactivation/reactivation.
- Two-factor setup state changes after a valid TOTP code is verified.
- Two-factor login decisioning after the Django adapter extracts the temporary
  MFA token and submitted code.

Layer-2 prompts for these flows may add commands, handlers, DTO mappers, domain
methods, and outbox events. Layer-3 prompts should only adapt HTTP, serializer,
repository, or persistence concerns for these flows.

## Django-Native Flows

These flows intentionally remain in `django_app/identity/` unless a separate
migration plan is written first:

- Forgot-password and reset-password HTTP flow, including throttles, token
  records, token consumption, delivery audit records, and reset email dispatch.
- Password setup wrappers that clear cookies and coordinate active web sessions.
- Session tracking, refresh-token family storage, cookie issuance/clearing, CSRF
  checks, and session revocation.
- MFA setup presentation details such as QR-code delivery, temporary challenge
  cookies, redirects, and HTTP rate-limit behavior.
- Management commands that repair or administer persisted Django identity data.

Django-native flows may still create domain events when they mutate the identity
aggregate. For example, password reset writes `UserPasswordChanged` into
`IdentityDomainEventOutbox`; the outbox publisher performs session revocation.

## Prompt Scoping Rule

Before changing identity code, identify the flow's owner from this note. If the
flow is application-owned, keep new business rules out of Django views. If the
flow is Django-native, do not introduce parallel application handlers just to
mirror the Django implementation. Moving a Django-native flow into
`application/identity/` is a separate architectural migration and should remove
the old path in the same change.

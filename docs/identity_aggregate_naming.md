# Identity Aggregate Naming

## Decision

The identity aggregate remains named `User` for the current refactor.

`Account` is a reasonable future name for the authentication/account lifecycle
model, but the current public contract, repositories, application handlers,
Django model mapping, tests, and domain events all consistently expose `User`.
Renaming the aggregate now would create broad mechanical churn while the domain
package is still being split by concern.

## Consequence

New identity subpackages should move today's `User` behavior without renaming it.
A future `User` to `Account` rename should be handled as one explicit migration
after the package boundaries are stable.

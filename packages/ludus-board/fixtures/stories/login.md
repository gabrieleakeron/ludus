# Story: User Login

**As a** registered user,
**I want** to log in to the application with my email and password,
**So that** I can access my personal dashboard and data.

## Acceptance Criteria

1. The login form collects `email` and `password`.
2. Invalid credentials return a clear error message (no leaking which field is wrong).
3. Successful login issues a JWT token stored in an HttpOnly cookie.
4. After 5 failed attempts the account is temporarily locked (15 minutes).
5. A "Remember me" checkbox extends the session to 30 days.

## Technical Notes

- Auth endpoint: `POST /auth/login`
- Backend: FastAPI + PostgreSQL; use bcrypt for password hashing.
- Frontend: Angular reactive form with inline validation.
- JWT expiry: 1h (access token), 7d (refresh token).
- Rate limiting: 5 attempts / 15 min per IP.

## Out of Scope

- OAuth / SSO (deferred to a future story)
- Password reset flow

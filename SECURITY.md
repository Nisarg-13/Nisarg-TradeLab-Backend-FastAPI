# Security Policy

## Supported versions

Security fixes are applied to the `main` branch.

## Reporting a vulnerability

**Do not** open a public GitHub issue for security vulnerabilities.

Report privately via [GitHub Security Advisories](https://github.com/Nisarg-13/Nisarg-TradeLab-Backend-FastAPI/security/advisories/new).

Include:

- Description of the issue
- Steps to reproduce
- Impact (data exposure, auth bypass, etc.)

We aim to acknowledge reports within 7 days.

## Secrets and configuration

- Never commit `.env`, database URLs, or API keys.
- Set production secrets only in your hosting dashboard (FastAPI Cloud, etc.).
- MT5 connection keys (`TJ_...`) are user-specific credentials — treat them like passwords.
- See [`.env.example`](./.env.example) for required variables.

## MT5 sync

The Expert Advisor is read-only and uses hashed connection keys on the server. Do not share live `TJ_...` keys in issues or pull requests.

## Related repositories

- Frontend: [Nisarg-TradeLab-Frontend](https://github.com/Nisarg-13/Nisarg-TradeLab-Frontend)

# OLT Manager — Web / Multi-OLT

Development branch: `web-multi-olt`

This branch is the web and multi-device development line. The original `main` branch is kept unchanged.

## Deployment target

- Domain: `olt.admin89.ir`
- Host: Ubuntu 22.04 with aaPanel / Nginx
- Application: existing Flask application
- Protocols: SSH and Telnet per OLT
- Access model: one owner/admin account
- Credentials: per-device choice between session-only credentials and encrypted-at-rest credentials

## Current baseline

The application source is packaged in `OLT-MA5683T-EMU-Fan-Fixed.zip`. The GitHub Actions workflow extracts it and applies `traffic-live.patch.gz.b64` before building.

The baseline currently uses a process-global `CONN` and `LOCK`, so it supports one active OLT session. Multi-OLT work must replace this with an authenticated, per-device connection manager with an independent lock and lifecycle for each session.

## Development principles

1. Keep the existing ONT registration commands and parsing logic unless a change is required and tested.
2. Preserve the live interface traffic feature.
3. Keep SSH and Telnet selectable per device; prefer SSH or a VPN-protected management path.
4. Never commit real OLT addresses, usernames, passwords, secret keys, or session credentials.
5. Do not expose Telnet or the Flask development server directly to the public internet.
6. Run syntax checks and tests before deployment.
7. Deploy behind the existing aaPanel-managed Nginx/HTTPS configuration without changing unrelated websites or mail services.

## Clone this branch

```bash
git clone -b web-multi-olt https://github.com/babakghafouri/-OLT---MA5683T.git
```

## Update an existing checkout

```bash
git switch web-multi-olt
git pull origin web-multi-olt
```

## Deployment status

The branch is created as the development baseline. The web conversion and multi-OLT implementation are not yet complete; they will be committed here in small, testable steps.

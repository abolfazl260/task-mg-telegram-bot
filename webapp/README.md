# Telegram Web App

Phase 1 establishes an isolated Web App boundary for the task manager bot.

## Port

The Web App is planned to listen on `WEBAPP_HOST` / `WEBAPP_PORT`.

Recommended production values:

- `WEBAPP_HOST=127.0.0.1`
- `WEBAPP_PORT=8081`

The existing integration OAuth server keeps its separate `INTEGRATION_PORT` (default `8080`). Do not reuse that port for the Web App.

## Production URL

The Web App should eventually be exposed through HTTPS, for example:

`https://app.example.com`

Nginx should terminate TLS and proxy the Web App to `127.0.0.1:8081`.

## Phase 1 scope

- Keep the Web App isolated from the existing bot runtime.
- Reserve port `8081` for the Web App service.
- Do not change Telegram bot handlers or existing OAuth behavior.
- Authentication and task APIs will be added in later phases.

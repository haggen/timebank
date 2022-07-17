# Timebank

> ...

## Development with Docker

To run the application in production mode, type:

```sh
$ docker compose up
```

To run the application in development mode you'll need to merge the development config. and, optionally, enable the `proxy` profile.

```sh
$ docker compose -f compose.yml -f compose.development.yml --profile proxy up
```

> ℹ️ See `compose.yml` and `compose.development.yml` for available configuration.

Finally you can visit http://web-timebank.localhost to see it in action.

> ⚠️ The `proxy` profile assumes that ports `80` and `8080` are available and that you're using a browser that translates `*.localhost` to `127.0.0.1`. If this isn't the case you'll need to customize things or run it locally.

## Local development

You'll need:

1. Python v3.10+ with pipenv v2022+.
2. PostgreSQL v14+.

Copy `example.env` as `.env`.

```
$ cp example.env .env
```

Spin up your database and adjust the `DATABASE_URL` in `api/.env` accordingly.

Install dependencies.

```sh
$ pipenv install
```

Boot up the application.

```sh
$ env $(cat .env | xargs) pipenv run python src/main.py
```

> 💡 The `env $(cat .env | xargs)` part loads the environment configuration.

## Legal

Apache-2.0 ©️ 2022 Arthur Corenzan

# Timebank

> ...

The repository contains:

- The front-end application using Preact+Vite at `./www`.
- The back-end application using FastAPI+uvicorn at `./api`.

## Development with Docker

To run both applications in production mode, type:

```sh
$ docker compose up
```

For development you'll need to merge the development file and include `proxy` profile.

```sh
$ docker compose -f compose.yml -f compose.development.yml --profile proxy up
```

> ℹ️ See `compose.yml` and `compose.development.yml` for available configuration.

Finally you can visit http://www-timebank.localhost to see it in action.

> ⚠️ The `proxy` profile assumes that ports `80` and `8080` are available and that you're using a browser that translates `*.localhost` to `127.0.0.1`. If this isn't the case you'll need to customize things or run it locally.

## Local development

You'll need:

1. Python v3.10+ with pipenv v2022+.
2. Node.js v16+ with npm v8+.
3. PostgreSQL v14+.

Copy `example.env` as `.env` inside each application's directory.

```
$ cp www/example.env www/.env
$ cp api/example.env api/.env
```

Spin up your database and adjust the `DATABASE_URL` in `api/.env` accordingly.

Inside the `api` directory, prepare and run the back-end application.

```sh
$ pipenv install
$ env $(cat .env | xargs) pipenv run python src/main.py
```

Inside the `www` directory, start the front-end application.

```sh
$ env $(cat .env | xargs) npm start
```

> 💡 The `env $(cat .env | xargs)` part loads the configuration.

## Legal

Apache-2.0 ©️ 2022 Arthur Corenzan

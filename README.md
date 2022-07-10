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

ℹ️ See `compose.yml` and `compose.development.yml` for available configuration.

Finally you can visit http://www-timebank.localhost to see it in action.

⚠️ The `proxy` profile assumes that ports `80` and `8080` are available and that you're using a browser that translates `*.localhost` to `127.0.0.1`. If this isn't the case you'll need to customize things or run it locally.

## Local development

Copy `example.env` as `.env` inside each application's directory.

```
$ cp www/example.env www/.env
$ cp api/example.env api/.env
```

Spin up a PostgreSQL v14+ and adjust the `DATABASE_URL` in `api/.env` accordingly.

Setup a virtual environment for Python, activate it and install dependencies.

```sh
$ python -m venv api/.venv
$ source api/.venv/bin/activate
$ python -m pip install -r api/requirements.txt
```

Start the back-end application.

```sh
$ cd api; env $(cat .env | xargs) python main.py
```

Start the front-end application.

```sh
$ cd www; env $(cat .env | xargs) npm start
```

## Legal

Apache-2.0 ©️ 2022 Arthur Corenzan

FROM python:3-alpine

RUN pip install pipenv
ENV PIPENV_VENV_IN_PROJECT=1

WORKDIR /root/src
COPY Pipfile* .
RUN pipenv install

EXPOSE 5000

COPY . .

CMD ["pipenv", "run", "python", "src/main.py"]
# Base image.
FROM python:3.10-alpine

# Install dumb-init.
# @see https://github.com/Yelp/dumb-init
RUN apk add --no-cache dumb-init

# Install pipenv.
# @see https://pipenv.pypa.io/en/latest/
RUN pip install --no-cache-dir pipenv

# Install dependencies.
WORKDIR /root/src
COPY Pipfile* ./
RUN pipenv install --deploy --system

# Expose the application's port.
EXPOSE 5000

# Copy the application's files.
COPY . .

# Configure entrypoint.
ENTRYPOINT ["dumb-init", "--"]

# Configure default command.
CMD ["python", "src/main.py"]
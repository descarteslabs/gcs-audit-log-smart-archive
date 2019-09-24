FROM python:3

# allows containerized app to be aware of its build version via env var
ARG tag
ENV APP_VERSION="${tag}"
ENV PYTHONUNBUFFERED=1

COPY /app/requirements.txt /app/requirements.txt

RUN pip3 install -r /app/requirements.txt

COPY ./app/ /app

WORKDIR /app

ENTRYPOINT [ "python", "/app/main.py" ]

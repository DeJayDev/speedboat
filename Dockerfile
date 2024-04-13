FROM python:3.11

WORKDIR /opt/rowboat

RUN git config --global safe.directory *

COPY pyproject.toml poetry.lock manage.py .git/ ./

ENV POETRY_HOME=/opt/poetry
RUN python3 -m venv $POETRY_HOME
RUN $POETRY_HOME/bin/pip install poetry==1.7.1
RUN $POETRY_HOME/bin/poetry self add 'poethepoet[poetry_plugin]'

RUN $POETRY_HOME/bin/poetry --version
RUN $POETRY_HOME/bin/poetry config virtualenvs.create false
RUN $POETRY_HOME/bin/poetry config installer.max-workers 10
RUN $POETRY_HOME/bin/poetry install

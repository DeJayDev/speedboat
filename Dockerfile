FROM python:3.11

RUN mkdir /opt/rowboat

RUN pip install poetry
COPY poetry.lock pyproject.toml .git/ /opt/rowboat/
RUN poetry config virtualenvs.create false
RUN cd /opt/rowboat && poetry install
RUN cd /opt/rowboat && git fetch && git config --global --add safe.directory /opt/rowboat
RUN pip3 install cairosvg

COPY [^.]* /opt/rowboat/
WORKDIR /opt/rowboat


FROM python:3.11-slim

RUN mkdir /opt/rowboat

COPY requirements.txt /opt/rowboat/
RUN --mount=type=ssh pip install -r /opt/rowboat/requirements.txt

COPY [^.]* /opt/rowboat/
WORKDIR /opt/rowboat
FROM python:3.8

ENV PYTHONUNBUFFERED 1
ENV ENV docker

RUN mkdir /opt/rowboat

ADD requirements.txt /opt/rowboat/
RUN pip install -r /opt/rowboat/requirements.txt

ADD . /opt/rowboat/
WORKDIR /opt/rowboat

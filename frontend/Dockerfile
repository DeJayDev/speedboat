FROM node:8.5.0

RUN mkdir /opt/frontend

ADD package.json /opt/frontend
ADD package-lock.json /opt/frontend
RUN cd /opt/frontend && npm install
RUN npm install webpack-dev-server -g

ADD src /opt/frontend/src
WORKDIR /opt/frontend

FROM mhart/alpine-node:8.17

WORKDIR /opt/frontend

COPY package.json .
RUN npm install

COPY . .

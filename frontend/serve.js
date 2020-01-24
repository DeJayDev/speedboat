const proxy = require('http-proxy-middleware');
const Bundler = require('parcel-bundler');
const express = require('express');

const bundler = new Bundler(['./src/index.html'], {
  cache: false
});

const app = express();

let proxyURL = 'http://localhost:8686';

if (process.env.NODE_ENV == 'docker') {
  proxyURL = 'http://web:8686';
}

function relayRequestHeaders(apiReq, req) {
  Object.keys(req.headers).forEach(header => {
    apiReq.setHeader(key, req.headers[header])
  });
}

function relayResponseHeaders(apiRes, req, res) {
  Object.keys(apiRes.headers).forEach(header => {
    res.append(key, apiRes.headers[header])
  });
}

app.use('/api', (req, res) => {
  proxy({
    target: proxyURL,
    onProxyReq: relayRequestHeaders,
    onProxyRes: relayResponseHeaders
  })
});

app.use(bundler.middleware());

app.listen(Number(process.env.PORT || 80));
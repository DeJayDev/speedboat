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

var proxyOptions = {
  target: proxyURL,
  onProxyReq(proxyReq, req, res) {
    console.log(proxyReq.headers)
    Object.keys(req.headers).forEach(header => {
      proxyReq.setHeader(header, req.headers[header])
    });
  },
  onProxyRes(proxyRes, req, res) {
    console.log('proxyres: ' + proxyRes.headers)
    Object.keys(proxyRes.headers).forEach(header => {
      res.append(header, proxyRes.headers[header])
    });
  }
}

app.use('/api', proxy(proxyOptions));

app.use(bundler.middleware());

app.listen(Number(process.env.PORT || 80));
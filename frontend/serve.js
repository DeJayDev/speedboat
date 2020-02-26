const { createProxyMiddleware } = require('http-proxy-middleware');
const Bundler = require('parcel-bundler');
const express = require('express');

const bundler = new Bundler(['./src/index.html'], {
  cache: true
});

const app = express();

let proxyURL = 'http://localhost:8686';

if (process.env.NODE_ENV == 'docker') {
  //proxyURL = 'http://web:8686';
}

if (process.env.NODE_ENV == 'development') {
  proxyURL = 'http://kubernetes.docker.internal:8686';
}

var proxyOptions = {
  target: proxyURL,
  onProxyReq(proxyReq, _, res) {
    if(!proxyReq.headers) return;
    Object.keys(proxyReq.headers).forEach(header => {
      req.setHeader(header, req.headers[header])
    });
  },
  onProxyRes(proxyRes, _, res) {
    if(!proxyRes.headers) return;
    Object.keys(proxyRes.headers).forEach(header => {
      res.append(header, proxyRes.headers[header])
    });
  }
}

app.use('/api', createProxyMiddleware(proxyOptions));

app.use(bundler.middleware());

app.listen(Number(process.env.PORT || 80));
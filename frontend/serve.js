const proxy = require('http-proxy-middleware');
const Bundler = require('parcel-bundler');
const express = require('express');

const bundler = new Bundler(['./src/index.html'], {
  cache: false
});

const app = express();

let proxyURL = 'http://localhost:8686';

if (process.env.NODE_ENV == 'production') {
	proxyURL = 'http://web:8686';
}

app.use('/api', proxy({ target: proxyURL }));

app.use(bundler.middleware());

app.listen(Number(process.env.PORT || 80));

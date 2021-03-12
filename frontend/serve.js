const {createProxyMiddleware} = require('http-proxy-middleware')
const express = require('express')
const fs = require('fs')
const https = require('https')
const app = express()
const Parcel = require("@parcel/core").default
const path = require("path")

const bundler = new Parcel({
  entries: path.join(__dirname, "./src/index.html"),
  defaultConfig: require.resolve("@parcel/config-default")
})

let proxyURL = 'http://localhost:8686'

if (process.env.NODE_ENV === 'docker') {
  proxyURL = 'http://web:8686'
}

const proxyOptions = {
  target: proxyURL,
  onProxyReq(proxyReq, _, req) {
    if (!proxyReq.headers) return
    Object.keys(proxyReq.headers).forEach(header => {
      req.setHeader(header, req.headers[header])
    })
  },
  onProxyRes(proxyRes, _, res) {
    if (!proxyRes.headers) return
    Object.keys(proxyRes.headers).forEach(header => {
      res.append(header, proxyRes.headers[header])
    })
  }
}

app.use('/api', createProxyMiddleware(proxyOptions))

if (fs.existsSync('./ssl/certificate.pem') && fs.existsSync('./ssl/key.pem')) {
  https.createServer({
    key: fs.readFileSync('./ssl/key.pem'),
    cert: fs.readFileSync('./ssl/certificate.pem')
  }, app).listen(Number(process.env.PORT || 443))
} else {
    app.listen(Number(process.env.PORT || 80));
}
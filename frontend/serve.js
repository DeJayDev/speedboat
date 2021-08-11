const {createProxyMiddleware} = require('http-proxy-middleware')
const express = require('express')
const fs = require('fs')
const https = require('https')
const ip = Object.values(require('os').networkInterfaces()).flat().find(i => i.family == 'IPv4' && !i.internal).address // lol
const app = express()

app.use('/build', express.static(require("path").join(__dirname, 'build')))
app.use(express.static('src'))

let proxyURL = 'http://localhost:8686';

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

app.use(express.static('src'))
app.use('/api', createProxyMiddleware(proxyOptions))

if (fs.existsSync('./ssl/certificate.pem') && fs.existsSync('./ssl/key.pem')) {
  var listener = https.createServer({
    key: fs.readFileSync('./ssl/key.pem'),
    cert: fs.readFileSync('./ssl/certificate.pem')
  }, app).listen(443)
} else {
  var listener = app.listen(Number(process.env.PORT || 80));
}

console.log('Running on: ' + ip + ':' + listener.address().port)

// get a discord token and log into Discord

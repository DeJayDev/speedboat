const {createProxyMiddleware} = require('http-proxy-middleware')
const express = require('express')
const ip = Object.values(require('os').networkInterfaces()).flat().find(i => i.family == 'IPv4' && !i.internal).address // lol
const app = express()
const path = require('path')

let proxyURL = 'http://direct.speedboat.rocks:8686';

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
app.use(express.static('src'))
app.use('/*', function(req, res) {
  res.sendFile(path.join(__dirname, 'src/index.html'), function(err) {
    if (err) {
      res.status(500).send(err)
    }
 })
})

var listener = app.listen(Number(process.env.PORT || 8443));

console.log('Running on: ' + ip + ':' + listener.address()?.port)

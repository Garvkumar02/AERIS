const { getDefaultConfig } = require('expo/metro-config');
const http = require('http');

const config = getDefaultConfig(__dirname);

const API_PREFIXES = [
  '/auth',
  '/attendance',
  '/devices',
  '/biometric',
  '/admin',
  '/gate',
  '/notifications',
  '/presence',
  '/privacy',
  '/registry',
  '/docs',
  '/openapi.json',
  '/health'
];

config.server = config.server || {};
const originalEnhanceMiddleware = config.server.enhanceMiddleware;

config.server.enhanceMiddleware = (metroMiddleware, server) => {
  return (req, res, next) => {
    const url = req.url || '';
    const isApi = API_PREFIXES.some(prefix => 
      url === prefix || url.startsWith(prefix + '/') || url.startsWith(prefix + '?')
    );
    
    if (isApi) {
      // Proxy API calls directly to FastAPI backend on 127.0.0.1:8000
      const proxyReq = http.request({
        host: '127.0.0.1',
        port: 8000,
        path: req.url,
        method: req.method,
        headers: {
          ...req.headers,
          host: '127.0.0.1:8000',
          'x-forwarded-for': req.socket ? req.socket.remoteAddress : '',
          'x-forwarded-proto': 'https'
        }
      }, (proxyRes) => {
        res.writeHead(proxyRes.statusCode || 200, proxyRes.headers);
        proxyRes.pipe(res);
      });

      proxyReq.on('error', (err) => {
        console.error('Metro API proxy error:', err.message);
        if (!res.headersSent) {
          res.writeHead(502, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ detail: 'AERIS backend is starting up or unreachable on port 8000.' }));
        }
      });

      req.pipe(proxyReq);
      return;
    }

    if (originalEnhanceMiddleware) {
      return originalEnhanceMiddleware(metroMiddleware, server)(req, res, next);
    }
    return metroMiddleware(req, res, next);
  };
};

module.exports = config;

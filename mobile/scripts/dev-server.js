const http = require('node:http');
const net = require('node:net');
const path = require('node:path');
const { spawn } = require('node:child_process');

const mobileDir = path.resolve(__dirname, '..');
const backendDir = path.resolve(mobileDir, '..', 'backend');
const gatewayPort = Number(process.env.PORT || 8081);
const expoPort = Number(process.env.EXPO_PORT || 8082);
const backendPort = Number(process.env.BACKEND_PORT || 8000);
const backendHost = '127.0.0.1';
const expoHost = 'localhost';
const apiPrefixes = [
  '/auth',
  '/devices',
  '/biometric',
  '/attendance',
  '/admin-portal',
  '/docs',
  '/openapi.json',
  '/health',
];

const children = [];

function upstreamFor(url) {
  const pathname = new URL(url, 'http://localhost').pathname;
  const isAdminApi = ['/admin/stats', '/admin/attendance', '/admin/attempts', '/admin/campus']
    .some((route) => pathname === route || pathname.startsWith(`${route}/`));
  const isApi = isAdminApi || apiPrefixes.some((prefix) =>
    pathname === prefix || pathname.startsWith(`${prefix}/`),
  );
  return isApi
    ? { host: backendHost, port: backendPort, preserveHost: false }
    : { host: expoHost, port: expoPort, preserveHost: true };
}

function proxyHttp(request, response) {
  const target = upstreamFor(request.url);
  const upstreamRequest = http.request(
    {
      host: target.host,
      port: target.port,
      method: request.method,
      path: request.url,
      headers: {
        ...request.headers,
        host: target.preserveHost
          ? request.headers.host
          : `${target.host}:${target.port}`,
        'x-forwarded-host': request.headers.host || '',
        'x-forwarded-proto': 'http',
      },
    },
    (upstreamResponse) => {
      response.writeHead(upstreamResponse.statusCode || 502, upstreamResponse.headers);
      upstreamResponse.pipe(response);
    },
  );

  upstreamRequest.on('error', (error) => {
    console.error(`Proxy error for ${request.method} ${request.url}: ${error.message}`);
    if (!response.headersSent) {
      response.writeHead(502, { 'content-type': 'application/json' });
      response.end(JSON.stringify({ detail: 'AERIS service is not ready. Check the local servers.' }));
    } else {
      response.destroy(error);
    }
  });
  request.pipe(upstreamRequest);
}

function proxyWebSocket(request, socket, head) {
  const target = upstreamFor(request.url);
  const upstreamSocket = net.connect(target.port, target.host, () => {
    const headers = {
      ...request.headers,
      host: target.preserveHost ? request.headers.host : `${target.host}:${target.port}`,
    };
    const forwardedRequest = [
      `${request.method} ${request.url} HTTP/${request.httpVersion}`,
      ...Object.entries(headers).map(([name, value]) => `${name}: ${value}`),
      '',
      '',
    ].join('\r\n');
    upstreamSocket.write(forwardedRequest);
    if (head.length > 0) upstreamSocket.write(head);
    upstreamSocket.pipe(socket);
    socket.pipe(upstreamSocket);
  });

  upstreamSocket.on('error', (error) => {
    console.error(`WebSocket proxy error for ${request.url}: ${error.message}`);
    socket.destroy(error);
  });
  socket.on('error', () => upstreamSocket.destroy());
  socket.on('close', () => upstreamSocket.destroy());
}

function startChild(command, args, cwd, label, env = process.env) {
  const child = spawn(command, args, { cwd, env, stdio: 'inherit' });
  child.on('error', (error) => {
    console.error(`Failed to start ${label}: ${error.message}`);
    shutdown(1);
  });
  child.on('exit', (code, signal) => {
    if (!isShuttingDown) {
      console.error(`${label} exited unexpectedly (code ${code}, signal ${signal || 'none'})`);
      shutdown(code || 1);
    }
  });
  children.push(child);
  return child;
}

let isShuttingDown = false;
function shutdown(exitCode = 0) {
  if (isShuttingDown) return;
  isShuttingDown = true;
  server.close();
  for (const child of children) {
    if (child.exitCode === null && !child.killed) child.kill();
  }
  setTimeout(() => process.exit(exitCode), 500).unref();
}

const server = http.createServer(proxyHttp);
server.on('upgrade', proxyWebSocket);
server.on('error', (error) => {
  if (error.code === 'EADDRINUSE') {
    console.error(
      `Port ${gatewayPort} is already in use. Stop the current Expo server on that port, then run npm run start:all.`,
    );
  } else {
    console.error(`Gateway error: ${error.message}`);
  }
  shutdown(1);
});

server.listen(gatewayPort, '0.0.0.0', () => {
  console.log(`AERIS is starting at http://localhost:${gatewayPort}`);
  console.log(`Expo web server: http://localhost:${expoPort}`);
  console.log(`Backend API: http://127.0.0.1:${backendPort}`);

  const pythonExe = process.platform === 'win32' ? 'python.exe' : 'python';
  const venvPython = path.join(backendDir, '.venv', 'Scripts', pythonExe);
  const unixVenvPython = path.join(backendDir, '.venv', 'bin', 'python');
  const fs = require('node:fs');
  const python = fs.existsSync(venvPython)
    ? venvPython
    : fs.existsSync(unixVenvPython)
      ? unixVenvPython
      : (process.env.PYTHON || 'python');

  startChild(
    python,
    ['-m', 'uvicorn', 'app.main:app', '--host', backendHost, '--port', String(backendPort)],
    backendDir,
    'AERIS backend',
    { ...process.env, PORT: String(backendPort) },
  );
  startChild(
    process.execPath,
    [
      path.join(mobileDir, 'node_modules', 'expo', 'bin', 'cli'),
      'start',
      '--web',
      '--host',
      'localhost',
      '--port',
      String(expoPort),
    ],
    mobileDir,
    'Expo web',
    { ...process.env, BROWSER: 'none' },
  );
});

process.on('SIGINT', () => shutdown());
process.on('SIGTERM', () => shutdown());

const fs = require('node:fs');
const dgram = require('node:dgram');
const path = require('node:path');
const { spawn } = require('node:child_process');

const mobileDir = process.cwd();
const backendDir = path.resolve(mobileDir, '..', 'backend');
const expoPort = Number(process.env.EXPO_PORT || 8083);
const backendPort = Number(process.env.BACKEND_PORT || 8004);
const pythonExe = process.platform === 'win32' ? 'python.exe' : 'python';
const windowsVenvPython = path.join(backendDir, '.venv', 'Scripts', pythonExe);
const unixVenvPython = path.join(backendDir, '.venv', 'bin', 'python');
const python = fs.existsSync(windowsVenvPython)
  ? windowsVenvPython
  : fs.existsSync(unixVenvPython)
    ? unixVenvPython
    : process.env.PYTHON || 'python';

const children = [];
let isShuttingDown = false;

function shutdown(exitCode = 0) {
  if (isShuttingDown) return;
  isShuttingDown = true;
  for (const child of children) {
    if (child.exitCode === null && !child.killed) child.kill();
  }
  process.exitCode = exitCode;
}

function start(command, args, cwd, label, env = process.env) {
  const child = spawn(command, args, { cwd, env, stdio: 'inherit' });
  child.on('error', (error) => {
    console.error(`Failed to start ${label}: ${error.message}`);
    shutdown(1);
  });
  child.on('exit', (code, signal) => {
    if (!isShuttingDown) {
      console.error(`${label} exited unexpectedly (code ${code}, signal ${signal || 'none'})`);
      shutdown(code ?? 1);
    }
  });
  children.push(child);
}

function getLanAddress() {
  if (process.env.BACKEND_LAN_IP) {
    return Promise.resolve(process.env.BACKEND_LAN_IP);
  }

  return new Promise((resolve, reject) => {
    const socket = dgram.createSocket('udp4');
    socket.once('error', (error) => {
      socket.close();
      reject(error);
    });
    socket.connect(53, '8.8.8.8', () => {
      const address = socket.address().address;
      socket.close();
      resolve(address);
    });
  });
}

async function main() {
  const lanAddress = await getLanAddress();
  const apiUrl = `http://${lanAddress}:${backendPort}`;

  console.log(`Starting AERIS backend at ${apiUrl}.`);
  console.log(`Starting Expo Go over a tunnel on Metro port ${expoPort}.`);

  const env = {
    ...process.env,
    EXPO_PUBLIC_API_URL: apiUrl,
    EXPO_PUBLIC_WEB_API_URL: `http://127.0.0.1:${backendPort}`,
  };
  const backend = spawn(
    python,
    [
      '-m',
      'uvicorn',
      'app.main:app',
      '--host',
      '0.0.0.0',
      '--port',
      String(backendPort),
    ],
    { cwd: backendDir, env, stdio: 'inherit' },
  );
  backend.on('error', (error) => {
    console.error(`Failed to start AERIS backend: ${error.message}`);
    shutdown(1);
  });
  backend.on('exit', (code, signal) => {
    if (!isShuttingDown) {
      console.error(`AERIS backend exited (code ${code}, signal ${signal || 'none'})`);
      shutdown(code ?? 1);
    }
  });
  children.push(backend);

  start(
    process.execPath,
    [
      path.join(mobileDir, 'node_modules', 'expo', 'bin', 'cli'),
      'start',
      '--go',
      '--tunnel',
      '--port',
      String(expoPort),
    ],
    mobileDir,
    'Expo',
    env,
  );
}

main().catch((error) => {
  console.error(`Could not determine the computer's LAN address: ${error.message}`);
  console.error('Set BACKEND_LAN_IP to the computer IPv4 address and try again.');
  shutdown(1);
});

process.on('SIGINT', () => shutdown());
process.on('SIGTERM', () => shutdown());

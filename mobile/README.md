# AERIS Mobile (Expo)

The mobile app uses Expo SDK 57 and Expo Router. Use Expo Go to test it on a
physical Android/iOS device, or use an Android emulator.

## Run on a phone

From the repository root, install the backend dependencies once:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Then install the mobile packages once and start both services:

```powershell
cd ..\mobile
npm install
npm run start:phone
```

Install **Expo Go** on the phone and connect it and the computer to the same
Wi-Fi. Scan the QR code shown by Expo. On Android, scan from Expo Go; on iOS,
scan with the Camera app and open the link in Expo Go.

`npm run start:phone` runs Expo Go through a tunnel and FastAPI on
`0.0.0.0:8004`. Expo uses Metro port `8083` by default; set `EXPO_PORT` to
override it. The API port defaults to `8004` so it does not clash with the
browser gateway's local-only backend on `8000`; set `BACKEND_PORT` to override
it. The app launcher detects the computer's LAN address and configures the
mobile API URL automatically. If Windows Firewall prompts you, allow Node.js
and Python on **Private networks**. Keep the phone and computer on the same
Wi-Fi for the backend API connection even when Expo itself uses a tunnel.
If the backend status is still offline, tap the backend status in the app and
enter `http://<computer-LAN-IP>:8004`. Find that IPv4 address with `ipconfig`.

For an Android emulator, enter `http://10.0.2.2:8004` in API settings.
Stop any existing `start:all` web server before running the phone setup, since
both modes use the backend port `8000`. Keep the backend and Expo terminal
running while you use the app. Press `Ctrl+C` to stop both.

## Run in a browser

From the repository root, install and build the dashboard, then start the web
gateway from `mobile`:

```powershell
cd dashboard
npm install
npm run build
cd ..\mobile
npm run start:all
```

Open `http://localhost:8081`. The web gateway starts Expo Web and the backend
and routes API requests through the same address. The built dashboard is also
available at `http://localhost:8081/admin-portal/`. The web gateway uses ports
`8081` (browser), `8082` (Expo upstream), and `8000` (backend upstream) by
default. Set `PORT`, `EXPO_PORT`, or `BACKEND_PORT` to change them.

The backend uses the InsightFace `buffalo_l` models when `det_10g.onnx` and
`w600k_r50.onnx` are already cached under `~/.insightface/models/buffalo_l`.
Otherwise, it starts with the existing OpenCV fallback instead of downloading
model files during startup. If attendance reports `DEVICE_NOT_REGISTERED`,
choose **Register This Device & Try Again** to bind this app installation to
the signed-in account.

Edit screens in `src/app/`; this project uses file-based routing with
[Expo Router](https://docs.expo.dev/router/introduction).

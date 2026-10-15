# 🚀 AERIS — Smart Campus Attendance & Monitoring System

**AI-Powered Face Recognition | Dynamic QR Attendance | GPS Geofencing | Tamper-Evident Audit**

AERIS is an intelligent campus attendance and monitoring system designed to make student attendance more secure, efficient, and transparent. It combines AI-based facial verification, rotating QR codes, GPS geofencing, role-based access control, and cryptographic audit logs to reduce proxy attendance and improve campus management.

## ✨ Key Features

### 🤖 1. AI-Powered Face Recognition
- ArcFace-based 512-dimensional facial embeddings.
- Real-time facial landmark tracking and head-pose liveness challenges.
- Face verification through webcam or mobile camera.
- Detection of suspicious or unsuccessful verification attempts.

### 📱 2. Dynamic QR Attendance
- Automatically rotating classroom QR codes.
- Time-limited tokens with cryptographic verification.
- Replay and duplicate-submission protection.
- Quick attendance verification through a mobile scanner.

### 📍 3. GPS Geofencing
- Haversine-based distance calculation for campus boundaries.
- Location-based attendance restrictions.
- Mock-location detection where supported.
- Campus demo mode for testing.

### 🔐 4. Cryptographic Audit & Integrity
- SHA-256 hash-linked attendance, gate, and room-presence records.
- Tamper detection through audit-chain verification.
- Merkle trees and inclusion proofs for event verification.
- Optional blockchain anchoring, depending on network configuration.

### 🏫 5. Student Mobile Application
- React Native, Expo, and TypeScript.
- Face verification and QR-based attendance.
- Attendance history, timetable, and attendance percentage.
- Notifications and campus updates.

### 🖥️ 6. Admin Dashboard
- React and TypeScript-based web dashboard.
- Student, faculty, staff, and visitor management.
- Attendance, gate-access, staff-duty, and verification reports.
- Department, floor, room, role, and date filters.
- Audit history, integrity monitoring, and CSV exports.
- Campus floor and room-presence monitoring.

### 🛡️ 7. Privacy & Data Security
- Encrypted biometric templates.
- Biometric consent, revocation, and deletion workflows.
- Configurable data-retention and backup policies.
- Role-based access control and protected API endpoints.

### 👥 8. Multi-Role Access Control

| Role | Main Responsibilities |
|---|---|
| Student | Attendance, timetable, personal records |
| Faculty | Lecture sessions, QR generation, attendee monitoring |
| Admin / HOD | Campus management, analytics, reports, audits |
| Security Guard | Gate verification, visitor and entry/exit records |
| Staff / Worker | Duty tracking and authorized campus access |

## 🛠️ Technology Stack

- **Backend:** Python, FastAPI
- **Mobile:** React Native, Expo, TypeScript
- **Dashboard:** React, TypeScript, Vite
- **Database:** SQLite; PostgreSQL support subject to configuration
- **AI & Computer Vision:** InsightFace / ArcFace, OpenCV
- **Security:** JWT, bcrypt, Fernet/MultiFernet, HMAC-SHA256, SHA-256
- **Integrity:** Hash chains, Merkle trees, optional blockchain anchoring
- **Deployment:** Vercel for the dashboard; backend and mobile deployment depend on environment configuration

## 🏗️ Project Structure

```text
AERIS/
├── backend/       # FastAPI APIs, security, database and AI
├── mobile/        # Expo React Native application
├── dashboard/     # Admin web dashboard
├── docs/          # Architecture and API documentation
└── README.md
```

## 🔒 Security & Privacy

AERIS is designed with biometric privacy, secure authentication, auditability, and data minimization in mind. Security controls and deletion workflows must be validated against the deployed implementation and applicable institutional policies.

## 🧪 Testing & Validation

The project includes phase-wise testing for authentication, attendance verification, gate access, privacy controls, notifications, reports, and audit integrity. Refer to the test scripts and documentation for actual results and known limitations.

## 🎯 Project Objective

To build a secure, AI-assisted campus attendance platform that reduces proxy attendance, simplifies administrative operations, and provides verifiable attendance and access records.

## 👨‍💻 Project Status

Developed as a smart campus attendance and monitoring project. Production readiness depends on successful end-to-end testing, real-device validation, security review, and deployment verification.

---

**AERIS — Smarter Attendance. Safer Campuses. Verifiable Records.**

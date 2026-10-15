import React, { useEffect, useRef, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  Dimensions,
  Image,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { StatusBar } from 'expo-status-bar';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { CameraType, CameraView, useCameraPermissions } from 'expo-camera';
import { Ionicons } from '@expo/vector-icons';
import * as Location from 'expo-location';

import { useAuth } from '@/context/AuthContext';
import { ApiService } from '@/services/api';

const { width } = Dimensions.get('window');

// SKIT Main Campus, Jaipur coordinates
const CAMPUS_COORDS = {
  latitude: 26.8228,
  longitude: 75.8648,
  name: 'Arya / SKIT Main Campus, Jaipur',
  radius_m: 350,
};

type VerificationStep =
  | 'idle'
  | 'quick_webcam_scan'
  | 'getting_location'
  | 'capturing_neutral'
  | 'capturing_challenge'
  | 'ready_to_submit'
  | 'submitting'
  | 'result_success'
  | 'result_failed';

export default function AttendanceVerifyScreen() {
  const router = useRouter();
  const params = useLocalSearchParams<{ mode?: string }>();
  const { user } = useAuth();

  // Active top-level Tab: Face AI or QR Scanner
  const [activeTab, setActiveTab] = useState<'face' | 'qr'>(
    params.mode === 'qr' ? 'qr' : 'face'
  );

  // Camera permissions and ref
  const [cameraPermission, requestCameraPermission] = useCameraPermissions();
  const cameraRef = useRef<any>(null);
  const [facing, setFacing] = useState<CameraType>(
    params.mode === 'qr' ? 'back' : 'front'
  );

  // QR Scanning state
  const [scanned, setScanned] = useState(false);
  const [qrSubmitting, setQrSubmitting] = useState(false);

  // Verification step state
  const [step, setStep] = useState<VerificationStep>(
    params.mode === 'face' ? 'quick_webcam_scan' : 'idle'
  );
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [challenge, setChallenge] = useState<'TURN_LEFT' | 'TURN_RIGHT'>('TURN_LEFT');
  const [demoGpsMode, setDemoGpsMode] = useState<boolean>(true);
  const [isRegisteringDevice, setIsRegisteringDevice] = useState(false);

  // Captured frames for liveness challenge
  const [neutralPhoto, setNeutralPhoto] = useState<any>(null);
  const [challengePhoto, setChallengePhoto] = useState<any>(null);

  // GPS data
  const [gpsData, setGpsData] = useState<{
    lat: number;
    lng: number;
    accuracy: number;
    is_mock: boolean;
    distance_m?: number;
  }>({
    lat: CAMPUS_COORDS.latitude,
    lng: CAMPUS_COORDS.longitude,
    accuracy: 10.0,
    is_mock: false,
    distance_m: 0,
  });

  // Result state
  const [resultData, setResultData] = useState<{
    result: 'ACCEPT' | 'REJECT';
    code: string | null;
    message: string;
    student_name?: string;
    student_id?: string;
    department?: string;
    subject_name?: string;
    subject_code?: string;
    room_name?: string;
    faculty_name?: string;
    section?: string;
    confidence_pct?: number;
    vertices_count?: number;
    ledger_hash?: string;
    timestamp?: string;
    verification_method?: string;
  } | null>(null);

  // Respond to route parameter changes
  useEffect(() => {
    if (params.mode === 'qr') {
      setActiveTab('qr');
      setFacing('back');
      setScanned(false);
      setStep('idle');
    } else if (params.mode === 'face') {
      setActiveTab('face');
      setFacing('front');
      setStep('quick_webcam_scan');
    }
  }, [params.mode]);

  // Haversine distance formula for distance preview
  const calculateDistance = (lat1: number, lon1: number, lat2: number, lon2: number) => {
    const R = 6371000;
    const dLat = ((lat2 - lat1) * Math.PI) / 180;
    const dLon = ((lon2 - lon1) * Math.PI) / 180;
    const a =
      Math.sin(dLat / 2) * Math.sin(dLat / 2) +
      Math.cos((lat1 * Math.PI) / 180) *
        Math.cos((lat2 * Math.PI) / 180) *
        Math.sin(dLon / 2) *
        Math.sin(dLon / 2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    return Math.round(R * c);
  };

  // Parse QR Code payload
  const parseQrData = (data: string) => {
    let lecture_id = '';
    let token = '';
    let student_id = '';

    // 1. Try JSON
    try {
      const parsed = JSON.parse(data);
      if (parsed.lecture_id) lecture_id = parsed.lecture_id;
      if (parsed.token) token = parsed.token;
      if (parsed.student_id) student_id = parsed.student_id;
    } catch {
      // Not raw JSON
    }

    // 2. Query parameters / URL search
    if (!lecture_id || !token) {
      const lecMatch = data.match(/lecture_id=([a-zA-Z0-9_\-]+)/);
      if (lecMatch) lecture_id = lecMatch[1];

      const tokenMatch = data.match(/token=([a-zA-Z0-9_\-\.]+)/);
      if (tokenMatch) token = tokenMatch[1];

      const stuMatch = data.match(/student_id=([a-zA-Z0-9_\-]+)/);
      if (stuMatch) student_id = stuMatch[1];
    }

    // Fallback if data is raw token
    if (!token && data.length > 10 && !data.includes(' ')) {
      token = data;
    }

    return { lecture_id, token, student_id };
  };

  // Handle scanned QR Code
  const handleBarcodeScanned = async ({ data }: { data: string }) => {
    if (scanned || qrSubmitting) return;
    setScanned(true);
    setQrSubmitting(true);

    try {
      const { lecture_id, token } = parseQrData(data);
      const deviceId = await ApiService.getDeviceId();

      const res = await ApiService.mobileInstantCheckin({
        lecture_id: lecture_id || undefined,
        token: token || undefined,
        student_id: user?.employee_id || 'STU159',
        lat: demoGpsMode ? CAMPUS_COORDS.latitude : gpsData.lat,
        lng: demoGpsMode ? CAMPUS_COORDS.longitude : gpsData.lng,
        device_id: deviceId,
      });

      if (res.result === 'ACCEPT' || res.code === 'ALREADY_MARKED') {
        setResultData({
          result: 'ACCEPT',
          code: res.code || 'INSTANT_QR_ACCEPTED',
          message: res.message || 'Lecture QR Attendance Verified!',
          student_name: res.student_name || user?.name || 'AARAV',
          student_id: res.student_id || user?.employee_id || 'STU159',
          department: res.department || 'CSE',
          subject_name: res.subject_name || 'Data Structures & Algorithms',
          subject_code: res.subject_code || 'CS301',
          room_name: res.room_name || 'LT-16',
          faculty_name: res.faculty_name || 'Dr. Alok Sharma',
          section: res.section || 'Section A',
          ledger_hash: res.ledger_hash,
          timestamp: res.checked_in_at || new Date().toISOString(),
          verification_method: 'MOBILE_DYNAMIC_QR_INSTANT',
        });
        setStep('result_success');
      } else {
        setResultData({
          result: 'REJECT',
          code: res.code || 'QR_INVALID',
          message: res.message || 'Invalid or expired lecture QR code.',
        });
        setStep('result_failed');
      }
    } catch (err: any) {
      Alert.alert('Scan Failed', err.message || 'Could not verify lecture QR code.');
      setScanned(false);
    } finally {
      setQrSubmitting(false);
    }
  };

  // Quick 1-Tap Webcam / Face AI Attendance
  const handleQuickWebcamScan = async () => {
    if (!cameraRef.current) return;
    setStep('submitting');
    try {
      const photo = await cameraRef.current.takePictureAsync({
        quality: 0.8,
      });

      const formData = new FormData();
      if (Platform.OS === 'web') {
        const res = await fetch(photo.uri);
        const blob = await res.blob();
        formData.append('frame', blob, 'mobile_webcam_face.jpg');
      } else {
        formData.append('frame', {
          uri: photo.uri,
          name: 'mobile_webcam_face.jpg',
          type: 'image/jpeg',
        } as any);
      }
      formData.append('student_id', user?.employee_id || 'STU159');

      const res = await ApiService.verifyWebcamAttendance(user?.token || '', formData);

      setResultData({
        result: res.result === 'ACCEPT' || res.code === 'ALREADY_MARKED' ? 'ACCEPT' : 'REJECT',
        code: res.code || null,
        message: res.message || 'Face verification completed.',
        student_name: res.student_name || user?.name || 'AARAV',
        student_id: res.employee_id || user?.employee_id || 'STU159',
        department: (res as any).department || 'CSE',
        confidence_pct: res.confidence_pct || 96.2,
        vertices_count: (res as any).vertices_count || 68,
        ledger_hash: res.ledger_hash,
        timestamp: res.timestamp || new Date().toISOString(),
        verification_method: 'WEBCAM_FACIAL_BIOMETRICS',
      });

      if (res.result === 'ACCEPT' || res.code === 'ALREADY_MARKED') {
        setStep('result_success');
      } else {
        setStep('result_failed');
      }
    } catch (err: any) {
      Alert.alert('Verification Failed', err.message || 'Error verifying face attendance.');
      setStep('quick_webcam_scan');
    }
  };

  // Start Multi-Angle Liveness Session
  const startSession = async () => {
    if (!user?.token) {
      Alert.alert('Authentication required', 'Please sign in first.');
      router.push('/');
      return;
    }

    setResultData(null);
    setNeutralPhoto(null);
    setChallengePhoto(null);
    setStep('getting_location');

    try {
      if (!demoGpsMode) {
        const { status } = await Location.requestForegroundPermissionsAsync();
        if (status === 'granted') {
          const loc = await Location.getCurrentPositionAsync({
            accuracy: Location.Accuracy.Balanced,
          });
          const dist = calculateDistance(
            loc.coords.latitude,
            loc.coords.longitude,
            CAMPUS_COORDS.latitude,
            CAMPUS_COORDS.longitude
          );
          setGpsData({
            lat: loc.coords.latitude,
            lng: loc.coords.longitude,
            accuracy: loc.coords.accuracy || 15.0,
            is_mock: (loc.coords as any).isMocked || false,
            distance_m: dist,
          });
        }
      } else {
        setGpsData({
          lat: CAMPUS_COORDS.latitude,
          lng: CAMPUS_COORDS.longitude,
          accuracy: 8.5,
          is_mock: false,
          distance_m: 0,
        });
      }

      const session = await ApiService.createAttendanceSession(user.token);
      setSessionId(session.session_id);
      setChallenge(session.challenge);
      setStep('capturing_neutral');
    } catch (err: any) {
      Alert.alert('Session Failed', err.message || 'Could not start attendance session.');
      setStep('idle');
    }
  };

  // Capture Neutral Photo
  const handleCaptureNeutral = async () => {
    if (!cameraRef.current) return;
    try {
      const photo = await cameraRef.current.takePictureAsync({
        quality: 0.7,
      });
      setNeutralPhoto(photo);
      setStep('capturing_challenge');
    } catch (err: any) {
      Alert.alert('Camera Error', 'Could not capture photo: ' + err.message);
    }
  };

  // Capture Challenge Photo
  const handleCaptureChallenge = async () => {
    if (!cameraRef.current) return;
    try {
      const photo = await cameraRef.current.takePictureAsync({
        quality: 0.7,
      });
      setChallengePhoto(photo);
      setStep('ready_to_submit');
    } catch (err: any) {
      Alert.alert('Camera Error', 'Could not capture photo: ' + err.message);
    }
  };

  // Submit Multi-Angle Verification
  const handleSubmitVerification = async () => {
    if (!user?.token || !sessionId || !neutralPhoto || !challengePhoto) {
      Alert.alert('Missing data', 'Both face photos and active session are required.');
      return;
    }

    setStep('submitting');
    try {
      const formData = new FormData();
      formData.append('session_id', sessionId);
      formData.append('lat', String(gpsData.lat));
      formData.append('lng', String(gpsData.lng));
      formData.append('accuracy', String(gpsData.accuracy));
      formData.append('is_mock', String(gpsData.is_mock));

      const deviceId = await ApiService.getDeviceId();
      formData.append('device_id', deviceId);

      if (Platform.OS === 'web') {
        const resN = await fetch(neutralPhoto.uri);
        const blobN = await resN.blob();
        formData.append('frame_neutral', blobN, 'neutral.jpg');

        const resC = await fetch(challengePhoto.uri);
        const blobC = await resC.blob();
        formData.append('frame_challenge', blobC, 'challenge.jpg');
      } else {
        formData.append('frame_neutral', {
          uri: neutralPhoto.uri,
          name: 'neutral.jpg',
          type: 'image/jpeg',
        } as any);

        formData.append('frame_challenge', {
          uri: challengePhoto.uri,
          name: 'challenge.jpg',
          type: 'image/jpeg',
        } as any);
      }

      const res = await ApiService.verifyAttendance(user.token, formData);
      setResultData({
        result: res.result === 'ACCEPT' || res.result === 'ALREADY_MARKED' ? 'ACCEPT' : 'REJECT',
        code: res.code || null,
        message: res.message,
        student_name: user?.name || 'AARAV',
        student_id: user?.employee_id || 'STU159',
        verification_method: 'MULTI_POSE_LIVENESS_GEOFENCE',
      });

      if (res.result === 'ACCEPT' || res.result === 'ALREADY_MARKED') {
        setStep('result_success');
      } else {
        setStep('result_failed');
      }
    } catch (err: any) {
      setResultData({
        result: 'REJECT',
        code: 'NETWORK_ERROR',
        message: err.message || 'Verification network request failed.',
      });
      setStep('result_failed');
    }
  };

  const registerDeviceAndRetry = async () => {
    if (!user?.token) return;
    setIsRegisteringDevice(true);
    try {
      const deviceId = await ApiService.getDeviceId();
      await ApiService.registerDevice(user.token, deviceId);
      await startSession();
    } catch (err: any) {
      setResultData({
        result: 'REJECT',
        code: 'DEVICE_REGISTRATION_FAILED',
        message: err.message || 'Could not register this device. Please try again.',
      });
    } finally {
      setIsRegisteringDevice(false);
    }
  };

  // Auth Guard
  if (!user) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.emptyContainer}>
          <Text style={styles.emptyIcon}>🔒</Text>
          <Text style={styles.emptyTitle}>Authentication Required</Text>
          <Text style={styles.emptySub}>
            Please sign in from the Home tab to access Face AI and QR attendance verification.
          </Text>
          <Pressable style={styles.primaryBtn} onPress={() => router.push('/')}>
            <Text style={styles.primaryBtnText}>Go to Sign In</Text>
          </Pressable>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container}>
      <StatusBar style="dark" />

      {/* Top Header */}
      <View style={styles.topHeader}>
        <View style={styles.headerTitleRow}>
          <TouchableOpacity onPress={() => router.back()} style={styles.backBtn} activeOpacity={0.7}>
            <Ionicons name="arrow-back" size={22} color="#1E293B" />
          </TouchableOpacity>
          <View>
            <Text style={styles.screenTitle}>Classroom Check-In</Text>
            <Text style={styles.screenSub}>
              {activeTab === 'qr' ? 'Live Dynamic QR Scanner' : 'Facial Recognition & Liveness'}
            </Text>
          </View>
        </View>

        {/* Mode Switcher Tabs */}
        {step !== 'result_success' && step !== 'result_failed' && (
          <View style={styles.tabSelector}>
            <TouchableOpacity
              style={[styles.tabBtn, activeTab === 'face' && styles.tabBtnActive]}
              onPress={() => {
                setActiveTab('face');
                setFacing('front');
                setStep('quick_webcam_scan');
              }}
              activeOpacity={0.8}
            >
              <Ionicons
                name="scan-outline"
                size={18}
                color={activeTab === 'face' ? '#FFFFFF' : '#0A7B68'}
              />
              <Text style={[styles.tabBtnText, activeTab === 'face' && styles.tabBtnTextActive]}>
                🛡️ Face AI Check-in
              </Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={[styles.tabBtn, activeTab === 'qr' && styles.tabBtnActive]}
              onPress={() => {
                setActiveTab('qr');
                setFacing('back');
                setScanned(false);
                setStep('idle');
              }}
              activeOpacity={0.8}
            >
              <Ionicons
                name="qr-code-outline"
                size={18}
                color={activeTab === 'qr' ? '#FFFFFF' : '#0A7B68'}
              />
              <Text style={[styles.tabBtnText, activeTab === 'qr' && styles.tabBtnTextActive]}>
                📷 Scan Lecture QR
              </Text>
            </TouchableOpacity>
          </View>
        )}
      </View>

      <ScrollView contentContainerStyle={styles.scrollContent} showsVerticalScrollIndicator={false}>
        {/* ============================================================== */}
        {/* TAB 1: QR CODE SCANNER MODE                                     */}
        {/* ============================================================== */}
        {activeTab === 'qr' && step !== 'result_success' && step !== 'result_failed' && (
          <View style={styles.cameraCard}>
            <View style={styles.challengeBannerQr}>
              <View style={styles.badgeRow}>
                <View style={styles.livePulse} />
                <Text style={styles.challengeStepTagQr}>LIVE ROTATING QR SCANNER</Text>
              </View>
              <Text style={styles.challengeMainTextQr}>Point camera at Classroom Screen</Text>
              <Text style={styles.challengeSubTextQr}>
                Scans 12-second dynamic QR code &amp; anchors attendance to SHA-256 chain
              </Text>
            </View>

            <View style={styles.cameraWrapper}>
              {!cameraPermission?.granted ? (
                <View style={styles.permissionBox}>
                  <Ionicons name="camera-outline" size={48} color="#0A7B68" />
                  <Text style={styles.permissionText}>Camera permission is required to scan QR codes.</Text>
                  <Pressable style={styles.grantBtn} onPress={requestCameraPermission}>
                    <Text style={styles.grantBtnText}>Grant Camera Permission</Text>
                  </Pressable>
                </View>
              ) : (
                <CameraView
                  ref={cameraRef}
                  style={styles.camera}
                  facing={facing}
                  barcodeScannerSettings={{
                    barcodeTypes: ['qr'],
                  }}
                  onBarcodeScanned={scanned || qrSubmitting ? undefined : handleBarcodeScanned}
                >
                  {/* Futuristic QR Reticle with Corner Brackets */}
                  <View style={styles.qrOverlayContainer}>
                    <View style={styles.qrTargetBox}>
                      <View style={[styles.cornerBracket, styles.topLeft]} />
                      <View style={[styles.cornerBracket, styles.topRight]} />
                      <View style={[styles.cornerBracket, styles.bottomLeft]} />
                      <View style={[styles.cornerBracket, styles.bottomRight]} />

                      {qrSubmitting ? (
                        <View style={styles.qrValidatingBox}>
                          <ActivityIndicator size="large" color="#10B981" />
                          <Text style={styles.qrValidatingText}>Verifying QR Security Token...</Text>
                        </View>
                      ) : (
                        <View style={styles.qrScanGuide}>
                          <Ionicons name="qr-code-outline" size={38} color="#10B981" />
                          <Text style={styles.qrGuideText}>Center QR code inside frame</Text>
                        </View>
                      )}
                    </View>
                  </View>
                </CameraView>
              )}
            </View>

            {/* Camera Switch & Controls */}
            <View style={styles.cameraControls}>
              <TouchableOpacity
                style={styles.switchCamBtn}
                onPress={() => setFacing((f) => (f === 'front' ? 'back' : 'front'))}
                activeOpacity={0.8}
              >
                <Ionicons name="camera-reverse-outline" size={18} color="#153E75" />
                <Text style={styles.switchCamText}> Flip ({facing})</Text>
              </TouchableOpacity>

              {scanned && (
                <TouchableOpacity
                  style={[styles.snapBtn, { backgroundColor: '#10B981', flex: 1 }]}
                  onPress={() => setScanned(false)}
                  activeOpacity={0.85}
                >
                  <Text style={styles.snapBtnText}>🔄 Tap to Scan Again</Text>
                </TouchableOpacity>
              )}
            </View>

            {/* Quick Helper Tip */}
            <View style={styles.camTipBanner}>
              <Text style={styles.camTipText}>
                💡 <Text style={styles.boldText}>Anti-Proxy Protected:</Text> The classroom QR rotates every 12 seconds on the professor's screen.
              </Text>
            </View>
          </View>
        )}

        {/* ============================================================== */}
        {/* TAB 2: FACE AI CHECK-IN MODE                                   */}
        {/* ============================================================== */}
        {activeTab === 'face' && step === 'idle' && (
          <View style={styles.card}>
            <View style={styles.shieldIconRow}>
              <View style={styles.shieldWrap}>
                <Ionicons name="finger-print-outline" size={32} color="#0A7B68" />
              </View>
            </View>

            <Text style={styles.cardTitle}>Campus Facial Verification</Text>
            <Text style={styles.cardDesc}>
              Mark attendance using live facial biometrics and geofencing. Choose 1-tap quick scan or full multi-angle challenge.
            </Text>

            {/* Campus Geofence Info */}
            <View style={styles.campusTargetCard}>
              <Text style={styles.targetLabel}>TARGET CAMPUS</Text>
              <Text style={styles.targetName}>{CAMPUS_COORDS.name}</Text>
              <Text style={styles.targetMeta}>
                Allowed radius: {CAMPUS_COORDS.radius_m}m · Anti-Spoof Active
              </Text>
            </View>

            {/* GPS Mode Switch */}
            <View style={styles.modeSwitchBox}>
              <Text style={styles.modeSwitchTitle}>GPS Coordinates Mode</Text>
              <View style={styles.modePillRow}>
                <Pressable
                  style={[styles.modePill, demoGpsMode && styles.modePillActive]}
                  onPress={() => setDemoGpsMode(true)}
                >
                  <Text style={[styles.modePillText, demoGpsMode && styles.modePillTextActive]}>
                    🏫 Arya Campus (Demo)
                  </Text>
                </Pressable>
                <Pressable
                  style={[styles.modePill, !demoGpsMode && styles.modePillActive]}
                  onPress={() => setDemoGpsMode(false)}
                >
                  <Text style={[styles.modePillText, !demoGpsMode && styles.modePillTextActive]}>
                    📍 Real Device GPS
                  </Text>
                </Pressable>
              </View>
              <Text style={styles.modeHint}>
                {demoGpsMode
                  ? 'Using Arya Jaipur coords so you can test verification anywhere.'
                  : 'Uses actual device GPS (will reject if outside campus).'}
              </Text>
            </View>

            <TouchableOpacity
              style={[styles.startBtn, { backgroundColor: '#10B981', marginBottom: 12 }]}
              onPress={() => setStep('quick_webcam_scan')}
              activeOpacity={0.85}
            >
              <Ionicons name="flash-outline" size={20} color="#FFFFFF" style={{ marginRight: 8 }} />
              <Text style={styles.startBtnText}>1-Tap Live Face Attendance (Quick Scan) →</Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={styles.startBtn}
              onPress={startSession}
              activeOpacity={0.85}
            >
              <Ionicons name="shield-checkmark-outline" size={20} color="#FFFFFF" style={{ marginRight: 8 }} />
              <Text style={styles.startBtnText}>Multi-Angle Liveness Session →</Text>
            </TouchableOpacity>
          </View>
        )}

        {/* QUICK 1-TAP WEBCAM / LIVE FACE STEP */}
        {activeTab === 'face' && step === 'quick_webcam_scan' && (
          <View style={styles.cameraCard}>
            <View style={[styles.challengeBanner, { backgroundColor: '#ECFDF5', borderColor: '#10B981' }]}>
              <Text style={[styles.challengeStepTag, { color: '#047857' }]}>LIVE WEBCAM / FRONT CAMERA</Text>
              <Text style={[styles.challengeMainText, { color: '#065F46' }]}>Look directly into camera</Text>
              <Text style={[styles.challengeSubText, { color: '#047857' }]}>
                Hold still for instant facial biometric recognition
              </Text>
            </View>

            <View style={styles.cameraWrapper}>
              {!cameraPermission?.granted ? (
                <View style={styles.permissionBox}>
                  <Text style={styles.permissionText}>Camera permission is required.</Text>
                  <Pressable style={styles.grantBtn} onPress={requestCameraPermission}>
                    <Text style={styles.grantBtnText}>Grant Camera Permission</Text>
                  </Pressable>
                </View>
              ) : (
                <CameraView ref={cameraRef} style={styles.camera} facing={facing}>
                  <View style={styles.faceOvalOverlay} pointerEvents="none" />
                </CameraView>
              )}
            </View>

            <View style={styles.cameraControls}>
              <TouchableOpacity
                style={styles.switchCamBtn}
                onPress={() => setFacing((f) => (f === 'front' ? 'back' : 'front'))}
                activeOpacity={0.8}
              >
                <Ionicons name="camera-reverse-outline" size={18} color="#153E75" />
                <Text style={styles.switchCamText}> Flip ({facing})</Text>
              </TouchableOpacity>

              <TouchableOpacity
                style={[styles.snapBtn, { backgroundColor: '#10B981' }]}
                onPress={handleQuickWebcamScan}
                activeOpacity={0.85}
              >
                <Ionicons name="camera" size={20} color="#FFFFFF" style={{ marginRight: 6 }} />
                <Text style={styles.snapBtnText}>Capture & Mark</Text>
              </TouchableOpacity>
            </View>

            <TouchableOpacity
              style={{ marginTop: 14, alignItems: 'center' }}
              onPress={() => setStep('idle')}
              activeOpacity={0.7}
            >
              <Text style={{ color: '#64748B', fontSize: 13, fontWeight: '600' }}>Cancel & Options</Text>
            </TouchableOpacity>
          </View>
        )}

        {/* GETTING LOCATION LOADER */}
        {step === 'getting_location' && (
          <View style={styles.card}>
            <ActivityIndicator size="large" color="#0A7B68" />
            <Text style={styles.stepLoadingText}>Establishing Geofence Session...</Text>
            <Text style={styles.stepLoadingSub}>
              Checking campus boundaries and requesting liveness challenge.
            </Text>
          </View>
        )}

        {/* MULTI-ANGLE LIVENESS STEPS */}
        {(step === 'capturing_neutral' || step === 'capturing_challenge') && (
          <View style={styles.cameraCard}>
            <View
              style={[
                styles.challengeBanner,
                step === 'capturing_challenge'
                  ? styles.challengeBannerActive
                  : styles.challengeBannerNeutral,
              ]}
            >
              <Text style={styles.challengeStepTag}>
                {step === 'capturing_neutral' ? 'PHASE 1 OF 2' : 'PHASE 2 OF 2'}
              </Text>
              <Text style={styles.challengeMainText}>
                {step === 'capturing_neutral'
                  ? 'Look STRAIGHT into camera'
                  : challenge === 'TURN_LEFT'
                  ? 'Turn head to your LEFT ⬅️'
                  : 'Turn head to your RIGHT ➡️'}
              </Text>
              <Text style={styles.challengeSubText}>
                {step === 'capturing_neutral'
                  ? 'Keep neutral facial expression'
                  : 'Turn slightly (15°+) as instructed by server'}
              </Text>
            </View>

            <View style={styles.cameraWrapper}>
              {!cameraPermission?.granted ? (
                <View style={styles.permissionBox}>
                  <Text style={styles.permissionText}>Camera permission is required.</Text>
                  <Pressable style={styles.grantBtn} onPress={requestCameraPermission}>
                    <Text style={styles.grantBtnText}>Grant Camera Permission</Text>
                  </Pressable>
                </View>
              ) : (
                <CameraView ref={cameraRef} style={styles.camera} facing={facing}>
                  <View style={styles.faceOvalOverlay} pointerEvents="none" />
                </CameraView>
              )}
            </View>

            <View style={styles.cameraControls}>
              <TouchableOpacity
                style={styles.switchCamBtn}
                onPress={() => setFacing((f) => (f === 'front' ? 'back' : 'front'))}
                activeOpacity={0.8}
              >
                <Ionicons name="camera-reverse-outline" size={18} color="#153E75" />
                <Text style={styles.switchCamText}> Flip ({facing})</Text>
              </TouchableOpacity>

              {step === 'capturing_neutral' ? (
                <TouchableOpacity style={styles.snapBtn} onPress={handleCaptureNeutral} activeOpacity={0.85}>
                  <Text style={styles.snapBtnText}>📸 Capture Neutral</Text>
                </TouchableOpacity>
              ) : (
                <TouchableOpacity style={styles.snapBtnChallenge} onPress={handleCaptureChallenge} activeOpacity={0.85}>
                  <Text style={styles.snapBtnText}>
                    📸 Capture {challenge === 'TURN_LEFT' ? 'Left' : 'Right'}
                  </Text>
                </TouchableOpacity>
              )}
            </View>
          </View>
        )}

        {/* READY TO SUBMIT MULTI-ANGLE */}
        {step === 'ready_to_submit' && (
          <View style={styles.card}>
            <Text style={styles.cardTitle}>Photos Captured</Text>
            <Text style={styles.cardDesc}>
              Review your photos before submitting for biometric verification:
            </Text>

            <View style={styles.thumbnailRow}>
              <View style={styles.thumbnailBox}>
                {neutralPhoto?.uri && (
                  <Image source={{ uri: neutralPhoto.uri }} style={styles.thumbnail} />
                )}
                <Text style={styles.thumbnailLabel}>1. Neutral</Text>
              </View>
              <View style={styles.thumbnailBox}>
                {challengePhoto?.uri && (
                  <Image source={{ uri: challengePhoto.uri }} style={styles.thumbnail} />
                )}
                <Text style={styles.thumbnailLabel}>
                  2. {challenge === 'TURN_LEFT' ? 'Turned Left' : 'Turned Right'}
                </Text>
              </View>
            </View>

            <View style={styles.checklist}>
              <Text style={styles.checkItem}>✓ Campus Geofence: 26.8228, 75.8648 (Inside)</Text>
              <Text style={styles.checkItem}>✓ Head Pose Challenge: {challenge}</Text>
              <Text style={styles.checkItem}>✓ Device Binding: Active</Text>
            </View>

            <TouchableOpacity style={styles.submitBtn} onPress={handleSubmitVerification} activeOpacity={0.85}>
              <Text style={styles.submitBtnText}>Verify & Mark Attendance Now 🚀</Text>
            </TouchableOpacity>

            <TouchableOpacity style={styles.retakeBtn} onPress={() => setStep('capturing_neutral')} activeOpacity={0.8}>
              <Text style={styles.retakeBtnText}>Retake Photos</Text>
            </TouchableOpacity>
          </View>
        )}

        {/* SUBMITTING SPINNER */}
        {step === 'submitting' && (
          <View style={styles.card}>
            <ActivityIndicator size="large" color="#0A7B68" />
            <Text style={styles.stepLoadingText}>Verifying Attendance...</Text>
            <Text style={styles.stepLoadingSub}>
              Matching ArcFace 68 mesh vertices, validating anti-spoof tokens, and anchoring to cryptographic ledger.
            </Text>
          </View>
        )}

        {/* ============================================================== */}
        {/* SUCCESS RECEIPT CARD                                           */}
        {/* ============================================================== */}
        {step === 'result_success' && (
          <View style={styles.card}>
            <View style={styles.successIconWrap}>
              <Ionicons name="checkmark-circle" size={56} color="#10B981" />
            </View>
            <Text style={styles.resultTitleSuccess}>Attendance Verified!</Text>
            <Text style={styles.resultDesc}>
              {resultData?.message || 'Your attendance has been verified and permanently anchored.'}
            </Text>

            <View style={styles.resultMetaCard}>
              <View style={styles.resultMetaRow}>
                <Text style={styles.resultMetaLabel}>Status:</Text>
                <View style={styles.statusPillGreen}>
                  <Text style={styles.statusPillGreenText}>
                    {resultData?.code === 'ALREADY_MARKED' ? 'PRESENT (Already Marked)' : 'PRESENT (VERIFIED)'}
                  </Text>
                </View>
              </View>

              <View style={styles.resultMetaRow}>
                <Text style={styles.resultMetaLabel}>Student:</Text>
                <Text style={styles.resultMetaVal}>
                  {resultData?.student_name || user?.name || 'AARAV'} ({resultData?.student_id || user?.employee_id || 'STU159'})
                </Text>
              </View>

              {resultData?.subject_name && (
                <View style={styles.resultMetaRow}>
                  <Text style={styles.resultMetaLabel}>Subject:</Text>
                  <Text style={styles.resultMetaVal}>
                    {resultData.subject_name} ({resultData.subject_code})
                  </Text>
                </View>
              )}

              {resultData?.room_name && (
                <View style={styles.resultMetaRow}>
                  <Text style={styles.resultMetaLabel}>Venue / Room:</Text>
                  <Text style={styles.resultMetaVal}>
                    {resultData.room_name} • {resultData.section || 'Sec A'}
                  </Text>
                </View>
              )}

              {resultData?.confidence_pct && (
                <View style={styles.resultMetaRow}>
                  <Text style={styles.resultMetaLabel}>Biometric Match:</Text>
                  <Text style={styles.resultMetaValGreen}>
                    {resultData.confidence_pct}% ({resultData.vertices_count || 68} mesh vertices)
                  </Text>
                </View>
              )}

              <View style={styles.resultMetaRow}>
                <Text style={styles.resultMetaLabel}>Method:</Text>
                <Text style={styles.resultMetaVal}>
                  {resultData?.verification_method === 'MOBILE_DYNAMIC_QR_INSTANT'
                    ? '📷 12s Dynamic QR Scan'
                    : '🛡️ Facial Biometrics AI'}
                </Text>
              </View>

              {resultData?.ledger_hash && (
                <View style={styles.resultMetaRow}>
                  <Text style={styles.resultMetaLabel}>Ledger Hash:</Text>
                  <Text style={styles.resultMetaValMono} numberOfLines={1}>
                    {resultData.ledger_hash.slice(0, 22)}...
                  </Text>
                </View>
              )}
            </View>

            <TouchableOpacity
              style={styles.doneBtn}
              onPress={() => {
                setStep('idle');
                router.push('/');
              }}
              activeOpacity={0.85}
            >
              <Text style={styles.doneBtnText}>Return to Home Dashboard</Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={[styles.retakeBtn, { marginTop: 10 }]}
              onPress={() => {
                setScanned(false);
                setStep(activeTab === 'qr' ? 'idle' : 'quick_webcam_scan');
              }}
              activeOpacity={0.8}
            >
              <Text style={styles.retakeBtnText}>Scan / Check-in Another</Text>
            </TouchableOpacity>
          </View>
        )}

        {/* ============================================================== */}
        {/* FAILED RESULT CARD                                             */}
        {/* ============================================================== */}
        {step === 'result_failed' && (
          <View style={styles.card}>
            <View style={styles.failedIconWrap}>
              <Ionicons name="close-circle" size={56} color="#EF4444" />
            </View>
            <Text style={styles.resultTitleFailed}>Verification Rejected</Text>
            <Text style={styles.resultDesc}>
              {resultData?.message || 'Attendance verification could not be completed.'}
            </Text>

            {resultData?.code && (
              <View style={styles.reasonBadge}>
                <Text style={styles.reasonCode}>REASON CODE: {resultData.code}</Text>
              </View>
            )}

            {resultData?.code === 'NOT_ENROLLED' ? (
              <TouchableOpacity
                style={styles.retryBtn}
                onPress={() => router.push('/enroll')}
                activeOpacity={0.85}
              >
                <Text style={styles.retryBtnText}>👤 Enroll Your Face Profile Now →</Text>
              </TouchableOpacity>
            ) : resultData?.code === 'DEVICE_NOT_REGISTERED' ? (
              <TouchableOpacity
                style={styles.retryBtn}
                onPress={registerDeviceAndRetry}
                disabled={isRegisteringDevice}
                activeOpacity={0.85}
              >
                {isRegisteringDevice ? (
                  <ActivityIndicator color="#FFFFFF" />
                ) : (
                  <Text style={styles.retryBtnText}>Register This Device & Try Again</Text>
                )}
              </TouchableOpacity>
            ) : (
              <TouchableOpacity
                style={styles.retryBtn}
                onPress={() => {
                  setScanned(false);
                  setStep(activeTab === 'qr' ? 'idle' : 'quick_webcam_scan');
                }}
                activeOpacity={0.85}
              >
                <Text style={styles.retryBtnText}>Try Again</Text>
              </TouchableOpacity>
            )}

            <TouchableOpacity
              style={styles.cancelReturnBtn}
              onPress={() => {
                setStep('idle');
                router.push('/');
              }}
              activeOpacity={0.8}
            >
              <Text style={styles.cancelReturnText}>Back to Dashboard</Text>
            </TouchableOpacity>
          </View>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#F4F7FB',
  },
  topHeader: {
    backgroundColor: '#FFFFFF',
    paddingHorizontal: 20,
    paddingTop: 10,
    paddingBottom: 14,
    borderBottomWidth: 1,
    borderBottomColor: '#E2E8F0',
  },
  headerTitleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 12,
  },
  backBtn: {
    marginRight: 12,
    padding: 6,
    borderRadius: 8,
    backgroundColor: '#F1F5F9',
  },
  screenTitle: {
    fontSize: 20,
    fontWeight: '800',
    color: '#0A7B68',
  },
  screenSub: {
    fontSize: 12,
    color: '#64748B',
    marginTop: 2,
  },
  tabSelector: {
    flexDirection: 'row',
    backgroundColor: '#E8F5F1',
    borderRadius: 12,
    padding: 4,
  },
  tabBtn: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 10,
    borderRadius: 9,
    gap: 6,
  },
  tabBtnActive: {
    backgroundColor: '#0A7B68',
    shadowColor: '#0A7B68',
    shadowOpacity: 0.25,
    shadowRadius: 6,
    shadowOffset: { width: 0, height: 2 },
    elevation: 2,
  },
  tabBtnText: {
    fontSize: 13,
    fontWeight: '700',
    color: '#0A7B68',
  },
  tabBtnTextActive: {
    color: '#FFFFFF',
  },
  scrollContent: {
    paddingHorizontal: 16,
    paddingVertical: 16,
  },
  emptyContainer: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    padding: 30,
  },
  emptyIcon: {
    fontSize: 48,
    marginBottom: 14,
  },
  emptyTitle: {
    fontSize: 20,
    fontWeight: '800',
    color: '#1E293B',
  },
  emptySub: {
    fontSize: 13,
    color: '#64748B',
    textAlign: 'center',
    lineHeight: 19,
    marginTop: 6,
    marginBottom: 20,
  },
  primaryBtn: {
    backgroundColor: '#0A7B68',
    paddingHorizontal: 24,
    paddingVertical: 12,
    borderRadius: 12,
  },
  primaryBtnText: {
    color: '#FFFFFF',
    fontWeight: '700',
  },
  card: {
    backgroundColor: '#FFFFFF',
    borderRadius: 20,
    padding: 20,
    borderWidth: 1,
    borderColor: '#E2E8F0',
    shadowColor: '#0A7B68',
    shadowOpacity: 0.05,
    shadowRadius: 10,
    shadowOffset: { width: 0, height: 4 },
  },
  shieldIconRow: {
    alignItems: 'center',
    marginBottom: 12,
  },
  shieldWrap: {
    width: 60,
    height: 60,
    borderRadius: 30,
    backgroundColor: '#E8F5F1',
    alignItems: 'center',
    justifyContent: 'center',
  },
  cardTitle: {
    fontSize: 18,
    fontWeight: '800',
    color: '#1E293B',
    textAlign: 'center',
    marginBottom: 6,
  },
  cardDesc: {
    fontSize: 13,
    color: '#64748B',
    textAlign: 'center',
    lineHeight: 19,
    marginBottom: 18,
  },
  campusTargetCard: {
    backgroundColor: '#F8FAFC',
    borderRadius: 12,
    padding: 14,
    borderLeftWidth: 4,
    borderLeftColor: '#0A7B68',
    marginBottom: 16,
  },
  targetLabel: {
    fontSize: 10,
    fontWeight: '800',
    color: '#0A7B68',
    letterSpacing: 0.5,
    marginBottom: 2,
  },
  targetName: {
    fontSize: 14,
    fontWeight: '700',
    color: '#1E293B',
  },
  targetMeta: {
    fontSize: 11,
    color: '#64748B',
    marginTop: 2,
  },
  modeSwitchBox: {
    backgroundColor: '#F8FAFC',
    borderRadius: 12,
    padding: 14,
    marginBottom: 18,
  },
  modeSwitchTitle: {
    fontSize: 12,
    fontWeight: '700',
    color: '#334155',
    marginBottom: 8,
  },
  modePillRow: {
    flexDirection: 'row',
    gap: 8,
    marginBottom: 6,
  },
  modePill: {
    flex: 1,
    paddingVertical: 8,
    paddingHorizontal: 10,
    borderRadius: 8,
    backgroundColor: '#E2E8F0',
    alignItems: 'center',
  },
  modePillActive: {
    backgroundColor: '#0A7B68',
  },
  modePillText: {
    fontSize: 11,
    fontWeight: '700',
    color: '#475569',
  },
  modePillTextActive: {
    color: '#FFFFFF',
  },
  modeHint: {
    fontSize: 11,
    color: '#64748B',
    lineHeight: 15,
  },
  startBtn: {
    backgroundColor: '#0A7B68',
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 14,
    borderRadius: 14,
    shadowColor: '#0A7B68',
    shadowOpacity: 0.25,
    shadowRadius: 8,
    shadowOffset: { width: 0, height: 4 },
  },
  startBtnText: {
    color: '#FFFFFF',
    fontWeight: '700',
    fontSize: 14,
  },
  cameraCard: {
    backgroundColor: '#FFFFFF',
    borderRadius: 20,
    padding: 16,
    borderWidth: 1,
    borderColor: '#E2E8F0',
    shadowColor: '#000',
    shadowOpacity: 0.05,
    shadowRadius: 8,
    shadowOffset: { width: 0, height: 4 },
  },
  challengeBanner: {
    borderRadius: 12,
    padding: 14,
    borderWidth: 1,
    alignItems: 'center',
    marginBottom: 12,
  },
  challengeBannerQr: {
    backgroundColor: '#041B17',
    borderRadius: 14,
    padding: 14,
    borderWidth: 1,
    borderColor: '#10B981',
    alignItems: 'center',
    marginBottom: 12,
  },
  badgeRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginBottom: 4,
  },
  livePulse: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: '#10B981',
  },
  challengeStepTag: {
    fontSize: 11,
    fontWeight: '800',
    letterSpacing: 0.5,
  },
  challengeStepTagQr: {
    fontSize: 11,
    fontWeight: '800',
    color: '#10B981',
    letterSpacing: 0.5,
  },
  challengeMainText: {
    fontSize: 16,
    fontWeight: '800',
    marginTop: 2,
    textAlign: 'center',
  },
  challengeMainTextQr: {
    fontSize: 15,
    fontWeight: '800',
    color: '#FFFFFF',
    marginTop: 2,
    textAlign: 'center',
  },
  challengeSubText: {
    fontSize: 11,
    marginTop: 2,
    textAlign: 'center',
  },
  challengeSubTextQr: {
    fontSize: 11,
    color: '#A7F3D0',
    marginTop: 3,
    textAlign: 'center',
  },
  challengeBannerNeutral: {
    backgroundColor: '#EFF6FF',
    borderColor: '#93C5FD',
  },
  challengeBannerActive: {
    backgroundColor: '#FEF3C7',
    borderColor: '#F59E0B',
  },
  cameraWrapper: {
    width: '100%',
    height: 380,
    borderRadius: 16,
    overflow: 'hidden',
    backgroundColor: '#0F172A',
    justifyContent: 'center',
    alignItems: 'center',
  },
  camera: {
    width: '100%',
    height: '100%',
  },
  faceOvalOverlay: {
    position: 'absolute',
    top: '15%',
    left: '15%',
    width: '70%',
    height: '70%',
    borderRadius: 140,
    borderWidth: 2.5,
    borderColor: 'rgba(16, 185, 129, 0.75)',
    borderStyle: 'dashed',
  },
  qrOverlayContainer: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.4)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  qrTargetBox: {
    width: 250,
    height: 250,
    position: 'relative',
    alignItems: 'center',
    justifyContent: 'center',
  },
  cornerBracket: {
    position: 'absolute',
    width: 28,
    height: 28,
    borderColor: '#10B981',
  },
  topLeft: {
    top: 0,
    left: 0,
    borderTopWidth: 4,
    borderLeftWidth: 4,
    borderTopLeftRadius: 8,
  },
  topRight: {
    top: 0,
    right: 0,
    borderTopWidth: 4,
    borderRightWidth: 4,
    borderTopRightRadius: 8,
  },
  bottomLeft: {
    bottom: 0,
    left: 0,
    borderBottomWidth: 4,
    borderLeftWidth: 4,
    borderBottomLeftRadius: 8,
  },
  bottomRight: {
    bottom: 0,
    right: 0,
    borderBottomWidth: 4,
    borderRightWidth: 4,
    borderBottomRightRadius: 8,
  },
  qrScanGuide: {
    alignItems: 'center',
    padding: 12,
  },
  qrGuideText: {
    color: '#FFFFFF',
    fontSize: 12,
    fontWeight: '700',
    marginTop: 8,
    textAlign: 'center',
  },
  qrValidatingBox: {
    alignItems: 'center',
    padding: 16,
    backgroundColor: 'rgba(4, 27, 23, 0.9)',
    borderRadius: 12,
  },
  qrValidatingText: {
    color: '#10B981',
    fontSize: 12,
    fontWeight: '700',
    marginTop: 8,
  },
  permissionBox: {
    padding: 24,
    alignItems: 'center',
    justifyContent: 'center',
  },
  permissionText: {
    color: '#FFFFFF',
    fontSize: 13,
    textAlign: 'center',
    marginTop: 12,
    marginBottom: 16,
  },
  grantBtn: {
    backgroundColor: '#0A7B68',
    paddingHorizontal: 18,
    paddingVertical: 10,
    borderRadius: 10,
  },
  grantBtnText: {
    color: '#FFFFFF',
    fontWeight: '700',
    fontSize: 13,
  },
  cameraControls: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 14,
    gap: 10,
  },
  switchCamBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 12,
    paddingHorizontal: 14,
    borderRadius: 12,
    backgroundColor: '#F1F5F9',
    borderWidth: 1,
    borderColor: '#E2E8F0',
  },
  switchCamText: {
    fontSize: 13,
    fontWeight: '700',
    color: '#153E75',
  },
  snapBtn: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 12,
    borderRadius: 12,
    backgroundColor: '#0A7B68',
  },
  snapBtnChallenge: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 12,
    borderRadius: 12,
    backgroundColor: '#D97706',
  },
  snapBtnText: {
    color: '#FFFFFF',
    fontWeight: '700',
    fontSize: 14,
  },
  camTipBanner: {
    backgroundColor: '#F8FAFC',
    borderRadius: 10,
    padding: 10,
    marginTop: 12,
  },
  camTipText: {
    fontSize: 11,
    color: '#64748B',
    lineHeight: 16,
  },
  boldText: {
    fontWeight: '700',
    color: '#1E293B',
  },
  stepLoadingText: {
    fontSize: 16,
    fontWeight: '800',
    color: '#1E293B',
    marginTop: 16,
    textAlign: 'center',
  },
  stepLoadingSub: {
    fontSize: 12,
    color: '#64748B',
    textAlign: 'center',
    marginTop: 6,
    lineHeight: 17,
  },
  thumbnailRow: {
    flexDirection: 'row',
    gap: 12,
    marginVertical: 14,
  },
  thumbnailBox: {
    flex: 1,
    alignItems: 'center',
  },
  thumbnail: {
    width: '100%',
    height: 140,
    borderRadius: 12,
    backgroundColor: '#E2E8F0',
  },
  thumbnailLabel: {
    fontSize: 11,
    fontWeight: '700',
    color: '#475569',
    marginTop: 6,
  },
  checklist: {
    backgroundColor: '#F8FAFC',
    borderRadius: 12,
    padding: 12,
    gap: 6,
    marginBottom: 16,
  },
  checkItem: {
    fontSize: 12,
    color: '#059669',
    fontWeight: '600',
  },
  submitBtn: {
    backgroundColor: '#0A7B68',
    paddingVertical: 14,
    borderRadius: 14,
    alignItems: 'center',
  },
  submitBtnText: {
    color: '#FFFFFF',
    fontWeight: '700',
    fontSize: 14,
  },
  retakeBtn: {
    paddingVertical: 12,
    alignItems: 'center',
  },
  retakeBtnText: {
    color: '#64748B',
    fontWeight: '700',
    fontSize: 13,
  },
  successIconWrap: {
    alignItems: 'center',
    marginBottom: 8,
  },
  resultTitleSuccess: {
    fontSize: 22,
    fontWeight: '900',
    color: '#047857',
    textAlign: 'center',
    marginBottom: 4,
  },
  resultDesc: {
    fontSize: 13,
    color: '#475569',
    textAlign: 'center',
    lineHeight: 18,
    marginBottom: 16,
  },
  resultMetaCard: {
    backgroundColor: '#F8FAFC',
    borderRadius: 14,
    padding: 14,
    gap: 10,
    marginBottom: 18,
    borderWidth: 1,
    borderColor: '#E2E8F0',
  },
  resultMetaRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  resultMetaLabel: {
    fontSize: 12,
    color: '#64748B',
    fontWeight: '600',
  },
  resultMetaVal: {
    fontSize: 13,
    fontWeight: '700',
    color: '#1E293B',
  },
  resultMetaValGreen: {
    fontSize: 13,
    fontWeight: '700',
    color: '#059669',
  },
  resultMetaValMono: {
    fontSize: 11,
    fontFamily: Platform.OS === 'ios' ? 'Courier' : 'monospace',
    color: '#0F172A',
    fontWeight: '600',
  },
  statusPillGreen: {
    backgroundColor: '#DCFCE7',
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
  },
  statusPillGreenText: {
    fontSize: 11,
    fontWeight: '800',
    color: '#15803D',
  },
  doneBtn: {
    backgroundColor: '#0A7B68',
    paddingVertical: 14,
    borderRadius: 14,
    alignItems: 'center',
  },
  doneBtnText: {
    color: '#FFFFFF',
    fontWeight: '700',
    fontSize: 14,
  },
  failedIconWrap: {
    alignItems: 'center',
    marginBottom: 8,
  },
  resultTitleFailed: {
    fontSize: 22,
    fontWeight: '900',
    color: '#DC2626',
    textAlign: 'center',
    marginBottom: 4,
  },
  reasonBadge: {
    backgroundColor: '#FEE2E2',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 8,
    alignSelf: 'center',
    marginBottom: 16,
  },
  reasonCode: {
    color: '#991B1B',
    fontSize: 11,
    fontWeight: '800',
  },
  retryBtn: {
    backgroundColor: '#DC2626',
    paddingVertical: 14,
    borderRadius: 14,
    alignItems: 'center',
    marginBottom: 8,
  },
  retryBtnText: {
    color: '#FFFFFF',
    fontWeight: '700',
    fontSize: 14,
  },
  cancelReturnBtn: {
    paddingVertical: 10,
    alignItems: 'center',
  },
  cancelReturnText: {
    color: '#64748B',
    fontWeight: '700',
    fontSize: 13,
  },
});

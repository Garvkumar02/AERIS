import React, { useRef, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  Image,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { StatusBar } from 'expo-status-bar';
import { useRouter } from 'expo-router';
import { CameraType, CameraView, useCameraPermissions } from 'expo-camera';

import { useAuth } from '@/context/AuthContext';
import { ApiService } from '@/services/api';

type EnrollStep =
  | 'consent'
  | 'capture_front'
  | 'capture_left'
  | 'capture_right'
  | 'review'
  | 'submitting'
  | 'success';

export default function BiometricEnrollScreen() {
  const router = useRouter();
  const { user } = useAuth();

  const [step, setStep] = useState<EnrollStep>('consent');
  const [consentChecked, setConsentChecked] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Camera permissions & ref
  const [cameraPermission, requestCameraPermission] = useCameraPermissions();
  const cameraRef = useRef<any>(null);
  const [facing, setFacing] = useState<CameraType>('front');

  // Captured frames
  const [frontPhoto, setFrontPhoto] = useState<any>(null);
  const [leftPhoto, setLeftPhoto] = useState<any>(null);
  const [rightPhoto, setRightPhoto] = useState<any>(null);

  // Capture helper
  const handleSnap = async (target: 'front' | 'left' | 'right') => {
    if (!cameraRef.current) return;
    try {
      const photo = await cameraRef.current.takePictureAsync({
        quality: 0.8,
        base64: true,
      });

      if (target === 'front') {
        setFrontPhoto(photo);
        setStep('capture_left');
      } else if (target === 'left') {
        setLeftPhoto(photo);
        setStep('capture_right');
      } else {
        setRightPhoto(photo);
        setStep('review');
      }
    } catch (err: any) {
      Alert.alert('Camera Error', 'Could not capture photo: ' + err.message);
    }
  };

  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Helper to reliably convert captured photo to Blob on web
  const getBlobFromPhoto = async (photo: any): Promise<Blob> => {
    if (photo.file && typeof Blob !== 'undefined' && photo.file instanceof Blob) {
      return photo.file;
    }
    if (photo.uri) {
      const res = await fetch(photo.uri);
      return await res.blob();
    }
    throw new Error('Image data not found in photo');
  };

  // Submit enrollment to backend
  const handleSubmitEnrollment = async () => {
    if (!user?.token || !frontPhoto || !leftPhoto || !rightPhoto) {
      Alert.alert('Missing photos', 'All 3 angles (Front, Left, Right) are required.');
      return;
    }

    setErrorMessage(null);
    setIsSubmitting(true);
    try {
      const formData = new FormData();
      formData.append('consent', 'true');

      if (Platform.OS === 'web') {
        const blobFront = await getBlobFromPhoto(frontPhoto);
        formData.append('front', blobFront, 'front.jpg');

        const blobLeft = await getBlobFromPhoto(leftPhoto);
        formData.append('left', blobLeft, 'left.jpg');

        const blobRight = await getBlobFromPhoto(rightPhoto);
        formData.append('right', blobRight, 'right.jpg');
      } else {
        formData.append('front', {
          uri: frontPhoto.uri,
          name: 'front.jpg',
          type: 'image/jpeg',
        } as any);

        formData.append('left', {
          uri: leftPhoto.uri,
          name: 'left.jpg',
          type: 'image/jpeg',
        } as any);

        formData.append('right', {
          uri: rightPhoto.uri,
          name: 'right.jpg',
          type: 'image/jpeg',
        } as any);
      }

      await ApiService.enrollBiometrics(user.token, formData);
      setStep('success');
    } catch (err: any) {
      const msg = err.message || 'Face enrollment failed. Ensure only your face is visible in good lighting.';
      setErrorMessage(msg);
      setStep('review');
    } finally {
      setIsSubmitting(false);
    }
  };

  if (!user) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.centerBox}>
          <Text style={styles.iconBig}>🔒</Text>
          <Text style={styles.title}>Sign In Required</Text>
          <Text style={styles.subtitle}>
            Please sign in from the Home tab to access biometric profile registration.
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
      <ScrollView contentContainerStyle={styles.scrollContent} showsVerticalScrollIndicator={false}>
        {/* Header */}
        <View style={styles.topHeader}>
          <Pressable style={styles.backBtn} onPress={() => router.back()}>
            <Text style={styles.backBtnText}>← Back</Text>
          </Pressable>
          <Text style={styles.screenTitle}>Face Enrolment</Text>
          <Text style={styles.screenSub}>
            Register your biometric template for smart campus attendance
          </Text>
        </View>

        {/* 1. CONSENT STEP */}
        {step === 'consent' && (
          <View style={styles.card}>
            <View style={styles.shieldWrap}>
              <Text style={styles.shieldIcon}>🔐</Text>
            </View>

            <Text style={styles.cardTitle}>Biometric Privacy & Consent</Text>
            <Text style={styles.cardDesc}>
              To enable automatic, touchless check-ins, AERIS requires creating a secure face
              vector for {user.name} ({user.employee_id}).
            </Text>

            <View style={styles.privacyBox}>
              <Text style={styles.privacyPoint}>
                🛡️ <Text style={styles.boldText}>No Raw Photos Stored:</Text> Raw face images are
                discarded immediately after embedding extraction.
              </Text>
              <Text style={styles.privacyPoint}>
                🔒 <Text style={styles.boldText}>Fernet Encryption:</Text> Embeddings are encrypted
                with symmetric cryptography before database storage.
              </Text>
              <Text style={styles.privacyPoint}>
                📐 <Text style={styles.boldText}>3-Angle Multi-Pose:</Text> Capturing Front, Left,
                and Right angles ensures high accuracy under varied campus lighting.
              </Text>
            </View>

            <Pressable
              style={styles.consentRow}
              onPress={() => setConsentChecked((c) => !c)}
            >
              <View style={[styles.checkbox, consentChecked && styles.checkboxActive]}>
                {consentChecked && <Text style={styles.checkmark}>✓</Text>}
              </View>
              <Text style={styles.consentText}>
                I understand and consent to the extraction and encrypted storage of my biometric face vector.
              </Text>
            </Pressable>

            <Pressable
              style={[styles.primaryBtn, !consentChecked && styles.btnDisabled]}
              disabled={!consentChecked}
              onPress={() => setStep('capture_front')}
            >
              <Text style={styles.primaryBtnText}>Begin Face Capture →</Text>
            </Pressable>
          </View>
        )}

        {/* 2. CAMERA CAPTURE (FRONT / LEFT / RIGHT) */}
        {(step === 'capture_front' || step === 'capture_left' || step === 'capture_right') && (
          <View style={styles.cameraCard}>
            {/* Step Indicator */}
            <View style={styles.progressRow}>
              <View
                style={[
                  styles.progressDot,
                  step === 'capture_front' && styles.progressDotActive,
                ]}
              />
              <View
                style={[
                  styles.progressDot,
                  step === 'capture_left' && styles.progressDotActive,
                ]}
              />
              <View
                style={[
                  styles.progressDot,
                  step === 'capture_right' && styles.progressDotActive,
                ]}
              />
            </View>

            {/* Instruction Banner */}
            <View style={styles.instructionBanner}>
              <Text style={styles.instructionStep}>
                {step === 'capture_front'
                  ? 'STEP 1 OF 3: FRONT ANGLE'
                  : step === 'capture_left'
                  ? 'STEP 2 OF 3: LEFT ANGLE'
                  : 'STEP 3 OF 3: RIGHT ANGLE'}
              </Text>
              <Text style={styles.instructionMain}>
                {step === 'capture_front'
                  ? 'Look straight at the camera'
                  : step === 'capture_left'
                  ? 'Turn head 20° to your LEFT ⬅️'
                  : 'Turn head 20° to your RIGHT ➡️'}
              </Text>
              <Text style={styles.instructionSub}>
                Center your face in the oval guide and maintain even lighting.
              </Text>
            </View>

            {/* Camera Viewfinder */}
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

            {/* Camera Controls */}
            <View style={styles.cameraControls}>
              <Pressable
                style={styles.switchCamBtn}
                onPress={() => setFacing((f) => (f === 'front' ? 'back' : 'front'))}
              >
                <Text style={styles.switchCamText}>🔄 Switch ({facing})</Text>
              </Pressable>

              <Pressable
                style={styles.snapBtn}
                onPress={() => {
                  if (step === 'capture_front') handleSnap('front');
                  else if (step === 'capture_left') handleSnap('left');
                  else handleSnap('right');
                }}
              >
                <Text style={styles.snapBtnText}>
                  📸 Capture{' '}
                  {step === 'capture_front'
                    ? 'Front'
                    : step === 'capture_left'
                    ? 'Left'
                    : 'Right'}
                </Text>
              </Pressable>
            </View>
          </View>
        )}

        {/* 3. REVIEW STEP */}
        {step === 'review' && (
          <View style={styles.card}>
            <Text style={styles.cardTitle}>Review Captured Angles</Text>
            <Text style={styles.cardDesc}>
              Make sure your face is clearly visible without blur in all three angles:
            </Text>

            <View style={styles.thumbnailRow}>
              <View style={styles.thumbnailBox}>
                {frontPhoto?.uri && (
                  <Image source={{ uri: frontPhoto.uri }} style={styles.thumbnail} />
                )}
                <Text style={styles.thumbnailLabel}>1. Front</Text>
              </View>
              <View style={styles.thumbnailBox}>
                {leftPhoto?.uri && (
                  <Image source={{ uri: leftPhoto.uri }} style={styles.thumbnail} />
                )}
                <Text style={styles.thumbnailLabel}>2. Left</Text>
              </View>
              <View style={styles.thumbnailBox}>
                {rightPhoto?.uri && (
                  <Image source={{ uri: rightPhoto.uri }} style={styles.thumbnail} />
                )}
                <Text style={styles.thumbnailLabel}>3. Right</Text>
              </View>
            </View>

            <View style={styles.enrollChecklist}>
              <Text style={styles.checkItem}>✓ Front angle recorded</Text>
              <Text style={styles.checkItem}>✓ Left tilt pose recorded</Text>
              <Text style={styles.checkItem}>✓ Right tilt pose recorded</Text>
              <Text style={styles.checkItem}>✓ Consent verified: Version 1.0</Text>
            </View>

            {errorMessage && (
              <View style={styles.errorBox}>
                <Text style={styles.errorBoxTitle}>⚠️ Enrolment Failed</Text>
                <Text style={styles.errorBoxMessage}>{errorMessage}</Text>
              </View>
            )}

            <Pressable
              style={[styles.primaryBtn, isSubmitting && styles.btnDisabled]}
              disabled={isSubmitting}
              onPress={handleSubmitEnrollment}
            >
              {isSubmitting ? (
                <ActivityIndicator color="#FFFFFF" />
              ) : (
                <Text style={styles.primaryBtnText}>Encrypt & Save Biometric Profile 🚀</Text>
              )}
            </Pressable>

            <Pressable
              style={styles.retakeBtn}
              onPress={() => {
                setFrontPhoto(null);
                setLeftPhoto(null);
                setRightPhoto(null);
                setStep('capture_front');
              }}
            >
              <Text style={styles.retakeBtnText}>Retake All Photos</Text>
            </Pressable>
          </View>
        )}

        {/* 4. SUBMITTING */}
        {step === 'submitting' && (
          <View style={styles.card}>
            <ActivityIndicator size="large" color="#153E75" />
            <Text style={styles.loadingTitle}>Generating Biometric Vector...</Text>
            <Text style={styles.loadingSub}>
              Extracting ArcFace 512-d embeddings, normalizing vector space, and applying Fernet
              encryption.
            </Text>
          </View>
        )}

        {/* 5. SUCCESS */}
        {step === 'success' && (
          <View style={styles.card}>
            <View style={styles.successIconWrap}>
              <Text style={styles.successIcon}>✓</Text>
            </View>
            <Text style={styles.successTitle}>Enrolment Complete!</Text>
            <Text style={styles.successDesc}>
              Your biometric face profile has been registered and encrypted. You can now use
              face-verified attendance seamlessly.
            </Text>

            <View style={styles.profileSummaryBox}>
              <Text style={styles.summaryItem}>User: <Text style={styles.boldText}>{user.name}</Text></Text>
              <Text style={styles.summaryItem}>Model: <Text style={styles.boldText}>ArcFace buffalo_l</Text></Text>
              <Text style={styles.summaryItem}>Status: <Text style={styles.summaryGreen}>Active & Verified</Text></Text>
            </View>

            <Pressable
              style={styles.primaryBtn}
              onPress={() => router.push('/explore')}
            >
              <Text style={styles.primaryBtnText}>Test Attendance Now →</Text>
            </Pressable>

            <Pressable
              style={styles.retakeBtn}
              onPress={() => router.push('/')}
            >
              <Text style={styles.retakeBtnText}>Return to Dashboard</Text>
            </Pressable>
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
  scrollContent: {
    paddingHorizontal: 20,
    paddingVertical: 18,
  },
  topHeader: {
    marginBottom: 16,
  },
  backBtn: {
    alignSelf: 'flex-start',
    paddingVertical: 6,
    paddingHorizontal: 10,
    backgroundColor: '#EFF6FF',
    borderRadius: 8,
    marginBottom: 10,
  },
  backBtnText: {
    color: '#153E75',
    fontWeight: '700',
    fontSize: 12,
  },
  screenTitle: {
    fontSize: 22,
    fontWeight: '800',
    color: '#153E75',
  },
  screenSub: {
    fontSize: 12,
    color: '#64748B',
    marginTop: 2,
  },
  centerBox: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    padding: 30,
  },
  iconBig: {
    fontSize: 48,
    marginBottom: 12,
  },
  title: {
    fontSize: 20,
    fontWeight: '800',
    color: '#1E293B',
  },
  subtitle: {
    fontSize: 13,
    color: '#64748B',
    textAlign: 'center',
    lineHeight: 18,
    marginTop: 6,
    marginBottom: 20,
  },
  card: {
    backgroundColor: '#FFFFFF',
    borderRadius: 20,
    padding: 22,
    borderWidth: 1,
    borderColor: '#E2E8F0',
    shadowColor: '#153E75',
    shadowOpacity: 0.05,
    shadowRadius: 10,
    shadowOffset: { width: 0, height: 4 },
  },
  shieldWrap: {
    width: 60,
    height: 60,
    borderRadius: 30,
    backgroundColor: '#EFF6FF',
    alignItems: 'center',
    justifyContent: 'center',
    alignSelf: 'center',
    marginBottom: 12,
  },
  shieldIcon: {
    fontSize: 30,
  },
  cardTitle: {
    fontSize: 18,
    fontWeight: '800',
    color: '#1E293B',
    textAlign: 'center',
  },
  cardDesc: {
    fontSize: 13,
    color: '#64748B',
    textAlign: 'center',
    lineHeight: 19,
    marginTop: 6,
    marginBottom: 18,
  },
  privacyBox: {
    backgroundColor: '#F8FAFC',
    borderRadius: 14,
    padding: 14,
    borderWidth: 1,
    borderColor: '#E2E8F0',
    marginBottom: 18,
    gap: 10,
  },
  privacyPoint: {
    fontSize: 12,
    color: '#475569',
    lineHeight: 18,
  },
  boldText: {
    fontWeight: '700',
    color: '#1E293B',
  },
  consentRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 20,
    gap: 10,
  },
  checkbox: {
    width: 22,
    height: 22,
    borderRadius: 6,
    borderWidth: 2,
    borderColor: '#CBD5E1',
    alignItems: 'center',
    justifyContent: 'center',
  },
  checkboxActive: {
    backgroundColor: '#153E75',
    borderColor: '#153E75',
  },
  checkmark: {
    color: '#FFFFFF',
    fontSize: 12,
    fontWeight: '900',
  },
  consentText: {
    flex: 1,
    fontSize: 12,
    color: '#475569',
    lineHeight: 16,
  },
  primaryBtn: {
    backgroundColor: '#153E75',
    paddingVertical: 14,
    borderRadius: 14,
    alignItems: 'center',
  },
  primaryBtnText: {
    color: '#FFFFFF',
    fontSize: 15,
    fontWeight: '800',
  },
  btnDisabled: {
    backgroundColor: '#94A3B8',
  },
  cameraCard: {
    backgroundColor: '#FFFFFF',
    borderRadius: 20,
    overflow: 'hidden',
    borderWidth: 1,
    borderColor: '#E2E8F0',
  },
  progressRow: {
    flexDirection: 'row',
    justifyContent: 'center',
    gap: 8,
    paddingVertical: 10,
    backgroundColor: '#F8FAFC',
  },
  progressDot: {
    width: 28,
    height: 4,
    borderRadius: 2,
    backgroundColor: '#CBD5E1',
  },
  progressDotActive: {
    backgroundColor: '#153E75',
  },
  instructionBanner: {
    padding: 14,
    alignItems: 'center',
    backgroundColor: '#EFF6FF',
  },
  instructionStep: {
    fontSize: 10,
    fontWeight: '800',
    letterSpacing: 1,
    color: '#64748B',
  },
  instructionMain: {
    fontSize: 16,
    fontWeight: '800',
    color: '#1E293B',
    marginTop: 2,
  },
  instructionSub: {
    fontSize: 11,
    color: '#64748B',
    marginTop: 2,
  },
  cameraWrapper: {
    height: 380,
    backgroundColor: '#0F172A',
    position: 'relative',
    alignItems: 'center',
    justifyContent: 'center',
  },
  camera: {
    width: '100%',
    height: '100%',
  },
  faceOvalOverlay: {
    position: 'absolute',
    width: 200,
    height: 260,
    borderRadius: 100,
    borderWidth: 3,
    borderColor: 'rgba(255, 255, 255, 0.7)',
    borderStyle: 'dashed',
    top: 55,
    alignSelf: 'center',
  },
  permissionBox: {
    padding: 24,
    alignItems: 'center',
  },
  permissionText: {
    color: '#FFFFFF',
    fontSize: 14,
    marginBottom: 12,
  },
  grantBtn: {
    backgroundColor: '#153E75',
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderRadius: 8,
  },
  grantBtnText: {
    color: '#FFFFFF',
    fontWeight: '700',
  },
  cameraControls: {
    flexDirection: 'row',
    padding: 14,
    alignItems: 'center',
    gap: 12,
  },
  switchCamBtn: {
    paddingHorizontal: 14,
    paddingVertical: 12,
    borderRadius: 10,
    backgroundColor: '#EFF6FF',
    borderWidth: 1,
    borderColor: '#BFDBFE',
  },
  switchCamText: {
    color: '#1D4ED8',
    fontWeight: '700',
    fontSize: 12,
  },
  snapBtn: {
    flex: 1,
    backgroundColor: '#153E75',
    paddingVertical: 13,
    borderRadius: 12,
    alignItems: 'center',
  },
  snapBtnText: {
    color: '#FFFFFF',
    fontSize: 14,
    fontWeight: '800',
  },
  thumbnailRow: {
    flexDirection: 'row',
    gap: 8,
    marginVertical: 14,
  },
  thumbnailBox: {
    flex: 1,
    alignItems: 'center',
  },
  thumbnail: {
    width: '100%',
    height: 120,
    borderRadius: 10,
    backgroundColor: '#E2E8F0',
  },
  thumbnailLabel: {
    fontSize: 11,
    fontWeight: '700',
    color: '#475569',
    marginTop: 6,
  },
  enrollChecklist: {
    backgroundColor: '#F8FAFC',
    borderRadius: 12,
    padding: 12,
    marginBottom: 16,
    gap: 4,
  },
  checkItem: {
    fontSize: 12,
    color: '#16A34A',
    fontWeight: '600',
  },
  retakeBtn: {
    paddingVertical: 12,
    alignItems: 'center',
    marginTop: 8,
  },
  retakeBtnText: {
    color: '#64748B',
    fontSize: 13,
    fontWeight: '600',
  },
  loadingTitle: {
    fontSize: 16,
    fontWeight: '800',
    color: '#1E293B',
    textAlign: 'center',
    marginTop: 14,
  },
  loadingSub: {
    fontSize: 12,
    color: '#64748B',
    textAlign: 'center',
    marginTop: 6,
  },
  successIconWrap: {
    width: 64,
    height: 64,
    borderRadius: 32,
    backgroundColor: '#DCFCE7',
    alignItems: 'center',
    justifyContent: 'center',
    alignSelf: 'center',
    marginBottom: 12,
  },
  successIcon: {
    fontSize: 32,
    color: '#16A34A',
    fontWeight: '900',
  },
  successTitle: {
    fontSize: 20,
    fontWeight: '800',
    color: '#166534',
    textAlign: 'center',
  },
  successDesc: {
    fontSize: 13,
    color: '#64748B',
    textAlign: 'center',
    marginTop: 6,
    marginBottom: 16,
  },
  profileSummaryBox: {
    backgroundColor: '#F8FAFC',
    borderRadius: 12,
    padding: 14,
    marginBottom: 20,
    gap: 6,
  },
  summaryItem: {
    fontSize: 12,
    color: '#475569',
  },
  summaryGreen: {
    fontWeight: '800',
    color: '#16A34A',
  },
  errorBox: {
    backgroundColor: '#FEF2F2',
    borderRadius: 12,
    padding: 14,
    marginBottom: 16,
    borderWidth: 1,
    borderColor: '#FECACA',
  },
  errorBoxTitle: {
    fontSize: 13,
    fontWeight: '800',
    color: '#991B1B',
    marginBottom: 4,
  },
  errorBoxMessage: {
    fontSize: 12,
    color: '#B91C1C',
    lineHeight: 18,
  },
});

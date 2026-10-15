import React, { useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  Dimensions,
  Image,
  KeyboardAvoidingView,
  Modal,
  Platform,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';

import { useAuth } from '@/context/AuthContext';
import { ApiService, AttendanceRecordItem } from '@/services/api';

const { width } = Dimensions.get('window');

type RoleType = 'Student' | 'Faculty' | 'Employee' | 'HOD/Admin' | 'Security';

interface RolePreset {
  id: RoleType;
  label: string;
  icon: keyof typeof Ionicons.glyphMap;
  email: string;
  pass: string;
  roleType: 'student' | 'staff' | 'admin';
}

const ROLE_PRESETS: RolePreset[] = [
  { id: 'Student', label: 'Student', icon: 'person-outline', email: 'aarav.sharma@campusproof.edu', pass: 'Student@123', roleType: 'student' },
  { id: 'Faculty', label: 'Faculty', icon: 'school-outline', email: 'vikram.mehta@campusproof.edu', pass: 'Staff@123', roleType: 'staff' },
  { id: 'Employee', label: 'Employee', icon: 'briefcase-outline', email: 'sunil.kumar@campusproof.edu', pass: 'Staff@123', roleType: 'staff' },
  { id: 'HOD/Admin', label: 'HOD/Admin', icon: 'shield-checkmark-outline', email: 'admin@campusproof.edu', pass: 'Admin@123', roleType: 'admin' },
  { id: 'Security', label: 'Security', icon: 'key-outline', email: 'security@campusproof.edu', pass: 'Staff@123', roleType: 'staff' },
];

export default function HomeScreen() {
  const router = useRouter();
  const { user, login, registerStudent, logout, apiUrl, updateApiUrl, refreshHealth } = useAuth();

  // Auth screen state
  const [selectedRole, setSelectedRole] = useState<RoleType>('Student');
  const [authMode, setAuthMode] = useState<'login' | 'register'>('login');
  const [authModalVisible, setAuthModalVisible] = useState(false);
  const [email, setEmail] = useState('aarav.sharma@campusproof.edu');
  const [password, setPassword] = useState('Student@123');
  const [fullName, setFullName] = useState('');
  const [studentId, setStudentId] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [authError, setAuthError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  // IP Modal
  const [ipModalVisible, setIpModalVisible] = useState(false);
  const [customIpInput, setCustomIpInput] = useState(apiUrl);

  // Quick Action Modals
  const [actionModal, setActionModal] = useState<string | null>(null);

  // Sync role preset
  const handleSelectRole = (r: RoleType) => {
    setSelectedRole(r);
    const preset = ROLE_PRESETS.find((p) => p.id === r);
    if (preset) {
      setEmail(preset.email);
      setPassword(preset.pass);
    }
  };

  const handleOpenAuth = (mode: 'login' | 'register') => {
    setAuthMode(mode);
    setAuthError('');
    setAuthModalVisible(true);
  };

  const handleAuthSubmit = async () => {
    setAuthError('');
    setIsSubmitting(true);
    try {
      const preset = ROLE_PRESETS.find((p) => p.id === selectedRole);
      if (authMode === 'login') {
        await login(email.trim(), password, preset?.roleType);
        setAuthModalVisible(false);
      } else {
        if (!fullName.trim() || !studentId.trim() || !email.trim()) {
          setAuthError('Please fill all required fields');
          setIsSubmitting(false);
          return;
        }
        if (password !== confirmPassword) {
          setAuthError('Passwords do not match');
          setIsSubmitting(false);
          return;
        }
        await registerStudent({
          name: fullName.trim(),
          employeeId: studentId.trim(),
          email: email.trim(),
          password,
        });
        setAuthModalVisible(false);
      }
    } catch (err: any) {
      setAuthError(err.message || 'Authentication failed. Please verify credentials.');
    } finally {
      setIsSubmitting(false);
    }
  };

  /* ========================================================
     SCREEN 1: WELCOME & LOGIN SCREEN (WHEN NOT LOGGED IN)
     ======================================================== */
  if (!user) {
    return (
      <SafeAreaView style={styles.welcomeSafeArea} edges={['top', 'left', 'right', 'bottom']}>
        <ScrollView
          style={styles.welcomeScroll}
          contentContainerStyle={styles.welcomeContentContainer}
          showsVerticalScrollIndicator={false}
        >
          {/* Logo & Subtitle */}
          <View style={styles.brandContainer}>
            <View style={styles.logoCircle}>
              <Ionicons name="school" size={32} color="#0A7B68" />
            </View>
            <Text style={styles.brandTitle}>AERIS</Text>
            <Text style={styles.brandTagline}>Smart Campus, Smarter Tomorrow</Text>
          </View>

          {/* Campus Facade Image Card */}
          <View style={styles.campusImageCard}>
            <Image
              source={require('@/assets/images/campus_arya.jpg')}
              style={styles.campusImage}
              resizeMode="cover"
            />
            <View style={styles.campusCardOverlay}>
              <View style={styles.collegeBadgePill}>
                <Ionicons name="business" size={14} color="#0A7B68" />
                <Text style={styles.collegeBadgeText}>Arya Main Campus • Jaipur</Text>
              </View>
            </View>
          </View>

          {/* Login & Sign Up CTA Buttons */}
          <View style={styles.authButtonsRow}>
            <TouchableOpacity
              style={styles.mainLoginButton}
              onPress={() => handleOpenAuth('login')}
              activeOpacity={0.85}
            >
              <Text style={styles.mainLoginButtonText}>Login</Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={styles.mainSignUpButton}
              onPress={() => handleOpenAuth('register')}
              activeOpacity={0.85}
            >
              <Text style={styles.mainSignUpButtonText}>Sign Up</Text>
            </TouchableOpacity>
          </View>

          {/* Role Selection Section */}
          <View style={styles.roleSection}>
            <Text style={styles.roleSectionTitle}>Select Role</Text>
            <View style={styles.roleGrid}>
              {ROLE_PRESETS.map((preset) => {
                const isSelected = selectedRole === preset.id;
                return (
                  <TouchableOpacity
                    key={preset.id}
                    style={styles.roleItem}
                    onPress={() => {
                      handleSelectRole(preset.id);
                      handleOpenAuth('login');
                    }}
                    activeOpacity={0.7}
                  >
                    <View style={[styles.roleIconCircle, isSelected && styles.roleIconCircleSelected]}>
                      <Ionicons
                        name={preset.icon}
                        size={22}
                        color={isSelected ? '#FFFFFF' : '#0A7B68'}
                      />
                    </View>
                    <Text style={[styles.roleItemLabel, isSelected && styles.roleItemLabelSelected]}>
                      {preset.label}
                    </Text>
                  </TouchableOpacity>
                );
              })}
            </View>
          </View>

          {/* Backend Connection status indicator */}
          <TouchableOpacity
            style={styles.serverStatusPill}
            onPress={() => setIpModalVisible(true)}
            activeOpacity={0.7}
          >
            <View style={styles.statusDotGreen} />
            <Text style={styles.serverStatusText}>Backend API: {apiUrl.replace(/^https?:\/\//, '')}</Text>
            <Ionicons name="settings-outline" size={14} color="#64748B" />
          </TouchableOpacity>
        </ScrollView>

        {/* Login / Register Modal */}
        <Modal
          visible={authModalVisible}
          animationType="slide"
          transparent
          onRequestClose={() => setAuthModalVisible(false)}
        >
          <KeyboardAvoidingView
            behavior={Platform.OS === 'ios' ? 'padding' : undefined}
            style={styles.modalBackdrop}
          >
            <View style={styles.modalSheet}>
              <View style={styles.modalHeader}>
                <View>
                  <Text style={styles.modalTitle}>
                    {authMode === 'login' ? `Login as ${selectedRole}` : `Student Sign Up`}
                  </Text>
                  <Text style={styles.modalSubtitle}>
                    {authMode === 'login'
                      ? 'Enter your institutional email & password'
                      : 'Enroll student profile to AERIS'}
                  </Text>
                </View>
                <TouchableOpacity
                  style={styles.modalCloseBtn}
                  onPress={() => setAuthModalVisible(false)}
                >
                  <Ionicons name="close" size={20} color="#64748B" />
                </TouchableOpacity>
              </View>

              {authError ? (
                <View style={styles.authErrorBox}>
                  <Ionicons name="alert-circle" size={16} color="#DC2626" />
                  <Text style={styles.authErrorText}>{authError}</Text>
                </View>
              ) : null}

              <ScrollView showsVerticalScrollIndicator={false} style={styles.modalFormScroll}>
                {authMode === 'register' && (
                  <>
                    <Text style={styles.inputLabel}>Full Name</Text>
                    <TextInput
                      style={styles.textInput}
                      placeholder="e.g. Yashasvi Saini"
                      value={fullName}
                      onChangeText={setFullName}
                      placeholderTextColor="#94A3B8"
                    />

                    <Text style={styles.inputLabel}>Roll / Student ID</Text>
                    <TextInput
                      style={styles.textInput}
                      placeholder="e.g. 22CS101"
                      value={studentId}
                      onChangeText={setStudentId}
                      autoCapitalize="characters"
                      placeholderTextColor="#94A3B8"
                    />
                  </>
                )}

                <Text style={styles.inputLabel}>Institutional Email</Text>
                <TextInput
                  style={styles.textInput}
                  placeholder="name@campusproof.edu"
                  value={email}
                  onChangeText={setEmail}
                  autoCapitalize="none"
                  keyboardType="email-address"
                  placeholderTextColor="#94A3B8"
                />

                <Text style={styles.inputLabel}>Password</Text>
                <View style={styles.passwordWrapper}>
                  <TextInput
                    style={[styles.textInput, { flex: 1, marginBottom: 0 }]}
                    placeholder="••••••••"
                    value={password}
                    onChangeText={setPassword}
                    secureTextEntry={!showPassword}
                    placeholderTextColor="#94A3B8"
                  />
                  <TouchableOpacity
                    style={styles.eyeBtn}
                    onPress={() => setShowPassword(!showPassword)}
                  >
                    <Ionicons
                      name={showPassword ? 'eye-off-outline' : 'eye-outline'}
                      size={20}
                      color="#64748B"
                    />
                  </TouchableOpacity>
                </View>

                {authMode === 'register' && (
                  <>
                    <Text style={styles.inputLabel}>Confirm Password</Text>
                    <TextInput
                      style={styles.textInput}
                      placeholder="••••••••"
                      value={confirmPassword}
                      onChangeText={setConfirmPassword}
                      secureTextEntry={!showPassword}
                      placeholderTextColor="#94A3B8"
                    />
                  </>
                )}

                <TouchableOpacity
                  style={[styles.submitButton, isSubmitting && { opacity: 0.7 }]}
                  onPress={handleAuthSubmit}
                  disabled={isSubmitting}
                  activeOpacity={0.85}
                >
                  {isSubmitting ? (
                    <ActivityIndicator color="#FFFFFF" />
                  ) : (
                    <Text style={styles.submitButtonText}>
                      {authMode === 'login' ? 'Sign In to Campus' : 'Create Student Account'}
                    </Text>
                  )}
                </TouchableOpacity>

                {/* Quick Toggle */}
                <TouchableOpacity
                  style={styles.toggleAuthModeBtn}
                  onPress={() => setAuthMode(authMode === 'login' ? 'register' : 'login')}
                >
                  <Text style={styles.toggleAuthModeText}>
                    {authMode === 'login'
                      ? "Don't have an account? Sign Up"
                      : 'Already enrolled? Back to Login'}
                  </Text>
                </TouchableOpacity>
              </ScrollView>
            </View>
          </KeyboardAvoidingView>
        </Modal>

        {/* Server IP Modal */}
        <Modal
          visible={ipModalVisible}
          animationType="fade"
          transparent
          onRequestClose={() => setIpModalVisible(false)}
        >
          <View style={styles.modalBackdrop}>
            <View style={[styles.modalSheet, { maxHeight: 300 }]}>
              <Text style={styles.modalTitle}>Backend API Gateway</Text>
              <Text style={styles.modalSubtitle}>Configure FastAPI host address</Text>
              <TextInput
                style={[styles.textInput, { marginTop: 16 }]}
                value={customIpInput}
                onChangeText={setCustomIpInput}
                autoCapitalize="none"
              />
              <View style={{ flexDirection: 'row', gap: 10, marginTop: 12 }}>
                <TouchableOpacity
                  style={[styles.mainSignUpButton, { flex: 1 }]}
                  onPress={() => setIpModalVisible(false)}
                >
                  <Text style={styles.mainSignUpButtonText}>Cancel</Text>
                </TouchableOpacity>
                <TouchableOpacity
                  style={[styles.mainLoginButton, { flex: 1 }]}
                  onPress={async () => {
                    await updateApiUrl(customIpInput.trim());
                    await refreshHealth();
                    setIpModalVisible(false);
                  }}
                >
                  <Text style={styles.mainLoginButtonText}>Save</Text>
                </TouchableOpacity>
              </View>
            </View>
          </View>
        </Modal>
      </SafeAreaView>
    );
  }

  /* ========================================================
     SCREEN 2: STUDENT HOME DASHBOARD (WHEN LOGGED IN)
     ======================================================== */
  return (
    <SafeAreaView style={styles.dashboardSafeArea} edges={['top', 'left', 'right']}>
      {/* Top Header */}
      <View style={styles.dashHeader}>
        <View style={styles.dashHeaderLeft}>
          <View style={styles.userAvatar}>
            <Ionicons name="person" size={22} color="#FFFFFF" />
          </View>
          <View>
            <Text style={styles.greetingTitle}>Good Morning</Text>
            <Text style={styles.userNameText}>{user.name || 'Yashasvi'}</Text>
            <Text style={styles.userBranchText}>
              {user.role === 'student' ? 'B.Tech CSE | 2nd Year | Section A' : `Institutional ${user.role.toUpperCase()}`}
            </Text>
          </View>
        </View>

        <View style={styles.dashHeaderRight}>
          <TouchableOpacity
            style={styles.notifIconBtn}
            onPress={() => router.push('/notifications')}
            activeOpacity={0.7}
          >
            <Ionicons name="notifications-outline" size={22} color="#1E293B" />
            <View style={styles.notifBadge}>
              <Text style={styles.notifBadgeText}>4</Text>
            </View>
          </TouchableOpacity>

          <TouchableOpacity
            style={styles.logoutBtn}
            onPress={logout}
            activeOpacity={0.7}
          >
            <Ionicons name="log-out-outline" size={20} color="#EF4444" />
          </TouchableOpacity>
        </View>
      </View>

      <ScrollView
        style={styles.dashboardScroll}
        contentContainerStyle={styles.dashScrollContent}
        showsVerticalScrollIndicator={false}
      >
        {/* Search Bar */}
        <View style={styles.searchBar}>
          <Ionicons name="search-outline" size={18} color="#94A3B8" />
          <TextInput
            style={styles.searchInput}
            placeholder="Search classes, rooms, notices..."
            placeholderTextColor="#94A3B8"
          />
        </View>

        {/* "Today's Class" Hero Card */}
        <View style={styles.classHeroCard}>
          <View style={styles.classHeroLeft}>
            <View style={styles.liveTagRow}>
              <View style={styles.pulsingGreenDot} />
              <Text style={styles.liveTagText}>Today's Class</Text>
            </View>
            <Text style={styles.classHeroTitle}>AI & ML</Text>
            <Text style={styles.classHeroRoom}>LT-24</Text>
            <Text style={styles.classHeroTime}>10:40 AM - 11:30 AM</Text>

            <TouchableOpacity
              style={styles.viewDetailsBtn}
              onPress={() => router.push('/timetable')}
              activeOpacity={0.8}
            >
              <Text style={styles.viewDetailsBtnText}>View Details</Text>
            </TouchableOpacity>
          </View>

          <View style={styles.classHeroRight}>
            <Image
              source={require('@/assets/images/class_aiml.jpg')}
              style={styles.classHeroThumb}
              resizeMode="cover"
            />
          </View>
        </View>

        {/* Quick Action Biometric Verification CTA */}
        <TouchableOpacity
          style={styles.biometricCtaBanner}
          onPress={() => router.push({ pathname: '/explore', params: { mode: 'face' } })}
          activeOpacity={0.85}
        >
          <View style={styles.biometricCtaLeft}>
            <View style={styles.biometricIconCircle}>
              <Ionicons name="scan-outline" size={24} color="#044E42" />
            </View>
            <View>
              <Text style={styles.biometricCtaTitle}>Check-in with Face AI</Text>
              <Text style={styles.biometricCtaSub}>⚡ 1-Tap Live Face Scan &amp; Geofence</Text>
            </View>
          </View>
          <Ionicons name="chevron-forward" size={20} color="#FFFFFF" />
        </TouchableOpacity>

        {/* Quick Action QR Attendance Scanner CTA */}
        <TouchableOpacity
          style={[styles.biometricCtaBanner, { backgroundColor: '#064E3B', borderColor: '#10B981', marginTop: 10 }]}
          onPress={() => router.push({ pathname: '/explore', params: { mode: 'qr' } })}
          activeOpacity={0.85}
        >
          <View style={styles.biometricCtaLeft}>
            <View style={[styles.biometricIconCircle, { backgroundColor: '#10B981' }]}>
              <Ionicons name="qr-code-outline" size={24} color="#041B17" />
            </View>
            <View>
              <Text style={styles.biometricCtaTitle}>Scan Lecture QR Code</Text>
              <Text style={styles.biometricCtaSub}>📷 Instant Zero-Click Class Attendance</Text>
            </View>
          </View>
          <Ionicons name="chevron-forward" size={20} color="#10B981" />
        </TouchableOpacity>

        {/* Quick Action Grid (6 buttons) */}
        <View style={styles.gridContainer}>
          {/* 1. Attendance */}
          <TouchableOpacity
            style={styles.gridCard}
            onPress={() => router.push('/attendance')}
            activeOpacity={0.8}
          >
            <View style={[styles.gridIconCircle, { backgroundColor: '#E8F5F1' }]}>
              <Ionicons name="pie-chart-outline" size={22} color="#0A7B68" />
            </View>
            <Text style={styles.gridTitle}>Attendance</Text>
            <Text style={styles.gridMetric}>92%</Text>
          </TouchableOpacity>

          {/* 2. Timetable */}
          <TouchableOpacity
            style={styles.gridCard}
            onPress={() => router.push('/timetable')}
            activeOpacity={0.8}
          >
            <View style={[styles.gridIconCircle, { backgroundColor: '#EFF6FF' }]}>
              <Ionicons name="calendar-outline" size={22} color="#2563EB" />
            </View>
            <Text style={styles.gridTitle}>Timetable</Text>
            <Text style={styles.gridSub}>6 Lectures</Text>
          </TouchableOpacity>

          {/* 3. Campus Map */}
          <TouchableOpacity
            style={styles.gridCard}
            onPress={() => router.push('/campus-map')}
            activeOpacity={0.8}
          >
            <View style={[styles.gridIconCircle, { backgroundColor: '#F0FDF4' }]}>
              <Ionicons name="map-outline" size={22} color="#16A34A" />
            </View>
            <Text style={styles.gridTitle}>Campus Map</Text>
            <Text style={styles.gridSub}>3D Floorplan</Text>
          </TouchableOpacity>

          {/* 4. Exams */}
          <TouchableOpacity
            style={styles.gridCard}
            onPress={() => setActionModal('Exams: Mid-Term Examination scheduled starting next Monday at LT-16.')}
            activeOpacity={0.8}
          >
            <View style={[styles.gridIconCircle, { backgroundColor: '#FDF4FF' }]}>
              <Ionicons name="newspaper-outline" size={22} color="#9333EA" />
            </View>
            <Text style={styles.gridTitle}>Exams</Text>
            <Text style={styles.gridSub}>Mid-Term</Text>
          </TouchableOpacity>

          {/* 5. Notices */}
          <TouchableOpacity
            style={styles.gridCard}
            onPress={() => router.push('/notifications')}
            activeOpacity={0.8}
          >
            <View style={[styles.gridIconCircle, { backgroundColor: '#FEF3C7' }]}>
              <Ionicons name="megaphone-outline" size={22} color="#D97706" />
            </View>
            <Text style={styles.gridTitle}>Notices</Text>
            <Text style={styles.gridSub}>4 New</Text>
          </TouchableOpacity>

          {/* 6. Scan QR */}
          <TouchableOpacity
            style={styles.gridCard}
            onPress={() => router.push({ pathname: '/explore', params: { mode: 'qr' } })}
            activeOpacity={0.8}
          >
            <View style={[styles.gridIconCircle, { backgroundColor: '#ECFDF5' }]}>
              <Ionicons name="qr-code-outline" size={22} color="#059669" />
            </View>
            <Text style={styles.gridTitle}>Scan QR</Text>
            <Text style={[styles.gridSub, { color: '#059669', fontWeight: '700' }]}>Live Lecture</Text>
          </TouchableOpacity>
        </View>

        {/* Today's Schedule Timeline Section */}
        <View style={styles.scheduleHeaderRow}>
          <Text style={styles.scheduleSectionTitle}>Today's Schedule</Text>
          <TouchableOpacity onPress={() => router.push('/timetable')}>
            <Text style={styles.viewAllText}>View All</Text>
          </TouchableOpacity>
        </View>

        <View style={styles.timelineList}>
          {/* Item 1 */}
          <View style={styles.timelineItem}>
            <View style={[styles.timelineDot, { backgroundColor: '#10B981' }]} />
            <View style={styles.timelineTimeBox}>
              <Text style={styles.timelineTime}>09:00 - 09:50</Text>
            </View>
            <View style={styles.timelineDetailBox}>
              <Text style={styles.timelineClassName}>CD Lab (C1)</Text>
              <Text style={styles.timelineRoom}>NAB LAB</Text>
            </View>
          </View>

          {/* Item 2 */}
          <View style={styles.timelineItem}>
            <View style={[styles.timelineDot, { backgroundColor: '#0A7B68' }]} />
            <View style={styles.timelineTimeBox}>
              <Text style={styles.timelineTime}>09:50 - 10:40</Text>
            </View>
            <View style={styles.timelineDetailBox}>
              <Text style={styles.timelineClassName}>ADA Lab (C2)</Text>
              <Text style={styles.timelineRoom}>LT-24</Text>
            </View>
          </View>

          {/* Item 3 */}
          <View style={styles.timelineItem}>
            <View style={[styles.timelineDot, { backgroundColor: '#044E42' }]} />
            <View style={styles.timelineTimeBox}>
              <Text style={styles.timelineTime}>10:40 - 11:30</Text>
            </View>
            <View style={styles.timelineDetailBox}>
              <Text style={styles.timelineClassName}>Skill Development</Text>
              <Text style={styles.timelineRoom}>CL-24,25,27</Text>
            </View>
          </View>
        </View>

        {/* Face Enrollment Quick Access */}
        <TouchableOpacity
          style={styles.enrollHintCard}
          onPress={() => router.push('/enroll')}
          activeOpacity={0.8}
        >
          <Ionicons name="finger-print-outline" size={20} color="#0A7B68" />
          <Text style={styles.enrollHintText}>
            Face Biometrics enrolled. Tap here if you need to re-scan face embeddings.
          </Text>
        </TouchableOpacity>
      </ScrollView>

      {/* Info Modal */}
      {actionModal && (
        <Modal transparent animationType="fade" visible={!!actionModal} onRequestClose={() => setActionModal(null)}>
          <View style={styles.modalBackdrop}>
            <View style={[styles.modalSheet, { maxHeight: 240 }]}>
              <Text style={styles.modalTitle}>Campus Alert</Text>
              <Text style={[styles.modalSubtitle, { marginTop: 8 }]}>{actionModal}</Text>
              <TouchableOpacity
                style={[styles.mainLoginButton, { marginTop: 20 }]}
                onPress={() => setActionModal(null)}
              >
                <Text style={styles.mainLoginButtonText}>OK</Text>
              </TouchableOpacity>
            </View>
          </View>
        </Modal>
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  /* Welcome Screen Styles */
  welcomeSafeArea: {
    flex: 1,
    backgroundColor: '#FFFFFF',
  },
  welcomeScroll: {
    flex: 1,
  },
  welcomeContentContainer: {
    paddingHorizontal: 20,
    paddingTop: 16,
    paddingBottom: 32,
    alignItems: 'center',
  },
  brandContainer: {
    alignItems: 'center',
    marginBottom: 16,
  },
  logoCircle: {
    width: 60,
    height: 60,
    borderRadius: 30,
    backgroundColor: '#E6F5F2',
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 8,
  },
  brandTitle: {
    fontSize: 24,
    fontWeight: '800',
    color: '#044E42',
    letterSpacing: -0.5,
  },
  brandTagline: {
    fontSize: 13,
    fontWeight: '500',
    color: '#64748B',
    marginTop: 2,
  },
  campusImageCard: {
    width: '100%',
    height: 180,
    borderRadius: 20,
    overflow: 'hidden',
    marginBottom: 20,
    position: 'relative',
    backgroundColor: '#E2E8F0',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.1,
    shadowRadius: 10,
    elevation: 3,
  },
  campusImage: {
    width: '100%',
    height: '100%',
  },
  campusCardOverlay: {
    position: 'absolute',
    bottom: 12,
    left: 12,
  },
  collegeBadgePill: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    backgroundColor: 'rgba(255, 255, 255, 0.92)',
    paddingVertical: 5,
    paddingHorizontal: 10,
    borderRadius: 14,
  },
  collegeBadgeText: {
    fontSize: 11,
    fontWeight: '700',
    color: '#0A7B68',
  },
  authButtonsRow: {
    width: '100%',
    gap: 10,
    marginBottom: 24,
  },
  mainLoginButton: {
    backgroundColor: '#044E42',
    paddingVertical: 14,
    borderRadius: 24,
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: '#044E42',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.25,
    shadowRadius: 8,
    elevation: 3,
  },
  mainLoginButtonText: {
    fontSize: 16,
    fontWeight: '700',
    color: '#FFFFFF',
  },
  mainSignUpButton: {
    backgroundColor: '#FFFFFF',
    borderWidth: 1.5,
    borderColor: '#044E42',
    paddingVertical: 13,
    borderRadius: 24,
    alignItems: 'center',
    justifyContent: 'center',
  },
  mainSignUpButtonText: {
    fontSize: 16,
    fontWeight: '700',
    color: '#044E42',
  },
  roleSection: {
    width: '100%',
    alignItems: 'center',
    marginTop: 8,
  },
  roleSectionTitle: {
    fontSize: 14,
    fontWeight: '700',
    color: '#64748B',
    marginBottom: 14,
  },
  roleGrid: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    width: '100%',
    paddingHorizontal: 4,
  },
  roleItem: {
    alignItems: 'center',
    gap: 6,
  },
  roleIconCircle: {
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: '#E8F5F1',
    justifyContent: 'center',
    alignItems: 'center',
  },
  roleIconCircleSelected: {
    backgroundColor: '#0A7B68',
  },
  roleItemLabel: {
    fontSize: 11,
    fontWeight: '600',
    color: '#64748B',
  },
  roleItemLabelSelected: {
    color: '#0A7B68',
    fontWeight: '700',
  },
  serverStatusPill: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#F1F5F9',
    paddingVertical: 6,
    paddingHorizontal: 12,
    borderRadius: 16,
    marginTop: 28,
    gap: 8,
  },
  statusDotGreen: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: '#10B981',
  },
  serverStatusText: {
    fontSize: 12,
    color: '#475569',
    fontWeight: '500',
  },

  /* Modals */
  modalBackdrop: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.5)',
    justifyContent: 'flex-end',
  },
  modalSheet: {
    backgroundColor: '#FFFFFF',
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    padding: 24,
    maxHeight: '85%',
  },
  modalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 16,
  },
  modalTitle: {
    fontSize: 20,
    fontWeight: '800',
    color: '#0F172A',
  },
  modalSubtitle: {
    fontSize: 13,
    color: '#64748B',
    marginTop: 2,
  },
  modalCloseBtn: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: '#F1F5F9',
    justifyContent: 'center',
    alignItems: 'center',
  },
  modalFormScroll: {
    maxHeight: 400,
  },
  authErrorBox: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    backgroundColor: '#FEE2E2',
    padding: 10,
    borderRadius: 10,
    marginBottom: 14,
  },
  authErrorText: {
    fontSize: 12,
    color: '#B91C1C',
    flex: 1,
  },
  inputLabel: {
    fontSize: 13,
    fontWeight: '600',
    color: '#334155',
    marginBottom: 6,
    marginTop: 10,
  },
  textInput: {
    backgroundColor: '#F8FAFC',
    borderWidth: 1,
    borderColor: '#E2E8F0',
    borderRadius: 12,
    paddingVertical: 12,
    paddingHorizontal: 14,
    fontSize: 14,
    color: '#0F172A',
    marginBottom: 10,
  },
  passwordWrapper: {
    flexDirection: 'row',
    alignItems: 'center',
    position: 'relative',
    marginBottom: 10,
  },
  eyeBtn: {
    position: 'absolute',
    right: 12,
    height: '100%',
    justifyContent: 'center',
  },
  submitButton: {
    backgroundColor: '#044E42',
    paddingVertical: 14,
    borderRadius: 14,
    alignItems: 'center',
    marginTop: 16,
  },
  submitButtonText: {
    color: '#FFFFFF',
    fontSize: 15,
    fontWeight: '700',
  },
  toggleAuthModeBtn: {
    alignItems: 'center',
    paddingVertical: 14,
  },
  toggleAuthModeText: {
    fontSize: 13,
    fontWeight: '600',
    color: '#0A7B68',
  },

  /* Dashboard Screen Styles */
  dashboardSafeArea: {
    flex: 1,
    backgroundColor: '#F4F7F6',
  },
  dashHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 20,
    paddingVertical: 12,
    backgroundColor: '#FFFFFF',
    borderBottomWidth: 1,
    borderBottomColor: '#E2E8F0',
  },
  dashHeaderLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  userAvatar: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: '#0A7B68',
    justifyContent: 'center',
    alignItems: 'center',
  },
  greetingTitle: {
    fontSize: 11,
    fontWeight: '600',
    color: '#64748B',
    textTransform: 'uppercase',
  },
  userNameText: {
    fontSize: 17,
    fontWeight: '800',
    color: '#0F172A',
  },
  userBranchText: {
    fontSize: 11,
    fontWeight: '500',
    color: '#0A7B68',
  },
  dashHeaderRight: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  notifIconBtn: {
    width: 38,
    height: 38,
    borderRadius: 12,
    backgroundColor: '#F1F5F9',
    justifyContent: 'center',
    alignItems: 'center',
    position: 'relative',
  },
  notifBadge: {
    position: 'absolute',
    top: -2,
    right: -2,
    backgroundColor: '#EF4444',
    width: 16,
    height: 16,
    borderRadius: 8,
    justifyContent: 'center',
    alignItems: 'center',
  },
  notifBadgeText: {
    color: '#FFFFFF',
    fontSize: 9,
    fontWeight: '800',
  },
  logoutBtn: {
    width: 38,
    height: 38,
    borderRadius: 12,
    backgroundColor: '#FEE2E2',
    justifyContent: 'center',
    alignItems: 'center',
  },
  dashboardScroll: {
    flex: 1,
  },
  dashScrollContent: {
    padding: 16,
    paddingBottom: 40,
    gap: 16,
  },
  searchBar: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FFFFFF',
    borderRadius: 14,
    paddingHorizontal: 14,
    paddingVertical: 10,
    gap: 8,
    borderWidth: 1,
    borderColor: '#E2E8F0',
  },
  searchInput: {
    flex: 1,
    fontSize: 14,
    color: '#0F172A',
  },
  classHeroCard: {
    backgroundColor: '#FFFFFF',
    borderRadius: 20,
    padding: 16,
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.05,
    shadowRadius: 8,
    elevation: 2,
  },
  classHeroLeft: {
    flex: 1,
    gap: 3,
  },
  liveTagRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginBottom: 4,
  },
  pulsingGreenDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: '#10B981',
  },
  liveTagText: {
    fontSize: 12,
    fontWeight: '700',
    color: '#64748B',
  },
  classHeroTitle: {
    fontSize: 20,
    fontWeight: '800',
    color: '#0F172A',
  },
  classHeroRoom: {
    fontSize: 14,
    fontWeight: '600',
    color: '#0A7B68',
  },
  classHeroTime: {
    fontSize: 12,
    color: '#64748B',
    marginBottom: 10,
  },
  viewDetailsBtn: {
    backgroundColor: '#0A7B68',
    paddingVertical: 7,
    paddingHorizontal: 14,
    borderRadius: 12,
    alignSelf: 'flex-start',
  },
  viewDetailsBtnText: {
    fontSize: 12,
    fontWeight: '700',
    color: '#FFFFFF',
  },
  classHeroRight: {
    width: 110,
    height: 100,
    borderRadius: 14,
    overflow: 'hidden',
    marginLeft: 12,
  },
  classHeroThumb: {
    width: '100%',
    height: '100%',
  },
  biometricCtaBanner: {
    backgroundColor: '#044E42',
    borderRadius: 16,
    padding: 14,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    shadowColor: '#044E42',
    shadowOffset: { width: 0, height: 3 },
    shadowOpacity: 0.2,
    shadowRadius: 6,
    elevation: 3,
  },
  biometricCtaLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  biometricIconCircle: {
    width: 42,
    height: 42,
    borderRadius: 21,
    backgroundColor: '#A7F3D0',
    justifyContent: 'center',
    alignItems: 'center',
  },
  biometricCtaTitle: {
    fontSize: 15,
    fontWeight: '700',
    color: '#FFFFFF',
  },
  biometricCtaSub: {
    fontSize: 11,
    color: '#A7F3D0',
  },
  gridContainer: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 12,
    justifyContent: 'space-between',
  },
  gridCard: {
    width: (width - 44) / 3,
    backgroundColor: '#FFFFFF',
    borderRadius: 16,
    padding: 12,
    alignItems: 'center',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.04,
    shadowRadius: 6,
    elevation: 2,
    gap: 4,
  },
  gridIconCircle: {
    width: 42,
    height: 42,
    borderRadius: 21,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 4,
  },
  gridTitle: {
    fontSize: 12,
    fontWeight: '700',
    color: '#1E293B',
    textAlign: 'center',
  },
  gridMetric: {
    fontSize: 12,
    fontWeight: '800',
    color: '#0A7B68',
  },
  gridSub: {
    fontSize: 10,
    color: '#64748B',
  },
  scheduleHeaderRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: 4,
  },
  scheduleSectionTitle: {
    fontSize: 16,
    fontWeight: '800',
    color: '#0F172A',
  },
  viewAllText: {
    fontSize: 13,
    fontWeight: '700',
    color: '#0A7B68',
  },
  timelineList: {
    backgroundColor: '#FFFFFF',
    borderRadius: 18,
    padding: 16,
    gap: 14,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.04,
    shadowRadius: 6,
    elevation: 2,
  },
  timelineItem: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  timelineDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    marginRight: 10,
  },
  timelineTimeBox: {
    width: 95,
  },
  timelineTime: {
    fontSize: 12,
    fontWeight: '600',
    color: '#64748B',
  },
  timelineDetailBox: {
    flex: 1,
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  timelineClassName: {
    fontSize: 13,
    fontWeight: '700',
    color: '#1E293B',
  },
  timelineRoom: {
    fontSize: 12,
    fontWeight: '600',
    color: '#0A7B68',
  },
  enrollHintCard: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    backgroundColor: '#E8F5F1',
    padding: 14,
    borderRadius: 14,
    marginTop: 4,
  },
  enrollHintText: {
    fontSize: 12,
    color: '#044E42',
    flex: 1,
    lineHeight: 16,
    fontWeight: '500',
  },
});

import React, { useState } from 'react';
import {
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
  Dimensions,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import Svg, { Circle, Path, Defs, LinearGradient, Stop } from 'react-native-svg';

const { width } = Dimensions.get('window');

interface SubjectAttendance {
  id: string;
  name: string;
  code: string;
  percentage: number;
  attended: number;
  total: number;
  color: string;
}

const SUBJECTS: SubjectAttendance[] = [
  { id: '1', name: 'Data Structures', code: 'CS301', percentage: 95, attended: 21, total: 22, color: '#0A7B68' },
  { id: '2', name: 'DBMS', code: 'CS302', percentage: 88, attended: 22, total: 25, color: '#10B981' },
  { id: '3', name: 'Computer Networks', code: 'CS303', percentage: 92, attended: 23, total: 25, color: '#0A7B68' },
  { id: '4', name: 'Operating System', code: 'CS304', percentage: 90, attended: 18, total: 20, color: '#0A7B68' },
  { id: '5', name: 'AI & ML', code: 'CS305', percentage: 98, attended: 19, total: 19, color: '#044E42' },
  { id: '6', name: 'Skill Development', code: 'SK301', percentage: 85, attended: 15, total: 17, color: '#10B981' },
];

export default function AttendanceScreen() {
  const router = useRouter();
  const [selectedTab, setSelectedTab] = useState<'subject' | 'lecture'>('subject');
  const [semester, setSemester] = useState('Semester 3');

  // Gauge calculation
  const overallPercentage = 92;
  const radius = 58;
  const strokeWidth = 10;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - (circumference * overallPercentage) / 100;

  return (
    <SafeAreaView style={styles.safeArea} edges={['top', 'left', 'right']}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity
          onPress={() => router.back()}
          style={styles.backButton}
          activeOpacity={0.7}
        >
          <Ionicons name="arrow-back" size={24} color="#1E293B" />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Attendance</Text>
        <TouchableOpacity
          onPress={() => router.push('/explore')}
          style={styles.cameraButton}
          activeOpacity={0.7}
        >
          <Ionicons name="camera-outline" size={22} color="#0A7B68" />
        </TouchableOpacity>
      </View>

      <ScrollView
        style={styles.scroll}
        contentContainerStyle={styles.contentContainer}
        showsVerticalScrollIndicator={false}
      >
        {/* Quick Check-In Actions */}
        <View style={styles.actionRow}>
          <TouchableOpacity
            style={[styles.actionBtn, { backgroundColor: '#0A7B68' }]}
            onPress={() => router.push({ pathname: '/explore', params: { mode: 'face' } })}
            activeOpacity={0.85}
          >
            <Ionicons name="scan-outline" size={17} color="#FFFFFF" />
            <Text style={styles.actionBtnText}>Face AI Check-in</Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={[styles.actionBtn, { backgroundColor: '#064E3B', borderColor: '#10B981', borderWidth: 1 }]}
            onPress={() => router.push({ pathname: '/explore', params: { mode: 'qr' } })}
            activeOpacity={0.85}
          >
            <Ionicons name="qr-code-outline" size={17} color="#10B981" />
            <Text style={[styles.actionBtnText, { color: '#10B981' }]}>Scan Lecture QR</Text>
          </TouchableOpacity>
        </View>

        {/* Semester Selector */}
        <TouchableOpacity style={styles.semesterPill} activeOpacity={0.8}>
          <Text style={styles.semesterText}>{semester}</Text>
          <Ionicons name="chevron-down" size={16} color="#64748B" />
        </TouchableOpacity>

        {/* Circular Overall Gauge Card */}
        <View style={styles.gaugeCard}>
          <View style={styles.gaugeContainer}>
            <Svg width={140} height={140} viewBox="0 0 140 140">
              <Defs>
                <LinearGradient id="gaugeGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                  <Stop offset="0%" stopColor="#10B981" />
                  <Stop offset="100%" stopColor="#0A7B68" />
                </LinearGradient>
              </Defs>
              {/* Background Track */}
              <Circle
                cx="70"
                cy="70"
                r={radius}
                stroke="#E2E8F0"
                strokeWidth={strokeWidth}
                fill="none"
              />
              {/* Progress Ring */}
              <Circle
                cx="70"
                cy="70"
                r={radius}
                stroke="url(#gaugeGrad)"
                strokeWidth={strokeWidth}
                fill="none"
                strokeDasharray={`${circumference} ${circumference}`}
                strokeDashoffset={strokeDashoffset}
                strokeLinecap="round"
                transform="rotate(-90 70 70)"
              />
            </Svg>
            <View style={styles.gaugeCenterText}>
              <Text style={styles.gaugePercent}>{overallPercentage}%</Text>
              <Text style={styles.gaugeLabel}>Overall</Text>
            </View>
          </View>

          {/* Stats Breakdown */}
          <View style={styles.statsColumn}>
            <View style={styles.statRow}>
              <Text style={styles.statName}>Total Lectures</Text>
              <Text style={styles.statValue}>128</Text>
            </View>
            <View style={styles.divider} />
            <View style={styles.statRow}>
              <View style={styles.statBullet}>
                <View style={[styles.bulletDot, { backgroundColor: '#10B981' }]} />
                <Text style={styles.statName}>Present</Text>
              </View>
              <Text style={[styles.statValue, { color: '#0A7B68' }]}>118</Text>
            </View>
            <View style={styles.statRow}>
              <View style={styles.statBullet}>
                <View style={[styles.bulletDot, { backgroundColor: '#EF4444' }]} />
                <Text style={styles.statName}>Absent</Text>
              </View>
              <Text style={[styles.statValue, { color: '#EF4444' }]}>6</Text>
            </View>
            <View style={styles.statRow}>
              <View style={styles.statBullet}>
                <View style={[styles.bulletDot, { backgroundColor: '#F59E0B' }]} />
                <Text style={styles.statName}>Pending</Text>
              </View>
              <Text style={[styles.statValue, { color: '#F59E0B' }]}>4</Text>
            </View>
          </View>
        </View>

        {/* Tab Switcher: Subject Wise vs Lecture Wise */}
        <View style={styles.tabsWrapper}>
          <TouchableOpacity
            style={[styles.tabButton, selectedTab === 'subject' && styles.tabButtonActive]}
            onPress={() => setSelectedTab('subject')}
            activeOpacity={0.8}
          >
            <Text
              style={[styles.tabButtonText, selectedTab === 'subject' && styles.tabButtonTextActive]}
            >
              Subject Wise
            </Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.tabButton, selectedTab === 'lecture' && styles.tabButtonActive]}
            onPress={() => setSelectedTab('lecture')}
            activeOpacity={0.8}
          >
            <Text
              style={[styles.tabButtonText, selectedTab === 'lecture' && styles.tabButtonTextActive]}
            >
              Lecture Wise
            </Text>
          </TouchableOpacity>
        </View>

        {/* Subject Wise Progress List */}
        {selectedTab === 'subject' ? (
          <View style={styles.subjectsCard}>
            {SUBJECTS.map((sub, index) => (
              <View key={sub.id} style={styles.subjectItem}>
                <View style={styles.subjectMeta}>
                  <View style={styles.subjectLeft}>
                    <View style={styles.subjectIconBox}>
                      <Ionicons name="book-outline" size={16} color="#0A7B68" />
                    </View>
                    <Text style={styles.subjectName}>{sub.name}</Text>
                  </View>
                  <Text style={styles.subjectPercent}>{sub.percentage}%</Text>
                </View>
                {/* Progress bar */}
                <View style={styles.progressBarTrack}>
                  <View
                    style={[
                      styles.progressBarFill,
                      { width: `${sub.percentage}%`, backgroundColor: sub.color },
                    ]}
                  />
                </View>
                {index < SUBJECTS.length - 1 && <View style={styles.itemSeparator} />}
              </View>
            ))}
          </View>
        ) : (
          <View style={styles.subjectsCard}>
            <View style={styles.lectureNotice}>
              <Ionicons name="information-circle-outline" size={20} color="#0A7B68" />
              <Text style={styles.lectureNoticeText}>
                Total 128 registered lecture hours logged with GPS & biometric anti-spoofing verification.
              </Text>
            </View>
          </View>
        )}

        {/* Attendance Trend Section */}
        <View style={styles.trendCard}>
          <View style={styles.trendHeader}>
            <Text style={styles.trendTitle}>Attendance Trend</Text>
            <View style={styles.badgePill}>
              <Text style={styles.badgeText}>92% Target Met</Text>
            </View>
          </View>

          {/* SVG Trend Line Chart */}
          <View style={styles.chartContainer}>
            <Svg width={width - 64} height={120} viewBox="0 0 320 120">
              <Defs>
                <LinearGradient id="chartGrad" x1="0" y1="0" x2="0" y2="1">
                  <Stop offset="0" stopColor="#0A7B68" stopOpacity="0.25" />
                  <Stop offset="1" stopColor="#0A7B68" stopOpacity="0.0" />
                </LinearGradient>
              </Defs>

              {/* Area fill */}
              <Path
                d="M 20 85 C 60 75, 100 95, 140 60 C 180 40, 220 70, 260 45 L 295 40 L 295 110 L 20 110 Z"
                fill="url(#chartGrad)"
              />

              {/* Smooth Trend Line */}
              <Path
                d="M 20 85 C 60 75, 100 95, 140 60 C 180 40, 220 70, 260 45 L 295 40"
                stroke="#0A7B68"
                strokeWidth={3}
                fill="none"
              />

              {/* Data points */}
              <Circle cx="20" cy="85" r="4" fill="#0A7B68" />
              <Circle cx="75" cy="80" r="4" fill="#0A7B68" />
              <Circle cx="130" cy="68" r="4" fill="#0A7B68" />
              <Circle cx="185" cy="50" r="4" fill="#0A7B68" />
              <Circle cx="240" cy="52" r="4" fill="#0A7B68" />
              <Circle cx="295" cy="40" r="6" fill="#044E42" stroke="#FFFFFF" strokeWidth="2" />
            </Svg>

            {/* Floating marker pill on current month */}
            <View style={styles.trendPillMarker}>
              <Text style={styles.trendPillMarkerText}>92%</Text>
            </View>

            {/* Months row */}
            <View style={styles.monthsRow}>
              {['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'].map((month, idx) => (
                <Text key={idx} style={styles.monthLabel}>
                  {month}
                </Text>
              ))}
            </View>
          </View>
        </View>

        {/* Check-In Action Button */}
        <TouchableOpacity
          style={styles.verifyActionButton}
          onPress={() => router.push('/explore')}
          activeOpacity={0.85}
        >
          <Ionicons name="scan-circle-outline" size={24} color="#FFFFFF" />
          <Text style={styles.verifyActionText}>Scan Face & Verify Today's Class</Text>
        </TouchableOpacity>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: '#F4F7F6',
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 20,
    paddingVertical: 14,
    backgroundColor: '#FFFFFF',
    borderBottomWidth: 1,
    borderBottomColor: '#E2E8F0',
  },
  backButton: {
    width: 38,
    height: 38,
    borderRadius: 12,
    backgroundColor: '#F1F5F9',
    justifyContent: 'center',
    alignItems: 'center',
  },
  headerTitle: {
    fontSize: 18,
    fontWeight: '700',
    color: '#0F172A',
  },
  cameraButton: {
    width: 38,
    height: 38,
    borderRadius: 12,
    backgroundColor: '#E6F5F2',
    justifyContent: 'center',
    alignItems: 'center',
  },
  scroll: {
    flex: 1,
  },
  contentContainer: {
    padding: 16,
    paddingBottom: 40,
  },
  actionRow: {
    flexDirection: 'row',
    gap: 10,
    marginBottom: 16,
  },
  actionBtn: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 12,
    borderRadius: 12,
    gap: 6,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 2,
  },
  actionBtnText: {
    fontSize: 13,
    fontWeight: '700',
    color: '#FFFFFF',
  },
  semesterPill: {
    flexDirection: 'row',
    alignItems: 'center',
    alignSelf: 'flex-start',
    backgroundColor: '#FFFFFF',
    borderWidth: 1,
    borderColor: '#E2E8F0',
    paddingVertical: 6,
    paddingHorizontal: 12,
    borderRadius: 20,
    marginBottom: 14,
    gap: 6,
  },
  semesterText: {
    fontSize: 13,
    fontWeight: '600',
    color: '#334155',
  },
  gaugeCard: {
    backgroundColor: '#FFFFFF',
    borderRadius: 20,
    padding: 18,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.05,
    shadowRadius: 8,
    elevation: 2,
    marginBottom: 18,
  },
  gaugeContainer: {
    width: 140,
    height: 140,
    justifyContent: 'center',
    alignItems: 'center',
  },
  gaugeCenterText: {
    position: 'absolute',
    alignItems: 'center',
    justifyContent: 'center',
  },
  gaugePercent: {
    fontSize: 26,
    fontWeight: '800',
    color: '#0F172A',
  },
  gaugeLabel: {
    fontSize: 12,
    color: '#64748B',
    fontWeight: '500',
  },
  statsColumn: {
    flex: 1,
    marginLeft: 16,
    gap: 8,
  },
  statRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  divider: {
    height: 1,
    backgroundColor: '#F1F5F9',
    marginVertical: 2,
  },
  statBullet: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  bulletDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  statName: {
    fontSize: 13,
    color: '#64748B',
    fontWeight: '500',
  },
  statValue: {
    fontSize: 14,
    fontWeight: '700',
    color: '#1E293B',
  },
  tabsWrapper: {
    flexDirection: 'row',
    backgroundColor: '#E2E8F0',
    borderRadius: 12,
    padding: 3,
    marginBottom: 16,
  },
  tabButton: {
    flex: 1,
    paddingVertical: 10,
    borderRadius: 10,
    alignItems: 'center',
  },
  tabButtonActive: {
    backgroundColor: '#0A7B68',
    shadowColor: '#0A7B68',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.2,
    shadowRadius: 4,
    elevation: 2,
  },
  tabButtonText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#64748B',
  },
  tabButtonTextActive: {
    color: '#FFFFFF',
  },
  subjectsCard: {
    backgroundColor: '#FFFFFF',
    borderRadius: 20,
    padding: 16,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.05,
    shadowRadius: 8,
    elevation: 2,
    marginBottom: 18,
  },
  subjectItem: {
    paddingVertical: 8,
  },
  subjectMeta: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 6,
  },
  subjectLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  subjectIconBox: {
    width: 28,
    height: 28,
    borderRadius: 8,
    backgroundColor: '#E8F5F1',
    justifyContent: 'center',
    alignItems: 'center',
  },
  subjectName: {
    fontSize: 14,
    fontWeight: '600',
    color: '#1E293B',
  },
  subjectPercent: {
    fontSize: 14,
    fontWeight: '700',
    color: '#0A7B68',
  },
  progressBarTrack: {
    height: 6,
    borderRadius: 3,
    backgroundColor: '#F1F5F9',
    overflow: 'hidden',
  },
  progressBarFill: {
    height: '100%',
    borderRadius: 3,
  },
  itemSeparator: {
    height: 1,
    backgroundColor: '#F8FAFC',
    marginTop: 10,
  },
  lectureNotice: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    backgroundColor: '#F0FDF4',
    padding: 14,
    borderRadius: 12,
  },
  lectureNoticeText: {
    fontSize: 13,
    color: '#166534',
    flex: 1,
    lineHeight: 18,
  },
  trendCard: {
    backgroundColor: '#FFFFFF',
    borderRadius: 20,
    padding: 18,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.05,
    shadowRadius: 8,
    elevation: 2,
    marginBottom: 20,
  },
  trendHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 14,
  },
  trendTitle: {
    fontSize: 16,
    fontWeight: '700',
    color: '#0F172A',
  },
  badgePill: {
    backgroundColor: '#E6F5F2',
    paddingVertical: 4,
    paddingHorizontal: 8,
    borderRadius: 12,
  },
  badgeText: {
    fontSize: 11,
    fontWeight: '700',
    color: '#0A7B68',
  },
  chartContainer: {
    position: 'relative',
    alignItems: 'center',
  },
  trendPillMarker: {
    position: 'absolute',
    right: 18,
    top: 12,
    backgroundColor: '#044E42',
    paddingVertical: 3,
    paddingHorizontal: 8,
    borderRadius: 10,
  },
  trendPillMarkerText: {
    fontSize: 11,
    fontWeight: '700',
    color: '#FFFFFF',
  },
  monthsRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    width: '100%',
    paddingHorizontal: 16,
    marginTop: 6,
  },
  monthLabel: {
    fontSize: 11,
    color: '#94A3B8',
    fontWeight: '500',
  },
  verifyActionButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#0A7B68',
    paddingVertical: 14,
    borderRadius: 16,
    gap: 8,
    shadowColor: '#0A7B68',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 8,
    elevation: 4,
  },
  verifyActionText: {
    fontSize: 15,
    fontWeight: '700',
    color: '#FFFFFF',
  },
});

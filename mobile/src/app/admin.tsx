import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  Pressable,
  Platform,
  ScrollView,
  ActivityIndicator,
  RefreshControl,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { useAuth } from '@/context/AuthContext';
import { ApiService } from '@/services/api';

interface AdminAttempt {
  created_at: string;
  face_score: number | null;
  name: string;
  result: string;
}

interface AdminStatsResponse {
  total_staff: number;
  present_today: number;
  absent_today: number;
  rejections_today: number;
}

interface CampusConfig {
  name: string;
  latitude: number;
  longitude: number;
  radius_m: number;
}

export default function AdminScreen() {
  const router = useRouter();
  const { user, apiUrl } = useAuth();
  const [stats, setStats] = useState<{
    totalEnrolled: number;
    presentToday: number;
    rejectionsToday: number;
    attendanceRate: string;
  }>({
    totalEnrolled: 0,
    presentToday: 0,
    rejectionsToday: 0,
    attendanceRate: '0%',
  });
  const [recentLogs, setRecentLogs] = useState<AdminAttempt[]>([]);
  const [campus, setCampus] = useState<CampusConfig | null>(null);
  const [loadError, setLoadError] = useState('');
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  const fetchAdminSummary = async () => {
    try {
      setLoading(true);
      setLoadError('');
      const baseUrl = apiUrl || (await ApiService.getBaseUrl());
      const headers = user?.token ? { Authorization: `Bearer ${user.token}` } : undefined;
      const res = await fetch(`${baseUrl}/admin/stats`, { headers });
      if (!res.ok) {
        throw new Error(res.status === 401 || res.status === 403
          ? 'Sign in with an administrator account to view campus data.'
          : `Could not load admin statistics (HTTP ${res.status}).`);
      }
      const data: AdminStatsResponse = await res.json();
      setStats({
        totalEnrolled: data.total_staff,
        presentToday: data.present_today,
        rejectionsToday: data.rejections_today,
        attendanceRate: data.total_staff
          ? `${(((data.total_staff - data.absent_today) / data.total_staff) * 100).toFixed(1)}%`
          : '0%',
      });

      const logsRes = await fetch(`${baseUrl}/admin/attempts?limit=10`, { headers });
      if (!logsRes.ok) {
        throw new Error(`Could not load recent attempts (HTTP ${logsRes.status}).`);
      }
      const logsData: AdminAttempt[] = await logsRes.json();
      setRecentLogs(logsData);

      const campusRes = await fetch(`${baseUrl}/admin/campus`, { headers });
      if (!campusRes.ok) {
        throw new Error(`Could not load campus geofence (HTTP ${campusRes.status}).`);
      }
      setCampus(await campusRes.json());
    } catch (e) {
      setLoadError(e instanceof Error ? e.message : 'Could not load admin data.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchAdminSummary();
  }, [apiUrl, user?.token]);

  return (
    <SafeAreaView style={styles.mobileContainer}>
      <ScrollView
        contentContainerStyle={styles.mobileScroll}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={() => {
              setRefreshing(true);
              fetchAdminSummary();
            }}
            tintColor="#06b6d4"
          />
        }
      >
        <View style={styles.mobileHeader}>
          <Text style={styles.mobileTitle}>🛡️ Admin Console</Text>
          <Text style={styles.mobileSub}>Campus biometric oversight & threat mitigation</Text>
        </View>

        {loadError ? <Text style={styles.errorText}>{loadError}</Text> : null}

        {/* KPI Cards Grid */}
        <View style={styles.kpiGrid}>
          <View style={styles.kpiCard}>
            <Text style={styles.kpiLabel}>PRESENT TODAY</Text>
            <Text style={[styles.kpiValue, { color: '#10b981' }]}>{stats.presentToday}</Text>
            <Text style={styles.kpiSub}>Verified Biometrically</Text>
          </View>
          <View style={styles.kpiCard}>
            <Text style={styles.kpiLabel}>TOTAL ENROLLED</Text>
            <Text style={[styles.kpiValue, { color: '#06b6d4' }]}>{stats.totalEnrolled}</Text>
            <Text style={styles.kpiSub}>Students & Staff</Text>
          </View>
          <View style={styles.kpiCard}>
            <Text style={styles.kpiLabel}>REJECTIONS TODAY</Text>
            <Text style={[styles.kpiValue, { color: '#f43f5e' }]}>{stats.rejectionsToday}</Text>
            <Text style={styles.kpiSub}>Rejected verification attempts</Text>
          </View>
          <View style={styles.kpiCard}>
            <Text style={styles.kpiLabel}>ATTENDANCE RATE</Text>
            <Text style={[styles.kpiValue, { color: '#8b5cf6' }]}>{stats.attendanceRate}</Text>
            <Text style={styles.kpiSub}>Present / enrolled today</Text>
          </View>
        </View>

        {/* Geofence Status */}
        <View style={styles.statusBox}>
          <Text style={styles.statusTitle}>📍 {campus?.name || 'Campus Geofence'}</Text>
          <Text style={styles.statusDetail}>
            {campus
              ? `Center: ${campus.latitude.toFixed(4)}°, ${campus.longitude.toFixed(4)}° · Radius: ${campus.radius_m} m`
              : 'Loading campus configuration…'}
          </Text>
          <View style={styles.statusBadgeActive}>
            <Text style={styles.statusBadgeText}>● GEOFENCE ENFORCEMENT ACTIVE</Text>
          </View>
        </View>

        {Platform.OS === 'web' ? (
          <Pressable
            style={styles.quickBtn}
            onPress={() => window.location.assign('/admin-portal/')}
          >
            <Text style={styles.quickBtnText}>Open full Admin Dashboard</Text>
          </Pressable>
        ) : null}

        <View style={styles.statusBox}>
          <Text style={styles.statusTitle}>Recent verification attempts</Text>
          {loading && recentLogs.length === 0 ? (
            <ActivityIndicator color="#06b6d4" />
          ) : recentLogs.length === 0 ? (
            <Text style={styles.statusDetail}>No recent attempts</Text>
          ) : (
            recentLogs.map((log, index) => (
              <Text key={`${log.created_at}-${index}`} style={styles.statusDetail}>
                {log.name} · {log.result} · Face score {log.face_score?.toFixed(2) ?? 'N/A'} ·{' '}
                {new Date(log.created_at).toLocaleString()}
              </Text>
            ))
          )}
        </View>

        {/* Quick Actions */}
        <View style={styles.quickActions}>
          <Pressable style={styles.quickBtn} onPress={() => router.push('/explore')}>
            <Text style={styles.quickBtnText}>📸 Test Face Verification</Text>
          </Pressable>
          <Pressable style={styles.quickBtn} onPress={() => router.push('/enroll')}>
            <Text style={styles.quickBtnText}>👤 Enroll New Face</Text>
          </Pressable>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  mobileContainer: {
    flex: 1,
    backgroundColor: '#0a0f1d',
  },
  mobileScroll: {
    padding: 16,
    paddingBottom: 40,
  },
  mobileHeader: {
    marginBottom: 20,
  },
  mobileTitle: {
    fontSize: 24,
    fontWeight: '800',
    color: '#f8fafc',
    marginBottom: 4,
  },
  mobileSub: {
    fontSize: 13,
    color: '#94a3b8',
  },
  kpiGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 12,
    marginBottom: 20,
  },
  kpiCard: {
    flex: 1,
    minWidth: '45%',
    backgroundColor: '#111827',
    padding: 16,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.06)',
  },
  kpiLabel: {
    fontSize: 10,
    fontWeight: '700',
    color: '#64748b',
    letterSpacing: 0.8,
    marginBottom: 6,
  },
  kpiValue: {
    fontSize: 26,
    fontWeight: '800',
    marginBottom: 4,
  },
  kpiSub: {
    fontSize: 11,
    color: '#94a3b8',
  },
  statusBox: {
    backgroundColor: '#111827',
    padding: 16,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: 'rgba(6, 182, 212, 0.2)',
    marginBottom: 20,
  },
  statusTitle: {
    fontSize: 14,
    fontWeight: '700',
    color: '#f8fafc',
    marginBottom: 4,
  },
  statusDetail: {
    fontSize: 12,
    color: '#94a3b8',
    marginBottom: 10,
  },
  errorText: {
    color: '#fb7185',
    fontSize: 13,
    marginBottom: 16,
  },
  statusBadgeActive: {
    alignSelf: 'flex-start',
    backgroundColor: 'rgba(16, 185, 129, 0.15)',
    paddingVertical: 4,
    paddingHorizontal: 10,
    borderRadius: 6,
  },
  statusBadgeText: {
    fontSize: 10,
    fontWeight: '700',
    color: '#10b981',
    letterSpacing: 0.5,
  },
  quickActions: {
    flexDirection: 'column',
    gap: 10,
  },
  quickBtn: {
    backgroundColor: 'rgba(255, 255, 255, 0.05)',
    paddingVertical: 14,
    paddingHorizontal: 18,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.1)',
    alignItems: 'center',
  },
  quickBtnText: {
    color: '#f8fafc',
    fontSize: 14,
    fontWeight: '600',
  },
});

import React, { useState } from 'react';
import {
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';

interface NotificationItem {
  id: string;
  category: 'Classes' | 'Attendance' | 'Exams' | 'Security';
  title: string;
  message: string;
  time: string;
  icon: keyof typeof Ionicons.glyphMap;
  iconBg: string;
  iconColor: string;
  unread?: boolean;
}

const NOTIFICATIONS: NotificationItem[] = [
  {
    id: '1',
    category: 'Classes',
    title: 'Class Rescheduled',
    message: 'AOA LAB (C2) rescheduled to LT-20 tomorrow at 10:40 AM',
    time: '5 min ago',
    icon: 'time-outline',
    iconBg: '#E0F2FE',
    iconColor: '#0284C7',
    unread: true,
  },
  {
    id: '2',
    category: 'Attendance',
    title: 'Attendance Marked',
    message: 'You are marked Present for CD LAB (C1) via biometric check-in.',
    time: '1 hr ago',
    icon: 'checkmark-circle-outline',
    iconBg: '#DCFCE7',
    iconColor: '#16A34A',
    unread: true,
  },
  {
    id: '3',
    category: 'Exams',
    title: 'New Exam Schedule',
    message: 'Mid Term Exam schedule released for B.Tech CSE Semester 3.',
    time: '2 hr ago',
    icon: 'newspaper-outline',
    iconBg: '#F3E8FF',
    iconColor: '#9333EA',
    unread: false,
  },
  {
    id: '4',
    category: 'Classes',
    title: 'Room Change',
    message: 'Skill Development moved to CL-27 (1st Floor) today.',
    time: '3 hr ago',
    icon: 'business-outline',
    iconBg: '#EDE9FE',
    iconColor: '#6366F1',
    unread: false,
  },
  {
    id: '5',
    category: 'Security',
    title: 'Security Alert',
    message: 'Unauthorized entry attempt detected at Main Gate perimeter.',
    time: '4 hr ago',
    icon: 'warning-outline',
    iconBg: '#FEE2E2',
    iconColor: '#DC2626',
    unread: false,
  },
  {
    id: '6',
    category: 'Classes',
    title: 'Venue Booking Approved',
    message: 'Your event \'Tech Club Activity\' in Auditorium is approved.',
    time: '1 day ago',
    icon: 'calendar-outline',
    iconBg: '#ECFDF5',
    iconColor: '#059669',
    unread: false,
  },
];

const CATEGORIES = ['All', 'Classes', 'Attendance', 'Exams'];

export default function NotificationsScreen() {
  const router = useRouter();
  const [selectedCategory, setSelectedCategory] = useState('All');

  const filtered = selectedCategory === 'All'
    ? NOTIFICATIONS
    : NOTIFICATIONS.filter((n) => n.category === selectedCategory);

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
        <Text style={styles.headerTitle}>Notifications</Text>
        <TouchableOpacity
          style={styles.markReadButton}
          onPress={() => alert('All notifications marked as read')}
        >
          <Ionicons name="checkmark-done" size={20} color="#0A7B68" />
        </TouchableOpacity>
      </View>

      {/* Filter Pills */}
      <View style={styles.pillsContainer}>
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={styles.pillsScroll}
        >
          {CATEGORIES.map((cat) => {
            const isSelected = selectedCategory === cat;
            return (
              <TouchableOpacity
                key={cat}
                style={[styles.pill, isSelected && styles.pillActive]}
                onPress={() => setSelectedCategory(cat)}
                activeOpacity={0.8}
              >
                <Text style={[styles.pillText, isSelected && styles.pillTextActive]}>
                  {cat}
                </Text>
              </TouchableOpacity>
            );
          })}
        </ScrollView>
      </View>

      {/* Notifications List */}
      <ScrollView
        style={styles.scroll}
        contentContainerStyle={styles.listContainer}
        showsVerticalScrollIndicator={false}
      >
        {filtered.map((item) => (
          <View
            key={item.id}
            style={[styles.card, item.unread && styles.cardUnread]}
          >
            <View style={[styles.iconBox, { backgroundColor: item.iconBg }]}>
              <Ionicons name={item.icon} size={20} color={item.iconColor} />
            </View>

            <View style={styles.contentBox}>
              <View style={styles.cardHeaderRow}>
                <Text style={styles.cardTitle}>{item.title}</Text>
                <Text style={styles.cardTime}>{item.time}</Text>
              </View>
              <Text style={styles.cardMessage}>{item.message}</Text>
            </View>

            {item.unread && <View style={styles.unreadDot} />}
          </View>
        ))}
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
  markReadButton: {
    width: 38,
    height: 38,
    borderRadius: 12,
    backgroundColor: '#E6F5F2',
    justifyContent: 'center',
    alignItems: 'center',
  },
  pillsContainer: {
    backgroundColor: '#FFFFFF',
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#E2E8F0',
  },
  pillsScroll: {
    paddingHorizontal: 16,
    gap: 8,
  },
  pill: {
    paddingVertical: 6,
    paddingHorizontal: 16,
    borderRadius: 20,
    backgroundColor: '#F1F5F9',
  },
  pillActive: {
    backgroundColor: '#044E42',
  },
  pillText: {
    fontSize: 13,
    fontWeight: '600',
    color: '#64748B',
  },
  pillTextActive: {
    color: '#FFFFFF',
  },
  scroll: {
    flex: 1,
  },
  listContainer: {
    padding: 16,
    paddingBottom: 24,
    gap: 12,
  },
  card: {
    flexDirection: 'row',
    backgroundColor: '#FFFFFF',
    borderRadius: 16,
    padding: 14,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.04,
    shadowRadius: 6,
    elevation: 2,
    alignItems: 'flex-start',
  },
  cardUnread: {
    borderLeftWidth: 3.5,
    borderLeftColor: '#0A7B68',
  },
  iconBox: {
    width: 38,
    height: 38,
    borderRadius: 12,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 12,
  },
  contentBox: {
    flex: 1,
    gap: 4,
  },
  cardHeaderRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  cardTitle: {
    fontSize: 15,
    fontWeight: '700',
    color: '#1E293B',
  },
  cardTime: {
    fontSize: 11,
    color: '#94A3B8',
    fontWeight: '500',
  },
  cardMessage: {
    fontSize: 13,
    color: '#475569',
    lineHeight: 18,
  },
  unreadDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: '#0A7B68',
    marginLeft: 6,
    marginTop: 6,
  },
});

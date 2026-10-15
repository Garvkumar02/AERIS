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

interface ClassItem {
  id: string;
  time: string;
  name: string;
  room: string;
  floor: string;
  isBreak?: boolean;
  isActive?: boolean;
}

const SCHEDULE_DATA: Record<string, ClassItem[]> = {
  Mon: [
    { id: '1', time: '09:00 - 09:50', name: 'CD Lab (C1)', room: 'NAB LAB | C1', floor: '1st Floor' },
    { id: '2', time: '09:50 - 10:40', name: 'ADA Lab (C2)', room: 'LT-24', floor: '1st Floor' },
    { id: '3', time: '10:40 - 11:30', name: 'Skill Development', room: 'CL-27', floor: '1st Floor', isActive: true },
    { id: '4', time: '11:30 - 12:20', name: 'Library Hour', room: 'Reading Club | Library', floor: '1st Floor' },
    { id: '5', time: '12:20 - 01:10', name: 'Break', room: 'Cafeteria / Lawn', floor: 'Ground Floor', isBreak: true },
    { id: '6', time: '01:10 - 02:00', name: 'CG (Computer Graphics)', room: 'LT-20', floor: '1st Floor' },
  ],
  Tue: [
    { id: '21', time: '09:00 - 09:50', name: 'AI & Machine Learning', room: 'LT-24', floor: '1st Floor' },
    { id: '22', time: '09:50 - 10:40', name: 'Operating Systems', room: 'LT-16', floor: '1st Floor' },
    { id: '23', time: '10:40 - 11:30', name: 'Data Structures Lab', room: 'CL-02', floor: '2nd Floor' },
    { id: '24', time: '12:20 - 01:10', name: 'Break', room: 'Cafeteria', floor: 'Ground Floor', isBreak: true },
    { id: '25', time: '01:10 - 02:00', name: 'DBMS Lecture', room: 'LT-11', floor: '1st Floor' },
  ],
  Wed: [
    { id: '31', time: '09:00 - 10:40', name: 'Full Stack Project Lab', room: 'Lab 4', floor: '2nd Floor' },
    { id: '32', time: '10:40 - 11:30', name: 'Computer Networks', room: 'LT-20', floor: '1st Floor' },
    { id: '33', time: '12:20 - 01:10', name: 'Break', room: 'Cafeteria', floor: 'Ground Floor', isBreak: true },
    { id: '34', time: '01:10 - 02:50', name: 'Cyber Security Workshop', room: 'Auditorium', floor: 'Ground Floor' },
  ],
  Thu: [
    { id: '41', time: '09:00 - 09:50', name: 'Compiler Design', room: 'LT-16', floor: '1st Floor' },
    { id: '42', time: '09:50 - 10:40', name: 'Software Engineering', room: 'LT-24', floor: '1st Floor' },
    { id: '43', time: '10:40 - 11:30', name: 'Cloud Computing', room: 'LT-11', floor: '1st Floor' },
  ],
  Fri: [
    { id: '51', time: '09:00 - 10:40', name: 'AI & ML Seminar', room: 'Auditorium', floor: 'Ground Floor' },
    { id: '52', time: '10:40 - 11:30', name: 'Group Discussion', room: 'Reading Club', floor: '1st Floor' },
  ],
  Sat: [
    { id: '61', time: '09:30 - 11:30', name: 'Hackathon & Coding Club', room: 'ECE Labs', floor: '1st Floor' },
  ],
};

const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

export default function TimetableScreen() {
  const router = useRouter();
  const [selectedDay, setSelectedDay] = useState('Mon');
  const classes = SCHEDULE_DATA[selectedDay] || [];

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
        <Text style={styles.headerTitle}>Timetable</Text>
        <View style={{ width: 38 }} />
      </View>

      {/* Days Pill Selector */}
      <View style={styles.daysScrollWrapper}>
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={styles.daysContainer}
        >
          {DAYS.map((day) => {
            const isCurrent = day === selectedDay;
            return (
              <TouchableOpacity
                key={day}
                style={[styles.dayPill, isCurrent && styles.dayPillActive]}
                onPress={() => setSelectedDay(day)}
                activeOpacity={0.8}
              >
                <Text style={[styles.dayPillText, isCurrent && styles.dayPillTextActive]}>
                  {day}
                </Text>
              </TouchableOpacity>
            );
          })}
        </ScrollView>
      </View>

      {/* Classes List */}
      <ScrollView
        style={styles.scroll}
        contentContainerStyle={styles.listContainer}
        showsVerticalScrollIndicator={false}
      >
        {classes.map((item) => (
          <View
            key={item.id}
            style={[
              styles.classCard,
              item.isBreak && styles.breakCard,
              item.isActive && styles.activeClassCard,
            ]}
          >
            {/* Left timeline accent line */}
            <View
              style={[
                styles.timelineIndicator,
                item.isBreak
                  ? { backgroundColor: '#F59E0B' }
                  : item.isActive
                  ? { backgroundColor: '#0A7B68' }
                  : { backgroundColor: '#94A3B8' },
              ]}
            />

            <View style={styles.cardContent}>
              <View style={styles.timeRow}>
                <Text style={styles.timeText}>{item.time}</Text>
                {item.isActive && (
                  <View style={styles.liveBadge}>
                    <View style={styles.liveDot} />
                    <Text style={styles.liveBadgeText}>Ongoing</Text>
                  </View>
                )}
              </View>

              <Text style={styles.className}>{item.name}</Text>

              <View style={styles.locationRow}>
                <Ionicons
                  name={item.isBreak ? 'cafe-outline' : 'location-outline'}
                  size={15}
                  color={item.isBreak ? '#D97706' : '#0A7B68'}
                />
                <Text style={styles.locationText}>
                  {item.room}  •  {item.floor}
                </Text>
              </View>
            </View>
          </View>
        ))}
      </ScrollView>

      {/* Bottom CTA Button: Navigate to Class */}
      <View style={styles.bottomBar}>
        <TouchableOpacity
          style={styles.navigateButton}
          onPress={() => router.push('/campus-map')}
          activeOpacity={0.85}
        >
          <Ionicons name="navigate" size={20} color="#FFFFFF" />
          <View>
            <Text style={styles.navigateTitle}>Navigate to Class</Text>
            <Text style={styles.navigateSubtitle}>Get directions on campus map</Text>
          </View>
        </TouchableOpacity>
      </View>
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
  daysScrollWrapper: {
    backgroundColor: '#FFFFFF',
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#E2E8F0',
  },
  daysContainer: {
    paddingHorizontal: 16,
    gap: 8,
  },
  dayPill: {
    paddingVertical: 8,
    paddingHorizontal: 16,
    borderRadius: 20,
    backgroundColor: '#F1F5F9',
  },
  dayPillActive: {
    backgroundColor: '#044E42',
  },
  dayPillText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#64748B',
  },
  dayPillTextActive: {
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
  classCard: {
    flexDirection: 'row',
    backgroundColor: '#FFFFFF',
    borderRadius: 16,
    padding: 14,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.04,
    shadowRadius: 6,
    elevation: 2,
    overflow: 'hidden',
  },
  breakCard: {
    backgroundColor: '#FFFBEB',
    borderColor: '#FEF3C7',
    borderWidth: 1,
  },
  activeClassCard: {
    borderColor: '#0A7B68',
    borderWidth: 1.5,
  },
  timelineIndicator: {
    width: 4,
    borderRadius: 2,
    marginRight: 12,
  },
  cardContent: {
    flex: 1,
    gap: 6,
  },
  timeRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  timeText: {
    fontSize: 13,
    fontWeight: '600',
    color: '#64748B',
  },
  liveBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#E8F5F1',
    paddingVertical: 2,
    paddingHorizontal: 8,
    borderRadius: 10,
    gap: 5,
  },
  liveDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: '#0A7B68',
  },
  liveBadgeText: {
    fontSize: 11,
    fontWeight: '700',
    color: '#0A7B68',
  },
  className: {
    fontSize: 16,
    fontWeight: '700',
    color: '#1E293B',
  },
  locationRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginTop: 2,
  },
  locationText: {
    fontSize: 13,
    color: '#64748B',
    fontWeight: '500',
  },
  bottomBar: {
    padding: 16,
    backgroundColor: '#FFFFFF',
    borderTopWidth: 1,
    borderTopColor: '#E2E8F0',
  },
  navigateButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#044E42',
    paddingVertical: 14,
    borderRadius: 16,
    gap: 12,
    shadowColor: '#044E42',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.25,
    shadowRadius: 8,
    elevation: 4,
  },
  navigateTitle: {
    fontSize: 15,
    fontWeight: '700',
    color: '#FFFFFF',
  },
  navigateSubtitle: {
    fontSize: 11,
    color: '#A7F3D0',
    fontWeight: '500',
  },
});

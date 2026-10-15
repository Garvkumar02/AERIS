import React, { useState } from 'react';
import {
  Dimensions,
  Image,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';

const { width } = Dimensions.get('window');

interface RoomPin {
  id: string;
  name: string;
  type: string;
  block: string;
  floor: string;
  xPercent: number; // For interactive overlay
  yPercent: number;
}

const ROOMS_ECE: RoomPin[] = [
  { id: 'lt16', name: 'LT-16 Lecture Theatre', type: 'Lecture Theatre', block: 'ECE Block', floor: 'First Floor', xPercent: 24, yPercent: 22 },
  { id: 'lt11', name: 'LT-11 Classroom', type: 'Classroom', block: 'ECE Block', floor: 'First Floor', xPercent: 35, yPercent: 47 },
  { id: 'ece_lab', name: 'ECE Labs', type: 'Research & Practical Lab', block: 'East Wing', floor: 'First Floor', xPercent: 78, yPercent: 25 },
  { id: 'lib', name: 'Central Library', type: 'Quiet Study & Digital Resources', block: 'Central Core', floor: 'First Floor', xPercent: 52, yPercent: 56 },
  { id: 'audi', name: 'Auditorium Hall', type: 'Events & Seminars', block: 'South Wing', floor: 'Ground Floor', xPercent: 50, yPercent: 82 },
];

const ROOMS_CSE: RoomPin[] = [
  { id: 'cl02', name: 'FF-CL 02 Computer Lab', type: 'AI & Data Lab', block: 'CSE Block', floor: 'Second Floor', xPercent: 68, yPercent: 28 },
  { id: 'lt24', name: 'LT-24 Smart Room', type: 'AI & ML Lecture Hall', block: 'North Wing', floor: 'Second Floor', xPercent: 28, yPercent: 32 },
  { id: 'staff_cse', name: 'CSE Faculty Lounge', type: 'Staff Offices', block: 'West Wing', floor: 'Second Floor', xPercent: 44, yPercent: 52 },
];

export default function CampusMapScreen() {
  const router = useRouter();
  const [selectedFloor, setSelectedFloor] = useState<'ece' | 'cse'>('ece');
  const [selectedRoom, setSelectedRoom] = useState<RoomPin>(ROOMS_ECE[0]);
  const [navigating, setNavigating] = useState(false);

  const activeRooms = selectedFloor === 'ece' ? ROOMS_ECE : ROOMS_CSE;

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
        <Text style={styles.headerTitle}>Campus Map</Text>
        <TouchableOpacity
          style={styles.searchButton}
          activeOpacity={0.7}
          onPress={() => alert('Search Campus: Select any room below or on the 3D map.')}
        >
          <Ionicons name="search-outline" size={20} color="#0A7B68" />
        </TouchableOpacity>
      </View>

      {/* Floor selector pills */}
      <View style={styles.floorPillContainer}>
        <TouchableOpacity
          style={[styles.floorPill, selectedFloor === 'ece' && styles.floorPillActive]}
          onPress={() => {
            setSelectedFloor('ece');
            setSelectedRoom(ROOMS_ECE[0]);
          }}
          activeOpacity={0.8}
        >
          <Text style={[styles.floorPillText, selectedFloor === 'ece' && styles.floorPillTextActive]}>
            First Floor (ECE)
          </Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={[styles.floorPill, selectedFloor === 'cse' && styles.floorPillActive]}
          onPress={() => {
            setSelectedFloor('cse');
            setSelectedRoom(ROOMS_CSE[0]);
          }}
          activeOpacity={0.8}
        >
          <Text style={[styles.floorPillText, selectedFloor === 'cse' && styles.floorPillTextActive]}>
            Second Floor (CSE)
          </Text>
        </TouchableOpacity>
      </View>

      {/* 3D Map Area */}
      <ScrollView
        style={styles.scroll}
        contentContainerStyle={styles.scrollContent}
        maximumZoomScale={2.5}
        minimumZoomScale={1}
        showsVerticalScrollIndicator={false}
      >
        <View style={styles.mapGraphicWrapper}>
          <Image
            source={require('@/assets/images/campus_floor_3d.jpg')}
            style={styles.mapImage}
            resizeMode="cover"
          />

          {/* Interactive Room Pins overlay */}
          {activeRooms.map((room) => {
            const isSelected = selectedRoom.id === room.id;
            return (
              <TouchableOpacity
                key={room.id}
                style={[
                  styles.roomPin,
                  { left: `${room.xPercent}%`, top: `${room.yPercent}%` },
                  isSelected && styles.roomPinSelected,
                ]}
                onPress={() => {
                  setSelectedRoom(room);
                  setNavigating(false);
                }}
                activeOpacity={0.8}
              >
                <View style={[styles.pinDot, isSelected && styles.pinDotSelected]} />
                <Text style={[styles.pinLabel, isSelected && styles.pinLabelSelected]}>
                  {room.name.split(' ')[0]}
                </Text>
              </TouchableOpacity>
            );
          })}
        </View>

        {/* Quick Room Badges List */}
        <View style={styles.roomBadgesRow}>
          <Text style={styles.roomListHeader}>Quick Select Room:</Text>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.badgesScroll}>
            {activeRooms.map((room) => (
              <TouchableOpacity
                key={room.id}
                style={[
                  styles.badgeButton,
                  selectedRoom.id === room.id && styles.badgeButtonSelected,
                ]}
                onPress={() => {
                  setSelectedRoom(room);
                  setNavigating(false);
                }}
              >
                <Ionicons
                  name={selectedRoom.id === room.id ? 'radio-button-on' : 'radio-button-off'}
                  size={14}
                  color={selectedRoom.id === room.id ? '#FFFFFF' : '#0A7B68'}
                />
                <Text
                  style={[
                    styles.badgeButtonText,
                    selectedRoom.id === room.id && styles.badgeButtonTextSelected,
                  ]}
                >
                  {room.name.split(' ')[0]}
                </Text>
              </TouchableOpacity>
            ))}
          </ScrollView>
        </View>
      </ScrollView>

      {/* Selected Room Bottom Navigation Card */}
      <View style={styles.bottomCardWrapper}>
        <View style={styles.roomInfoCard}>
          <View style={styles.roomTextContainer}>
            <Text style={styles.roomCardTitle}>{selectedRoom.name}</Text>
            <Text style={styles.roomCardSubtitle}>
              {selectedRoom.floor} • {selectedRoom.block}
            </Text>
            <Text style={styles.roomCardType}>{selectedRoom.type}</Text>
          </View>

          <TouchableOpacity
            style={[styles.navigateActionButton, navigating && styles.navigatingActiveButton]}
            onPress={() => setNavigating(!navigating)}
            activeOpacity={0.85}
          >
            <Ionicons
              name={navigating ? 'checkmark-circle' : 'navigate'}
              size={18}
              color="#FFFFFF"
            />
            <Text style={styles.navigateActionText}>
              {navigating ? 'Route Active' : 'Navigate'}
            </Text>
          </TouchableOpacity>
        </View>

        {navigating && (
          <View style={styles.navigationNoticeBanner}>
            <Ionicons name="compass" size={16} color="#0A7B68" />
            <Text style={styles.navigationNoticeText}>
              Head straight down Central Hallway, turn right at Staircase B (30 meters).
            </Text>
          </View>
        )}
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
  searchButton: {
    width: 38,
    height: 38,
    borderRadius: 12,
    backgroundColor: '#E6F5F2',
    justifyContent: 'center',
    alignItems: 'center',
  },
  floorPillContainer: {
    flexDirection: 'row',
    paddingHorizontal: 16,
    paddingVertical: 12,
    backgroundColor: '#FFFFFF',
    borderBottomWidth: 1,
    borderBottomColor: '#E2E8F0',
    gap: 10,
  },
  floorPill: {
    paddingVertical: 8,
    paddingHorizontal: 16,
    borderRadius: 20,
    backgroundColor: '#F1F5F9',
  },
  floorPillActive: {
    backgroundColor: '#044E42',
  },
  floorPillText: {
    fontSize: 13,
    fontWeight: '600',
    color: '#64748B',
  },
  floorPillTextActive: {
    color: '#FFFFFF',
  },
  scroll: {
    flex: 1,
  },
  scrollContent: {
    paddingBottom: 16,
  },
  mapGraphicWrapper: {
    position: 'relative',
    width: width - 32,
    height: (width - 32) * 1.3,
    alignSelf: 'center',
    marginTop: 16,
    borderRadius: 24,
    overflow: 'hidden',
    backgroundColor: '#E2E8F0',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.08,
    shadowRadius: 10,
    elevation: 3,
  },
  mapImage: {
    width: '100%',
    height: '100%',
  },
  roomPin: {
    position: 'absolute',
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: 'rgba(255, 255, 255, 0.92)',
    paddingVertical: 4,
    paddingHorizontal: 8,
    borderRadius: 14,
    gap: 4,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.15,
    shadowRadius: 4,
    elevation: 3,
  },
  roomPinSelected: {
    backgroundColor: '#044E42',
  },
  pinDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: '#0A7B68',
  },
  pinDotSelected: {
    backgroundColor: '#10B981',
  },
  pinLabel: {
    fontSize: 11,
    fontWeight: '700',
    color: '#1E293B',
  },
  pinLabelSelected: {
    color: '#FFFFFF',
  },
  roomBadgesRow: {
    marginTop: 16,
    paddingHorizontal: 16,
  },
  roomListHeader: {
    fontSize: 12,
    fontWeight: '600',
    color: '#64748B',
    marginBottom: 8,
  },
  badgesScroll: {
    gap: 8,
  },
  badgeButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingVertical: 6,
    paddingHorizontal: 12,
    backgroundColor: '#FFFFFF',
    borderWidth: 1,
    borderColor: '#E2E8F0',
    borderRadius: 16,
  },
  badgeButtonSelected: {
    backgroundColor: '#0A7B68',
    borderColor: '#0A7B68',
  },
  badgeButtonText: {
    fontSize: 12,
    fontWeight: '600',
    color: '#334155',
  },
  badgeButtonTextSelected: {
    color: '#FFFFFF',
  },
  bottomCardWrapper: {
    backgroundColor: '#FFFFFF',
    padding: 16,
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: -4 },
    shadowOpacity: 0.06,
    shadowRadius: 10,
    elevation: 6,
  },
  roomInfoCard: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  roomTextContainer: {
    flex: 1,
    marginRight: 14,
    gap: 2,
  },
  roomCardTitle: {
    fontSize: 16,
    fontWeight: '700',
    color: '#0F172A',
  },
  roomCardSubtitle: {
    fontSize: 12,
    fontWeight: '500',
    color: '#0A7B68',
  },
  roomCardType: {
    fontSize: 11,
    color: '#64748B',
    marginTop: 2,
  },
  navigateActionButton: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#0A7B68',
    paddingVertical: 12,
    paddingHorizontal: 18,
    borderRadius: 16,
    gap: 6,
  },
  navigatingActiveButton: {
    backgroundColor: '#044E42',
  },
  navigateActionText: {
    fontSize: 14,
    fontWeight: '700',
    color: '#FFFFFF',
  },
  navigationNoticeBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#E8F5F1',
    padding: 10,
    borderRadius: 12,
    marginTop: 12,
    gap: 8,
  },
  navigationNoticeText: {
    fontSize: 12,
    color: '#044E42',
    fontWeight: '500',
    flex: 1,
  },
});

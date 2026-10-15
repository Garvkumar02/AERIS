import {
  Tabs,
  TabList,
  TabTrigger,
  TabSlot,
  TabTriggerSlotProps,
  TabListProps,
} from 'expo-router/ui';
import { Pressable, useColorScheme, View, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import { ThemedText } from './themed-text';
import { ThemedView } from './themed-view';

import { Colors, MaxContentWidth, Spacing } from '@/constants/theme';
import { useAuth } from '@/context/AuthContext';

export default function AppTabs() {
  const { user } = useAuth();

  return (
    <Tabs>
      <TabSlot style={{ flex: 1, paddingBottom: 76 }} />
      <TabList asChild>
        <CustomTabList>
          <TabTrigger name="home" href="/" asChild>
            <TabButton icon="home-outline">Home</TabButton>
          </TabTrigger>

          <TabTrigger name="timetable" href="/timetable" asChild>
            <TabButton icon="calendar-outline">Schedule</TabButton>
          </TabTrigger>

          <TabTrigger name="campus-map" href="/campus-map" asChild>
            <TabButton icon="map-outline">Map</TabButton>
          </TabTrigger>

          <TabTrigger name="notifications" href="/notifications" asChild>
            <TabButton icon="notifications-outline">Alerts</TabButton>
          </TabTrigger>

          <TabTrigger name="attendance" href="/attendance" asChild>
            <TabButton icon="pie-chart-outline">Attendance</TabButton>
          </TabTrigger>

          {user?.role === 'admin' ? (
            <TabTrigger name="admin" href="/admin" asChild>
              <TabButton icon="shield-outline">Admin</TabButton>
            </TabTrigger>
          ) : null}
        </CustomTabList>
      </TabList>
    </Tabs>
  );
}

export function TabButton({
  children,
  isFocused,
  icon,
  ...props
}: TabTriggerSlotProps & { icon?: keyof typeof Ionicons.glyphMap }) {
  return (
    <Pressable {...props} style={({ pressed }) => [styles.tabPressable, pressed && styles.pressed]}>
      <View
        style={[
          styles.tabButtonView,
          isFocused ? styles.tabButtonActive : styles.tabButtonInactive,
        ]}
      >
        {icon && (
          <Ionicons
            name={icon}
            size={18}
            color={isFocused ? '#FFFFFF' : '#64748B'}
          />
        )}
        <ThemedText
          type="smallBold"
          style={{ color: isFocused ? '#FFFFFF' : '#64748B', fontSize: 12 }}
        >
          {children}
        </ThemedText>
      </View>
    </Pressable>
  );
}

export function CustomTabList(props: TabListProps) {
  const scheme = useColorScheme();
  const colors = Colors[scheme === 'unspecified' ? 'light' : scheme];

  return (
    <View {...props} style={styles.tabListContainer}>
      <View style={styles.innerContainer}>
        {props.children}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  tabListContainer: {
    position: 'absolute',
    bottom: 0,
    width: '100%',
    padding: Spacing.two,
    justifyContent: 'center',
    alignItems: 'center',
    flexDirection: 'row',
    backgroundColor: 'rgba(255, 255, 255, 0.95)',
    borderTopWidth: 1,
    borderTopColor: '#E2E8F0',
  },
  innerContainer: {
    paddingVertical: 6,
    paddingHorizontal: 12,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-around',
    flexGrow: 1,
    gap: 8,
    maxWidth: MaxContentWidth,
  },
  tabPressable: {
    flex: 1,
    alignItems: 'center',
  },
  pressed: {
    opacity: 0.7,
  },
  tabButtonView: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingVertical: 8,
    paddingHorizontal: 14,
    borderRadius: 20,
  },
  tabButtonActive: {
    backgroundColor: '#044E42',
  },
  tabButtonInactive: {
    backgroundColor: 'transparent',
  },
});

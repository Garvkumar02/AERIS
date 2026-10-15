import AsyncStorage from '@react-native-async-storage/async-storage';
import Constants from 'expo-constants';
import { Platform } from 'react-native';

const STORAGE_KEY_API_URL = '@aeris_api_url';
const STORAGE_KEY_TOKEN = '@aeris_auth_token';
const STORAGE_KEY_USER = '@aeris_auth_user';
const STORAGE_KEY_DEVICE_ID = '@aeris_device_id';
const LEGACY_API_URLS = new Set([
  'http://192.168.5.236:8081',
  'http://10.0.2.2:8081',
  'http://127.0.0.1:8081',
]);

// Default base URL depending on platform
export const getDefaultApiUrl = (): string => {
  const hostUri = Constants.expoConfig?.hostUri;
  if (hostUri) {
    // If running in tunnel mode (exp.direct or ngrok), Metro itself proxies all API routes over HTTPS!
    if (hostUri.includes('.exp.direct') || hostUri.includes('.ngrok')) {
      return `https://${hostUri}`;
    }
    const host = hostUri.replace(/:\d+$/, '');
    return `http://${host}:8000`;
  }

  const configuredApiUrl = process.env.EXPO_PUBLIC_API_URL;
  if (Platform.OS === 'web') {
    return process.env.EXPO_PUBLIC_WEB_API_URL ||
      configuredApiUrl ||
      (typeof window === 'undefined' ? 'http://127.0.0.1:8000' : window.location.origin);
  }

  if (configuredApiUrl) {
    return configuredApiUrl;
  }

  return Platform.OS === 'android' ? 'http://10.0.2.2:8000' : 'http://127.0.0.1:8000';
};

export interface UserProfile {
  employee_id: string;
  name: string;
  role: 'student' | 'staff' | 'admin';
  token: string;
  email?: string;
}

export interface AttendanceRecordItem {
  day: string;
  checked_in_at: string;
  risk_score: number;
}

export interface ServerHealth {
  online: boolean;
  project?: string;
  version?: string;
  error?: string;
}

export class ApiService {
  private static cachedBaseUrl: string | null = null;

  static async getBaseUrl(): Promise<string> {
    if (Platform.OS === 'web' && typeof window !== 'undefined') {
      this.cachedBaseUrl = getDefaultApiUrl();
      return this.cachedBaseUrl;
    }
    if (this.cachedBaseUrl) return this.cachedBaseUrl;
    try {
      const stored = await AsyncStorage.getItem(STORAGE_KEY_API_URL);
      if (stored && stored.trim().length > 0) {
        const storedUrl = stored.trim();
        const hostUri = Constants.expoConfig?.hostUri;
        // If we are on a tunnel, discard any stale LAN 192.168.x IP so tunnel proxy is used!
        if (hostUri && (hostUri.includes('.exp.direct') || hostUri.includes('.ngrok')) && storedUrl.includes('192.168.')) {
          this.cachedBaseUrl = getDefaultApiUrl();
          await AsyncStorage.setItem(STORAGE_KEY_API_URL, this.cachedBaseUrl);
          return this.cachedBaseUrl;
        }
        if (Platform.OS !== 'web' && LEGACY_API_URLS.has(storedUrl)) {
          this.cachedBaseUrl = getDefaultApiUrl();
          await AsyncStorage.setItem(STORAGE_KEY_API_URL, this.cachedBaseUrl);
          return this.cachedBaseUrl;
        }
        this.cachedBaseUrl = storedUrl;
        return this.cachedBaseUrl;
      }
    } catch {
      // Fallback
    }
    this.cachedBaseUrl = getDefaultApiUrl();
    return this.cachedBaseUrl;
  }

  static async setBaseUrl(url: string): Promise<void> {
    const cleanUrl = url.trim().replace(/\/+$/, '');
    this.cachedBaseUrl = cleanUrl;
    await AsyncStorage.setItem(STORAGE_KEY_API_URL, cleanUrl);
  }

  static async getDeviceId(): Promise<string> {
    const stored = await AsyncStorage.getItem(STORAGE_KEY_DEVICE_ID);
    if (stored) return stored;

    const deviceId = `aeris-${Platform.OS}-${Date.now().toString(36)}-${Math.random()
      .toString(36)
      .slice(2, 12)}`;
    await AsyncStorage.setItem(STORAGE_KEY_DEVICE_ID, deviceId);
    return deviceId;
  }

  static async registerDevice(token: string, deviceId: string): Promise<void> {
    const baseUrl = await this.getBaseUrl();
    const res = await fetch(`${baseUrl}/devices/register`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ device_id: deviceId, platform: Platform.OS }),
    });
    const data = await res.json().catch(() => null);
    if (!res.ok) {
      throw new Error(data?.detail || `Device registration failed (HTTP ${res.status}).`);
    }
  }

  static async checkHealth(): Promise<ServerHealth> {
    try {
      const baseUrl = await this.getBaseUrl();
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 4000);

      const res = await fetch(`${baseUrl}/health`, {
        method: 'GET',
        signal: controller.signal,
      });
      clearTimeout(timeoutId);

      if (res.ok) {
        const data = await res.json();
        return { online: true, project: data.project, version: data.version };
      }
      return { online: false, error: `Server returned HTTP ${res.status}` };
    } catch (err: any) {
      return {
        online: false,
        error: err.name === 'AbortError' ? 'Connection timed out' : 'Cannot reach server',
      };
    }
  }

  static async login(
    email: string,
    password: string,
    expectedRole?: UserProfile['role'],
  ): Promise<UserProfile> {
    const baseUrl = await this.getBaseUrl();
    const res = await fetch(`${baseUrl}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: email.trim(), password }),
    });

    const data = await res.json().catch(() => null);
    if (!res.ok) {
      throw new Error(
        data?.detail || `Login failed (HTTP ${res.status}). Please check credentials and server logs.`,
      );
    }
    if (!data) {
      throw new Error('The server returned an invalid response. Please try again.');
    }
    if (expectedRole && data.role !== expectedRole) {
      throw new Error(`This account is registered as ${data.role}, not ${expectedRole}.`);
    }

    const profile: UserProfile = {
      token: data.token,
      role: data.role,
      name: data.name,
      employee_id: data.employee_id,
      email: email.trim(),
    };

    await AsyncStorage.setItem(STORAGE_KEY_TOKEN, profile.token);
    await AsyncStorage.setItem(STORAGE_KEY_USER, JSON.stringify(profile));

    return profile;
  }

  static async registerStudent(details: {
    name: string;
    employeeId: string;
    email: string;
    password: string;
  }): Promise<UserProfile> {
    const baseUrl = await this.getBaseUrl();
    const res = await fetch(`${baseUrl}/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: details.name.trim(),
        employee_id: details.employeeId.trim(),
        email: details.email.trim(),
        password: details.password,
      }),
    });

    const data = await res.json().catch(() => null);
    if (!res.ok) {
      throw new Error(data?.detail || `Student registration failed (HTTP ${res.status}).`);
    }
    if (!data) {
      throw new Error('The server returned an invalid response. Please try again.');
    }

    const profile: UserProfile = {
      token: data.token,
      role: data.role,
      name: data.name,
      employee_id: data.employee_id,
      email: details.email.trim(),
    };
    await AsyncStorage.setItem(STORAGE_KEY_TOKEN, profile.token);
    await AsyncStorage.setItem(STORAGE_KEY_USER, JSON.stringify(profile));
    return profile;
  }

  static async getStoredSession(): Promise<UserProfile | null> {
    try {
      const rawUser = await AsyncStorage.getItem(STORAGE_KEY_USER);
      const token = await AsyncStorage.getItem(STORAGE_KEY_TOKEN);
      if (rawUser && token) {
        const user = JSON.parse(rawUser);
        user.token = token;
        return user;
      }
    } catch {
      // Ignored
    }
    return null;
  }

  static async clearSession(): Promise<void> {
    await AsyncStorage.multiRemove([STORAGE_KEY_TOKEN, STORAGE_KEY_USER]);
  }

  static async getMyAttendance(token: string): Promise<AttendanceRecordItem[]> {
    const baseUrl = await this.getBaseUrl();
    const res = await fetch(`${baseUrl}/attendance/me`, {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Failed to fetch attendance history');
    }

    return await res.json();
  }

  static async createAttendanceSession(token: string): Promise<{
    session_id: string;
    challenge: 'TURN_LEFT' | 'TURN_RIGHT';
    expires_in: number;
  }> {
    const baseUrl = await this.getBaseUrl();
    const res = await fetch(`${baseUrl}/attendance/session`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Failed to create attendance session');
    }

    return await res.json();
  }

  static async verifyAttendance(
    token: string,
    formData: FormData
  ): Promise<{
    result: 'ACCEPT' | 'REJECT' | 'ALREADY_MARKED';
    code: string | null;
    message: string;
  }> {
    const baseUrl = await this.getBaseUrl();
    const res = await fetch(`${baseUrl}/attendance/verify`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
        // Note: Do NOT set Content-Type header manually when sending FormData,
        // fetch will automatically set multipart/form-data with the correct boundary!
      },
      body: formData,
    });

    const data = await res.json();
    return data;
  }

  static async verifyWebcamAttendance(
    token: string,
    formData: FormData
  ): Promise<{
    result: 'ACCEPT' | 'REJECT';
    code?: string;
    message: string;
    student_name?: string;
    employee_id?: string;
    confidence_pct?: number;
    ledger_hash?: string;
    timestamp?: string;
  }> {
    const baseUrl = await this.getBaseUrl();
    const res = await fetch(`${baseUrl}/attendance/webcam-verify`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
      },
      body: formData,
    });
    const data = await res.json();
    return data;
  }

  static async mobileInstantCheckin(params: {
    lecture_id?: string;
    token?: string;
    student_id: string;
    lat?: number;
    lng?: number;
    device_id?: string;
  }): Promise<{
    result: 'ACCEPT' | 'REJECT';
    status?: string;
    code?: string;
    message: string;
    student_name?: string;
    student_id?: string;
    department?: string;
    subject_name?: string;
    subject_code?: string;
    room_name?: string;
    faculty_name?: string;
    section?: string;
    checked_in_at?: string;
    ledger_hash?: string;
    verification_method?: string;
    double_verified?: boolean;
  }> {
    const baseUrl = await this.getBaseUrl();
    const res = await fetch(`${baseUrl}/attendance/mobile-instant-checkin`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        lecture_id: params.lecture_id,
        token: params.token,
        student_id: params.student_id,
        lat: params.lat ?? 26.8228,
        lng: params.lng ?? 75.8648,
        device_id: params.device_id,
      }),
    });
    const data = await res.json();
    return data;
  }

  static async getBiometricStatus(token: string): Promise<{
    enrolled: boolean;
    model_version?: string;
    enrolled_at?: string;
  }> {
    const baseUrl = await this.getBaseUrl();
    const res = await fetch(`${baseUrl}/biometric/status`, {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });

    if (!res.ok) {
      return { enrolled: false };
    }
    return await res.json();
  }

  static async enrollBiometrics(
    token: string,
    formData: FormData
  ): Promise<{
    enrolled: boolean;
    model_version: string;
  }> {
    const baseUrl = await this.getBaseUrl();
    const res = await fetch(`${baseUrl}/biometric/enroll`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
      },
      body: formData,
    });

    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || 'Biometric enrollment failed.');
    }
    return data;
  }
}

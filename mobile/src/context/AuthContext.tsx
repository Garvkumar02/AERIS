import React, { createContext, useContext, useEffect, useState } from 'react';
import { ApiService, ServerHealth, UserProfile } from '../services/api';

interface AuthContextType {
  user: UserProfile | null;
  isLoading: boolean;
  serverHealth: ServerHealth | null;
  apiUrl: string;
  login: (email: string, password: string, expectedRole?: UserProfile['role']) => Promise<UserProfile>;
  registerStudent: (details: {
    name: string;
    employeeId: string;
    email: string;
    password: string;
  }) => Promise<UserProfile>;
  logout: () => Promise<void>;
  updateApiUrl: (newUrl: string) => Promise<void>;
  refreshHealth: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [serverHealth, setServerHealth] = useState<ServerHealth | null>(null);
  const [apiUrl, setApiUrlState] = useState<string>('');

  const refreshHealth = async () => {
    const health = await ApiService.checkHealth();
    setServerHealth(health);
  };

  useEffect(() => {
    let mounted = true;

    async function init() {
      try {
        const currentUrl = await ApiService.getBaseUrl();
        if (mounted) setApiUrlState(currentUrl);

        const health = await ApiService.checkHealth();
        if (mounted) setServerHealth(health);

        const session = await ApiService.getStoredSession();
        if (session && mounted) {
          setUser(session);
        }
      } catch (err) {
        console.warn('Auth init failed:', err);
      } finally {
        if (mounted) setIsLoading(false);
      }
    }

    init();
    return () => {
      mounted = false;
    };
  }, []);

  const login = async (
    email: string,
    password: string,
    expectedRole?: UserProfile['role'],
  ): Promise<UserProfile> => {
    setIsLoading(true);
    try {
      const profile = await ApiService.login(email, password, expectedRole);
      setUser(profile);
      await refreshHealth();
      return profile;
    } finally {
      setIsLoading(false);
    }
  };

  const registerStudent = async (details: {
    name: string;
    employeeId: string;
    email: string;
    password: string;
  }): Promise<UserProfile> => {
    setIsLoading(true);
    try {
      const profile = await ApiService.registerStudent(details);
      setUser(profile);
      await refreshHealth();
      return profile;
    } finally {
      setIsLoading(false);
    }
  };

  const logout = async () => {
    setIsLoading(true);
    try {
      await ApiService.clearSession();
      setUser(null);
    } finally {
      setIsLoading(false);
    }
  };

  const updateApiUrl = async (newUrl: string) => {
    await ApiService.setBaseUrl(newUrl);
    setApiUrlState(newUrl);
    await refreshHealth();
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        isLoading,
        serverHealth,
        apiUrl,
        login,
        registerStudent,
        logout,
        updateApiUrl,
        refreshHealth,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

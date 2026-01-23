/* eslint-disable react-refresh/only-export-components */
import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';

const AuthContext = createContext();

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

export const AuthProvider = ({ children }) => {
  const [apiKey, setApiKey] = useState(localStorage.getItem('ki_api_key'));
  const [user, setUser] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  const API_BASE = import.meta.env.VITE_API_URL || '';

  const fetchUserInfo = useCallback(async (key) => {
    try {
      const response = await fetch(`${API_BASE}/auth/me`, {
        headers: { 'X-API-Key': key }
      });
      if (response.ok) {
        const userData = await response.json();
        setUser(userData);
      } else {
        // Key might be invalid
        setApiKey(null);
        localStorage.removeItem('ki_api_key');
      }
    } catch (error) {
      console.error('Failed to fetch user info:', error);
    } finally {
      setIsLoading(false);
    }
  }, [API_BASE]);

  useEffect(() => {
    if (apiKey) {
      fetchUserInfo(apiKey);
    } else {
      setIsLoading(false);
    }
  }, [apiKey, fetchUserInfo]);

  const login = useCallback((key) => {
    setApiKey(key);
    localStorage.setItem('ki_api_key', key);
  }, []);

  const logout = useCallback(() => {
    setApiKey(null);
    setUser(null);
    localStorage.removeItem('ki_api_key');
  }, []);

  const signup = useCallback(async (email, password) => {
    const response = await fetch(`${API_BASE}/auth/signup`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password })
    });

    const data = await response.json();
    if (response.ok) {
      login(data.api_key);
      return { success: true };
    } else {
      return { success: false, error: data.detail || 'Signup failed' };
    }
  }, [API_BASE, login]);

  const value = React.useMemo(() => ({
    apiKey,
    user,
    isLoading,
    login,
    logout,
    signup,
    isAuthenticated: !!apiKey
  }), [apiKey, user, isLoading, login, logout, signup]);

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
};

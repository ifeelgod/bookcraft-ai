'use client';

/**
 * Authentication and Pro Tier state manager for BookCraft AI.
 * Handles JWT token persistence in localStorage and provides reactive React hook.
 */
import { useEffect, useState, useCallback } from 'react';
import type { AuthStateData } from '@/types/api';

const TOKEN_KEY = 'bookcraft_auth_token';
const TIER_KEY = 'bookcraft_user_tier';
const EMAIL_KEY = 'bookcraft_user_email';
const NAME_KEY = 'bookcraft_user_name';
const EXPIRES_KEY = 'bookcraft_token_expires';

export function getStoredToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function getStoredTier(): 'demo' | 'pro' | 'pro_pass' | 'author_pro' | 'tier_1_pass' | 'tier_2_monthly' | 'tier_3_monthly' | 'tier_3_annual' {
  if (typeof window === 'undefined') return 'demo';
  const tier = localStorage.getItem(TIER_KEY);
  if (tier && ['pro', 'pro_pass', 'author_pro', 'tier_1_pass', 'tier_2_monthly', 'tier_3_monthly', 'tier_3_annual'].includes(tier)) {
    return tier as any;
  }
  return 'demo';
}

export function getStoredEmail(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem(EMAIL_KEY);
}

export function getStoredName(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem(NAME_KEY);
}

export function isProUser(): boolean {
  const tier = getStoredTier();
  return tier !== 'demo';
}

export function setStoredAuth(
  token: string,
  tier: string = 'pro',
  email?: string,
  name?: string,
  expiresAt?: string,
): void {
  if (typeof window === 'undefined') return;
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(TIER_KEY, tier);
  if (email) localStorage.setItem(EMAIL_KEY, email);
  if (name) localStorage.setItem(NAME_KEY, name);
  if (expiresAt) localStorage.setItem(EXPIRES_KEY, expiresAt);

  // Dispatch custom storage event for in-tab reactive syncing
  window.dispatchEvent(new Event('bookcraft-auth-changed'));
}

export function clearStoredAuth(): void {
  if (typeof window === 'undefined') return;
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(TIER_KEY);
  localStorage.removeItem(EMAIL_KEY);
  localStorage.removeItem(NAME_KEY);
  localStorage.removeItem(EXPIRES_KEY);
  window.dispatchEvent(new Event('bookcraft-auth-changed'));
}

/**
 * React hook to access and mutate current authentication and tier state.
 */
export function useAuth() {
  const [authState, setAuthState] = useState<AuthStateData>({
    token: null,
    tier: 'demo',
    email: null,
    name: null,
    expiresAt: null,
  });

  const syncState = useCallback(() => {
    if (typeof window === 'undefined') return;
    setAuthState({
      token: localStorage.getItem(TOKEN_KEY),
      tier: getStoredTier(),
      email: localStorage.getItem(EMAIL_KEY),
      name: localStorage.getItem(NAME_KEY),
      expiresAt: localStorage.getItem(EXPIRES_KEY),
    });
  }, []);

  useEffect(() => {
    syncState();

    const handleAuthChange = () => syncState();
    window.addEventListener('storage', handleAuthChange);
    window.addEventListener('bookcraft-auth-changed', handleAuthChange);

    return () => {
      window.removeEventListener('storage', handleAuthChange);
      window.removeEventListener('bookcraft-auth-changed', handleAuthChange);
    };
  }, [syncState]);

  const login = (
    token: string,
    tier: string = 'pro',
    email?: string,
    name?: string,
    expiresAt?: string,
  ) => {
    setStoredAuth(token, tier, email, name, expiresAt);
    syncState();
  };

  const logout = () => {
    clearStoredAuth();
    syncState();
  };

  const isPro = authState.tier !== 'demo' || Boolean(authState.token);

  return {
    ...authState,
    isPro,
    login,
    logout,
  };
}

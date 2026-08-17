"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import {
  AuthSession,
  clearStoredSession,
  readStoredSession,
  writeStoredSession,
} from "@/lib/auth-storage";

type AuthStatus = "loading" | "authenticated" | "unauthenticated";

type AuthContextValue = {
  session: AuthSession | null;
  status: AuthStatus;
  setSession: (session: AuthSession) => void;
  clearSession: () => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [session, setSessionState] = useState<AuthSession | null>(null);
  const [status, setStatus] = useState<AuthStatus>("loading");

  useEffect(() => {
    const nextSession = readStoredSession();
    setSessionState(nextSession);
    setStatus(nextSession ? "authenticated" : "unauthenticated");
  }, []);

  const setSession = useCallback((nextSession: AuthSession) => {
    writeStoredSession(nextSession);
    setSessionState(nextSession);
    setStatus("authenticated");
  }, []);

  const clearSession = useCallback(() => {
    clearStoredSession();
    setSessionState(null);
    setStatus("unauthenticated");
  }, []);

  const value = useMemo(
    () => ({ session, status, setSession, clearSession }),
    [clearSession, session, setSession, status],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);

  if (!context) {
    throw new Error("useAuth must be used within AuthProvider.");
  }

  return context;
}

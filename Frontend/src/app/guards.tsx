import { useEffect } from 'react';
import { Navigate, Outlet, useNavigate } from 'react-router-dom';
import type { ReactNode } from 'react';
import { AppShell } from '@/components/layout/AppShell';
import { useToast } from '@/components/ui/ToastContext';
import { apiFetch, tokenMemory } from '@/lib/apiClient';
import { useAppStore } from '@/store/appStore';
import type { Role } from '@/types/api';

const IDLE_LIMIT_MS = Math.max(2, Number(import.meta.env.VITE_SESSION_IDLE_MINUTES) || 15) * 60 * 1000;
const IDLE_WARNING_MS = 60 * 1000;

// Role guards only hide UI. The backend must enforce every permission on every request.
export function RoleGuard({ roles, children }: { roles: Role[]; children: ReactNode }) {
  const user = useAppStore(state => state.user);
  return user && roles.includes(user.role) ? <>{children}</> : <Navigate to="/dashboard" replace />;
}

export function ProtectedLayout() {
  const user = useAppStore(state => state.user);
  const navigate = useNavigate();
  const { push } = useToast();
  useEffect(() => {
    if (!user) return;
    let timer: number;
    let warning: number;
    const events = ['pointerdown', 'keydown', 'mousemove', 'touchstart'];
    const expire = () => {
      void apiFetch<void>('/auth/logout/', { method: 'POST' }).catch(() => undefined);
      tokenMemory.set(null);
      useAppStore.getState().setUser(null);
      if (typeof BroadcastChannel !== 'undefined') {
        const sender = new BroadcastChannel('jg-session');
        sender.postMessage('logout');
        sender.close();
      }
      navigate('/login');
    };
    const reset = () => {
      window.clearTimeout(timer);
      window.clearTimeout(warning);
      warning = window.setTimeout(() => push({ type: 'warning', title: 'Sesión por expirar', message: 'Se cerrará en un minuto por inactividad.' }), IDLE_LIMIT_MS - IDLE_WARNING_MS);
      timer = window.setTimeout(expire, IDLE_LIMIT_MS);
    };
    events.forEach(event => window.addEventListener(event, reset, { passive: true }));
    reset();
    const channel = typeof BroadcastChannel !== 'undefined' ? new BroadcastChannel('jg-session') : null;
    if (channel) channel.onmessage = event => {
      if (event.data === 'logout') {
        tokenMemory.set(null);
        useAppStore.getState().setUser(null);
        navigate('/login');
      }
    };
    return () => {
      events.forEach(event => window.removeEventListener(event, reset));
      window.clearTimeout(timer);
      window.clearTimeout(warning);
      channel?.close();
    };
  }, [user, navigate, push]);
  if (!user) return <Navigate to="/login" replace />;
  return <AppShell><Outlet /></AppShell>;
}

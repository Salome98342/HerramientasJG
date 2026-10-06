import { useRef, useState, type FormEvent } from 'react';
import { Eye, EyeOff, LockKeyhole, Wrench } from 'lucide-react';
import { Navigate, useNavigate } from 'react-router-dom';
import { z } from 'zod';
import { ApiError, apiFetch, tokenMemory } from '@/lib/apiClient';
import { useAppStore } from '@/store/appStore';

const schema = z.object({ username: z.string().trim().min(1), password: z.string().min(1) });

export default function Login() {
  const user = useAppStore(state => state.user);
  const setUser = useAppStore(state => state.setUser);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<'invalid' | 'blocked' | 'throttled' | null>(null);
  const submitting = useRef(false);
  const navigate = useNavigate();

  if (user) return <Navigate to="/dashboard" replace />;

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submitting.current) return;
    setError(null);
    const parsed = schema.safeParse({ username, password });
    if (!parsed.success) { setError('invalid'); return; }
    submitting.current = true;
    setBusy(true);
    try {
      const data = await apiFetch<{ access: string; user: { id: string; name: string; role: 'ADMIN' | 'CAJERO' } }>('/auth/login/', { method: 'POST', body: JSON.stringify(parsed.data) });
      tokenMemory.set(data.access);
      setUser(data.user);
      if (typeof BroadcastChannel !== 'undefined') {
        const channel = new BroadcastChannel('jg-session');
        channel.postMessage('login');
        channel.close();
      }
      navigate('/dashboard');
    } catch (cause) {
      if (cause instanceof ApiError && cause.status === 403) setError('blocked');
      else if (cause instanceof ApiError && cause.status === 429) setError('throttled');
      else setError('invalid');
    } finally {
      submitting.current = false;
      setBusy(false);
    }
  }

  return <main className="jg-login"><section className="jg-login__card">
    <div className="jg-login__brand"><span className="jg-brand-mark"><Wrench size={24} /></span><span><b>Herramientas JG</b><small>Gestión simple. Negocio en marcha.</small></span></div>
    <div className="jg-login__heading"><h1>Qué bueno verte</h1><p>Ingresa a tu espacio de trabajo</p></div>
    <form onSubmit={event => void submit(event)} noValidate>
      <label htmlFor="username">Usuario</label><div className="jg-input-wrap"><span className="jg-input-wrap__icon"><LockKeyhole size={17} /></span><input id="username" autoComplete="username" value={username} onChange={event => setUsername(event.target.value)} placeholder="Tu usuario" /></div>
      <label htmlFor="password">Contraseña</label><div className="jg-input-wrap"><span className="jg-input-wrap__icon"><LockKeyhole size={17} /></span><input id="password" type={showPassword ? 'text' : 'password'} autoComplete="current-password" value={password} onChange={event => setPassword(event.target.value)} placeholder="Tu contraseña" /><button type="button" className="jg-input-wrap__toggle" aria-label={showPassword ? 'Ocultar contraseña' : 'Mostrar contraseña'} onClick={() => setShowPassword(!showPassword)}>{showPassword ? <EyeOff size={18} /> : <Eye size={18} />}</button></div>
      {error && <p className="jg-login__error" role="alert">{error === 'blocked' ? 'Acceso temporalmente bloqueado. Intenta nuevamente más tarde.' : error === 'throttled' ? 'Demasiados intentos. Espera un momento e inténtalo de nuevo.' : 'No fue posible iniciar sesión. Revisa tus datos e inténtalo de nuevo.'}</p>}
      <button className="jg-button jg-button--primary jg-login__submit" disabled={busy}>{busy ? 'Ingresando…' : 'Ingresar'}</button>
    </form>
    <p className="jg-login__foot">¿Necesitas ayuda? Comunícate con el administrador</p>
  </section><small className="jg-login__copyright">© 2026 Herramientas JG · Hecho para trabajar mejor</small></main>;
}

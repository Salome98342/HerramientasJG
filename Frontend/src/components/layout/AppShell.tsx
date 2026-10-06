import { Bell, ChartNoAxesCombined, ChevronDown, CircleHelp, ClipboardList, LayoutDashboard, LogOut, Menu, Moon, Package, Settings, Sun, Wrench, X } from 'lucide-react';
import { useEffect, useState } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { apiFetch, tokenMemory } from '@/lib/apiClient';
import { enableBrowserPush } from '@/lib/push';
import { notifications as mockNotifications } from '@/mocks/data';
import { inventarioApi } from '@/features/inventario/api';
import { cajasApi } from '@/features/cajas/api';
import { useAppStore } from '@/store/appStore';
import type { AppNotification } from '@/types/api';
import { useToast } from '@/components/ui/ToastContext';
import type { ReactNode } from 'react';

const nav = [
  { label: 'Resumen', to: '/dashboard', icon: LayoutDashboard },
  { label: 'Ventas', to: '/ventas', icon: ClipboardList },
  { label: 'Inventario', to: '/inventario', icon: Package },
  { label: 'Compras', to: '/compras', icon: ClipboardList, adminOnly: true },
  { label: 'Alquileres', to: '/alquileres', icon: Wrench },
  { label: 'Cajas y finanzas', to: '/cajas', icon: ChartNoAxesCombined },
  { label: 'Reportes', to: '/reportes', icon: ChartNoAxesCombined, adminOnly: true },
];

export function AppShell({ children }: { children: ReactNode }) {
  const user = useAppStore(state => state.user);
  const theme = useAppStore(state => state.theme);
  const toggleTheme = useAppStore(state => state.toggleTheme);
  const setNotifications = useAppStore(state => state.setNotifications);
  const items = useAppStore(state => state.notifications);
  const markRead = useAppStore(state => state.markRead);
  const [open, setOpen] = useState(false);
  const [sidebar, setSidebar] = useState(false);
  const navigate = useNavigate();
  const { push } = useToast();
  const stockAlerts = useQuery({ queryKey: ['inventario-alertas'], queryFn: inventarioApi.alertas, retry: false });
  const cajaActual = useQuery({ queryKey: ['cajas-actual'], queryFn: cajasApi.actual, retry: false, refetchInterval: 30_000 });

  useEffect(() => {
    const alerts: AppNotification[] = (stockAlerts.data?.results ?? []).map(product => ({
      id: `stock-${product.id}`, title: product.estado_stock === 'agotado' ? 'Producto agotado' : 'Stock bajo',
      detail: `${product.referencia} · ${product.nombre} · quedan ${product.stock_actual}`,
      kind: product.estado_stock === 'agotado' ? 'danger' : 'warning', createdAt: 'Ahora', read: false,
    }));
    setNotifications([...mockNotifications.filter(item => !item.id.startsWith('stock-')), ...alerts]);
  }, [stockAlerts.data, setNotifications]);

  const logout = () => {
    void apiFetch<void>('/auth/logout/', { method: 'POST' }).catch(() => undefined);
    tokenMemory.set(null);
    useAppStore.getState().setUser(null);
    if (typeof BroadcastChannel !== 'undefined') {
      const channel = new BroadcastChannel('jg-session');
      channel.postMessage('logout');
      channel.close();
    }
    navigate('/login');
  };

  const activatePush = async () => {
    try {
      await enableBrowserPush();
      push({ type: 'success', title: 'Avisos activados', message: 'Recibirás alertas importantes en este navegador.' });
    } catch {
      push({ type: 'info', title: 'Avisos no disponibles', message: 'Puedes seguir usando las notificaciones dentro de la app.' });
    }
  };

  const unread = items.filter(item => !item.read).length;
  return <div className="jg-shell">
    <aside className={`jg-sidebar${sidebar ? ' jg-sidebar--open' : ''}`}>
      <div className="jg-sidebar__brand"><span className="jg-brand-mark"><Wrench size={22} /></span><span><b>Herramientas JG</b><small>Gestión de negocio</small></span><button className="jg-icon-button jg-sidebar__close" aria-label="Cerrar menú" onClick={() => setSidebar(false)}><X /></button></div>
      <span className="jg-sidebar__caption">MENÚ PRINCIPAL</span>
      <nav className="jg-sidebar__nav" aria-label="Navegación principal">
        {nav.filter(item => !item.adminOnly || user?.role === 'ADMIN').map(item => <NavLink key={item.to} to={item.to} onClick={() => setSidebar(false)} className={({ isActive }) => `jg-sidebar__link${isActive ? ' jg-sidebar__link--active' : ''}`}><item.icon size={19} /><span>{item.label}</span>{item.label === 'Inventario' && <span className="jg-sidebar__dot" />}</NavLink>)}
      </nav>
      <div className="jg-sidebar__bottom">
        {user?.role === 'ADMIN' && <NavLink to="/configuracion" className="jg-sidebar__link"><Settings size={19} /><span>Configuración</span></NavLink>}
        <NavLink to="/ayuda" className="jg-sidebar__link"><CircleHelp size={19} /><span>Centro de ayuda</span></NavLink>
        <div className="jg-sidebar__profile"><span className="jg-avatar">{user?.name.slice(0, 1) ?? 'U'}</span><span className="jg-sidebar__person"><b>{user?.name ?? 'Usuario'}</b><small>{user?.role === 'ADMIN' ? 'Administrador' : 'Cajero'}</small></span><button className="jg-icon-button" aria-label="Cerrar sesión" onClick={logout}><LogOut size={17} /></button></div>
      </div>
    </aside>
    <div className="jg-shell__main">
      <header className="jg-topbar"><button className="jg-icon-button jg-topbar__menu" aria-label="Abrir menú" onClick={() => setSidebar(true)}><Menu /></button><div className="jg-topbar__crumb">Panel <span>/</span> <b>Resumen</b></div>
        <div className="jg-topbar__actions"><button className={`cash-topbar-status${cajaActual.data?.turno ? ' cash-topbar-status--open' : ''}${cajaActual.isError ? ' cash-topbar-status--error' : ''}`} onClick={() => navigate('/cajas')} aria-label={`Estado de caja: ${cajaActual.isError ? 'no disponible' : cajaActual.data?.turno ? 'abierta' : 'cerrada'}`}><i />{cajaActual.isLoading ? 'Consultando caja' : cajaActual.isError ? 'Caja no disponible' : cajaActual.data?.turno ? `Abierta · ${cajaActual.data.turno.caja_nombre}` : 'Caja cerrada'}</button><button className="jg-icon-button" aria-label={theme === 'light' ? 'Activar tema oscuro' : 'Activar tema claro'} onClick={toggleTheme}>{theme === 'light' ? <Moon size={19} /> : <Sun size={19} />}</button>
          <div className="jg-notification"><button className="jg-icon-button jg-notification__trigger" aria-label={`Notificaciones, ${unread} sin leer`} aria-expanded={open} onClick={() => setOpen(!open)}><Bell size={19} />{unread > 0 && <i />}</button>
            {open && <><button className="jg-dismiss" aria-label="Cerrar notificaciones" onClick={() => setOpen(false)} /><section className="jg-notification__panel" aria-label="Centro de notificaciones"><header><div><b>Notificaciones</b><span>{unread} nuevas</span></div><button className="jg-text-button" onClick={() => items.forEach(item => markRead(item.id))}>Marcar leídas</button></header>
              {'Notification' in window && Notification.permission !== 'granted' && <button className="jg-notification__push" onClick={() => void activatePush()}>Activar avisos de este dispositivo</button>}
              {items.map(item => <button className={`jg-notification__item${item.read ? '' : ' jg-notification__item--unread'}`} key={item.id} onClick={() => markRead(item.id)}><span className={`jg-notification__icon jg-notification__icon--${item.kind}`}><Bell size={16} /></span><span><b>{item.title}</b><small>{item.detail}</small><em>{item.createdAt}</em></span></button>)}<footer>Ver todas las notificaciones</footer></section></>}
          </div><span className="jg-topbar__divider" /><button className="jg-topbar__user"><span className="jg-avatar">{user?.name.slice(0, 1) ?? 'U'}</span><span><b>{user?.name ?? 'Usuario'}</b><small>{user?.role === 'ADMIN' ? 'Administrador' : 'Cajero'}</small></span><ChevronDown size={15} /></button>
        </div>
      </header>{children}
    </div>
    {sidebar && <button className="jg-shell__scrim" aria-label="Cerrar menú" onClick={() => setSidebar(false)} />}
  </div>;
}

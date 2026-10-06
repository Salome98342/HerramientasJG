import { useQuery } from '@tanstack/react-query';
import { format } from 'date-fns';
import { es } from 'date-fns/locale';
import { Activity, ArrowDownRight, ArrowUpRight, Banknote, CircleAlert, PackageCheck, Wallet } from 'lucide-react';
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { apiFetch } from '@/lib/apiClient';
import { dashboard as fallback } from '@/mocks/data';
import { useAppStore } from '@/store/appStore';
import type { DashboardSummary } from '@/types/api';

const cop = new Intl.NumberFormat('es-CO', { style: 'currency', currency: 'COP', maximumFractionDigits: 0 });

export default function Dashboard() {
  const { data = fallback, isLoading } = useQuery({ queryKey: ['dashboard'], queryFn: () => apiFetch<DashboardSummary>('/dashboard/summary/') });
  const user = useAppStore(state => state.user);
  const today = format(new Date(), "EEEE, d 'de' MMMM 'de' yyyy", { locale: es }).toLocaleUpperCase('es-CO');
  return <main className="jg-page jg-dashboard jg-enter">
    <div className="jg-page__heading"><div><p className="jg-eyebrow">{today}</p><h1>Buenos días, {user?.name.split(' ')[0] ?? 'equipo'} <span aria-hidden="true">☀️</span></h1><p>Este es el resumen de tu negocio hoy.</p></div><button className="jg-button jg-button--secondary"><Activity size={17} /> Esta semana <span>⌄</span></button></div>
    <section className="jg-metrics jg-stagger" aria-label="Indicadores del negocio">
      <article className="jg-card jg-metric"><div className="jg-metric__top"><span>Ventas de hoy</span><span className="jg-metric__icon jg-metric__icon--amber"><Banknote size={19} /></span></div><strong>{cop.format(data.salesToday)}</strong><small className="jg-trend jg-trend--up"><ArrowUpRight size={15} /> 12,8% <span>vs. ayer</span></small><div className="jg-sparkline jg-sparkline--amber" /></article>
      {user?.role === 'ADMIN' && <>
        <article className="jg-card jg-metric"><div className="jg-metric__top"><span>Inversión total</span><span className="jg-metric__icon jg-metric__icon--blue"><PackageCheck size={19} /></span></div><strong>{cop.format(data.investment)}</strong><small className="jg-metric__muted">Inventario disponible</small><div className="jg-sparkline jg-sparkline--blue" /></article>
        <article className="jg-card jg-metric"><div className="jg-metric__top"><span>Ganancia del periodo</span><span className="jg-metric__icon jg-metric__icon--green"><ArrowUpRight size={19} /></span></div><strong>{cop.format(data.profit)}</strong><small className="jg-trend jg-trend--up"><ArrowUpRight size={15} /> 8,2% <span>vs. periodo anterior</span></small><div className="jg-sparkline jg-sparkline--green" /></article>
        <article className="jg-card jg-metric"><div className="jg-metric__top"><span>Gastos del periodo</span><span className="jg-metric__icon jg-metric__icon--rose"><Wallet size={19} /></span></div><strong>{cop.format(data.expenses)}</strong><small className="jg-trend jg-trend--down"><ArrowDownRight size={15} /> 3,1% <span>vs. periodo anterior</span></small><div className="jg-sparkline jg-sparkline--rose" /></article>
      </>}
    </section>
    <section className="jg-dashboard__grid">
      {user?.role === 'ADMIN' && <article className="jg-card jg-chart"><div className="jg-section-heading"><div><h2>Movimiento financiero</h2><p>Ventas y gastos durante la semana</p></div><button className="jg-text-button">Ver reporte <span>↗</span></button></div>
        <div className="jg-chart__area"><ResponsiveContainer width="100%" height="100%"><AreaChart data={data.chart} margin={{ top: 14, right: 8, left: -16, bottom: 0 }}><defs><linearGradient id="salesFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="var(--color-primary)" stopOpacity={0.2} /><stop offset="95%" stopColor="var(--color-primary)" stopOpacity={0} /></linearGradient></defs><CartesianGrid stroke="var(--color-border-subtle)" vertical={false} /><XAxis dataKey="day" axisLine={false} tickLine={false} tick={{ fill: 'var(--color-text-muted)', fontSize: 12 }} dy={10} /><YAxis axisLine={false} tickLine={false} tick={{ fill: 'var(--color-text-muted)', fontSize: 11 }} tickFormatter={value => `${Number(value) / 1000000}m`} /><Tooltip formatter={value => cop.format(Number(value))} /><Area type="monotone" dataKey="sales" name="Ventas" stroke="var(--color-primary)" strokeWidth={2.5} fill="url(#salesFill)" /><Area type="monotone" dataKey="expenses" name="Gastos" stroke="var(--color-info)" strokeWidth={2} fill="transparent" /></AreaChart></ResponsiveContainer></div>
        <div className="jg-chart__legend"><span><i className="jg-chart__legend-dot jg-chart__legend-dot--sales" /> Ventas</span><span><i className="jg-chart__legend-dot jg-chart__legend-dot--expenses" /> Gastos</span></div>
      </article>}
      <div className="jg-dashboard__side">
        <article className="jg-card jg-register"><div className="jg-section-heading"><div><h2>Estado de caja</h2><p>Turno actual</p></div><span className="jg-badge jg-badge--success"><i /> Abierta</span></div><span className="jg-register__label">Base + movimientos</span><strong>{cop.format(data.registerAmount)}</strong><div className="jg-register__meta"><span><i /> Turno iniciado 8:02 a. m.</span><button className="jg-text-button">Ver caja →</button></div></article>
        <article className="jg-card jg-alerts"><div className="jg-section-heading"><div><h2>Necesita atención</h2><p>Alertas para revisar</p></div><span className="jg-alerts__count">{data.alerts.length}</span></div>{data.alerts.map(alert => <div className="jg-alert" key={alert.id}><span className={`jg-alert__icon jg-alert__icon--${alert.kind}`}><CircleAlert size={17} /></span><span><b>{alert.title}</b><small>{alert.detail}</small></span><span className={`jg-alert__dot jg-alert__dot--${alert.kind}`} /></div>)}</article>
      </div>
    </section>
    <p className="jg-dashboard__loading" aria-live="polite">{isLoading ? 'Actualizando datos…' : ''}</p>
  </main>;
}

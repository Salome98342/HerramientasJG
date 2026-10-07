import { useQuery } from '@tanstack/react-query';
import { format } from 'date-fns';
import { es } from 'date-fns/locale';
import { Activity, ArrowDownRight, ArrowUpRight, Banknote, CircleAlert, PackageCheck, Wallet } from 'lucide-react';
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { Button, EmptyState, Skeleton } from '@/components/ui/Primitives';
import { finanzasApi } from '@/features/finanzas/api';
import { useAppStore } from '@/store/appStore';

const cop = new Intl.NumberFormat('es-CO', { style: 'currency', currency: 'COP', maximumFractionDigits: 0 });

export default function Dashboard() {
  const user = useAppStore(state => state.user);
  const navigate = useNavigate();
  const dashboard = useQuery({
    queryKey: ['dashboard-resumen', user?.id],
    queryFn: finanzasApi.dashboard,
    refetchInterval: 60_000,
  });
  const data = dashboard.data;
  const today = format(new Date(), "EEEE, d 'de' MMMM 'de' yyyy", { locale: es }).toLocaleUpperCase('es-CO');
  return <main className="jg-page jg-dashboard jg-enter">
    <div className="jg-page__heading"><div><p className="jg-eyebrow">{today}</p><h1>Buenos días, {user?.name.split(' ')[0] ?? 'equipo'} <span aria-hidden="true">☀️</span></h1><p>Este es el resumen de tu negocio hoy.</p></div><Button onClick={() => void dashboard.refetch()}><Activity size={17} /> Actualizar</Button></div>
    {dashboard.isLoading ? <section className="jg-metrics">{[1, 2, 3, 4].map(item => <Skeleton key={item} className="finance-dashboard-skeleton" />)}</section> :
      dashboard.isError || !data ? <EmptyState title="Resumen no disponible" description="No se pudieron cargar los datos del negocio." action={<Button onClick={() => void dashboard.refetch()}>Reintentar</Button>} /> :
        <>
          <section className="jg-metrics jg-stagger" aria-label="Indicadores del negocio">
            <article className="jg-card jg-metric"><div className="jg-metric__top"><span>Ventas de hoy</span><span className="jg-metric__icon jg-metric__icon--amber"><Banknote size={19} /></span></div><AnimatedAmount value={Number(data.ventas_hoy)} /><small className="jg-metric__muted">Ventas registradas</small><div className="jg-sparkline jg-sparkline--amber" /></article>
            {user?.role === 'ADMIN' && <>
              <article className="jg-card jg-metric"><div className="jg-metric__top"><span>Inversión en inventario</span><span className="jg-metric__icon jg-metric__icon--blue"><PackageCheck size={19} /></span></div><AnimatedAmount value={Number(data.inversion ?? 0)} /><small className="jg-metric__muted">Costo del stock disponible</small><div className="jg-sparkline jg-sparkline--blue" /></article>
              <article className="jg-card jg-metric"><div className="jg-metric__top"><span>Ganancia neta del mes</span><span className="jg-metric__icon jg-metric__icon--green"><ArrowUpRight size={19} /></span></div><AnimatedAmount value={Number(data.ganancia_neta ?? 0)} /><small className="jg-metric__muted">Resultado operativo simple</small><div className="jg-sparkline jg-sparkline--green" /></article>
              <article className="jg-card jg-metric"><div className="jg-metric__top"><span>Gastos del mes</span><span className="jg-metric__icon jg-metric__icon--rose"><Wallet size={19} /></span></div><AnimatedAmount value={Number(data.gastos_periodo ?? 0)} /><small className="jg-trend jg-trend--down"><ArrowDownRight size={15} /> Gastos registrados</small><div className="jg-sparkline jg-sparkline--rose" /></article>
            </>}
          </section>
          <section className="jg-dashboard__grid">
            <article className="jg-card jg-chart"><div className="jg-section-heading"><div><h2>Movimiento financiero</h2><p>Ventas y gastos de los últimos siete días</p></div><span className="jg-text-button">Últimos 7 días</span></div>
              <div className="jg-chart__area"><ResponsiveContainer width="100%" height="100%"><AreaChart data={data.grafica.map(item => ({ ...item, dia: new Date(`${item.dia}T12:00:00`).toLocaleDateString('es-CO', { weekday: 'short' }) }))} margin={{ top: 14, right: 8, left: -16, bottom: 0 }}>
                <defs><linearGradient id="salesFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="var(--color-primary)" stopOpacity={0.2} /><stop offset="95%" stopColor="var(--color-primary)" stopOpacity={0} /></linearGradient></defs>
                <CartesianGrid stroke="var(--color-border-subtle)" vertical={false} /><XAxis dataKey="dia" axisLine={false} tickLine={false} tick={{ fill: 'var(--color-text-muted)', fontSize: 12 }} dy={10} />
                <YAxis axisLine={false} tickLine={false} tick={{ fill: 'var(--color-text-muted)', fontSize: 11 }} tickFormatter={value => `${Number(value) / 1000000}m`} /><Tooltip formatter={value => cop.format(Number(value))} />
                <Area type="monotone" dataKey="ventas" name="Ventas" stroke="var(--color-primary)" strokeWidth={2.5} fill="url(#salesFill)" />
                <Area type="monotone" dataKey="gastos" name="Gastos" stroke="var(--color-info)" strokeWidth={2} fill="transparent" />
              </AreaChart></ResponsiveContainer></div>
            </article>
            <div className="jg-dashboard__side">
              <article className="jg-card jg-register"><div className="jg-section-heading"><div><h2>Estado de caja</h2><p>{data.turno ?? 'Turno actual'}</p></div><span className={`jg-badge jg-badge--${data.caja_abierta ? 'success' : 'neutral'}`}><i /> {data.caja_abierta ? 'Abierta' : 'Cerrada'}</span></div><span className="jg-register__label">Efectivo esperado</span><strong>{cop.format(Number(data.saldo_caja))}</strong><div className="jg-register__meta"><span><i /> {data.caja_abierta ? 'Turno en curso' : 'No hay turno abierto'}</span><Button onClick={() => navigate('/cajas')}>Ver caja →</Button></div></article>
              <article className="jg-card jg-alerts"><div className="jg-section-heading"><div><h2>Necesita atención</h2><p>Alertas pendientes de revisar</p></div><span className="jg-alerts__count">{data.conteo_alertas}</span></div>
                {data.alertas.length ? data.alertas.map(alert => <div className="jg-alert" key={alert.id}><span className={`jg-alert__icon jg-alert__icon--${alert.tipo}`}><CircleAlert size={17} /></span><span><b>{alert.titulo}</b><small>{alert.detalle}</small></span><span className={`jg-alert__dot jg-alert__dot--${alert.tipo}`} /></div>) : <p className="finance-empty-copy">No hay alertas pendientes.</p>}
              </article>
            </div>
          </section>
        </>}
  </main>;
}

function AnimatedAmount({ value }: { value: number }) {
  const [display, setDisplay] = useState(0);
  useEffect(() => {
    let frame = 0;
    const start = performance.now();
    const duration = 650;
    const animate = (now: number) => {
      const progress = Math.min((now - start) / duration, 1);
      setDisplay(Math.round(value * progress));
      if (progress < 1) frame = requestAnimationFrame(animate);
    };
    frame = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(frame);
  }, [value]);
  return <strong>{cop.format(display)}</strong>;
}

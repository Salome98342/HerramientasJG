import { useMutation, useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { Button, EmptyState, Input, Skeleton } from '@/components/ui/Primitives';
import { useToast } from '@/components/ui/ToastContext';
import { useAppStore } from '@/store/appStore';
import { finanzasApi } from './api';

const cop = new Intl.NumberFormat('es-CO', { style: 'currency', currency: 'COP', maximumFractionDigits: 0 });
const palette = ['#e98218', '#3975b8', '#16845b', '#c33e42', '#805ad5', '#0f9d9a'];
const localDate = (date = new Date()) => [
  date.getFullYear(),
  String(date.getMonth() + 1).padStart(2, '0'),
  String(date.getDate()).padStart(2, '0'),
].join('-');
const today = () => localDate();
const monthStart = () => {
  const date = new Date();
  date.setDate(1);
  return localDate(date);
};

export default function Reportes() {
  const user = useAppStore(state => state.user);
  const { push } = useToast();
  const [desde, setDesde] = useState(monthStart);
  const [hasta, setHasta] = useState(today);
  const [periodo, setPeriodo] = useState({ desde: monthStart(), hasta: today() });
  const valid = desde <= hasta;
  const report = useQuery({
    queryKey: ['finanzas-reporte', user?.business?.id, periodo.desde, periodo.hasta],
    queryFn: () => finanzasApi.reporte(periodo.desde, periodo.hasta),
    enabled: !!user && user.role === 'ADMIN' && periodo.desde <= periodo.hasta,
  });
  const exportExcel = useMutation({
    mutationFn: () => finanzasApi.exportarReporte(periodo.desde, periodo.hasta),
    onError: error => push({
      type: 'error', title: 'No se pudo exportar',
      message: error instanceof Error ? error.message : 'Intenta exportar nuevamente.',
    }),
  });
  const data = report.data;
  const summary = data?.resumen;
  const paymentRows = data?.ingresos_egresos_por_medio.filter(item => Number(item.ingresos) > 0) ?? [];

  if (user?.role !== 'ADMIN') return <main className="jg-page"><EmptyState title="Acceso restringido" description="Solo un administrador puede consultar los reportes financieros." /></main>;

  return <main className="jg-page finance-page">
    <header className="jg-page__heading">
      <div><span className="jg-eyebrow">ANÁLISIS DEL NEGOCIO</span><h1>Reportes financieros</h1><p>Consulta resultados por periodo y exporta los datos para Excel.</p></div>
      <Button variant="primary" onClick={() => exportExcel.mutate()} disabled={!data || exportExcel.isPending}>
        {exportExcel.isPending ? 'Preparando Excel…' : 'Exportar a Excel'}
      </Button>
    </header>
    <section className="jg-card finance-period">
      <label>Desde<Input type="date" value={desde} max={hasta} onChange={event => setDesde(event.target.value)} /></label>
      <label>Hasta<Input type="date" value={hasta} min={desde} max={today()} onChange={event => setHasta(event.target.value)} /></label>
      <Button variant="primary" disabled={!valid} onClick={() => setPeriodo({ desde, hasta })}>Consultar periodo</Button>
      {!valid && <span role="alert">La fecha inicial debe ser anterior a la fecha final.</span>}
    </section>
    {report.isLoading ? <div className="finance-report-skeleton">{[1, 2, 3].map(item => <Skeleton key={item} className="finance-skeleton" />)}</div> :
      report.isError ? <EmptyState title="Reporte no disponible" description="No fue posible cargar los datos del periodo." action={<Button onClick={() => void report.refetch()}>Reintentar</Button>} /> :
        data && <>
          <section className="finance-report-metrics">
            <article className="jg-card finance-report-metric"><span>Inversión en compras</span><strong>{cop.format(Number(summary?.inversion_compras ?? 0))}</strong></article>
            <article className="jg-card finance-report-metric"><span>Ganancia bruta</span><strong>{cop.format(Number(summary?.ganancia_bruta ?? 0))}</strong></article>
            <article className="jg-card finance-report-metric"><span>Gastos operativos</span><strong>{cop.format(Number(summary?.gastos_operativos ?? 0))}</strong></article>
            <article className="jg-card finance-report-metric finance-report-metric--net"><span>Ganancia neta</span><strong>{cop.format(Number(summary?.ganancia_neta ?? 0))}</strong></article>
          </section>
          <section className="finance-chart-grid">
            <article className="jg-card finance-chart-card"><header><h2>Ventas y gastos por día</h2><p>Valores registrados en el periodo.</p></header>
              <div className="finance-chart"><ResponsiveContainer width="100%" height="100%"><LineChart data={data.serie_diaria}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} /><XAxis dataKey="dia" tickFormatter={value => new Date(`${value}T12:00:00`).toLocaleDateString('es-CO', { day: 'numeric', month: 'short' })} />
                <YAxis tickFormatter={value => `${Number(value) / 1000}k`} /><Tooltip formatter={value => cop.format(Number(value))} />
                <Legend /><Line type="monotone" dataKey="ventas" name="Ventas" stroke="#e98218" strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="gastos" name="Gastos" stroke="#3975b8" strokeWidth={2} dot={false} />
              </LineChart></ResponsiveContainer></div>
            </article>
            <article className="jg-card finance-chart-card"><header><h2>Ingresos por medio de pago</h2><p>Recaudos registrados en caja.</p></header>
              {paymentRows.length ?
                <div className="finance-chart"><ResponsiveContainer width="100%" height="100%"><PieChart>
                  <Pie data={paymentRows} dataKey="ingresos" nameKey="medio_pago" outerRadius="72%" label>
                    {paymentRows.map((item, index) => <Cell key={item.medio_pago} fill={palette[index % palette.length]} />)}
                  </Pie><Tooltip formatter={value => cop.format(Number(value))} /><Legend />
                </PieChart></ResponsiveContainer></div> : <EmptyState title="Sin ingresos registrados" description="No hay movimientos de ingreso para mostrar." />}
            </article>
            <article className="jg-card finance-chart-card finance-chart-card--wide"><header><h2>Productos más vendidos</h2><p>Cantidad vendida por producto.</p></header>
              {data.productos_mas_vendidos.length ? <div className="finance-chart"><ResponsiveContainer width="100%" height="100%"><BarChart data={data.productos_mas_vendidos.slice(0, 8)} margin={{ left: 6, right: 12 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} /><XAxis dataKey="referencia" /><YAxis /><Tooltip formatter={(value, name) => name === 'Ventas' ? cop.format(Number(value)) : value} />
                <Legend /><Bar dataKey="cantidad" name="Unidades" fill="#e98218" radius={[5, 5, 0, 0]} /><Bar dataKey="ingresos" name="Ventas" fill="#3975b8" radius={[5, 5, 0, 0]} />
              </BarChart></ResponsiveContainer></div> : <EmptyState title="Sin ventas en el periodo" description="No hay productos vendidos en las fechas seleccionadas." />}
            </article>
          </section>
          <section className="finance-data-grid">
            <ReportTable title="Gastos por categoría" columns={['Categoría', 'Total']} rows={data.gastos_por_categoria.map(row => [row.categoria, cop.format(Number(row.total))])} />
            <ReportTable title="Artículos más alquilados" columns={['Artículo', 'Cantidad']} rows={data.articulos_mas_alquilados.map(row => [`${row.referencia} · ${row.articulo}`, row.cantidad])} />
            <ReportTable title="Cartera de crédito" columns={['Cliente', 'Saldo']} rows={data.cartera_credito.map(row => [row.cliente, cop.format(Number(row.saldo))])} />
            <ReportTable title="Caja por turno" columns={['Turno / caja', 'Estado', 'Diferencia']} rows={data.estado_caja_por_turno.map(row => [`#${row.turno_id} · ${row.caja}`, row.estado, row.diferencia === null ? '—' : cop.format(Number(row.diferencia))])} />
          </section>
        </>}
  </main>;
}

function ReportTable({ title, columns, rows }: { title: string; columns: string[]; rows: string[][] }) {
  return <article className="jg-card finance-data-card"><h2>{title}</h2>
    {rows.length ? <div className="finance-table-wrap"><table className="finance-table"><thead><tr>{columns.map(column => <th key={column}>{column}</th>)}</tr></thead>
      <tbody>{rows.map((row, index) => <tr key={`${title}-${index}`}>{row.map((cell, cellIndex) => <td key={`${title}-${index}-${cellIndex}`}>{cell}</td>)}</tr>)}</tbody>
    </table></div> : <p className="finance-empty-copy">Sin registros para mostrar.</p>}
  </article>;
}

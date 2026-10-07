import { useState, type FormEvent } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { History, Pencil, Plus, Search } from 'lucide-react';
import { Badge, Button, Drawer, Input, Select } from '@/components/ui/Primitives';
import { useToast } from '@/components/ui/ToastContext';
import { ventasApi, type Cliente, type Venta } from './api';

const currency = new Intl.NumberFormat('es-CO', { style: 'currency', currency: 'COP', maximumFractionDigits: 0 });
const pesos = (value: string | number) => currency.format(Number(value || 0));
type ClienteForm = Pick<Cliente, 'tipo_documento' | 'documento' | 'nombre' | 'telefono' | 'correo' | 'direccion' | 'permite_credito' | 'cupo_credito'>;
const emptyForm: ClienteForm = { tipo_documento: '', documento: '', nombre: '', telefono: '', correo: '', direccion: '', permite_credito: false, cupo_credito: '0' };

export default function Clientes() {
  const [search, setSearch] = useState('');
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<Cliente | null>(null);
  const [form, setForm] = useState<ClienteForm>(emptyForm);
  const [historyClient, setHistoryClient] = useState<Cliente | null>(null);
  const qc = useQueryClient();
  const { push } = useToast();
  const clients = useQuery({
    queryKey: ['clientes', search],
    queryFn: () => ventasApi.clientes(search),
  });
  const history = useQuery({
    queryKey: ['clientes-historial', historyClient?.id],
    queryFn: () => ventasApi.historialCliente(historyClient!.id),
    enabled: Boolean(historyClient),
  });
  const save = useMutation({
    mutationFn: () => editing
      ? ventasApi.actualizarCliente(editing.id, form)
      : ventasApi.crearCliente(form),
    onSuccess: () => {
      setFormOpen(false);
      setEditing(null);
      setForm(emptyForm);
      void qc.invalidateQueries({ queryKey: ['clientes'] });
      push({ type: 'success', title: editing ? 'Cliente actualizado' : 'Cliente creado', message: 'Los datos quedaron guardados.' });
    },
    onError: error => push({ type: 'error', title: 'No se pudo guardar el cliente', message: error.message }),
  });
  const openForm = (cliente?: Cliente) => {
    setEditing(cliente ?? null);
    setForm(cliente ? {
      tipo_documento: cliente.tipo_documento,
      documento: cliente.documento,
      nombre: cliente.nombre,
      telefono: cliente.telefono,
      correo: cliente.correo,
      direccion: cliente.direccion,
      permite_credito: cliente.permite_credito,
      cupo_credito: cliente.cupo_credito,
    } : emptyForm);
    setFormOpen(true);
  };
  const setField = <K extends keyof ClienteForm>(key: K, value: ClienteForm[K]) =>
    setForm(current => ({ ...current, [key]: value }));
  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!form.nombre.trim()) {
      push({ type: 'error', title: 'Falta el nombre', message: 'El nombre del cliente es obligatorio.' });
      return;
    }
    if (form.permite_credito && Number(form.cupo_credito) <= 0) {
      push({ type: 'error', title: 'Cupo inválido', message: 'Define un cupo mayor que cero para habilitar crédito.' });
      return;
    }
    save.mutate();
  };

  return <main className="jg-page sales-page">
    <header className="sales-heading"><div><span className="jg-eyebrow">DIRECTORIO</span><h1>Clientes</h1><p>Administra datos, crédito e historial de compra.</p></div><Button variant="primary" onClick={() => openForm()}><Plus size={17} /> Nuevo cliente</Button></header>
    <section className="sales-panel">
      <label className="sales-client-search"><Search size={17} /><Input aria-label="Buscar clientes" placeholder="Nombre, documento, teléfono o correo" value={search} onChange={event => setSearch(event.target.value)} /></label>
      {clients.isError && <p className="sales-error" role="alert">{clients.error.message}</p>}
      <div className="sales-table-wrap"><table className="sales-table"><thead><tr><th>Cliente</th><th>Documento</th><th>Teléfono</th><th>Crédito</th><th>Cupo</th><th>Saldo crédito</th><th>Acciones</th></tr></thead><tbody>
        {clients.data?.results.map(cliente => <tr key={cliente.id}>
          <td><b>{cliente.nombre}</b><small className="sales-table-sub">{cliente.correo || 'Sin correo'}</small></td>
          <td>{cliente.tipo_documento} {cliente.documento}</td><td>{cliente.telefono || '—'}</td>
          <td><Badge tone={cliente.permite_credito ? 'success' : 'neutral'}>{cliente.permite_credito ? 'Habilitado' : 'No habilitado'}</Badge></td>
          <td>{pesos(cliente.cupo_credito)}</td><td><b>{pesos(cliente.saldo_credito)}</b></td>
          <td className="sales-actions"><Button aria-label={`Ver historial de ${cliente.nombre}`} onClick={() => setHistoryClient(cliente)}><History size={16} /> Historial</Button><Button aria-label={`Editar ${cliente.nombre}`} onClick={() => openForm(cliente)}><Pencil size={16} /> Editar</Button></td>
        </tr>)}
      </tbody></table></div>
      {!clients.isLoading && !clients.data?.results.length && <div className="sales-empty"><b>No hay clientes</b><p>Crea un cliente o cambia el término de búsqueda.</p></div>}
    </section>
    {formOpen && <div className="jg-modal__backdrop"><section className="jg-modal sales-client-modal" role="dialog" aria-modal="true" aria-label={editing ? 'Editar cliente' : 'Nuevo cliente'}>
      <header><h2>{editing ? 'Editar cliente' : 'Nuevo cliente'}</h2><button className="jg-icon-button" aria-label="Cerrar" onClick={() => setFormOpen(false)}>×</button></header>
      <form className="jg-modal__body sales-client-form" onSubmit={submit}>
        <div className="sales-form-grid">
          <label>Tipo de documento<Select value={form.tipo_documento} onChange={event => setField('tipo_documento', event.target.value)}><option value="">Sin documento</option><option value="CC">Cédula</option><option value="CE">Cédula extranjería</option><option value="NIT">NIT</option><option value="TI">Tarjeta identidad</option><option value="PAS">Pasaporte</option><option value="OTRO">Otro</option></Select></label>
          <label>Número de documento<Input value={form.documento} onChange={event => setField('documento', event.target.value)} maxLength={30} /></label>
          <label className="sales-form-wide">Nombre completo<Input required autoFocus value={form.nombre} onChange={event => setField('nombre', event.target.value)} maxLength={180} /></label>
          <label>Teléfono<Input value={form.telefono} onChange={event => setField('telefono', event.target.value)} maxLength={30} /></label>
          <label>Correo<Input type="email" value={form.correo} onChange={event => setField('correo', event.target.value)} /></label>
          <label className="sales-form-wide">Dirección<Input value={form.direccion} onChange={event => setField('direccion', event.target.value)} maxLength={250} /></label>
        </div>
        <label className="sales-checkbox"><input type="checkbox" checked={form.permite_credito} onChange={event => setField('permite_credito', event.target.checked)} /> Habilitar compras a crédito</label>
        {form.permite_credito && <label>Cupo de crédito<Input type="number" min="0.01" step="0.01" value={form.cupo_credito} onChange={event => setField('cupo_credito', event.target.value)} /></label>}
        <div className="sales-modal-actions"><Button type="button" onClick={() => setFormOpen(false)}>Cancelar</Button><Button variant="primary" type="submit" disabled={save.isPending}>{save.isPending ? 'Guardando…' : 'Guardar cliente'}</Button></div>
      </form>
    </section></div>}
    {historyClient && <HistoryDrawer cliente={historyClient} rows={history.data?.results ?? []} isError={history.isError ? history.error.message : ''} onClose={() => setHistoryClient(null)} />}
  </main>;
}

function HistoryDrawer({ cliente, rows, isError, onClose }: { cliente: Cliente; rows: Venta[]; isError: string; onClose: () => void }) {
  return <Drawer title={`Historial · ${cliente.nombre}`} onClose={onClose}>
    {isError && <p className="sales-error" role="alert">{isError}</p>}
    {!isError && rows.length === 0 ? <p className="sales-muted">Este cliente todavía no tiene ventas.</p> : rows.map(sale => <article className="sales-client-history" key={sale.id}>
      <header><b>Venta #{sale.numero}</b><Badge tone={sale.estado === 'PAGADA' ? 'success' : sale.estado === 'PENDIENTE' ? 'warning' : 'neutral'}>{sale.estado}</Badge></header>
      <p>{new Date(sale.fecha).toLocaleString('es-CO')} · {sale.tipo}</p>
      <div><span>Total <b>{pesos(sale.total)}</b></span><span>Saldo <b>{pesos(sale.saldo_pendiente)}</b></span></div>
    </article>)}
  </Drawer>;
}

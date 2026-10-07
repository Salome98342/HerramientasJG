import { useState, type FormEvent } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ArrowLeft, PackagePlus, Pencil, Plus } from 'lucide-react';
import { Link } from 'react-router-dom';
import { Badge, Button, EmptyState, Input, Modal, Select } from '@/components/ui/Primitives';
import { useToast } from '@/components/ui/ToastContext';
import { useAppStore } from '@/store/appStore';
import { alquileresApi, type ArticuloAlquiler, type TipoArticuloAlquiler } from './api';

const money = new Intl.NumberFormat('es-CO', { style: 'currency', currency: 'COP', maximumFractionDigits: 2 });
const pesos = (value: string | number) => money.format(Number(value));
const types: { value: TipoArticuloAlquiler; label: string }[] = [
  { value: 'ANDAMIO', label: 'Andamio' },
  { value: 'HERRAMIENTA', label: 'Herramienta' },
  { value: 'OTRO', label: 'Otro' },
];

interface ArticleForm {
  referencia: string;
  nombre: string;
  tipo: TipoArticuloAlquiler;
  cantidad_total: string;
  tarifa_diaria: string;
  costo_diario: string;
  valor_reposicion: string;
}
const emptyForm: ArticleForm = {
  referencia: '',
  nombre: '',
  tipo: 'HERRAMIENTA',
  cantidad_total: '0',
  tarifa_diaria: '0',
  costo_diario: '0',
  valor_reposicion: '0',
};

export default function InventarioAlquiler() {
  const isAdmin = useAppStore(state => state.user?.role === 'ADMIN');
  const queryClient = useQueryClient();
  const { push } = useToast();
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<ArticuloAlquiler | null>(null);
  const [form, setForm] = useState<ArticleForm>(emptyForm);
  const [search, setSearch] = useState('');
  const items = useQuery({
    queryKey: ['alquiler-articulos', search, isAdmin],
    queryFn: () => alquileresApi.articulos(search, !isAdmin),
  });

  const save = useMutation({
    mutationFn: () => {
      const payload = { ...form, referencia: form.referencia.trim(), nombre: form.nombre.trim(), activo: editing?.activo ?? true };
      return editing
        ? alquileresApi.actualizarArticulo(editing.id, payload)
        : alquileresApi.crearArticulo(payload);
    },
    onSuccess: () => {
      setFormOpen(false);
      setEditing(null);
      void queryClient.invalidateQueries({ queryKey: ['alquiler-articulos'] });
      push({ type: 'success', title: editing ? 'Artículo actualizado' : 'Artículo creado', message: 'Inventario de alquiler actualizado.' });
    },
    onError: error => push({ type: 'error', title: 'No se pudo guardar el artículo', message: error.message }),
  });
  const toggleActive = useMutation({
    mutationFn: async (article: ArticuloAlquiler) => {
      if (article.activo) await alquileresApi.desactivarArticulo(article.id);
      else await alquileresApi.actualizarArticulo(article.id, { activo: true });
    },
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ['alquiler-articulos'] }),
    onError: error => push({ type: 'error', title: 'No se pudo actualizar el artículo', message: error.message }),
  });

  const openNew = () => {
    setEditing(null);
    setForm(emptyForm);
    setFormOpen(true);
  };
  const openEdit = (item: ArticuloAlquiler) => {
    setEditing(item);
    setForm({
      referencia: item.referencia,
      nombre: item.nombre,
      tipo: item.tipo,
      cantidad_total: item.cantidad_total,
      tarifa_diaria: item.tarifa_diaria,
      costo_diario: item.costo_diario,
      valor_reposicion: item.valor_reposicion,
    });
    setFormOpen(true);
  };
  const submit = (event: FormEvent) => {
    event.preventDefault();
    save.mutate();
  };

  return <main className="jg-page rental-page">
    <header className="rental-heading">
      <div><span className="jg-eyebrow">ACTIVOS INDEPENDIENTES</span><h1>Inventario de alquiler</h1><p>Unidades disponibles, reservadas y tarifas diarias del inventario de renta.</p></div>
      <div className="rental-heading__actions"><Link className="jg-button jg-button--secondary" to="/alquileres"><ArrowLeft size={16} /> Volver a alquileres</Link>{isAdmin && <Button variant="primary" onClick={openNew}><Plus size={17} /> Nuevo artículo</Button>}</div>
    </header>
    <section className="rental-panel">
      <div className="rental-filters"><Input aria-label="Buscar artículo de alquiler" placeholder="Buscar por nombre o referencia" value={search} onChange={event => setSearch(event.target.value)} /></div>
      {items.isError && <p className="rental-error" role="alert">{items.error.message}</p>}
      {items.isLoading ? <p className="rental-muted">Cargando inventario…</p> : (items.data?.results.length ?? 0) === 0
        ? <EmptyState title="Inventario sin artículos" description="Crea el primer artículo para empezar a controlar unidades destinadas a alquiler." action={isAdmin ? <Button variant="primary" onClick={openNew}>Crear artículo</Button> : undefined} />
        : <div className="rental-table-wrap"><table className="rental-table"><thead><tr><th>Artículo</th><th>Tipo</th><th>Total</th><th>Disponibles</th><th>En alquiler</th><th>Tarifa diaria</th><th>Estado</th>{isAdmin && <th>Acciones</th>}</tr></thead><tbody>
          {items.data?.results.map(item => {
            const available = Number(item.cantidad_disponible);
            const tone = !item.activo ? 'neutral' : available === 0 ? 'warning' : 'success';
            const label = !item.activo ? 'Inactivo' : available === 0 ? 'Sin disponibilidad' : 'Disponible';
            return <tr key={item.id}>
              <td className="rental-ref">{item.nombre}<small>{item.referencia}</small></td>
              <td>{types.find(type => type.value === item.tipo)?.label ?? item.tipo}</td>
              <td>{item.cantidad_total}</td>
              <td><b>{item.cantidad_disponible}</b></td>
              <td>{item.cantidad_en_alquiler}</td>
              <td>{pesos(item.tarifa_diaria)}</td>
              <td><Badge tone={tone}>{label}</Badge></td>
              {isAdmin && <td><div className="rental-actions"><Button onClick={() => openEdit(item)}><Pencil size={15} /> Editar</Button><Button variant={item.activo ? 'danger' : 'secondary'} onClick={() => toggleActive.mutate(item)} disabled={toggleActive.isPending}>{item.activo ? 'Desactivar' : 'Activar'}</Button></div></td>}
            </tr>;
          })}
        </tbody></table></div>}
    </section>

    {formOpen && <Modal title={editing ? 'Editar artículo' : 'Nuevo artículo de alquiler'} onClose={() => setFormOpen(false)}>
      <form className="rental-form" onSubmit={submit}>
        <div className="rental-form__dates">
          <label>Referencia<Input required maxLength={60} value={form.referencia} onChange={event => setForm({ ...form, referencia: event.target.value })} /></label>
          <label>Tipo<Select value={form.tipo} onChange={event => setForm({ ...form, tipo: event.target.value as TipoArticuloAlquiler })}>{types.map(type => <option value={type.value} key={type.value}>{type.label}</option>)}</Select></label>
        </div>
        <label>Nombre<Input required maxLength={180} value={form.nombre} onChange={event => setForm({ ...form, nombre: event.target.value })} /></label>
        <div className="rental-form__dates">
          <label>Cantidad total<Input required min={editing ? Number(editing.cantidad_en_alquiler) : 0} step="0.01" type="number" value={form.cantidad_total} onChange={event => setForm({ ...form, cantidad_total: event.target.value })} /></label>
          <label>Tarifa diaria<Input required min="0" step="0.01" type="number" value={form.tarifa_diaria} onChange={event => setForm({ ...form, tarifa_diaria: event.target.value })} /></label>
        </div>
        <div className="rental-form__dates">
          <label>Costo diario interno<Input min="0" step="0.01" type="number" value={form.costo_diario} onChange={event => setForm({ ...form, costo_diario: event.target.value })} /></label>
          <label>Valor de reposición<Input min="0" step="0.01" type="number" value={form.valor_reposicion} onChange={event => setForm({ ...form, valor_reposicion: event.target.value })} /></label>
        </div>
        {save.isError && <p className="rental-error" role="alert">{save.error.message}</p>}
        <footer className="rental-modal-actions"><Button type="button" onClick={() => setFormOpen(false)}>Cancelar</Button><Button variant="primary" type="submit" disabled={save.isPending}><PackagePlus size={16} /> Guardar artículo</Button></footer>
      </form>
    </Modal>}
  </main>;
}

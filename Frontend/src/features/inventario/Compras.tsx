import { useFieldArray, useForm } from 'react-hook-form';
import { z } from 'zod';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Button, EmptyState, Input, Select, Skeleton } from '@/components/ui/Primitives';
import { useToast } from '@/components/ui/ToastContext';
import { useAppStore } from '@/store/appStore';
import { inventarioApi } from './api';

const compraSchema = z.object({ proveedor: z.coerce.number().positive(), items: z.array(z.object({ producto: z.coerce.number().positive(), cantidad: z.coerce.number().positive(), costo_unitario: z.coerce.number().min(0) })).min(1) });
type CompraForm = z.infer<typeof compraSchema>;
const cop = new Intl.NumberFormat('es-CO', { style:'currency', currency:'COP', maximumFractionDigits:0 });
export default function Compras() {
  const user = useAppStore(s => s.user); const { push } = useToast(); const qc = useQueryClient();
  const providers = useQuery({ queryKey:['inventario-proveedores'], queryFn:inventarioApi.proveedores });
  const products = useQuery({ queryKey:['inventario-productos-compra'], queryFn:() => inventarioApi.productos() });
  const history = useQuery({ queryKey:['inventario-compras'], queryFn:inventarioApi.compras });
  const form = useForm<CompraForm>({ defaultValues:{ proveedor:0, items:[{producto:0,cantidad:1,costo_unitario:0}] } });
  const rows = useFieldArray({ control:form.control, name:'items' });
  const save = useMutation({ mutationFn:inventarioApi.crearCompra, onSuccess:() => { form.reset({ proveedor:0, items:[{producto:0,cantidad:1,costo_unitario:0}] }); void qc.invalidateQueries({queryKey:['inventario']}); void qc.invalidateQueries({queryKey:['inventario-compras']}); push({type:'success',title:'Compra registrada',message:'El stock y el costo promedio fueron actualizados.'}); }, onError:() => push({type:'error',title:'No se pudo registrar',message:'Revisa proveedor, productos y cantidades.'}) });
  const submit = form.handleSubmit(values => { const parsed = compraSchema.safeParse(values); if (!parsed.success) { push({type:'error',title:'Compra incompleta',message:'Selecciona proveedor y al menos un producto con cantidades válidas.'}); return; } save.mutate(parsed.data); });
  if (user?.role !== 'ADMIN') return <main className="jg-page"><EmptyState title="Acceso restringido" description="Solo un administrador puede registrar compras y consultar costos."/></main>;
  const items = products.data?.results ?? [];
  return <main className="jg-page inventory-page"><header className="inventory-page__heading"><div><span className="jg-eyebrow">ABASTECIMIENTO</span><h1>Compras</h1><p>Registra entradas de proveedor y actualiza el costo promedio ponderado.</p></div></header>
    <section className="purchase-layout"><form className="purchase-form" onSubmit={submit}><h2>Registrar compra</h2>{providers.isLoading || products.isLoading ? <Skeleton className="inventory-skeleton__row"/> : providers.isError || products.isError ? <p role="alert">No se pudieron cargar proveedores o productos.</p> : <><label>Proveedor<Select {...form.register('proveedor')}><option value={0}>Selecciona proveedor</option>{providers.data?.results.filter(p=>p.activo).map(p=><option key={p.id} value={p.id}>{p.nombre}</option>)}</Select></label><div className="purchase-form__rows"><div className="purchase-form__labels"><span>Producto</span><span>Cantidad</span><span>Costo unitario</span><span/></div>{rows.fields.map((row,index)=><div className="purchase-form__row" key={row.id}><Select {...form.register(`items.${index}.producto`)} aria-label="Producto"><option value={0}>Seleccionar</option>{items.filter(p=>p.activo).map(p=><option key={p.id} value={p.id}>{p.referencia} · {p.nombre}</option>)}</Select><Input aria-label="Cantidad" type="number" min="0.01" step="0.01" {...form.register(`items.${index}.cantidad`)}/><Input aria-label="Costo unitario" type="number" min="0" step="0.01" {...form.register(`items.${index}.costo_unitario`)}/><Button type="button" aria-label="Quitar producto" onClick={()=>rows.remove(index)} disabled={rows.fields.length===1}>Quitar</Button></div>)}</div><Button type="button" onClick={()=>rows.append({producto:0,cantidad:1,costo_unitario:0})}>Añadir producto</Button><Button variant="primary" type="submit" disabled={save.isPending}>{save.isPending?'Registrando…':'Registrar compra'}</Button></>}</form>
    <section className="purchase-history"><h2>Historial de compras</h2>{history.isLoading ? <div className="inventory-skeleton">{[1,2,3].map(n=><Skeleton key={n} className="inventory-skeleton__row"/>)}</div> : history.isError ? <EmptyState title="Historial no disponible" description="Intenta cargarlo nuevamente." action={<Button onClick={()=>void history.refetch()}>Reintentar</Button>}/> : !history.data?.results.length ? <EmptyState title="Aún no hay compras" description="Las compras registradas aparecerán aquí."/> : <div className="purchase-list">{history.data.results.map(c=><article key={c.id}><header><b>Compra #{c.numero}</b><span>{new Date(c.fecha).toLocaleDateString('es-CO')}</span></header><p>{c.proveedor_nombre} · {c.detalles.length} productos</p><ul>{c.detalles.map((d,i)=><li key={`${c.id}-${i}`}>{d.producto_nombre} <span>{d.cantidad} und.</span></li>)}</ul><strong>{cop.format(Number(c.total ?? 0))}</strong></article>)}</div>}</section></section>
  </main>;
}

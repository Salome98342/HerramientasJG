import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Download, FileSpreadsheet, Upload } from 'lucide-react';
import { Badge, Button, Card, Input } from '@/components/ui/Primitives';
import { useToast } from '@/components/ui/ToastContext';
import { apiDownload } from '@/lib/apiClient';
import { inventarioApi, type ImportacionPreview } from './api';

export default function ImportacionInventario() {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<ImportacionPreview | null>(null);
  const queryClient = useQueryClient();
  const { push } = useToast();
  const previsualizar = useMutation({
    mutationFn: inventarioApi.previsualizarImportacion,
    onSuccess: setPreview,
    onError: error => push({ type: 'error', title: 'No se pudo validar el archivo', message: error.message }),
  });
  const confirmar = useMutation({
    mutationFn: inventarioApi.confirmarImportacion,
    onSuccess: result => {
      setPreview(null);
      setFile(null);
      void queryClient.invalidateQueries({ queryKey: ['inventario'] });
      void queryClient.invalidateQueries({ queryKey: ['inventario-alquiler'] });
      push({
        type: 'success',
        title: 'Importación completada',
        message: `Creados ${result.importados.Venta} productos de venta y ${result.importados.Alquiler} artículos de alquiler.`,
      });
    },
    onError: error => push({ type: 'error', title: 'No se pudo confirmar', message: error.message }),
  });

  const selectFile = (selected: File | undefined) => {
    setFile(selected ?? null);
    setPreview(null);
  };
  const downloadTemplate = () => {
    void apiDownload('/inventario/importaciones/plantilla/', 'plantilla_inventario_jg.xlsx')
      .catch(error => push({ type: 'error', title: 'No se pudo descargar la plantilla', message: error.message }));
  };

  return <main className="jg-page inventory-page">
    <header className="inventory-page__heading">
      <div><span className="jg-eyebrow">ADMINISTRACIÓN</span><h1>Importar inventario desde Excel</h1><p>Valida ambas hojas y revisa cada fila antes de confirmar los cambios.</p></div>
      <Button onClick={downloadTemplate}><Download size={17}/> Descargar plantilla</Button>
    </header>
    <Card>
      <form className="inventory-form" onSubmit={event => { event.preventDefault(); if (file) previsualizar.mutate(file); }}>
        <p><FileSpreadsheet size={18}/> Carga la plantilla .xlsx. Incluye las hojas <b>Venta</b> y <b>Alquiler</b>; las referencias existentes se omiten sin sobrescribir datos.</p>
        <label>Archivo Excel (.xlsx)<Input type="file" accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" onChange={event => selectFile(event.currentTarget.files?.[0])}/></label>
        {file && <p>Seleccionado: <b>{file.name}</b> ({Math.ceil(file.size / 1024)} KB)</p>}
        <footer>
          <Button type="submit" variant="primary" disabled={!file || previsualizar.isPending || file.size > 10 * 1024 * 1024}>
            <Upload size={17}/>{previsualizar.isPending ? 'Validando…' : 'Validar archivo'}
          </Button>
          {file && file.size > 10 * 1024 * 1024 && <small>El tamaño máximo permitido es 10 MB.</small>}
        </footer>
      </form>
    </Card>
    {preview && <Card className="import-preview">
      <h2>Resultado de la validación</h2>
      <p>{preview.resumen.validas} filas nuevas, {preview.resumen.existentes} referencias existentes y {preview.resumen.invalidas} filas con errores.</p>
      {!!preview.errores.length && <div role="alert"><b>Corrige estos errores antes de confirmar:</b><ul>{preview.errores.map((error, index) => <li key={`${index}-${error}`}>{error}</li>)}</ul></div>}
      <div className="inventory-table-wrap"><table className="inventory-table"><thead><tr><th>Hoja</th><th>Fila</th><th>Referencia</th><th>Resultado</th><th>Detalle</th></tr></thead><tbody>
        {preview.filas.map(row => <tr key={`${row.hoja}-${row.fila}`}><td>{row.hoja}</td><td>{row.fila}</td><td>{row.referencia || '—'}</td><td><Badge tone={row.estado === 'ERROR' ? 'danger' : row.estado === 'OMITIR_EXISTENTE' ? 'warning' : 'success'}>{row.estado === 'OMITIR_EXISTENTE' ? 'Ya existe; se omitirá' : row.estado}</Badge></td><td>{row.errores.length ? row.errores.join(' ') : '—'}</td></tr>)}
      </tbody></table></div>
      <footer>
        <Button onClick={() => { setPreview(null); if (file) previsualizar.mutate(file); }} disabled={!file || previsualizar.isPending}>Volver a validar</Button>
        <Button variant="primary" disabled={!preview.puede_confirmar || confirmar.isPending || !file} onClick={() => { if (file && window.confirm('¿Confirmas la importación de las filas válidas? Las referencias existentes no se modificarán.')) confirmar.mutate(file); }}>
          {confirmar.isPending ? 'Importando…' : 'Confirmar importación'}
        </Button>
      </footer>
    </Card>}
  </main>;
}

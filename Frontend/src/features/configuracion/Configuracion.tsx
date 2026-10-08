import { Save, ShieldCheck, Upload } from 'lucide-react';
import { useState, type ChangeEvent, type FormEvent } from 'react';
import { Button, Input, Select } from '@/components/ui/Primitives';

type PaymentState = {
  efectivo: boolean;
  transferencia: boolean;
  addi: boolean;
  sistecredito: boolean;
};

const initialPaymentState: PaymentState = {
  efectivo: true,
  transferencia: true,
  addi: true,
  sistecredito: true,
};

const initialConfig = {
  nombreComercial: 'Herramientas JG',
  razonSocial: 'Herramientas JG S.A.S.',
  nit: '900123456-7',
  direccion: 'Calle 10 # 5-20',
  ciudad: 'Bogotá',
  telefono: '+57 300 123 4567',
  correo: 'ventas@herramientasjg.com',
  recibosPrefijo: 'JG',
  alquilerMult: '1.25',
  politicaCancelacion: 'DEVOLVER_TODO',
  retencion: '10.00',
  horasAviso: '24',
  cupoCredito: '2500000',
  stockMinimo: '10',
};

export default function Configuracion() {
  const [form, setForm] = useState(initialConfig);
  const [payment, setPayment] = useState<PaymentState>(initialPaymentState);
  const [logoName, setLogoName] = useState('logo-actual.png');

  const onChange = (event: ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value } = event.target;
    setForm(current => ({ ...current, [name]: value }));
  };

  const togglePayment = (method: keyof PaymentState) => {
    setPayment(current => ({
      ...current,
      [method]: !current[method],
    }));
  };

  const onSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    console.info('Configuración guardada', { ...form, payment });
  };

  const totals = Object.values(payment).filter(Boolean).length;

  return <main className="jg-page jg-enter">
    <header className="jg-page__heading">
      <div>
        <span className="jg-eyebrow">ADMINISTRACIÓN</span>
        <h1>Configuración del negocio</h1>
        <p>Ajusta la información empresarial, medios de pago y políticas operativas.</p>
      </div>
      <Button variant="primary" type="submit" form="config-form">
        <Save size={17} /> Guardar cambios
      </Button>
    </header>

    <form id="config-form" className="jg-stack" onSubmit={onSubmit}>
      <section className="jg-card">
        <div className="jg-section-heading">
          <div>
            <h2>Datos del negocio</h2>
            <p>Información visible para clientes, recibos y reportes.</p>
          </div>
          <span className="jg-badge jg-badge--success">{totals}/4 métodos activos</span>
        </div>

        <div className="jg-grid jg-grid--2">
          <label>Nombre comercial<Input name="nombreComercial" value={form.nombreComercial} onChange={onChange} /></label>
          <label>Razón social<Input name="razonSocial" value={form.razonSocial} onChange={onChange} /></label>
          <label>NIT<Input name="nit" value={form.nit} onChange={onChange} /></label>
          <label>Ciudad<Input name="ciudad" value={form.ciudad} onChange={onChange} /></label>
          <label className="jg-span-2">Dirección<Input name="direccion" value={form.direccion} onChange={onChange} /></label>
          <label>Teléfono<Input name="telefono" value={form.telefono} onChange={onChange} /></label>
          <label>Correo<Input type="email" name="correo" value={form.correo} onChange={onChange} /></label>
        </div>
      </section>

      <section className="jg-card">
        <div className="jg-section-heading">
          <div>
            <h2>Logo y recibos</h2>
            <p>Define el branding y la numeración de comprobantes.</p>
          </div>
        </div>
        <div className="jg-grid jg-grid--2">
          <label className="jg-upload">
            <span>Logo del negocio</span>
            <div className="jg-upload__box">
              <Upload size={18} />
              <span>{logoName}</span>
              <input type="file" accept="image/*" onChange={event => setLogoName(event.target.files?.[0]?.name ?? 'logo-actual.png')} />
            </div>
          </label>
          <label>Prefijo de recibos<Input name="recibosPrefijo" value={form.recibosPrefijo} onChange={onChange} /></label>
        </div>
      </section>

      <section className="jg-card">
        <div className="jg-section-heading">
          <div>
            <h2>Medios de pago habilitados</h2>
            <p>Controla qué opciones acepta el negocio en ventas y abonos.</p>
          </div>
          <ShieldCheck size={18} />
        </div>
        <div className="jg-toggle-grid">
          {[
            { key: 'efectivo', label: 'Efectivo' },
            { key: 'transferencia', label: 'Transferencia' },
            { key: 'addi', label: 'Addi' },
            { key: 'sistecredito', label: 'Sistecrédito' },
          ].map(item => (
            <label key={item.key} className="jg-toggle">
              <input type="checkbox" checked={payment[item.key as keyof PaymentState]} onChange={() => togglePayment(item.key as keyof PaymentState)} />
              <span>{item.label}</span>
            </label>
          ))}
        </div>
      </section>

      <section className="jg-card">
        <div className="jg-section-heading">
          <div>
            <h2>Política de alquiler y crédito</h2>
            <p>Configura los indicadores principales que rigen la operación.</p>
          </div>
        </div>

        <div className="jg-grid jg-grid--2">
          <label>Recargo diario por alquiler<Input name="alquilerMult" type="number" min="0" step="0.01" value={form.alquilerMult} onChange={onChange} /></label>
          <label>Horas de anticipación para avisar vencimiento<Input name="horasAviso" type="number" min="1" step="1" value={form.horasAviso} onChange={onChange} /></label>
          <label>Política de cancelación<Select name="politicaCancelacion" value={form.politicaCancelacion} onChange={onChange}>
            <option value="DEVOLVER_TODO">Devolver todo</option>
            <option value="RETENER_PORCENTAJE">Retener porcentaje</option>
          </Select></label>
          <label>Porcentaje de retención<Input name="retencion" type="number" min="0" max="100" step="0.01" value={form.retencion} onChange={onChange} /></label>
          <label>Cupo por defecto de crédito<Input name="cupoCredito" type="number" min="0" step="1000" value={form.cupoCredito} onChange={onChange} /></label>
          <label>Stock mínimo por defecto<Input name="stockMinimo" type="number" min="0" step="1" value={form.stockMinimo} onChange={onChange} /></label>
        </div>
      </section>
    </form>
  </main>;
}

import { BookOpen, CircleHelp, FileText, ShieldCheck, Sparkles } from 'lucide-react';
import { Button } from '@/components/ui/Primitives';

const sections = [
  {
    title: 'Cómo operar la app',
    icon: BookOpen,
    items: [
      'Abre la caja antes de registrar ventas o gastos.',
      'Usa la sección de inventario para consultar existencias y compras.',
      'Consulta los reportes desde el panel administrativo cuando necesites análisis.',
    ],
  },
  {
    title: 'Política del negocio',
    icon: ShieldCheck,
    items: [
      'Los permisos de administración solo están habilitados para usuarios con rol administrador.',
      'La configuración de medios de pago y reglas comerciales se mantienen por negocio.',
      'Las políticas de alquiler y retención se aplican según la configuración activa del negocio.',
    ],
  },
  {
    title: 'Soporte técnico',
    icon: FileText,
    items: [
      'Revisa la información de recibos y reportes antes de cerrar semana o periodo.',
      'Si necesitas cambiar un prefijo o logo, usa la configuración del negocio.',
      'Para incidencias no técnicas, conserva evidencia de ventas, cajas y cierres.',
    ],
  },
];

export default function Ayuda() {
  return <main className="jg-page jg-page--help jg-enter">
    <header className="jg-page__heading">
      <div>
        <span className="jg-eyebrow">CENTRO DE AYUDA</span>
        <h1>Guía rápida</h1>
        <p>Información útil para usar el sistema con rapidez y mantener la operación clara.</p>
      </div>
      <Button variant="primary"><CircleHelp size={17} /> Ver más</Button>
    </header>

    <section className="jg-card">
      <div className="jg-section-heading">
        <div>
          <h2>¿Necesitas ayuda?</h2>
          <p>Todo el contenido de apoyo está pensado para orientar tanto a cajeros como a administradores.</p>
        </div>
        <Sparkles size={19} />
      </div>

      <div className="jg-help-grid">
        {sections.map(section => (
          <article key={section.title} className="jg-help-card">
            <div className="jg-help-card__icon">
              <section.icon size={20} />
            </div>
            <h3>{section.title}</h3>
            <ul>
              {section.items.map(item => <li key={item}>{item}</li>)}
            </ul>
          </article>
        ))}
      </div>
    </section>
  </main>;
}

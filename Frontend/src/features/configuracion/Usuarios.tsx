import { ArrowUpRight, Shield, UserCog, Users } from 'lucide-react';
import { Button, EmptyState } from '@/components/ui/Primitives';

const rows = [
  { id: 1, nombre: 'Ana Morales', rol: 'Administrador', negocio: 'Herramientas JG', ultimoAcceso: 'Hace 5 minutos' },
  { id: 2, nombre: 'Carlos Ruiz', rol: 'Cajero', negocio: 'Herramientas JG', ultimoAcceso: 'Hace 1 hora' },
  { id: 3, nombre: 'Laura Gómez', rol: 'Cajero', negocio: 'Herramientas JG', ultimoAcceso: 'Ayer' },
];

export default function Usuarios() {
  return <main className="jg-page jg-enter">
    <header className="jg-page__heading">
      <div>
        <span className="jg-eyebrow">SEGURIDAD</span>
        <h1>Usuarios y permisos</h1>
        <p>Consulta rápidamente la lista de accesos del negocio y sus roles vigentes.</p>
      </div>
      <Button variant="primary"><UserCog size={17} /> Nuevo usuario</Button>
    </header>

    <section className="jg-card">
      <div className="jg-section-heading">
        <div>
          <h2>Accesos del sistema</h2>
          <p>Los administradores pueden gestionar roles y permisos desde la configuración de negocio.</p>
        </div>
        <span className="jg-badge jg-badge--info"><Users size={15} /> {rows.length} usuarios</span>
      </div>

      {rows.length ? <div className="jg-table-wrap">
        <table className="jg-table">
          <thead>
            <tr>
              <th>Usuario</th>
              <th>Rol</th>
              <th>Negocio</th>
              <th>Último acceso</th>
              <th>Estado</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(item => <tr key={item.id}>
              <td><b>{item.nombre}</b></td>
              <td>{item.rol}</td>
              <td>{item.negocio}</td>
              <td>{item.ultimoAcceso}</td>
              <td>
                <span className={`jg-badge ${item.rol === 'Administrador' ? 'jg-badge--success' : 'jg-badge--neutral'}`}>
                  {item.rol === 'Administrador' ? 'Activo' : 'Disponible'}
                </span>
              </td>
            </tr>)}
          </tbody>
        </table>
      </div> : <EmptyState title="No hay usuarios" description="Aún no se han creado accesos para este negocio." />}
    </section>

    <section className="jg-card">
      <div className="jg-section-heading">
        <div>
          <h2>Permisos del negocio</h2>
          <p>Revisa los niveles de acceso resumidos del módulo actual.</p>
        </div>
      </div>
      <div className="jg-metrics jg-metrics--compact">
        <article className="jg-metric jg-metric--compact">
          <span className="jg-metric__icon jg-metric__icon--blue"><Shield size={18} /></span>
          <div>
            <small>Administración</small>
            <strong>1 perfil</strong>
          </div>
        </article>
        <article className="jg-metric jg-metric--compact">
          <span className="jg-metric__icon jg-metric__icon--green"><ArrowUpRight size={18} /></span>
          <div>
            <small>Operación</small>
            <strong>2 cajeros</strong>
          </div>
        </article>
      </div>
    </section>
  </main>;
}

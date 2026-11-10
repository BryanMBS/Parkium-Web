/* Layout del módulo de PLATAFORMA (Fase 3): espacio separado del operativo,
 * tema oscuro propio (docs/06 §6.11: foco visible, responsive a 390 px). */

import { NavLink, Outlet, Navigate, useNavigate } from 'react-router-dom'
import { useAuth } from '../../hooks/useAuth'
import '../../theme/platform.css'

const ITEMS = [
  { to: '/plataforma', etiqueta: 'Resumen', icono: '▤', fin: true },
  { to: '/plataforma/clientes', etiqueta: 'Clientes', icono: '◉' },
  { to: '/plataforma/auditoria', etiqueta: 'Auditoría', icono: '☰' },
]

export function PlatformLayout(): JSX.Element {
  const { usuario, cerrar } = useAuth()
  const navegar = useNavigate()

  async function salir(): Promise<void> {
    await cerrar()
    navegar('/login', { replace: true })
  }

  if (!usuario || usuario.rol !== 'PLATFORM_ADMIN') return <Navigate to="/login" replace />

  return (
    <div className="pf">
      <nav className="pf-sidebar" aria-label="Módulo de plataforma">
        <div className="pf-marca">
          <span className="lema">PARKIUM</span>
          <span className="pf-insignia">PLATAFORMA</span>
        </div>
        {ITEMS.map((i) => (
          <NavLink
            key={i.to}
            to={i.to}
            end={i.fin}
            className={({ isActive }) => `pf-item${isActive ? ' activo' : ''}`}
          >
            <span className="icono" aria-hidden="true">{i.icono}</span>
            {i.etiqueta}
          </NavLink>
        ))}
        <div className="pf-usuario">
          <span className="nombre">{usuario.nombre_completo || usuario.usuario}</span>
          <span className="correo">{usuario.usuario}</span>
          <span className="cargo">SUPER ADMIN</span>
        </div>
        <button className="pf-item" onClick={salir}>
          <span className="icono" aria-hidden="true">⏻</span>
          Salir
        </button>
      </nav>
      <main className="pf-contenido" id="contenido">
        <Outlet />
      </main>
    </div>
  )
}

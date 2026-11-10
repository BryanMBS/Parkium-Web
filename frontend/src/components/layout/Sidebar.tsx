import { NavLink } from 'react-router-dom'
import { useAuth } from '../../hooks/useAuth'
import { useTheme } from '../../theme/ThemeProvider'

export interface ItemNavegacion {
  glifo: string
  texto: string
  ruta: string
  /** el backend exige estos roles; la UI sólo oculta, la autorización es de la API */
  rolMinimo: 'OPERATOR' | 'ADMIN' | 'SUPERADMIN'
}

const ITEMS: ItemNavegacion[] = [
  { glifo: '▦', texto: 'Dashboard', ruta: '/', rolMinimo: 'OPERATOR' },
  { glifo: '↦', texto: 'Operación', ruta: '/operacion', rolMinimo: 'OPERATOR' },
  { glifo: '▤', texto: 'Histórico', ruta: '/historico', rolMinimo: 'ADMIN' },
  { glifo: '◈', texto: 'Mensualidades', ruta: '/mensualidades', rolMinimo: 'ADMIN' },
  { glifo: '⚙', texto: 'Configuración', ruta: '/configuracion', rolMinimo: 'OPERATOR' },
  { glifo: '◫', texto: 'Reportes', ruta: '/reportes', rolMinimo: 'SUPERADMIN' },
]

const NIVEL: Record<string, number> = { OPERATOR: 0, ADMIN: 1, SUPERADMIN: 2 }

export function Sidebar(): JSX.Element {
  const { usuario, cerrar } = useAuth()
  const { modo, setModo } = useTheme()

  return (
    <aside className="sidebar">
      <div className="logo">
        <img src="/marca/logo.png" alt="Parkium" />
        <span className="nombre">PARKIUM</span>
      </div>
      <nav aria-label="Navegación principal">
        {ITEMS.filter((i) => usuario && NIVEL[usuario.rol] >= NIVEL[i.rolMinimo]).map((i) => (
          <NavLink
            key={i.ruta}
            to={i.ruta}
            end
            aria-label={i.texto}
            className={({ isActive }) => `item${isActive ? ' activo' : ''}`}
          >
            <span className="glifo" aria-hidden="true">{i.glifo}</span>
            <span className="texto">{i.texto}</span>
          </NavLink>
        ))}
      </nav>
      <button className="salir" onClick={() => setModo(modo === 'claro' ? 'oscuro' : 'claro')}>
        {modo === 'claro' ? '◐ Modo noche' : '◑ Modo día'}
      </button>
      <div className="usuario">
        <span className="glifo" aria-hidden="true">•</span>
        <div className="datos">
          <div><strong>{usuario?.nombre_completo}</strong></div>
          <div className="rol">{usuario?.etiqueta_rol ?? usuario?.rol}</div>
        </div>
      </div>
      <button className="salir" onClick={() => void cerrar()}>Cerrar sesión</button>
    </aside>
  )
}

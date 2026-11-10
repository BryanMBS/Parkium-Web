import { Outlet } from 'react-router-dom'
import { Sidebar } from './Sidebar'

/** Estructura general autenticada: barra lateral 235 px + contenido. */
export function Shell(): JSX.Element {
  return (
    <div className="shell">
      <Sidebar />
      <main className="pagina" id="contenido">
        <Outlet />
      </main>
    </div>
  )
}

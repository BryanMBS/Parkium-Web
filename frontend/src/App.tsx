import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { useAuth } from './hooks/useAuth'
import { Shell } from './components/layout/Shell'

import { LoginPage } from './pages/LoginPage'
import { RecoveryPage } from './pages/RecoveryPage'
import { DashboardPage } from './pages/DashboardPage'
import { OperationsPage } from './pages/OperationsPage'
import { HistoryPage } from './pages/HistoryPage'
import { OcupacionDetallePage } from './pages/OcupacionDetallePage'
import { SubscriptionsPage } from './pages/SubscriptionsPage'
import { SettingsPage } from './pages/SettingsPage'
import { ReportsPage } from './pages/ReportsPage'
import { NotFoundPage } from './pages/NotFoundPage'

import { PlatformLayout } from './pages/platform/PlatformLayout'
import { PlatformSummaryPage } from './pages/platform/PlatformSummaryPage'
import { PlatformClientsPage } from './pages/platform/PlatformClientsPage'
import { PlatformClientDetailPage } from './pages/platform/PlatformClientDetailPage'
import { PlatformAuditPage } from './pages/platform/PlatformAuditPage'

/** Ruta guardada: si no hay sesión, el flujo acción → login. */
function Protegida({ solo, children }: { solo?: 'ADMIN' | 'SUPERADMIN'; children: React.ReactNode }): JSX.Element {
  const { usuario } = useAuth()
  if (!usuario) return <Navigate to="/login" replace />
  if (solo === 'SUPERADMIN' && usuario.rol !== 'SUPERADMIN') return <Navigate to="/" replace />
  if (solo === 'ADMIN' && usuario.rol === 'OPERATOR') return <Navigate to="/" replace />
  return <>{children}</>
}

export default function App(): JSX.Element {
  const { usuario, cargando } = useAuth()
  const ubicacion = useLocation()

  // fix UX-S022: el título del documento refleja la vista activa
  const TITULOS: Array<[string, string]> = [
    ['/historico', 'Histórico — Parkium'],
    ['/ocupacion', 'Detalle de ocupación — Parkium'],
    ['/mensualidades', 'Mensualidades — Parkium'],
    ['/configuracion', 'Configuración — Parkium'],
    ['/reportes', 'Reportes — Parkium'],
    ['/recuperar', 'Recuperación — Parkium'],
    ['/plataforma', 'Plataforma — Parkium'],
    ['/operacion', 'Operación — Parkium'],
  ]
  document.title = TITULOS.find(([ruta]) => ubicacion.pathname.startsWith(ruta))?.[1] ?? 'Parkium'

  if (cargando) {
    return <div style={{ padding: 60, textAlign: 'center', color: 'var(--color-muted)' }}>Cargando Parkium…</div>
  }

  const publica = ubicacion.pathname === '/login' || ubicacion.pathname === '/recuperar'

  if (!usuario) {
    // el recibo público /r/:token lo sirve el backend como HTML: no pasa por aquí
    return publicRoutes()
  }

  if (publica) return <Navigate to="/" replace />

  // El administrador de PLATAFORMA tiene su propio espacio (docs/02: dos
  // espacios separados); jamás entra al operativo.
  if (usuario.rol === 'PLATFORM_ADMIN') {
    return (
      <Routes>
        <Route path="/plataforma" element={<PlatformLayout />}>
          <Route index element={<PlatformSummaryPage />} />
          <Route path="clientes" element={<PlatformClientsPage />} />
          <Route path="clientes/:id" element={<PlatformClientDetailPage />} />
          <Route path="auditoria" element={<PlatformAuditPage />} />
          <Route path="*" element={<Navigate to="/plataforma" replace />} />
        </Route>
        <Route path="*" element={<Navigate to="/plataforma" replace />} />
      </Routes>
    )
  }

  // Un usuario de tenant jamás ve /plataforma: vuelve a su espacio operativo.
  if (ubicacion.pathname.startsWith('/plataforma')) return <Navigate to="/" replace />

  return (
    <Routes>
      <Route element={<Shell />}>
        <Route index element={<DashboardPage />} />
        <Route path="/operacion" element={<OperationsPage />} />
        <Route path="/recuperar" element={<RecoveryPage />} />
        <Route
          path="/historico"
          element={
            <Protegida solo="ADMIN">
              <HistoryPage />
            </Protegida>
          }
        />
        <Route
          path="/ocupacion/:dia/:hora"
          element={
            <Protegida solo="ADMIN">
              <OcupacionDetallePage />
            </Protegida>
          }
        />
        <Route
          path="/mensualidades"
          element={
            <Protegida solo="ADMIN">
              <SubscriptionsPage />
            </Protegida>
          }
        />
        <Route path="/configuracion" element={<SettingsPage />} />
        <Route
          path="/reportes"
          element={
            <Protegida solo="SUPERADMIN">
              <ReportsPage />
            </Protegida>
          }
        />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  )
}

function publicRoutes(): JSX.Element {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/recuperar" element={<RecoveryPage />} />
      <Route path="*" element={<LoginPage />} />
    </Routes>
  )
}

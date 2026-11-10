/* Resumen del módulo de plataforma: KPIs generales + últimos clientes. */

import { useEffect, useState } from 'react'
import { plataforma, type Resumen, type Tenant } from '../../api/platform'
import { Aviso, MensajeApi } from '../../components/ui/Aviso'

export function PlatformSummaryPage(): JSX.Element {
  const [resumen, setResumen] = useState<Resumen | null>(null)
  const [clientes, setClientes] = useState<Tenant[]>([])
  const [error, setError] = useState<string | null>(null)
  const [cargando, setCargando] = useState(true)

  useEffect(() => {
    let vive = true
    Promise.all([plataforma.resumen(), plataforma.listarTenants()])
      .then(([r, lista]) => {
        if (!vive) return
        setResumen(r)
        setClientes([...lista].sort((a, b) => b.created_at.localeCompare(a.created_at)).slice(0, 5))
      })
      .catch((e) => {
        if (vive) setError(MensajeApi(e) || 'No se pudo cargar el resumen.')
      })
      .finally(() => {
        if (vive) setCargando(false)
      })
    return () => { vive = false }
  }, [])

  const kpis: Array<{ cifra: string; etiqueta: string }> = [
    { cifra: resumen ? String(resumen.clientes) : '—', etiqueta: 'Clientes' },
    { cifra: resumen ? String(resumen.activos) : '—', etiqueta: 'Activos' },
    { cifra: resumen ? String(resumen.suspendidos) : '—', etiqueta: 'Suspendidos' },
    { cifra: resumen ? String(resumen.sedes) : '—', etiqueta: 'Sedes' },
    { cifra: resumen ? String(resumen.usuarios) : '—', etiqueta: 'Usuarios' },
  ]

  return (
    <>
      <h1 className="pf-titulo">Resumen</h1>
      <p className="pf-subtitulo">Estado general de la plataforma Parkium.</p>

      <Aviso variante="error">{error}</Aviso>

      {cargando && <p role="status">Cargando resumen…</p>}

      <div className="pf-kpis">
        {kpis.map((k) => (
          <div className="pf-kpi" key={k.etiqueta}>
            <div className="cifra">{k.cifra}</div>
            <div className="etiqueta">{k.etiqueta}</div>
          </div>
        ))}
      </div>

      <div className="pf-tarjeta">
        <h2 style={{ marginTop: 0, fontSize: 16 }}>Últimos clientes</h2>
        {!cargando && clientes.length === 0 && !error && (
          <p role="status" style={{ color: 'var(--pf-muted, #8b88a0)' }}>
            Aún no hay clientes. Crea el primero en «Clientes».
          </p>
        )}
        <ul style={{ margin: 0, padding: 0, listStyle: 'none', display: 'grid', gap: 10 }}>
          {clientes.map((t) => (
            <li key={t.id} style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
              <span style={{ fontWeight: 600 }}>{t.name}</span>
              <span className="mono" style={{ color: '#a78bfa', fontSize: 13 }}>{t.nit}</span>
              <span className={`pf-estado ${t.status === 'ACTIVE' ? 'active' : 'suspended'}`}>
                {t.status === 'ACTIVE' ? 'Activo' : 'Suspendido'}
              </span>
              <span style={{ color: '#8b88a0', fontSize: 12.5 }}>
                Plan {t.plan} · límites: {t.sedes ?? 0}/{t.max_sites} sedes · {t.usuarios ?? 0}/{t.max_users} usuarios
              </span>
            </li>
          ))}
        </ul>
      </div>
    </>
  )
}

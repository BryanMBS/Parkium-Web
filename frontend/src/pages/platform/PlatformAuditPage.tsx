/* Auditoría de la plataforma: tabla paginada de audit_logs con filtros
 * desde/hasta/acción/tenant. Fechas formateadas en es-CO. */

import { useCallback, useEffect, useState } from 'react'
import { plataforma, type EventoAuditoria, type Tenant } from '../../api/platform'
import { Aviso, MensajeApi } from '../../components/ui/Aviso'

const FRMT_FECHA = new Intl.DateTimeFormat('es-CO', { dateStyle: 'medium', timeStyle: 'short' })

export function PlatformAuditPage(): JSX.Element {
  const [eventos, setEventos] = useState<EventoAuditoria[]>([])
  const [tenants, setTenants] = useState<Tenant[]>([])
  const [pagina, setPagina] = useState(1)
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // filtros (aplicados al pulsar «Filtrar»)
  const [desde, setDesde] = useState('')
  const [hasta, setHasta] = useState('')
  const [accion, setAccion] = useState('')
  const [tenantId, setTenantId] = useState('')

  const porPagina = 25

  const cargar = useCallback((pag: number) => {
    setCargando(true)
    setError(null)
    plataforma
      .auditar({
        pagina: pag,
        por_pagina: porPagina,
        desde: desde || undefined,
        hasta: hasta || undefined,
        accion: accion || undefined,
        tenant_id: tenantId ? Number(tenantId) : undefined,
      })
      .then((r) => setEventos(r.eventos))
      .catch((e) => setError(MensajeApi(e) || 'No se pudo cargar la auditoría.'))
      .finally(() => setCargando(false))
  }, [desde, hasta, accion, tenantId])

  useEffect(() => { cargar(1) }, []) // carga inicial con filtros vacíos

  useEffect(() => {
    plataforma.listarTenants().then(setTenants).catch(() => {}) // sólo para el filtro
  }, [])

  function filtrar(e: React.FormEvent): void {
    e.preventDefault()
    setPagina(1)
    cargar(1)
  }

  function mover(d: number): void {
    const nueva = Math.max(1, pagina + d)
    setPagina(nueva)
    cargar(nueva)
  }

  return (
    <>
      <h1 className="pf-titulo">Auditoría</h1>
      <p className="pf-subtitulo">Eventos de creación, cambio y suspensión de clientes.</p>

      <Aviso variante="error">{error}</Aviso>

      <div className="pf-barra">
        <form onSubmit={filtrar} style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'flex-end' }}>
          <div className="campo">
            <label htmlFor="pf-desde">Desde</label>
            <input id="pf-desde" type="date" value={desde} onChange={(e) => setDesde(e.target.value)} />
          </div>
          <div className="campo">
            <label htmlFor="pf-hasta">Hasta</label>
            <input id="pf-hasta" type="date" value={hasta} onChange={(e) => setHasta(e.target.value)} />
          </div>
          <div className="campo">
            <label htmlFor="pf-acc">Acción</label>
            <input
              id="pf-acc"
              value={accion}
              onChange={(e) => setAccion(e.target.value)}
              placeholder="TENANT_…"
              maxLength={60}
            />
          </div>
          <div className="campo">
            <label htmlFor="pf-tenant">Cliente</label>
            <select id="pf-tenant" value={tenantId} onChange={(e) => setTenantId(e.target.value)}>
              <option value="">Todos</option>
              {tenants.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
            </select>
          </div>
          <button type="submit" className="pf-btn pf-btn-suave" disabled={cargando}>
            Filtrar
          </button>
        </form>
      </div>

      {cargando && <p role="status">Cargando eventos…</p>}
      {!cargando && eventos.length === 0 && !error && (
        <p role="status" style={{ color: '#8b88a0' }}>Sin eventos para estos filtros.</p>
      )}

      {eventos.length > 0 && (
        <div className="pf-tarjeta" style={{ overflowX: 'auto' }}>
          <table className="tabla">
            <thead>
              <tr>
                <th scope="col">Fecha</th>
                <th scope="col">Acción</th>
                <th scope="col">Entidad</th>
                <th scope="col">Cliente</th>
                <th scope="col">Actor</th>
                <th scope="col">IP</th>
                <th scope="col">Detalles</th>
              </tr>
            </thead>
            <tbody>
              {eventos.map((ev) => (
                <tr key={ev.id}>
                  <td style={{ whiteSpace: 'nowrap' }}>{FRMT_FECHA.format(new Date(ev.occurred_at))}</td>
                  <td className="mono">{ev.action}</td>
                  <td>
                    {ev.entity_type ?? '—'}
                    {ev.entity_id != null ? ` #${ev.entity_id}` : ''}
                  </td>
                  <td>{ev.tenant ?? '—'}</td>
                  <td>{ev.actor ?? '—'}</td>
                  <td className="mono">{ev.ip_address ?? '—'}</td>
                  <td className="mono" style={{ maxWidth: 260, fontSize: 12 }}>
                    {ev.after_data ?? ev.before_data ?? '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="pf-paginacion">
        <button className="pf-btn pf-btn-suave pf-btn-compacto" onClick={() => mover(-1)} disabled={pagina === 1 || cargando}>
          ← Anterior
        </button>
        <span style={{ color: '#8b88a0', fontSize: 13 }}>Página {pagina}</span>
        <button
          className="pf-btn pf-btn-suave pf-btn-compacto"
          onClick={() => mover(1)}
          disabled={cargando || eventos.length < porPagina}
        >
          Siguiente →
        </button>
      </div>
    </>
  )
}

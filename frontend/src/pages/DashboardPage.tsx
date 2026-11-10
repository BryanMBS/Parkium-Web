import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { parking } from '../api/parking'
import { historico, reloj, type EstadoReloj } from '../api/historico'
import { OccupancyChart } from '../components/charts/OccupancyChart'
import { Aviso, MensajeApi } from '../components/ui/Aviso'
import { dinero } from '../lib/formato'
import { etiquetaDe, TIPOS_VEHICULO } from '../theme/catalogos'
import { isoDe } from '../components/DatePicker/DatePicker'

/** Dashboard: ocupación, recaudo de hoy, estado del reloj con «Verificar hora»
 * y el gráfico de ocupación del día con detalle por hora (docs/04 §4.5). */
export function DashboardPage(): JSX.Element {
  const queryClient = useQueryClient()
  const navegar = useNavigate()
  const [errorReloj, setErrorReloj] = useState<string | null>(null)
  const [fecha, setFecha] = useState(isoDe(new Date()))

  const dash = useQuery({ queryKey: ['dashboard'], queryFn: () => parking.dashboard() })
  const hourly = useQuery({
    queryKey: ['hourly', fecha],
    queryFn: ({ signal }) => historico.ocupacionPorHora(fecha, signal),
  })

  const relojQ = useQuery({ queryKey: ['reloj'], queryFn: () => reloj.estado(), refetchInterval: 60_000 })

  const verificar = useMutation({
    mutationFn: () => reloj.verificar(true),
    onSuccess: (estado: EstadoReloj) => {
      setErrorReloj(null)
      queryClient.setQueryData(['reloj'], estado)
    },
    onError: (e) => setErrorReloj(MensajeApi(e)),
  })

  if (dash.isError) {
    return <Aviso variante="error">{MensajeApi(dash.error)}</Aviso>
  }

  const d = dash.data

  return (
    <>
      <div className="titulo">
        <h1>Dashboard</h1>
      </div>

      <div className="rejilla rejilla-4">
        <div className="tarjeta metrica">
          <div className="etiqueta">Ocupados ahora</div>
          <div className="cifra">
            {d ? d.ocupacion.ocupados : '—'} <span style={{ fontSize: 14, color: 'var(--color-muted)' }}>/ {d?.ocupacion.capacidad_total ?? '—'}</span>
          </div>
          {d && (
            <div style={{ fontSize: 12, color: 'var(--color-muted)' }}>
              {Object.entries(d.ocupacion.por_tipo)
                .map(([c, n]) => `${etiquetaDe(TIPOS_VEHICULO, c)}: ${n}`)
                .join(' · ') || 'Sin vehículos dentro'}
            </div>
          )}
        </div>
        <div className="tarjeta metrica">
          <div className="etiqueta">Disponibles</div>
          <div className="cifra">{d?.ocupacion.disponibles ?? '—'}</div>
        </div>
        <div className="tarjeta metrica">
          <div className="etiqueta">Recaudo de hoy</div>
          <div className="cifra importe">{d ? dinero(d.hoy.ingresos) : '—'}</div>
          <div style={{ fontSize: 12, color: 'var(--color-muted)' }}>Salidas cobradas: {d?.hoy.salidas_cobradas ?? '—'}</div>
        </div>
        <div className="tarjeta metrica">
          <div className="etiqueta">Mensualidades de hoy</div>
          <div className="cifra importe">{d ? dinero(d.hoy.mensualidades) : '—'}</div>
        </div>
      </div>

      <div className="rejilla rejilla-dashboard">
        <div className="tarjeta">
          <h2>Ocupación por hora {fecha !== hoy() ? `· ${fecha}` : ''}</h2>
          {hourly.isLoading && <Cargando />}
          {hourly.isError && <Aviso variante="error">{MensajeApi(hourly.error)}</Aviso>}
          {hourly.data && (
            <div style={{ position: 'relative' }}>
              <OccupancyChart capacidadTotal={hourly.data.capacidad_total} puntos={hourly.data.puntos} />
              <div style={{ display: 'flex', gap: 8, alignItems: 'flex-end', marginTop: 8, flexWrap: 'wrap' }}>
                <input
                  type="date"
                  value={fecha}
                  onChange={(e) => e.target.value && setFecha(e.target.value)}
                  aria-label="Fecha del gráfico"
                  style={{
                    background: 'var(--color-field-bg)', border: '1px solid var(--color-field-border)',
                    borderRadius: 10, padding: '8px 10px', color: 'var(--color-text)', fontFamily: 'var(--font-mono)',
                  }}
                />
              </div>
            </div>
          )}
          {hourly.data?.puntos && hourly.data.maximo > 0 && (
            <DetalleHora fecha={fecha} puntos={hourly.data.puntos} nav={navegar} />
          )}
        </div>

        <div className="tarjeta">
          <h2>Estado del reloj</h2>
          {relojQ.isLoading && <Cargando />}
          {relojQ.data && (
            <>
              <Aviso variante={relojQ.data.ok ? 'ok' : 'error'}>{relojQ.data.mensaje}</Aviso>
              <dl style={{ fontSize: 13, display: 'grid', gridTemplateColumns: 'auto 1fr', gap: '4px 12px' }}>
                <dt style={{ color: 'var(--color-muted)' }}>Fuente</dt>
                <dd style={{ margin: 0 }}>{etiquetaFuente(relojQ.data.fuente)}</dd>
                <dt style={{ color: 'var(--color-muted)' }}>Hora del sistema</dt>
                <dd style={{ margin: 0, fontFamily: 'var(--font-mono)' }}>{relojQ.data.hora_sistema}</dd>
                <dt style={{ color: 'var(--color-muted)' }}>Referencia</dt>
                <dd style={{ margin: 0, fontFamily: 'var(--font-mono)' }}>{relojQ.data.hora_referencia}</dd>
                <dt style={{ color: 'var(--color-muted)' }}>Deriva</dt>
                <dd style={{ margin: 0, fontFamily: 'var(--font-mono)', fontWeight: 700 }}>
                  {relojQ.data.deriva_texto}
                </dd>
                {relojQ.data.verificaciones_sospechosas > 0 && (
                  <>
                    <dt style={{ color: 'var(--color-muted)' }}>Sospechas</dt>
                    <dd className="sospechas" style={{ margin: 0, fontWeight: 700 }}>
                      {relojQ.data.verificaciones_sospechosas}
                    </dd>
                  </>
                )}
              </dl>
              <button
                className="btn btn-primario"
                style={{ marginTop: 12 }}
                onClick={() => verificar.mutate()}
                disabled={verificar.isPending}
              >
                {verificar.isPending ? 'Verificando…' : 'Verificar hora'}
              </button>
              <Aviso variante="error">{errorReloj}</Aviso>
            </>
          )}
        </div>
      </div>
    </>
  )
}

/** Selector de hora para el detalle «qué había en esta hora» (docs/04 §4.5). */
function DetalleHora({
  fecha,
  puntos,
  nav,
}: {
  fecha: string
  puntos: Array<{ hora: number; ocupados: number }>
  nav: (ruta: string) => void
}): JSX.Element {
  const [hora, setHora] = useState(new Date().getHours())
  const ocupados = puntos[hora]?.ocupados ?? 0
  return (
    <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginTop: 10, flexWrap: 'wrap' }}>
      <label htmlFor="sel-hora" style={{ fontSize: 13 }}>
        Detalle de la hora
      </label>
      <select
        id="sel-hora"
        value={hora}
        onChange={(e) => setHora(Number(e.target.value))}
        style={{
          background: 'var(--color-field-bg)', border: '1px solid var(--color-field-border)',
          borderRadius: 10, padding: '8px 10px', color: 'var(--color-text)',
        }}
      >
        {Array.from({ length: 24 }, (_, h) => (
          <option key={h} value={h}>
            {String(h).padStart(2, '0')}:00 · {puntos[h]?.ocupados ?? 0} veh.
          </option>
        ))}
      </select>
      <span style={{ color: 'var(--color-muted)', fontSize: 12 }}>{ocupados} en esa franja</span>
      <button className="btn btn-suave btn-compacto" onClick={() => nav(`/ocupacion/${fecha}/${hora}`)}>
        Ver vehículos de la hora
      </button>
    </div>
  )
}

function etiquetaFuente(f: string): string {
  const mapa: Record<string, string> = {
    SISTEMA: 'Ancla del servidor',
    FUENTE_EXTERNA: 'Fuente externa (HTTP Date)',
    ANCLA: 'Ancla del servidor',
  }
  return mapa[f] ?? f
}

function hoy(): string {
  return isoDe(new Date())
}

function Cargando(): JSX.Element {
  return <div style={{ color: 'var(--color-muted)' }}>Cargando…</div>
}

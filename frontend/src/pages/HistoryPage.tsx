import { useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { historico, comprobantes, type ResultadoHistorico } from '../api/historico'
import { Aviso, MensajeApi } from '../components/ui/Aviso'
import { DatePicker, isoDe, leerFecha } from '../components/DatePicker/DatePicker'
import { dinero } from '../lib/formato'
import { ESTADOS_ESTADIA, TIPOS_VEHICULO } from '../theme/catalogos'

const ESTADOS = [
  { codigo: '', etiqueta: 'Todos los estados' },
  { codigo: 'ACTIVE', etiqueta: 'Activas' },
  { codigo: 'PENDING_PAYMENT', etiqueta: 'Pendiente de pago' },
  { codigo: 'PAID', etiqueta: 'Cobradas' },
  { codigo: 'CANCELLED', etiqueta: 'Anuladas' },
]

/** Histórico (docs/04 §4.5): búsqueda por placa parcial y rango civil local.
 * Sin rango, el backend limita la búsqueda al día de hoy. */
export function HistoryPage(): JSX.Element {
  const hoy = isoDe(new Date())
  const [placa, setPlaca] = useState('')
  const [desde, setDesde] = useState(hoy)
  const [hasta, setHasta] = useState(hoy)
  const [estado, setEstado] = useState('')
  const [tipo, setTipo] = useState('')
  const [avisoReimp, setAvisoReimp] = useState<string | null>(null)

  /** desde > hasta: el backend responde 400 validación; se avisa antes de enviar */
  const d = leerFecha(desde)
  const h = leerFecha(hasta)
  const rangoInvalido = d != null && h != null && d > h
  /** fix UX-S015: texto presente pero no parsea → aviso y no consulta */
  const fechaInvalida = (desde.trim() !== '' && d == null) || (hasta.trim() !== '' && h == null)
  const consulta = useQuery({
    queryKey: ['historico', { placa, desde: d, hasta: h, estado, tipo }],
    queryFn: ({ signal }) =>
      historico.buscar(
        {
          placa: placa.trim() || undefined,
          desde: d ?? undefined,
          hasta: h ?? undefined,
          estado: estado || undefined,
          tipo_vehiculo: tipo || undefined,
        },
        signal,
      ),
    enabled: !rangoInvalido && !fechaInvalida,
  })

  // fix UX-S024: paginación client-side (15 por página), patrón de Plataforma
  const POR_PAGINA = 15
  const [pagina, setPagina] = useState(1)
  const resultados = consulta.data?.resultados ?? []
  const totalPaginas = Math.max(1, Math.ceil(resultados.length / POR_PAGINA))
  const paginaActual = Math.min(pagina, totalPaginas)
  const visibles = resultados.slice((paginaActual - 1) * POR_PAGINA, paginaActual * POR_PAGINA)

  const reimprimir = useMutation({
    mutationFn: ({ id, tipo: t }: { id: number; tipo: string }) => comprobantes.reimprimir(id, t),
    onSuccess: (_r, v) => setAvisoReimp(`Reimpresión registrada del comprobante ${v.id} (queda identificable por su contador).`),
    onError: (e) => setAvisoReimp(`No se pudo reimprimir: ${MensajeApi(e)}`),
  })

  return (
    <>
      <div className="titulo">
        <h1>Histórico</h1>
      </div>

      <div className="tarjeta" style={{ marginBottom: 14 }}>
        <div className="fila">
          <div className="campo">
            <label htmlFor="hi-placa">Placa (parcial)</label>
            <input id="hi-placa" value={placa} onChange={(e) => setPlaca(e.target.value.toUpperCase())} placeholder="ABC…" />
          </div>
          <div className="campo">
            <label htmlFor="hi-desde">Desde</label>
            <DatePicker id="hi-desde" etiqueta="Desde" valor={desde} alCambiar={setDesde} />
          </div>
          <div className="campo">
            <label htmlFor="hi-hasta">Hasta</label>
            <DatePicker id="hi-hasta" etiqueta="Hasta" valor={hasta} alCambiar={setHasta} />
          </div>
          <div className="campo">
            <label htmlFor="hi-estado">Estado</label>
            <select id="hi-estado" value={estado} onChange={(e) => setEstado(e.target.value)}>
              {ESTADOS.map((e) => (
                <option key={e.codigo} value={e.codigo}>
                  {e.etiqueta}
                </option>
              ))}
            </select>
          </div>
          <div className="campo">
            <label htmlFor="hi-tipo">Tipo</label>
            <select id="hi-tipo" value={tipo} onChange={(e) => setTipo(e.target.value)}>
              <option value="">Todos</option>
              {TIPOS_VEHICULO.map((t) => (
                <option key={t.codigo} value={t.codigo}>
                  {t.etiqueta}
                </option>
              ))}
            </select>
          </div>
        </div>
        {rangoInvalido && (
          <Aviso variante="aviso">El rango es inválido: «desde» es mayor que «hasta».</Aviso>
        )}
        {fechaInvalida && (
          <Aviso variante="aviso">Hay una fecha no válida: corrígela (DD/MM/AAAA o AAAA-MM-DD).</Aviso>
        )}
        <Aviso variante="ok">{avisoReimp}</Aviso>
      </div>

      {consulta.isLoading && <p className="cargando">Cargando histórico</p>}
      {consulta.isError && <Aviso variante="error">{MensajeApi(consulta.error)}</Aviso>}
      {consulta.data && (
        <>
          <p style={{ color: 'var(--color-muted)' }}>
            {consulta.data.total} estadía{consulta.data.total === 1 ? '' : 's'} encontradas
            {consulta.data.total > consulta.data.resultados.length && ` (mostrando ${consulta.data.resultados.length})`}
          </p>
          <div className="contenedor-tabla">
            <table className="tabla">
              <thead>
                <tr>
                  <th scope="col">Placa</th>
                  <th scope="col">Tipo</th>
                  <th scope="col">Ingreso</th>
                  <th scope="col">Salida</th>
                  <th scope="col">Duración</th>
                  <th scope="col">Estado</th>
                  <th scope="col" style={{ textAlign: 'right' }}>Importe</th>
                  <th scope="col">Comprobantes</th>
                </tr>
              </thead>
              <tbody>
                {visibles.map((r) => (
                  <FilaResultado
                    key={r.estadia_id}
                    r={r}
                    onReimp={(v) => reimprimir.mutate(v)}
                  />
                ))}
                {consulta.data.resultados.length === 0 && (
                  <tr>
                    <td colSpan={8} style={{ textAlign: 'center', color: 'var(--color-muted)' }}>
                      Sin resultados en el rango y filtros indicados.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
          {resultados.length > POR_PAGINA && (
            <div style={{ display: 'flex', gap: 10, alignItems: 'center', marginTop: 10 }}>
              <button
                className="btn btn-suave btn-compacto"
                onClick={() => setPagina((p) => Math.max(1, p - 1))}
                disabled={paginaActual === 1}
              >
                ‹ Anterior
              </button>
              <span style={{ fontSize: 13, color: 'var(--color-muted)' }}>
                Página {paginaActual} de {totalPaginas}
              </span>
              <button
                className="btn btn-suave btn-compacto"
                onClick={() => setPagina((p) => Math.min(totalPaginas, p + 1))}
                disabled={paginaActual === totalPaginas}
              >
                Siguiente ›
              </button>
            </div>
          )}
        </>
      )}
    </>
  )
}

function FilaResultado({
  r,
  onReimp,
}: {
  r: ResultadoHistorico
  onReimp: (v: { id: number; tipo: string }) => void
}): JSX.Element {
  const duracion =
    r.duracion_minutos == null ? '—' : `${Math.floor(r.duracion_minutos / 60)} h ${r.duracion_minutos % 60} min`
  return (
    <tr>
      <td style={{ fontFamily: 'var(--font-mono)', fontWeight: 700 }}>{r.placa}</td>
      <td>{r.tipo_vehiculo}</td>
      <td>
        {r.fecha_ingreso} · {r.hora_ingreso}
      </td>
      <td>{r.fecha_salida ? `${r.fecha_salida} · ${r.hora_salida}` : '—'}</td>
      <td>{duracion}</td>
      <td>
        <span className={`pill ${r.estado === 'PAID' ? 'pill-verde' : r.estado === 'ACTIVE' ? 'pill-naranja' : 'pill-gris'}`}>
          {ESTADOS_ESTADIA[r.estado] ?? r.estado}
        </span>
      </td>
      <td style={{ textAlign: 'right' }} className="importe">
        {r.monto ? dinero(r.monto) : '—'}
      </td>
      <td>
        {r.recibo_ingreso?.puede_reimprimir && (
          <button
            className="btn btn-compacto btn-suave"
            onClick={() => onReimp({ id: r.recibo_ingreso!.id, tipo: 'ENTRY' })}
            title={`Reimprimir factura de ingreso #${r.recibo_ingreso.numero}`}
          >
            ingreso #{r.recibo_ingreso.numero}
          </button>
        )}{' '}
        {r.recibo_salida?.puede_reimprimir && (
          <button
            className="btn btn-compacto btn-suave"
            onClick={() => onReimp({ id: r.recibo_salida!.id, tipo: 'EXIT' })}
            title={`Reimprimir recibo de salida #${r.recibo_salida.numero}`}
          >
            salida #{r.recibo_salida.numero}
          </button>
        )}
      </td>
    </tr>
  )
}

import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { caja, type TurnoCaja } from '../api/cash'
import { parking, type CobroResult, type Cotizacion, type EstadiaActiva } from '../api/parking'
import { Aviso, MensajeApi } from '../components/ui/Aviso'
import { Modal } from '../components/ui/Modal'
import { aImporte, dinero } from '../lib/formato'
import { ESTADOS_ESTADIA, METODOS_PAGO, TIPOS_VEHICULO } from '../theme/catalogos'
import { useAuth } from '../hooks/useAuth'

/** Operación (docs/04 §4.3): registrar entrada → cotizar → cobrar,
 * con cambio en vivo para efectivo y turnos de caja. */
export function OperationsPage(): JSX.Element {
  const [placa, setPlaca] = useState('')
  const placaHi = placa.trim().toUpperCase()

  const activa = useQuery<EstadiaActiva, Error>({
    queryKey: ['estadia', placaHi],
    enabled: /^[A-Z0-9]{3,8}$/.test(placaHi),
    retry: false,
    queryFn: async () => {
      try {
        return await parking.estadíaActiva(placaHi)
      } catch (e) {
        if ((e as { estado?: number }).estado === 404) throw new Error('sin-estadia')
        throw e
      }
    },
  })

  const sinEstadia = activa.error?.message === 'sin-estadia'

  const [error, setError] = useState<string | null>(null)
  const [resultado, setResultado] = useState<CobroResult | null>(null)
  const queryClient = useQueryClient()
  // fix UX-S007: bloqueo anti-doble envío en «Registrar entrada»
  const [enviandoEntrada, setEnviandoEntrada] = useState(false)

  async function crearEntrada(metodo: string): Promise<void> {
    setError(null)
    setEnviandoEntrada(true)
    try {
      await parking.entrada(placaHi, metodo)
      await queryClient.invalidateQueries({ queryKey: ['estadia', placaHi] })
      await queryClient.invalidateQueries({ queryKey: ['dashboard'] })
    } catch (e) {
      setError(MensajeApi(e))
    } finally {
      setEnviandoEntrada(false)
    }
  }

  const coti = useQuery<Cotizacion, Error>({
    queryKey: ['cotizacion', placaHi],
    enabled: !!activa.data && estadoPermitido(activa.data.estado),
    refetchInterval: 30_000, // la cotización envejece: se refresca antes de cobrar
    queryFn: () => parking.cotizar(placaHi),
  })

  return (
    <>
      <div className="titulo">
        <h1>Operación</h1>
      </div>

      <div className="rejilla rejilla-2">
        <div className="tarjeta">
          <h2>Entrada / salida de un vehículo</h2>
          <div className="campo">
            <label htmlFor="op-placa">Placa</label>
            <input
              id="op-placa"
              value={placa}
              autoCapitalize="characters"
              autoCorrect="off"
              spellCheck={false}
              onChange={(e) => {
                setPlaca(e.target.value.toUpperCase())
                setResultado(null)
                setError(null)
              }}
              placeholder="ABC123"
              autoFocus
            />
            <span className="ayuda">Se normaliza a mayúsculas sin espacios (3 a 8 caracteres).</span>
          </div>

          {activa.isFetching && <p style={{ color: 'var(--color-muted)' }}>Consultando…</p>}
          <Aviso variante="aviso">{sinEstadia && placaHi ? `No hay estadía activa de ${placaHi}. Registra la entrada.` : null}</Aviso>
          <Aviso variante="error">{error}</Aviso>

          {activa.data && (
            <p style={{ marginTop: 4, fontSize: 13 }}>
              Estadía <strong>{activa.data.estadia_id}</strong> · ingreso {activa.data.ingreso_local} · estado{' '}
              <strong>{ESTADOS_ESTADIA[activa.data.estado] ?? activa.data.estado}</strong>
            </p>
          )}

          {sinEstadia && (
            <CrearEntrada placa={placaHi} enviando={enviandoEntrada} onOk={(t) => void crearEntrada(t)} />
          )}

          {coti.data && resultado == null && (
            <Cotizador
              cotizacion={coti.data}
              placa={placaHi}
              alCobrar={(r) => {
                setResultado(r)
                void queryClient.invalidateQueries({ queryKey: ['estadia', placaHi] })
                void queryClient.invalidateQueries({ queryKey: ['dashboard'] })
                void queryClient.invalidateQueries({ queryKey: ['cotizacion', placaHi] })
              }}
              alError={setError}
            />
          )}

          {resultado && (
            <ReciboCobro
              r={resultado}
              alSeguir={() => {
                setResultado(null)
                setPlaca('')
              }}
            />
          )}
        </div>

        <PanelCaja />
      </div>
    </>
  )
}

/** Sólo ACTIVE/PENDING_PAYMENT admiten movimiento; una cobrada ya se fue. */
function estadoPermitido(estado: string): boolean {
  return estado === 'ACTIVE' || estado === 'PENDING_PAYMENT'
}

function CrearEntrada({ placa, enviando, onOk }: { placa: string; enviando: boolean; onOk: (tipo: string) => void }): JSX.Element {
  const [tipo, setTipo] = useState('CAR')
  return (
    <div style={{ marginTop: 10 }}>
      <div className="campo">
        <label htmlFor="op-tipo">Tipo de vehículo</label>
        <select id="op-tipo" value={tipo} onChange={(e) => setTipo(e.target.value)}>
          {TIPOS_VEHICULO.map((t) => (
            <option key={t.codigo} value={t.codigo}>
              {t.etiqueta}
            </option>
          ))}
        </select>
      </div>
      <button className="btn btn-primario" onClick={() => onOk(tipo)} disabled={enviando}>
        ↦ {enviando ? 'Registrando…' : `Registrar entrada de ${placa || 'la placa'}`}
      </button>
    </div>
  )
}

/** Cotización + forma de pago + efectivo del operador con cambio en vivo
 * (anunciado por aria-live, docs/06 §6.11). */
function Cotizador({
  cotizacion,
  placa,
  alCobrar,
  alError,
}: {
  cotizacion: Cotizacion
  placa: string
  alCobrar: (r: CobroResult) => void
  alError: (msg: string) => void
}): JSX.Element {
  const [metodo, setMetodo] = useState('CASH')
  const [recibido, setRecibido ] = useState('')
  const [referencia, setReferencia] = useState('')
  const [enCurso, setEnCurso] = useState(false)
  const [falta, setFalta] = useState<string | null>(null)

  const monto = cotizacion.monto_a_cobrar
  const cambioEnVivo = useMemo(() => {
    if (metodo !== 'CASH') return null
    const r = aImporte(recibido)
    if (r == null) return null
    const delta = Number(r) - Number(monto)
    return String(delta)
  }, [metodo, recibido, monto])

  function cobrar(): void {
    setEnCurso(true)
    setFalta(null)
    const recibidoFinal =
      metodo === 'CASH' ? aImporte(recibido) : null
    if (metodo === 'CASH' && recibidoFinal == null) {
      setFalta('Escribe el efectivo recibido.')
      setEnCurso(false)
      return
    }
    parking
      .cobrar(placa, metodo, monto, recibidoFinal, referencia.trim() || null)
      .then(alCobrar)
      .catch((e) => alError(MensajeApi(e)))
      .finally(() => setEnCurso(false))
  }

  const esCobroCero = Number(monto) <= 0

  return (
    <div style={{ marginTop: 14, borderTop: '1px solid var(--color-border)', paddingTop: 12 }}>
      <h3>Cobro</h3>
      <div aria-live="polite" style={{ margin: '8px 0' }}>
        Minutos: <strong>{cotizacion.minutos}</strong> · esquema{' '}
        <strong>{cotizacion.esquema}</strong>
        {cotizacion.mensualidad_vigente && ' · ¡placa con mensualidad vigente!'}
        <div className="cifra-cobro importe">{dinero(monto)}</div>
        {cambioEnVivo !== null && Number(recibido.replace(/[.,]/g, '') || 0) > 0 && (
          <div style={{ fontSize: 14 }}>
            Cambio: <strong className={`cifra-cambio importe`}>{dinero(cambioEnVivo)}</strong>
            {Number(cambioEnVivo) < 0 && (
              <span style={{ color: 'var(--color-danger)' }}>
                {' '}
                (¡faltan {dinero(String(-Number(cambioEnVivo)))}!)
              </span>
            )}
          </div>
        )}
      </div>

      {cotizacion.mensualidad_vigente && esCobroCero && (
        <Aviso variante="aviso">El cobro es $0: la mensualidad cubre la estadía.</Aviso>
      )}

      <div className="fila">
        <div className="campo" style={{ margin: 0 }}>
          <label htmlFor="op-metodo">Forma de pago</label>
          <select id="op-metodo" value={metodo} onChange={(e) => setMetodo(e.target.value)}>
            {METODOS_PAGO.map((m) => (
              <option key={m.codigo} value={m.codigo}>
                {m.etiqueta}
              </option>
            ))}
          </select>
        </div>
        {metodo === 'CASH' && (
          <div className="campo" style={{ margin: 0 }}>
            <label htmlFor="op-recibido">Efectivo recibido</label>
            <input
              id="op-recibido"
              inputMode="decimal"
              value={recibido}
              onChange={(e) => {
                setRecibido(e.target.value)
                setFalta(null)
              }}
              placeholder="0,00"
            />
            <Aviso variante="error" anunciar="assertive">
              {falta}
            </Aviso>
          </div>
        )}
        {metodo !== 'CASH' && (
          <div className="campo" style={{ margin: 0 }}>
            <label htmlFor="op-ref">Referencia / aprobación</label>
            <input
              id="op-ref"
              value={referencia}
              onChange={(e) => setReferencia(e.target.value)}
              placeholder="Nº de autorización"
            />
          </div>
        )}
        <button className="btn btn-exito" onClick={cobrar} disabled={enCurso || !!falta}>
          {enCurso ? 'Cobrando…' : '$ Cobrar'}
        </button>
      </div>
    </div>
  )
}

function ReciboCobro({ r, alSeguir }: { r: CobroResult; alSeguir: () => void }): JSX.Element {
  return (
    <div style={{ marginTop: 14, borderTop: '1px solid var(--color-border)', paddingTop: 12 }}>
      <h3>Cobro registrado</h3>
      <Aviso variante="ok">
        {r.idempotente
          ? 'La misma Idempotency-Key: se devolvió el pago ya existente (sin duplicar).'
          : 'Cobro transaccional confirmado: pago, estadía cerrada y comprobante emitados juntos.'}
      </Aviso>
      <ul style={{ lineHeight: 1.7 }}>
        <li>Pago <strong>{r.pago_id}</strong> · monto <span className="importe">{dinero(r.monto)}</span></li>
        {r.cambio != null && (
          <li>
            Efectivo <span className="importe">{dinero(r.efectivo_recibido ?? '0')}</span> · cambio{' '}
            <strong className="importe">{dinero(r.cambio)}</strong>
          </li>
        )}
        <li>
          Recibo <strong>{r.recibo.numero ?? r.recibo.receipt_number}</strong> ({r.recibo.tipo})
          {r.recibo.token && (
            <>
              {' '}
              · <a href={`/r/${r.recibo.token}`} target="_blank" rel="noreferrer">
                Ver comprobante (imprimible)
              </a>
            </>
          )}
        </li>
      </ul>
      <button className="btn btn-primario" onClick={alSeguir}>
        Siguiente vehículo
      </button>
    </div>
  )
}

/** Panel de caja por turno (docs/04 §4.7): abrir turno, esperado en vivo
 * y cierre con conteo y diferencia. */
function PanelCaja(): JSX.Element {
  const { usuario } = useAuth()
  const queryClient = useQueryClient()
  const [error, setError] = useState<string | null>(null)
  const [aviso, setAviso] = useState<string | null>(null)
  const [abiertoDialogoAbrir, setDialogoAbrir] = useState(false)
  const [abiertoDialogoCerrar, setDialogoCerrar] = useState(false)
  const [montoInicial, setMontoInicial] = useState('')
  const [contado, setContado] = useState('')

  const turnoQ = useQuery({
    queryKey: ['turno-caja', usuario?.id],
    queryFn: () => caja.listar(true),
    refetchInterval: 30_000,
  })

  const miTurno: TurnoCaja | undefined = (turnoQ.data ?? []).find(
    (t) => t.user_id === usuario?.id && t.status === 'OPEN',
  )
  const miTurnoId = miTurno?.id

  const esperadoQ = useQuery({
    queryKey: ['caja-esperado', miTurnoId],
    enabled: miTurnoId != null,
    queryFn: () => caja.esperado(miTurnoId!),
    refetchInterval: 30_000,
  })

  const abrir = useMutation({
    mutationFn: (monto: string) => caja.abrir(monto),
    onSuccess: () => {
      setDialogoAbrir(false)
      setMontoInicial('')
      setAviso('Turno de caja abierto.')
      void queryClient.invalidateQueries({ queryKey: ['turno-caja'] })
    },
    onError: (e) => setError(MensajeApi(e)),
  })

  const cerrar = useMutation({
    mutationFn: ({ id, monto }: { id: number; monto: string }) => caja.cerrar(id, monto),
    onSuccess: (r) => {
      setDialogoCerrar(false)
      setContado('')
      setAviso(
        `Cierre registrado. Esperado ${dinero(r.esperado)}, contado ${dinero(r.contado)}, diferencia ${dinero(r.diferencia)}.`,
      )
      void queryClient.invalidateQueries({ queryKey: ['turno-caja'] })
    },
    onError: (e) => setError(MensajeApi(e)),
  })

  return (
    <div className="tarjeta">
      <h2>Caja por turno</h2>
      <Aviso variante="error">{error}</Aviso>
      <Aviso variante="ok">{aviso}</Aviso>

      {turnoQ.isLoading && <p style={{ color: 'var(--color-muted)' }}>Buscando turno…</p>}

      {!miTurno && !turnoQ.isLoading && (
        <>
          <Aviso variante="aviso">Sin turno abierto: el cobro en efectivo lo exige (docs/04 §4.3, regla 5).</Aviso>
          <button className="btn btn-primario" onClick={() => setDialogoAbrir(true)}>
            Abrir turno de caja
          </button>
        </>
      )}

      {miTurno && (
        <>
          <p>
            Turno <strong>{miTurno.id}</strong> abierto {miTurno.opened_at.slice(0, 16).replace('T', ' ')} · apertura{' '}
            <span className="importe">{dinero(String(miTurno.opening_amount))}</span>
          </p>
          {esperadoQ.data && (
            <p>
              Cobros en efectivo: <strong>{esperadoQ.data.cobros_efectivo}</strong> · esperado{' '}
              <span className="importe"><strong>{dinero(esperadoQ.data.esperado)}</strong></span>
            </p>
          )}
          <button className="btn btn-peligro" onClick={() => setDialogoCerrar(true)}>
            Cerrar turno
          </button>
        </>
      )}

      <Modal titulo="Abrir turno de caja" abierto={abiertoDialogoAbrir} alCerrar={() => setDialogoAbrir(false)}>
        <div className="campo">
          <label htmlFor="caja-inicial">Monto inicial en la caja</label>
          <input
            id="caja-inicial"
            inputMode="decimal"
            value={montoInicial}
            onChange={(e) => setMontoInicial(e.target.value)}
            placeholder="50000"
          />
        </div>
        <div className="pie-dialogo">
          <button className="btn btn-fantasma" onClick={() => setDialogoAbrir(false)}>
            Cancelar
          </button>
          <button
            className="btn btn-primario"
            disabled={abrir.isPending}
            onClick={() => {
              const m = aImporte(montoInicial)
              if (m == null) {
                setError('Monto inicial inválido.')
                return
              }
              abrir.mutate(m)
            }}
          >
            {abrir.isPending ? 'Abriendo…' : 'Abrir turno'}
          </button>
        </div>
      </Modal>

      <Modal titulo="Cerrar turno de caja" abierto={abiertoDialogoCerrar} alCerrar={() => setDialogoCerrar(false)}>
        {esperadoQ.data && (
          <Aviso variante="aviso">
            Esperado según los cobros: <strong>{dinero(esperadoQ.data.esperado)}</strong>. El sistema guardará la
            diferencia contra lo contado.
          </Aviso>
        )}
        <div className="campo">
          <label htmlFor="caja-contado">Monto contado en la caja</label>
          <input
            id="caja-contado"
            inputMode="decimal"
            value={contado}
            onChange={(e) => setContado(e.target.value)}
            placeholder="0,00"
          />
        </div>
        <div className="pie-dialogo">
          <button className="btn btn-fantasma" onClick={() => setDialogoCerrar(false)}>
            Cancelar
          </button>
          <button
            className="btn btn-peligro"
            disabled={cerrar.isPending}
            onClick={() => {
              const m = aImporte(contado)
              if (m == null || !miTurno) {
                setError('Monto contado inválido.')
                return
              }
              cerrar.mutate({ id: miTurno.id, monto: m })
            }}
          >
            {cerrar.isPending ? 'Cerrando…' : 'Cerrar turno'}
          </button>
        </div>
      </Modal>
    </div>
  )
}

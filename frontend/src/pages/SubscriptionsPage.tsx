import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { clients, mensualidades, type ClientePlan } from '../api/subscriptions'
import { Aviso, MensajeApi } from '../components/ui/Aviso'
import { Modal } from '../components/ui/Modal'
import { DatePicker, isoDe, leerFecha } from '../components/DatePicker/DatePicker'
import { aImporte, dinero } from '../lib/formato'
import { ESTADOS_SUSCRIPCION, METODOS_PAGO, TIPOS_VEHICULO } from '../theme/catalogos'

/** Mensualidades (docs/04 §4.6) — /docs/09 §9.16: los 5 diálogos del MVP:
 * 1) nuevo cliente · 2) agregar placa · 3) nueva mensualidad · 4) pagar ·
 * 5) renovar (+#6 cancelar). Renovar es UNA transacción con el cobro. */
export function SubscriptionsPage(): JSX.Element {
  const queryClient = useQueryClient()
  const [q, setQ] = useState('')
  const [estado, setEstado] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [ok, setOk] = useState<string | null>(null)

  const lista = useQuery({
    queryKey: ['clientes', { q, estado }],
    queryFn: ({ signal }) => clients.listar({ q: q.trim() || undefined, estado: estado || undefined }, signal),
  })

  // fix UX-S024: paginación client-side del listado (15 por página)
  const POR_PAGINA = 15
  const [pagina, setPagina] = useState(1)
  const clientes = lista.data?.clientes ?? []
  const totalPaginas = Math.max(1, Math.ceil(clientes.length / POR_PAGINA))
  const paginaActual = Math.min(pagina, totalPaginas)
  const visibles = clientes.slice((paginaActual - 1) * POR_PAGINA, paginaActual * POR_PAGINA)

  const alertas = useQuery({ queryKey: ['alertas'], queryFn: ({ signal }) => mensualidades.alertas(7, signal) })

  const invalidar = async (): Promise<void> => {
    await queryClient.invalidateQueries({ queryKey: ['clientes'] })
    await queryClient.invalidateQueries({ queryKey: ['alertas'] })
    await queryClient.invalidateQueries({ queryKey: ['dashboard'] })
  }

  // diálogos
  const [dlg, setDlg] = useState<
    null | { tipo: 'cliente' } | { tipo: 'placa'; c: ClientePlan } | { tipo: 'plan'; c: ClientePlan }
      | { tipo: 'pagar'; c: ClientePlan } | { tipo: 'renovar'; c: ClientePlan } | { tipo: 'cancelar'; c: ClientePlan }
  >(null)

  const TITULO: Record<string, string> = {
    cliente: 'Nuevo cliente',
    placa: 'Agregar placa',
    plan: 'Nueva mensualidad',
    pagar: 'Registrar pago',
    renovar: 'Renovar mensualidad',
    cancelar: 'Cancelar mensualidad',
  }

  return (
    <>
      <div className="titulo">
        <h1>Mensualidades</h1>
      </div>

      <div className="tarjeta" style={{ marginBottom: 14 }}>
        <div className="fila" style={{ alignItems: 'flex-end' }}>
          <div className="campo" style={{ flex: 2, margin: 0 }}>
            <label htmlFor="mq">Buscar cliente</label>
            <input id="mq" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Nombre, documento, teléfono o placa…" />
          </div>
          <div className="campo" style={{ margin: 0 }}>
            <label htmlFor="me">Estado</label>
            <select id="me" value={estado} onChange={(e) => setEstado(e.target.value)}>
              <option value="">Todos</option>
              {Object.entries(ESTADOS_SUSCRIPCION).map(([c, e]) => (
                <option key={c} value={c}>
                  {e}
                </option>
              ))}
            </select>
          </div>
          <button
            className="btn btn-suave"
            onClick={() => {
              setDlg({ tipo: 'cliente' })
              setError(null)
              setOk(null)
            }}
          >
            + Nuevo cliente
          </button>
        </div>
        <Aviso variante="error">{error}</Aviso>
        <Aviso variante="ok">{ok}</Aviso>
      </div>

      {alertas.data && alertas.data.alertas?.length > 0 && (
        <div className="tarjeta" style={{ marginBottom: 14, borderColor: 'var(--color-warning)' }}>
          <h2>
            Avisos (por vencer o vencidas con saldo, aviso a 7 días — docs/04 §4.6)
          </h2>
          <ul style={{ margin: 0, paddingLeft: 18, fontSize: 14 }}>
            {alertas.data.alertas.map((a) => (
              <li key={a.suscripcion_id}>
                <strong>{a.cliente}</strong> · {a.plan} · vence {a.vence} · saldo{' '}
                <span className="importe">{dinero(a.saldo)}</span> ·{' '}
                <span className={`pill ${a.status === 'VENCIDA' ? 'pill-rojo' : 'pill-naranja'}`}>{a.status}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {lista.isError && <Aviso variante="error">{MensajeApi(lista.error)}</Aviso>}
      {lista.isPending && <p className="cargando">Cargando clientes</p>}

      {lista.data && (
        <div className="contenedor-tabla">
          <table className="tabla">
            <thead>
              <tr>
                <th scope="col">Cliente</th>
                <th scope="col">Plan</th>
                <th scope="col">Placas</th>
                <th scope="col">Periodo</th>
                <th scope="col">Situación</th>
                <th scope="col" style={{ textAlign: 'right' }}>Valor</th>
                <th scope="col" style={{ textAlign: 'right' }}>Saldo</th>
                <th scope="col" style={{ minWidth: 330 }}>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {visibles.map((c) => (
                <tr key={`${c.cliente_id}-${c.suscripcion_id ?? 'noplan'}`}>
                  <td>
                    <strong>{c.nombre}</strong>
                    <div style={{ fontSize: 12, color: 'var(--color-muted)' }}>
                      {c.documento ? `${c.documento.tipo} ${c.documento.numero}` : 'Sin documento'}
                      {c.telefono && ` · ${c.telefono}`}
                    </div>
                  </td>
                  <td>{c.plan ?? '—'}</td>
                  <td style={{ fontFamily: 'var(--font-mono)' }}>{c.placas.join(' · ') || '—'}</td>
                  <td>{c.inicio && c.vence ? `${c.inicio} → ${c.vence}` : '—'}</td>
                  <td>
                    <span className={`pill ${pillEstado(c.estado)}`}>{c.estado_texto || ESTADOS_SUSCRIPCION[c.estado] || c.estado}</span>
                  </td>
                  <td className="importe" style={{ textAlign: 'right' }}>{c.valor ? dinero(c.valor) : '—'}</td>
                  <td className="importe" style={{ textAlign: 'right' }}>{dinero(c.saldo)}</td>
                  <td>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }} role="group" aria-label={`Acciones de ${c.nombre}`}>
                      <button className="btn btn-compacto btn-suave" onClick={() => setDlg({ tipo: 'placa', c })}>
                        + Placa
                      </button>
                      <button className="btn btn-compacto btn-primario" onClick={() => setDlg({ tipo: 'plan', c })}>
                        + Mensualidad
                      </button>
                      {c.suscripcion_id && (
                        <>
                          <button className="btn btn-compacto btn-exito" onClick={() => setDlg({ tipo: 'pagar', c })}>
                            $ Pagar
                          </button>
                          <button className="btn btn-compacto btn-primario" onClick={() => setDlg({ tipo: 'renovar', c })}>
                            ⟳ Renovar
                          </button>
                          <button className="btn btn-compacto btn-peligro" onClick={() => setDlg({ tipo: 'cancelar', c })}>
                            ✕ Cancelar
                          </button>
                        </>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
              {visibles.length === 0 && (
                <tr>
                  <td colSpan={8} style={{ textAlign: 'center', color: 'var(--color-muted)' }}>
                    Sin clientes con los filtros indicados.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {lista.data && clientes.length > POR_PAGINA && (
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

      {dlg && (
        <Modal
          titulo={TITULO[dlg.tipo]}
          abierto
          alCerrar={() => setDlg(null)}
          ancho={dlg.tipo === 'plan' || dlg.tipo === 'cliente' ? 560 : 480}
        >
          {dlg.tipo === 'cliente' && (
            <DialogoNuevoCliente
              alCerrado={async (msg: string) => {
                setDlg(null)
                setOk(msg)
                await invalidar()
              }}
              alError={(m) => setError(m)}
            />
          )}
          {dlg.tipo === 'placa' && (
            <DialogoPlaca
              c={dlg.c}
              alCerrado={async (msg: string) => {
                setDlg(null)
                setOk(msg)
                await invalidar()
              }}
              alError={(m) => setError(m)}
            />
          )}
          {dlg.tipo === 'plan' && (
            <DialogoPlan
              c={dlg.c}
              alCerrado={async (msg: string) => {
                setDlg(null)
                setOk(msg)
                await invalidar()
              }}
              alError={(m) => setError(m)}
            />
          )}
          {(dlg.tipo === 'pagar' || dlg.tipo === 'renovar') && (
            <DialogoPagoRenovar
              c={dlg.c}
              modo={dlg.tipo}
              alCerrado={async (msg: string) => {
                setDlg(null)
                setOk(msg)
                await invalidar()
              }}
              alError={(m) => setError(m)}
            />
          )}
          {dlg.tipo === 'cancelar' && (
            <DialogoCancelar
              c={dlg.c}
              alCerrado={async (msg: string) => {
                setDlg(null)
                setOk(msg)
                await invalidar()
              }}
              alError={(m) => setError(m)}
            />
          )}
        </Modal>
      )}
    </>
  )
}

function pillEstado(estado: string): string {
  if (estado === 'ACTIVE') return 'pill-verde'
  if (estado === 'EXPIRING') return 'pill-naranja'
  if (estado === 'EXPIRED') return 'pill-rojo'
  if (estado === 'CANCELLED') return 'pill-rojo'
  return 'pill-gris'
}

/* ---------------- diálogos ---------------- */

type Cb = { alCerrado: (msg: string) => Promise<void> | void; alError: (m: string) => void }

function DialogoNuevoCliente({ alCerrado, alError }: Cb): JSX.Element {
  const [nombre, setNombre] = useState('')
  const [tipoDoc, setTipoDoc] = useState('CC')
  const [docNumero, setDocNumero] = useState('')
  const [telefono, setTelefono] = useState('')
  const [correo, setCorreo] = useState('')
  const [placasTexto, setPlacasTexto] = useState('')
  const [enCurso, setEnCurso] = useState(false)

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault()
        setEnCurso(true)
        clients
          .crear({
            nombre: nombre.trim(),
            documento: { tipo: tipoDoc, numero: docNumero.trim() },
            telefono: telefono.trim() || null,
            correo: correo.trim() || null,
            direccion: null,
            placas: placasTexto.trim() ? placasTexto.split(/[ ,;]+/).map((p) => p.toUpperCase()) : [],
          })
          .then((r) => alCerrado(`Cliente creado (${r.cliente_id}). Las placas quedaron asociadas.`))
          .catch((e2) => {
            alError(MensajeApi(e2))
            setEnCurso(false)
          })
      }}
    >
      <div className="campo">
        <label htmlFor="nc-nombre">Nombre completo</label>
        <input id="nc-nombre" value={nombre} onChange={(e) => setNombre(e.target.value)} required />
      </div>
      <div className="fila">
        <div className="campo" style={{ width: 130 }}>
          <label htmlFor="nc-tipo">Documento</label>
          <select id="nc-tipo" value={tipoDoc} onChange={(e) => setTipoDoc(e.target.value)}>
            <option value="CC">CC</option>
            <option value="CE">CE</option>
            <option value="NIT">NIT</option>
            <option value="PASAPORTE">Pasaporte</option>
          </select>
        </div>
        <div className="campo" style={{ flex: 1 }}>
          <label htmlFor="nc-doc">Número</label>
          <input id="nc-doc" value={docNumero} onChange={(e) => setDocNumero(e.target.value)} required />
        </div>
      </div>
      <div className="fila">
        <div className="campo" style={{ flex: 1 }}>
          <label htmlFor="nc-tel">Teléfono</label>
          <input id="nc-tel" type="tel" inputMode="tel" autoComplete="tel" value={telefono} onChange={(e) => setTelefono(e.target.value)} style={{ maxWidth: 200 }} />
        </div>
        <div className="campo" style={{ flex: 1 }}>
          <label htmlFor="nc-correo">Correo</label>
          <input id="nc-correo" type="email" value={correo} onChange={(e) => setCorreo(e.target.value)} style={{ maxWidth: 200 }} />
        </div>
      </div>
      <div className="campo">
        <label htmlFor="nc-placas">Placas iniciales (separadas por espacio o coma)</label>
        <input id="nc-placas" value={placasTexto} onChange={(e) => setPlacasTexto(e.target.value.toUpperCase())} placeholder="ABC123 XYZ789" />
      </div>
      <div className="pie-dialogo">
        <button type="button" className="btn btn-fantasma" onClick={() => alCerrado('')}>
          Cancelar
        </button>
        <button type="submit" className="btn btn-primario" disabled={enCurso}>
          {enCurso ? 'Guardando…' : 'Crear cliente'}
        </button>
      </div>
    </form>
  )
}

function DialogoPlaca({ c, alCerrado, alError }: Cb & { c: ClientePlan }): JSX.Element {
  const [placa, setPlaca] = useState('')
  const [tipo, setTipo] = useState('CAR')
  const [enCurso, setEnCurso] = useState(false)
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault()
        setEnCurso(true)
        clients
          .agregarPlaca(c.cliente_id, placa.trim(), tipo)
          .then(() => alCerrado(`Placa ${placa.trim().toUpperCase()} asociada a ${c.nombre}.`))
          .catch((e2) => {
            alError(MensajeApi(e2))
            setEnCurso(false)
          })
      }}
    >
      <p style={{ color: 'var(--color-muted)', fontSize: 13 }}>Placas actuales: {c.placas.join(' · ') || 'ninguna'}</p>
      <div className="fila">
        <div className="campo" style={{ flex: 1, margin: 0 }}>
          <label htmlFor="dp-placa">Placa</label>
          <input id="dp-placa" value={placa} onChange={(e) => setPlaca(e.target.value.toUpperCase())} required />
        </div>
        <div className="campo" style={{ margin: 0 }}>
          <label htmlFor="dp-tipo">Tipo</label>
          <select id="dp-tipo" value={tipo} onChange={(e) => setTipo(e.target.value)}>
            {TIPOS_VEHICULO.map((t) => (
              <option key={t.codigo} value={t.codigo}>
                {t.etiqueta}
              </option>
            ))}
          </select>
        </div>
      </div>
      <div className="pie-dialogo">
        <button type="button" className="btn btn-fantasma" onClick={() => alCerrado('')}>
          Cancelar
        </button>
        <button type="submit" className="btn btn-primario" disabled={enCurso}>
          {enCurso ? 'Asociando…' : 'Asociar placa'}
        </button>
      </div>
    </form>
  )
}

function DialogoPlan({ c, alCerrado, alError }: Cb & { c: ClientePlan }): JSX.Element {
  const hoy = isoDe(new Date())
  const [plan, setPlan] = useState('Mensualidad')
  const [inicio, setInicio] = useState(hoy)
  const [meses, setMeses] = useState(1)
  const [valor, setValor] = useState('')
  const [usaHorario, setUsaHorario] = useState(false)
  const [desde, setDesde] = useState('06:00')
  const [hasta, setHasta] = useState('20:00')
  const [enCurso, setEnCurso] = useState(false)

  return (
    <form
      onSubmit={(ev) => {
        ev.preventDefault()
        setEnCurso(true)
        const v = aImporte(valor)
        const i = leerFecha(inicio)
        if (v == null || !i) {
          alError('Valor o fecha de inicio inválidos.')
          setEnCurso(false)
          return
        }
        mensualidades
          .crear({
            cliente_id: c.cliente_id,
            plan: plan.trim(),
            placas: c.placas,
            inicio: i,
            meses,
            valor: v,
            horario: usaHorario ? { desde, hasta } : null,
          })
          .then((r) =>
            alCerrado(
              `Mensualidad ${r.suscripcion_id} creada para ${c.nombre} con vencimiento según fin de mes real.`,
            ),
          )
          .catch((e2) => {
            alError(MensajeApi(e2))
            setEnCurso(false)
          })
      }}
    >
      <p style={{ color: 'var(--color-muted)', fontSize: 13 }}>
        Cliente: <strong>{c.nombre}</strong> · cubre las placas {c.placas.join(' · ') || '(el cliente no tiene placas: agrega una primero)'}
      </p>
      <div className="campo">
        <label htmlFor="nl-plan">Nombre del plan</label>
        <input id="nl-plan" value={plan} onChange={(e) => setPlan(e.target.value)} required />
      </div>
      <div className="fila">
        <div className="campo" style={{ margin: 0 }}>
          <label htmlFor="nl-inicio">Inicio</label>
          <DatePicker id="nl-inicio" etiqueta="Inicio" valor={inicio} alCambiar={setInicio} />
        </div>
        <div className="campo" style={{ width: 110 }}>
          <label htmlFor="nl-meses">Meses</label>
          <input
            id="nl-meses"
            type="number"
            min={1}
            max={24}
            value={meses}
            onChange={(e) => setMeses(Math.max(1, Number(e.target.value) || 1))}
          />
        </div>
        <div className="campo" style={{ flex: 1 }}>
          <label htmlFor="nl-valor">Valor del período</label>
          <input id="nl-valor" inputMode="decimal" value={valor} onChange={(e) => setValor(e.target.value)} placeholder="90000" required />
        </div>
      </div>
      <label style={{ display: 'flex', gap: 8, alignItems: 'center', fontSize: 14 }}>
        <input type="checkbox" checked={usaHorario} onChange={(e) => setUsaHorario(e.target.checked)} />
        Restringir a un horario permitido (ambas horas o ninguna — docs/04 §4.6)
      </label>
      {usaHorario && (
        <div className="fila" style={{ marginTop: 8 }}>
          <div className="campo" style={{ margin: 0 }}>
            <label htmlFor="nl-ll">Desde (hora)</label>
            <input id="nl-ll" type="time" value={desde} onChange={(e) => setDesde(e.target.value)} />
          </div>
          <div className="campo" style={{ margin: 0 }}>
            <label htmlFor="nl-l1">Hasta (hora)</label>
            <input id="nl-l1" type="time" value={hasta} onChange={(e) => setHasta(e.target.value)} />
          </div>
        </div>
      )}
      <div className="pie-dialogo">
        <button type="button" className="btn btn-fantasma" onClick={() => alCerrado('')}>
          Cancelar
        </button>
        <button type="submit" className="btn btn-primario" disabled={enCurso || c.placas.length === 0}>
          {enCurso ? 'Creando…' : 'Crear mensualidad'}
        </button>
      </div>
    </form>
  )
}

/** Pagar la mensualidad vigente o renovar (una sola transacción con el cobro). */
function DialogoPagoRenovar({
  c,
  modo,
  alCerrado,
  alError,
}: Cb & { c: ClientePlan; modo: 'pagar' | 'renovar' }): JSX.Element {
  const [metodo, setMetodo] = useState('CASH')
  const [monto, setMonto] = useState(c.saldo && Number(c.saldo) > 0 ? String(Number(c.saldo)) : c.valor ?? '')
  const [recibido, setRecibido] = useState('')
  const [meses, setMeses] = useState(1)
  const [enCurso, setEnCurso] = useState(false)

  return (
    <form
      onSubmit={(ev) => {
        ev.preventDefault()
        setEnCurso(true)
        const m = aImporte(monto)
        if (m == null) {
          alError('Monto inválido.')
          setEnCurso(false)
          return
        }
        const r = metodo === 'CASH' ? aImporte(recibido) : null
        const t =
          modo === 'pagar'
            ? mensualidades.pagar(c.suscripcion_id!, metodo, m, r)
            : mensualidades.renovar(c.suscripcion_id!, metodo, m, r, meses)
        void t
          .then((res) => {
            if (modo === 'pagar') return alCerrado(`Pago ${res.pago_id} registrado para ${c.nombre}.`)
            const rr = res as { pago_id: number; inicio: string; vence: string; suscripcion_nueva: number }
            return alCerrado(
              `Renovación cobrada en una sola transacción: nueva suscripción ${rr.suscripcion_nueva}, de ${rr.inicio} a ${rr.vence}.`,
            )
          })
          .catch((e2) => {
            alError(MensajeApi(e2))
            setEnCurso(false)
          })
      }}
    >
      <p style={{ color: 'var(--color-muted)', fontSize: 13 }}>
        {modo === 'pagar'
          ? `Saldo pendiente de ${c.nombre}: ${dinero(c.saldo)}. Sólo efectivo registra cambio.`
          : `Renueve tras vencimiento. Plan NO vencido: el período será continuar al día siguiente; vencido: comienza hoy.`}
      </p>
      <div className="fila">
        <div className="campo" style={{ margin: 0 }}>
          <label htmlFor="pr-metodo">Forma de pago</label>
          <select id="pr-metodo" value={metodo} onChange={(e) => setMetodo(e.target.value)}>
            {METODOS_PAGO.map((m) => (
              <option key={m.codigo} value={m.codigo}>
                {m.etiqueta}
              </option>
            ))}
          </select>
        </div>
        <div className="campo" style={{ margin: 0 }}>
          <label htmlFor="pr-monto">Monto</label>
          <input id="pr-monto" inputMode="decimal" value={monto} onChange={(e) => setMonto(e.target.value)} required />
        </div>
        {metodo === 'CASH' && (
          <div className="campo" style={{ margin: 0 }}>
            <label htmlFor="pr-rec">Efectivo recibido</label>
            <input id="pr-rec" inputMode="decimal" value={recibido} onChange={(e) => setRecibido(e.target.value)} placeholder="0,00" />
          </div>
        )}
        {modo === 'renovar' && (
          <div className="campo" style={{ width: 110 }}>
            <label htmlFor="pr-meses">Meses</label>
            <input
              id="pr-meses"
              type="number"
              min={1}
              max={24}
              value={meses}
              onChange={(e) => setMeses(Math.max(1, Number(e.target.value) || 1))}
            />
          </div>
        )}
      </div>
      <div className="pie-dialogo">
        <button type="button" className="btn btn-fantasma" onClick={() => alCerrado('')}>
          Cancelar
        </button>
        <button type="submit" className="btn btn-exito" disabled={enCurso}>
          {enCurso ? 'Procesando…' : modo === 'pagar' ? 'Registrar pago' : 'Renovar y cobrar'}
        </button>
      </div>
    </form>
  )
}

function DialogoCancelar({ c, alCerrado, alError }: Cb & { c: ClientePlan }): JSX.Element {
  const [motivo, setMotivo] = useState('')
  const [enCurso, setEnCurso] = useState(false)
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault()
        setEnCurso(true)
        mensualidades
          .cancelar(c.suscripcion_id!, motivo.trim() || 'Cancelación sin motivo')
          .then(() =>
            alCerrado(
              `Mensualidad de ${c.nombre} cancelada. El historial de pagos se conserva (docs/04 §4.6).`,
            ),
          )
          .catch((e2) => {
            alError(MensajeApi(e2))
            setEnCurso(false)
          })
      }}
    >
      <p style={{ color: 'var(--color-muted)', fontSize: 13 }}>
        La cancelación conserva el historial de pagos. El estado derivado pasará a «CANCELADA».
      </p>
      <div className="campo">
        <label htmlFor="dc-motivo">Motivo</label>
        <input id="dc-motivo" value={motivo} onChange={(e) => setMotivo(e.target.value)} placeholder="Cliente se retiró" />
      </div>
      <div className="pie-dialogo">
        <button type="button" className="btn btn-fantasma" onClick={() => alCerrado('')}>
          Cerrar
        </button>
        <button type="submit" className="btn btn-peligro" disabled={enCurso}>
          {enCurso ? 'Cancelando…' : 'Cancelar mensualidad'}
        </button>
      </div>
    </form>
  )
}

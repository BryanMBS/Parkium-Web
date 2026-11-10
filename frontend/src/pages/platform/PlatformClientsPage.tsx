/* Clientes de la plataforma (tenants): altas con primer admin, filtro de
 * búsqueda, suspender/reactivar con motivo obligatorio en Modal. */

import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { plataforma, type CrearTenantDatos, type Tenant, type TenantDetalle } from '../../api/platform'
import { Aviso, MensajeApi } from '../../components/ui/Aviso'
import { Modal } from '../../components/ui/Modal'

type Accion = 'suspend' | 'reactivate'

const PLANES = ['BASIC', 'PRO', 'ENTERPRISE'] as const

export function PlatformClientsPage(): JSX.Element {
  const [clientes, setClientes] = useState<Tenant[]>([])
  const [q, setQ] = useState('')
  const [estado, setEstado] = useState('')
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [abiertoAlta, setAbiertoAlta] = useState(false)
  const [creado, setCreado] = useState<TenantDetalle | null>(null)
  const [mensaje, setMensaje] = useState<string | null>(null)
  const [errorAlta, setErrorAlta] = useState<string | null>(null)
  const [enCurso, setEnCurso] = useState(false)

  // confirmación de suspensión/reactivación
  const [destino, setDestino] = useState<{ t: Tenant; a: Accion } | null>(null)
  const [motivo, setMotivo] = useState('')

  const cargar = useCallback((busqueda?: string, filtroEstado?: string) => {
    setCargando(true)
    setError(null)
    plataforma
      .listarTenants(busqueda, filtroEstado)
      .then((lista) => setClientes(lista))
      .catch((e) => setError(MensajeApi(e) || 'No se pudo cargar la lista de clientes.'))
      .finally(() => setCargando(false))
  }, [])

  useEffect(() => { cargar() }, [cargar])

  function buscar(e: React.FormEvent): void {
    e.preventDefault()
    cargar(q, estado)
  }

  async function crear(e: React.FormEvent<HTMLFormElement>): Promise<void> {
    e.preventDefault()
    const f = new FormData(e.currentTarget)
    const datos: CrearTenantDatos = {
      name: String(f.get('name') || '').trim(),
      nit: String(f.get('nit') || '').trim(),
      plan: String(f.get('plan') || 'BASIC') as Tenant['plan'],
      max_sites: Number(f.get('max_sites') || 1),
      max_users: Number(f.get('max_users') || 5),
      billing_cutoff_day: Number(f.get('corte') || 1),
      sede_nombre: (f.get('sede_nombre') as string) || null,
      sede_cupos: Number(f.get('sede_cupos')) || null,
      admin_username: (f.get('admin_username') as string) || null,
      admin_nombre: (f.get('admin_nombre') as string) || null,
    }
    if (!datos.name || !datos.nit) {
      setErrorAlta('La razón social y el NIT son obligatorios.')
      return
    }
    setEnCurso(true)
    setErrorAlta(null)
    try {
      const r = await plataforma.crearTenant(datos)
      setCreado(r) // muestra la contraseña temporal UNA sola vez
      setMensaje(null)
      e.currentTarget.reset()
      cargar(q, estado)
    } catch (err) {
      setErrorAlta(MensajeApi(err) || 'No se pudo crear el cliente.')
    } finally {
      setEnCurso(false)
    }
  }

  async function ejecutarDestino(): Promise<void> {
    if (!destino) return
    if (!motivo.trim()) {
      setError('El motivo es obligatorio.')
      return
    }
    setEnCurso(true)
    setError(null)
    try {
      await (destino.a === 'suspend'
        ? plataforma.suspenderTenant(destino.t.id, motivo.trim())
        : plataforma.reactivarTenant(destino.t.id, motivo.trim()))
      setMensaje(destino.a === 'suspend'
        ? `${destino.t.name} quedará suspendido: sus sesiones activas se cierran.`
        : `${destino.t.name} volvió a estar activo.`)
      setDestino(null)
      setMotivo('')
      cargar(q, estado)
    } catch (err) {
      setError(MensajeApi(err) || 'No se pudo completar la acción.')
    } finally {
      setEnCurso(false)
    }
  }

  return (
    <>
      <h1 className="pf-titulo">Clientes</h1>
      <p className="pf-subtitulo">
        Cada cliente es un tenant independiente con su propio espacio, sedes y usuarios.
      </p>

      <Aviso variante="error">{error}</Aviso>
      <Aviso variante="ok">{mensaje}</Aviso>

      <div className="pf-barra">
        <form onSubmit={buscar} style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'flex-end' }}>
          <div className="campo">
            <label htmlFor="pf-buscar">Buscar</label>
            <input
              id="pf-buscar"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Razón social o NIT"
            />
          </div>
          <div className="campo">
            <label htmlFor="pf-estado">Estado</label>
            <select id="pf-estado" value={estado} onChange={(e) => setEstado(e.target.value)}>
              <option value="">Todos</option>
              <option value="ACTIVE">Activos</option>
              <option value="SUSPENDED">Suspendidos</option>
            </select>
          </div>
          <button type="submit" className="pf-btn pf-btn-suave" disabled={cargando}>
            Buscar
          </button>
        </form>
        <button
          className="pf-btn pf-btn-primario"
          aria-expanded={abiertoAlta}
          onClick={() => { setAbiertoAlta(!abiertoAlta); setCreado(null); setErrorAlta(null) }}
        >
          {abiertoAlta ? '− Cerrar nuevo cliente' : '+ Nuevo cliente'}
        </button>
      </div>

      {abiertoAlta && (
        <div className="pf-tarjeta" style={{ marginBottom: 20 }}>
          <h2 style={{ margin: '0 0 12px', fontSize: 16 }}>Nuevo cliente</h2>
          <Aviso variante="error">{errorAlta}</Aviso>
          <form onSubmit={crear}>
            <div className="pf-fila">
              <div className="campo">
                <label htmlFor="pf-name">Razón social</label>
                <input id="pf-name" name="name" autoComplete="organization" required maxLength={120} />
              </div>
              <div className="campo">
                <label htmlFor="pf-nit">NIT</label>
                <input id="pf-nit" name="nit" required maxLength={32} placeholder="900123456-7" />
              </div>
              <div className="campo">
                <label htmlFor="pf-plan">Plan</label>
                <select id="pf-plan" name="plan" defaultValue="BASIC">
                  {PLANES.map((p) => <option key={p}>{p}</option>)}
                </select>
              </div>
            </div>
            <div className="pf-fila">
              <div className="campo">
                <label htmlFor="pf-maxs">Máx. sedes</label>
                <input id="pf-maxs" name="max_sites" type="number" min={1} defaultValue={1} />
              </div>
              <div className="campo">
                <label htmlFor="pf-maxu">Máx. usuarios</label>
                <input id="pf-maxu" name="max_users" type="number" min={1} defaultValue={5} />
              </div>
              <div className="campo">
                <label htmlFor="pf-corte">Día de corte</label>
                <input id="pf-corte" name="corte" type="number" min={1} max={28} defaultValue={1} />
              </div>
            </div>
            <div className="pf-fila">
              <div className="campo">
                <label htmlFor="pf-sede">Primera sede (opcional)</label>
                <input id="pf-sede" name="sede_nombre" maxLength={120} placeholder="Sede principal" />
              </div>
              <div className="campo">
                <label htmlFor="pf-cupos">Cupos de la sede</label>
                <input id="pf-cupos" name="sede_cupos" type="number" min={0} placeholder="30" />
              </div>
            </div>
            <div className="pf-fila">
              <div className="campo">
                <label htmlFor="pf-admin">Usuario del primer administrador (opcional)</label>
                <input id="pf-admin" name="admin_username" maxLength={60} placeholder="admin" />
              </div>
              <div className="campo">
                <label htmlFor="pf-nombre">Nombre del administrador</label>
                <input id="pf-nombre" name="admin_nombre" maxLength={120} />
              </div>
            </div>
            <button type="submit" className="pf-btn pf-btn-primario" disabled={enCurso}>
              {enCurso ? 'Creando…' : 'Crear cliente'}
            </button>
          </form>

          {creado && (
            <div className="pf-tarjeta" style={{ marginTop: 14, borderColor: '#7c3aed' }}>
              <strong>Cliente «{creado.tenant.name}» creado (id {creado.tenant.id}).</strong>
              {creado.contrasena_temporal ? (
                <div style={{ marginTop: 8 }}>
                  <p style={{ margin: 0 }}>
                    Contraseña temporal de <strong>{creado.admin?.username}</strong>&nbsp;
                    (se muestra una sola vez; obliga a cambio en el primer login):
                  </p>
                  <p className="mono" style={{ fontSize: 16, letterSpacing: 1, margin: '6px 0 0' }}>
                    {creado.contrasena_temporal}
                  </p>
                </div>
              ) : (
                <p style={{ margin: '6px 0 0', color: '#8b88a0' }}>
                  No se pidió administrador inicial; recuérdalo al crear sus usuarios.
                </p>
              )}
            </div>
          )}
        </div>
      )}

      {cargando && <p role="status">Cargando clientes…</p>}
      {!cargando && clientes.length === 0 && !error && (
        <p role="status" style={{ color: '#8b88a0' }}>
          Sin resultados para esta búsqueda.
        </p>
      )}

      <p style={{ color: '#8b88a0', fontSize: 13 }}>Registrados ({clientes.length})</p>
      <div className="pf-clientes">
        {clientes.map((t) => (
          <article className="pf-cliente" key={t.id}>
            <div className="cabecera">
              <span className="nombre">{t.name}</span>
              <span className={`pf-estado ${t.status === 'ACTIVE' ? 'active' : 'suspended'}`}>
                {t.status === 'ACTIVE' ? 'Activo' : 'Suspendido'}
              </span>
            </div>
            <span className="nit">{t.nit}</span>
            <span className="plan-linea">
              Plan {t.plan} · límites: {t.sedes ?? 0}/{t.max_sites} sedes · {t.usuarios ?? 0}/{t.max_users} usuarios · corte día {t.billing_cutoff_day}
            </span>
            <div className="acciones">
              <Link to={`/plataforma/clientes/${t.id}`} className="pf-btn pf-btn-primario pf-btn-compacto">
                Administrar
              </Link>
              {t.status === 'ACTIVE' ? (
                <button
                  className="pf-btn pf-btn-outline-danger pf-btn-compacto"
                  onClick={() => { setDestino({ t, a: 'suspend' }); setMotivo('') }}
                  disabled={enCurso}
                >
                  Suspender
                </button>
              ) : (
                <button
                  className="pf-btn pf-btn-outline-danger pf-btn-compacto"
                  onClick={() => { setDestino({ t, a: 'reactivate' }); setMotivo('') }}
                  disabled={enCurso}
                >
                  Reactivar
                </button>
              )}
            </div>
          </article>
        ))}
      </div>

      <Modal
        titulo={destino?.a === 'suspend' ? 'Suspender cliente' : 'Reactivar cliente'}
        abierto={destino !== null}
        alCerrar={() => { setDestino(null); setMotivo(''); setError(null) }}
        ancho={460}
      >
        <div className="pf-tarjeta" style={{ boxShadow: 'none' }}>
          <Aviso variante="error">{error}</Aviso>
          {destino && destino.a === 'suspend' ? (
            <p style={{ marginTop: 0 }}>
              Al suspender a <strong>{destino.t.name}</strong> se cancela su inicio de sesión y
              se cierran sus sesiones activas. Los recibos públicos ya emitidos seguirán visibles.
            </p>
          ) : destino && (
            <p style={{ marginTop: 0 }}>
              Al reactivar a <strong>{destino.t.name}</strong> sus usuarios podrán volver a iniciar
              sesión con sus credenciales vigentes.
            </p>
          )}
          <div className="campo">
            <label htmlFor="pf-motivo">Motivo (obligatorio, queda en auditoría)</label>
            <textarea
              id="pf-motivo"
              value={motivo}
              onChange={(e) => setMotivo(e.target.value)}
              rows={3}
              maxLength={500}
            />
          </div>
          <button
            className="pf-btn pf-btn-outline-danger"
            onClick={ejecutarDestino}
            disabled={enCurso}
          >
            {enCurso ? 'Aplicando…' : destino?.a === 'suspend' ? 'Suspender' : 'Reactivar'}
          </button>
        </div>
      </Modal>
    </>
  )
}

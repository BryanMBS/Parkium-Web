/* Detalle de un cliente (tenant): pestañas General, Sedes, Administradores
 * y Plan y límites. Nada destructivo: sólo editar y crear. */

import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  plataforma,
  type AdminTenant,
  type Sede,
  type Tenant,
} from '../../api/platform'
import { Aviso, MensajeApi } from '../../components/ui/Aviso'
import { Modal } from '../../components/ui/Modal'

type Pestana = 'general' | 'sedes' | 'admins' | 'plan'

const PLANES = ['BASIC', 'PRO', 'ENTERPRISE'] as const
const PESTANAS: Array<{ id: Pestana; etiqueta: string }> = [
  { id: 'general', etiqueta: 'General' },
  { id: 'sedes', etiqueta: 'Sedes' },
  { id: 'admins', etiqueta: 'Administradores' },
  { id: 'plan', etiqueta: 'Plan y límites' },
]

export function PlatformClientDetailPage(): JSX.Element {
  const { id } = useParams()
  const tenantId = Number(id)

  const [tenant, setTenant] = useState<Tenant | null>(null)
  const [pestana, setPestana] = useState<Pestana>('general')
  const [error, setError] = useState<string | null>(null)
  const [mensaje, setMensaje] = useState<string | null>(null)
  const [cargando, setCargando] = useState(true)
  const [enCurso, setEnCurso] = useState(false)

  const cargar = useCallback(() => {
    if (!Number.isFinite(tenantId)) {
      setError('Cliente no encontrado.')
      setCargando(false)
      return
    }
    setCargando(true)
    plataforma
      .detalleTenant(tenantId)
      .then(setTenant)
      .catch((e) => setError(MensajeApi(e) || 'No se pudo cargar el cliente.'))
      .finally(() => setCargando(false))
  }, [tenantId])

  useEffect(() => { cargar() }, [cargar])

  async function guardarGeneral(e: React.FormEvent<HTMLFormElement>): Promise<void> {
    e.preventDefault()
    const f = new FormData(e.currentTarget)
    setEnCurso(true)
    setError(null)
    setMensaje(null)
    try {
      const r = await plataforma.parcharTenant(tenantId, {
        name: String(f.get('name') || '').trim(),
      })
      setTenant(r)
      setMensaje('Datos actualizados.')
    } catch (err) {
      setError(MensajeApi(err) || 'No se pudo guardar.')
    } finally {
      setEnCurso(false)
    }
  }

  async function guardarPlan(e: React.FormEvent<HTMLFormElement>): Promise<void> {
    e.preventDefault()
    const f = new FormData(e.currentTarget)
    setEnCurso(true)
    setError(null)
    setMensaje(null)
    try {
      const r = await plataforma.parcharTenant(tenantId, {
        plan: String(f.get('plan')),
        max_sites: Number(f.get('max_sites')),
        max_users: Number(f.get('max_users')),
        billing_cutoff_day: Number(f.get('corte')),
      })
      setTenant(r)
      setMensaje('Plan y límites actualizados.')
    } catch (err) {
      setError(MensajeApi(err) || 'No se pudo guardar.')
      setMensaje(null)
    } finally {
      setEnCurso(false)
    }
  }

  if (cargando) return <p role="status">Cargando cliente…</p>

  return (
    <>
      <p style={{ margin: 0 }}>
        <Link to="/plataforma/clientes" style={{ color: '#a78bfa' }}>← Volver a clientes</Link>
      </p>
      <h1 className="pf-titulo">{tenant?.name ?? 'Cliente'}</h1>
      <p className="pf-subtitulo">NIT {tenant?.nit}</p>

      <Aviso variante="error">{error}</Aviso>
      <Aviso variante="ok">{mensaje}</Aviso>

      <div className="pf-pestanias" aria-label="Secciones del cliente">
        {PESTANAS.map((p) => (
          <button
            key={p.id}
            className={pestana === p.id ? 'activo' : ''}
            onClick={() => setPestana(p.id)}
            aria-pressed={pestana === p.id}
          >
            {p.etiqueta}
          </button>
        ))}
      </div>

      {pestana === 'general' && tenant && (
        <div className="pf-tarjeta" style={{ maxWidth: 560 }}>
          <form onSubmit={guardarGeneral}>
            <div className="campo">
              <label htmlFor="pf-nombre-edit">Razón social</label>
              <input id="pf-nombre-edit" name="name" defaultValue={tenant.name} maxLength={120} required />
            </div>
            <button type="submit" className="pf-btn pf-btn-primario" disabled={enCurso}>
              Guardar
            </button>
          </form>
        </div>
      )}

      {pestana === 'sedes' && tenant && <PestanaSedes tenant={tenant} setError={setError} setMensaje={setMensaje} />}

      {pestana === 'admins' && tenant && <PestanaAdmins tenant={tenant} setError={setError} setMensaje={setMensaje} />}

      {pestana === 'plan' && tenant && (
        <div className="pf-tarjeta" style={{ maxWidth: 560 }}>
          <form onSubmit={guardarPlan}>
            <div className="pf-fila">
              <div className="campo">
                <label htmlFor="pf-plan-e">Plan</label>
                <select id="pf-plan-e" name="plan" defaultValue={tenant.plan}>
                  {PLANES.map((p) => <option key={p}>{p}</option>)}
                </select>
              </div>
              <div className="campo">
                <label htmlFor="pf-maxs-e">Máx. sedes</label>
                <input id="pf-maxs-e" name="max_sites" type="number" min={1} defaultValue={tenant.max_sites} />
              </div>
            </div>
            <div className="pf-fila">
              <div className="campo">
                <label htmlFor="pf-maxu-e">Máx. usuarios</label>
                <input id="pf-maxu-e" name="max_users" type="number" min={1} defaultValue={tenant.max_users} />
              </div>
              <div className="campo">
                <label htmlFor="pf-corte-e">Día de corte</label>
                <input id="pf-corte-e" name="corte" type="number" min={1} max={28} defaultValue={tenant.billing_cutoff_day} />
              </div>
            </div>
            <p style={{ color: '#8b88a0', fontSize: 12.5, marginTop: 0 }}>
              Uso actual: {tenant.sedes ?? 0}/{tenant.max_sites} sedes · {tenant.usuarios ?? 0}/{tenant.max_users} usuarios.
              Exigir más cupos que el uso actual no borra nada.
            </p>
            <button type="submit" className="pf-btn pf-btn-primario" disabled={enCurso}>
              Guardar
            </button>
          </form>
        </div>
      )}
    </>
  )
}

/** Pestaña de sedes: listado + alta + edición básica. */
function PestanaSedes({ tenant, setError, setMensaje }: {
  tenant: Tenant
  setError: (s: string | null) => void
  setMensaje: (s: string | null) => void
}): JSX.Element {
  const [sedes, setSedes] = useState<Sede[]>([])
  const [cargando, setCargando] = useState(true)
  const [editando, setEditando] = useState<{ s: Sede; campos: Partial<{ name: string; total_capacity: number }> } | null>(null)
  const [enCurso, setEnCurso] = useState(false)

  const cargar = useCallback(() => {
    setCargando(true)
    plataforma
      .listarSedes(tenant.id)
      .then(setSedes)
      .catch((e) => setError(MensajeApi(e)))
      .finally(() => setCargando(false))
  }, [tenant.id, setError])

  useEffect(() => { cargar() }, [cargar])

  async function crear(e: React.FormEvent<HTMLFormElement>): Promise<void> {
    e.preventDefault()
    const f = new FormData(e.currentTarget)
    const name = String(f.get('name') || '').trim()
    const cupos = Number(f.get('total_capacity') || 30)
    if (!name) {
      setError('El nombre de la sede es obligatorio.')
      return
    }
    setEnCurso(true)
    setError(null)
    try {
      await plataforma.crearSede(tenant.id, name, cupos)
      e.currentTarget.reset()
      setMensaje(`Sede «${name}» creada con tarifas y plantilla predeterminadas.`)
      cargar()
    } catch (err) {
      setError(MensajeApi(err) || 'No se pudo crear la sede.')
    } finally {
      setEnCurso(false)
    }
  }

  async function parchar(): Promise<void> {
    if (!editando) return
    setEnCurso(true)
    setError(null)
    try {
      await plataforma.parcharSede(tenant.id, editando.s.id, {
        name: editando.campos.name,
        total_capacity: editando.campos.total_capacity,
      })
      setEditando(null)
      setMensaje('Sede actualizada.')
      cargar()
    } catch (err) {
      setError(MensajeApi(err) || 'No se pudo actualizar la sede.')
    } finally {
      setEnCurso(false)
    }
  }

  return (
    <>
      <div className="pf-tarjeta" style={{ marginBottom: 16, maxWidth: 560 }}>
        <h2 style={{ margin: '0 0 10px', fontSize: 15 }}>Nueva sede</h2>
        <form onSubmit={crear}>
          <div className="pf-fila">
            <div className="campo">
              <label htmlFor="pf-sede-n">Nombre</label>
              <input id="pf-sede-n" name="name" maxLength={120} required />
            </div>
            <div className="campo">
              <label htmlFor="pf-cupos-n">Cupos totales</label>
              <input id="pf-cupos-n" name="total_capacity" type="number" min={0} defaultValue={30} />
            </div>
          </div>
          <button type="submit" className="pf-btn pf-btn-primario" disabled={enCurso}>
            Crear sede
          </button>
        </form>
      </div>

      {cargando && <p role="status">Cargando sedes…</p>}
      {!cargando && sedes.length === 0 && <p role="status" style={{ color: '#8b88a0' }}>No hay sedes todavía.</p>}

      <div className="pf-clientes">
        {sedes.map((s) => (
          <article className="pf-cliente" key={s.id}>
            <div className="cabecera">
              <span className="nombre">{s.name}</span>
              <span className={`pf-estado ${s.is_active ? 'active' : 'suspended'}`}>
                {s.is_active ? 'Activa' : 'Inactiva'}
              </span>
            </div>
            <span className="plan-linea">
              {s.total_capacity} cupos{s.address ? ` · ${s.address}` : ''}{s.phone ? ` · ${s.phone}` : ''}
            </span>
            <div className="acciones">
              <button
                className="pf-btn pf-btn-suave pf-btn-compacto"
                onClick={() => setEditando({ s, campos: { name: s.name, total_capacity: s.total_capacity } })}
              >
                Editar
              </button>
            </div>
          </article>
        ))}
      </div>

      <Modal titulo="Editar sede" abierto={editando !== null} alCerrar={() => setEditando(null)} ancho={480}>
        <div className="pf-tarjeta" style={{ boxShadow: 'none' }}>
          <div className="campo">
            <label htmlFor="pf-sede-e">Nombre</label>
            <input
              id="pf-sede-e"
              value={editando?.campos.name ?? ''}
              onChange={(e) => setEditando((x) => x && { ...x, campos: { ...x.campos, name: e.target.value } })}
              maxLength={120}
            />
          </div>
          <div className="campo">
            <label htmlFor="pf-cupos-e">Cupos totales</label>
            <input
              id="pf-cupos-e"
              type="number"
              min={0}
              value={editando?.campos.total_capacity ?? 0}
              onChange={(e) => setEditando((x) => x && { ...x, campos: { ...x.campos, total_capacity: Number(e.target.value) } })}
            />
          </div>
          <button className="pf-btn pf-btn-primario" onClick={parchar} disabled={enCurso}>
            Guardar
          </button>
        </div>
      </Modal>
    </>
  )
}

/** Pestaña de administradores: alta con contraseña temporal + «fijar» nueva. */
function PestanaAdmins({ tenant, setError, setMensaje }: {
  tenant: Tenant
  setError: (s: string | null) => void
  setMensaje: (s: string | null) => void
}): JSX.Element {
  const [admins, setAdmins] = useState<AdminTenant[]>([])
  const [cargando, setCargando] = useState(true)
  const [temporal, setTemporal] = useState<{ usuario: string; contrasena: string } | null>(null)
  const [reset, setReset] = useState<AdminTenant | null>(null)
  const [nueva, setNueva] = useState('')
  const [enCurso, setEnCurso] = useState(false)

  const cargar = useCallback(() => {
    setCargando(true)
    plataforma
      .listarAdmins(tenant.id)
      .then(setAdmins)
      .catch((e) => setError(MensajeApi(e)))
      .finally(() => setCargando(false))
  }, [tenant.id, setError])

  useEffect(() => { cargar() }, [cargar])

  async function crear(e: React.FormEvent<HTMLFormElement>): Promise<void> {
    e.preventDefault()
    const f = new FormData(e.currentTarget)
    const username = String(f.get('username') || '').trim()
    const nombre = String(f.get('nombre') || '').trim()
    const rol = String(f.get('rol') || 'ADMIN') as 'ADMIN' | 'SUPERADMIN'
    if (!username) {
      setError('El nombre de usuario es obligatorio.')
      return
    }
    setEnCurso(true)
    setError(null)
    try {
      const r = await plataforma.crearAdmin(tenant.id, username, nombre, rol)
      setTemporal({ usuario: r.usuario.username, contrasena: r.contrasena_temporal })
      e.currentTarget.reset()
      cargar()
    } catch (err) {
      setError(MensajeApi(err) || 'No se pudo crear el administrador.')
    } finally {
      setEnCurso(false)
    }
  }

  async function fijar(): Promise<void> {
    if (!reset || !nueva.trim()) {
      setError('Escribe la nueva contraseña.')
      return
    }
    setEnCurso(true)
    setError(null)
    try {
      await plataforma.fijarContrasenaAdmin(tenant.id, reset.id, nueva)
      setMensaje(`Contraseña fijada para ${reset.username}: sus sesiones activas quedan cerradas.`)
      setReset(null)
      setNueva('')
      cargar()
    } catch (err) {
      setError(MensajeApi(err) || 'No se pudo fijar la contraseña.')
    } finally {
      setEnCurso(false)
    }
  }

  return (
    <>
      <div className="pf-tarjeta" style={{ marginBottom: 16, maxWidth: 560 }}>
        <h2 style={{ margin: '0 0 10px', fontSize: 15 }}>Nuevo administrador</h2>
        <form onSubmit={crear}>
          <div className="pf-fila">
            <div className="campo">
              <label htmlFor="pf-adm-u">Usuario</label>
              <input id="pf-adm-u" name="username" maxLength={60} required />
            </div>
            <div className="campo">
              <label htmlFor="pf-adm-n">Nombre</label>
              <input id="pf-adm-n" name="nombre" maxLength={120} />
            </div>
            <div className="campo">
              <label htmlFor="pf-adm-r">Rol</label>
              <select id="pf-adm-r" name="rol" defaultValue="ADMIN">
                <option value="ADMIN">ADMIN</option>
                <option value="SUPERADMIN">SUPERADMIN</option>
              </select>
            </div>
          </div>
          <p style={{ color: '#8b88a0', fontSize: 12.5, marginTop: 0 }}>
            Recibirá una contraseña temporal y deberá cambiarla en su primer inicio de sesión.
          </p>
          <button type="submit" className="pf-btn pf-btn-primario" disabled={enCurso}>
            Crear administrador
          </button>
        </form>

        {temporal && (
          <div className="pf-tarjeta" style={{ marginTop: 12, borderColor: '#7c3aed' }}>
            <strong>{temporal.usuario}</strong> — contraseña temporal (mostrada una sola vez):
            <p className="mono" style={{ fontSize: 16, letterSpacing: 1, margin: '6px 0 0' }}>
              {temporal.contrasena}
            </p>
          </div>
        )}
      </div>

      {cargando && <p role="status">Cargando administradores…</p>}
      {!cargando && admins.length === 0 && <p role="status" style={{ color: '#8b88a0' }}>Sin administradores.</p>}

      <div className="pf-tarjeta">
        {admins.length > 0 && (
          <table className="tabla">
            <thead>
              <tr>
                <th scope="col">Usuario</th>
                <th scope="col">Nombre</th>
                <th scope="col">Rol</th>
                <th scope="col">Estado</th>
                <th scope="col">Acciones</th>
              </tr>
            </thead>
            <tbody>
              {admins.map((a) => (
                <tr key={a.id}>
                  <td className="mono">{a.username}</td>
                  <td>{a.full_name}</td>
                  <td>{a.rol}</td>
                  <td>{a.is_active ? 'Activo' : 'Inactivo'}</td>
                  <td>
                    <button
                      className="pf-btn pf-btn-suave pf-btn-compacto"
                      onClick={() => { setReset(a); setNueva('') }}
                    >
                      Fijar contraseña
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <Modal
        titulo={`Fijar contraseña de ${reset?.username ?? ''}`}
        abierto={reset !== null}
        alCerrar={() => { setReset(null); setNueva(''); setError(null) }}
        ancho={440}
      >
        <div className="pf-tarjeta" style={{ boxShadow: 'none' }}>
          <p style={{ marginTop: 0 }}>
            Entrégasela por un canal seguro: se puede fijar una definitiva para que el
            administrador entre de inmediato (sus sesiones activas se cierran).
          </p>
          <div className="campo">
            <label htmlFor="pf-nueva">Nueva contraseña</label>
            <input
              id="pf-nueva"
              type="password"
              autoComplete="new-password"
              value={nueva}
              onChange={(e) => setNueva(e.target.value)}
              maxLength={72}
            />
          </div>
          <button className="pf-btn pf-btn-primario" onClick={fijar} disabled={enCurso}>
            Fijar contraseña
          </button>
        </div>
      </Modal>
    </>
  )
}

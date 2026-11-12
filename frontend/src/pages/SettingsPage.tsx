import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { admin, type DatosSitio, type PlantillaRecibo, type Tarifa, type UsuarioLista } from '../api/admin'
import { auth } from '../api/auth'
import { useAuth } from '../hooks/useAuth'
import { Aviso, MensajeApi } from '../components/ui/Aviso'
import { aImporte } from '../lib/formato'
import { TIPOS_VEHICULO, ESQUEMAS_COBRO, ROLES } from '../theme/catalogos'

/** Configuración: 6 pestañas según rol (docs/02 §2.5, docs/04 §4.8):
 * 1) Mi perfil (todos) · 2) Tarifas · 3) Usuarios (admin+) ·
 * 4) Parqueadero · 5) Plantilla de recibo . */
export function SettingsPage(): JSX.Element {
  const { usuario } = useAuth()
  const esAdmin = usuario?.rol === 'ADMIN' || usuario?.rol === 'SUPERADMIN'
  const esSuper = usuario?.rol === 'SUPERADMIN'

  const PESTANAS = [
    ...(esAdmin
      ? ([
          { id: 'tarifas', nombre: 'Tarifas' },
          { id: 'usuarios', nombre: 'Usuarios' },
        ] as const)
      : []),
    ...(esSuper
      ? ([
          { id: 'sitio', nombre: 'Parqueadero' },
          { id: 'plantilla', nombre: 'Plantilla del recibo' },
        ] as const)
      : []),
    { id: 'perfil', nombre: 'Mi perfil' } as const,
  ]

  const [pestaña, setPestaña] = useState<string>(PESTANAS[0].id)

  return (
    <>
      <div className="titulo">
        <h1>Configuración</h1>
      </div>

      <div aria-label="Secciones de configuración" style={{ display: 'flex', gap: 6, marginBottom: 16, flexWrap: 'wrap' }}>
        {PESTANAS.map((p) => (
          <button
            key={p.id}
            onClick={() => setPestaña(p.id)}
            aria-pressed={pestaña === p.id}
            className={`btn btn-compacto ${pestaña === p.id ? 'btn-primario' : 'btn-suave'}`}
          >
            {p.nombre}
          </button>
        ))}
      </div>

      {pestaña === 'tarifas' && <TabTarifas />}
      {pestaña === 'usuarios' && <TabUsuarios />}
      {pestaña === 'sitio' && <TabSitio />}
      {pestaña === 'plantilla' && <TabPlantilla />}
      {pestaña === 'perfil' && <TabPerfil />}
    </>
  )
}

/* ------- Tarifas ------- */

function TabTarifas(): JSX.Element {
  const consulta = useQuery({ queryKey: ['tarifas'], queryFn: ({ signal }) => admin.tarifas(signal) })
  const [error, setError] = useState<string | null>(null)
  const [ok, setOk] = useState<string | null>(null)

  const crear = useMutation({
    mutationFn: (t: Tarifa) => admin.crearTarifa(t),
    onSuccess: () => setOk('Tarifa creada. Desde ahora los cobros la usarán.'),
    onError: (e) => setError(MensajeApi(e)),
  })

const lista: Tarifa[] = normalizaLista<Tarifa>(consulta.data)

  return (
    <div className="tarjeta">
      <h2>Tarifas vigentes</h2>
      <Aviso variante="error">{error}</Aviso>
      <Aviso variante="ok">{ok}</Aviso>
      <div className="contenedor-tabla" style={{ margin: '10px 0' }}>
        <table className="tabla">
          <thead>
            <tr>
              <th scope="col">Nombre</th>
              <th scope="col">Tipo</th>
              <th scope="col">Esquema</th>
              <th scope="col">Monto</th>
              <th scope="col">Gracia</th>
            </tr>
          </thead>
          <tbody>
            {lista.map((t) => (
              <tr key={t.id ?? `${t.tipo_vehiculo}-${t.nombre}`}>
                <td>{t.nombre}</td>
                <td>{t.tipo_vehiculo}</td>
                <td>
                  {ESQUEMAS_COBRO.find((e) => e.codigo === t.esquema)?.etiqueta ?? t.esquema}
                </td>
                <td className="importe">{t.monto}</td>
                <td>{t.gracia_minutos ?? '—'} min</td>
              </tr>
            ))}
            {lista.length === 0 && (
              <tr>
                <td colSpan={5} style={{ textAlign: 'center', color: 'var(--color-muted)' }}>
                  Sin tarifas aún: crea la primera abajo.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      <h3>Nueva tarifa</h3>
      <FormTarifa onSubmit={(t) => { setError(null); setOk(null); crear.mutate(t) }} enCurso={crear.isPending} />
    </div>
  )
}

function normalizaLista<T>(data: unknown): T[] {
  if (!data) return []
  if (Array.isArray(data)) return data as T[]
  const envueltos = (data as { tarifas?: unknown; usuarios?: unknown })
  const lista = envueltos.tarifas ?? envueltos.usuarios
  return (lista as T[]) ?? []
}

function FormTarifa({ onSubmit, enCurso }: { onSubmit: (t: Tarifa) => void; enCurso: boolean }): JSX.Element {
  const [nombre, setNombre] = useState('')
  const [tipo, setTipo] = useState('CAR')
  const [esquema, setEsquema] = useState('HOUR')
  const montoRef = useState('')
  const [monto, setMonto] = montoRef
  const [gracia, setGracia] = useState(5)

  return (
    <form
      className="fila"
      onSubmit={(e) => {
        e.preventDefault()
        const m = aImporte(monto)
        if (m == null) return
        onSubmit({ nombre, tipo_vehiculo: tipo, esquema, monto: m, gracia_minutos: esquema === 'HOUR' ? gracia : undefined })
      }}
    >
      <div className="campo" style={{ margin: 0 }}>
        <label htmlFor="tf-nombre">Nombre</label>
        <input id="tf-nombre" value={nombre} onChange={(e) => setNombre(e.target.value)} placeholder="Hora carro" required />
      </div>
      <div className="campo" style={{ margin: 0 }}>
        <label htmlFor="tf-tipo">Tipo</label>
        <select id="tf-tipo" value={tipo} onChange={(e) => setTipo(e.target.value)}>
          {TIPOS_VEHICULO.map((t) => (
            <option key={t.codigo} value={t.codigo}>{t.etiqueta}</option>
          ))}
        </select>
      </div>
      <div className="campo" style={{ margin: 0 }}>
        <label htmlFor="tf-esquema">Esquema</label>
        <select id="tf-esquema" value={esquema} onChange={(e) => setEsquema(e.target.value)}>
          {ESQUEMAS_COBRO.map((e) => (
            <option key={e.codigo} value={e.codigo}>{e.etiqueta}</option>
          ))}
        </select>
      </div>
      <div className="campo" style={{ margin: 0 }}>
        <label htmlFor="tf-monto">Monto</label>
        <input id="tf-monto" inputMode="decimal" value={monto} onChange={(e) => setMonto(e.target.value)} placeholder="5000" required />
      </div>
      {esquema === 'HOUR' && (
        <div className="campo" style={{ margin: 0, width: 120 }}>
          <label htmlFor="tf-gracia">Gracia (min)</label>
          <input id="tf-gracia" type="number" min={0} value={gracia} onChange={(e) => setGracia(Number(e.target.value) || 0)} />
        </div>
      )}
      <button type="submit" className="btn btn-primario" disabled={enCurso}>
        {enCurso ? 'Creando…' : 'Crear tarifa'}
      </button>
    </form>
  )
}

/* ------- Usuarios ------- */

function TabUsuarios(): JSX.Element {
  const { usuario } = useAuth()
  const consulta = useQuery({ queryKey: ['usuarios'], queryFn: ({ signal }) => admin.usuarios(signal) })
  const [error, setError] = useState<string | null>(null)
  const [ok, setOk] = useState<string | null>(null)
  const queryClient = useQueryClient()

  const invalidar = () => {
    void queryClient.invalidateQueries({ queryKey: ['usuarios'] })
  }
  const crear = useMutation({
    mutationFn: (c: { usuario: string; nombreCompleto: string; rol: string; contrasena: string }) =>
      admin.crearUsuario({
        usuario: c.usuario,
        nombre_completo: c.nombreCompleto,
        rol: c.rol,
        clave: c.contrasena,
      }),
    onSuccess: () => { setOk('Usuario creado.'); invalidar() },
    onError: (e) => setError(MensajeApi(e)),
  })
  const activar = useMutation({
    mutationFn: (v: { id: number; a: boolean }) => admin.cambiarActivo(v.id, v.a),
    onSuccess: (_r, v) => { setOk(v.a ? 'Usuario reactivado (se reconstituyen los accesos).' : 'Usuario desactivado: sus sesiones quedaron revocadas.'); invalidar() },
    onError: (e) => setError(MensajeApi(e)),
  })
  const resetear = useMutation({
    mutationFn: (v: { id: number; nueva: string }) => admin.fijarContrasena(v.id, v.nueva),
    onSuccess: () => { setOk('Contraseña restablecida.'); invalidar() },
    onError: (e) => setError(MensajeApi(e)),
  })

  const usuarios: UsuarioLista[] = normalizaLista<UsuarioLista>(consulta.data)
  const cargandoUsuarios = consulta.isPending && usuarios.length === 0

  return (
    <div className="tarjeta">
      <h2>Usuarios</h2>
      <Aviso variante="error">{error}</Aviso>
      <Aviso variante="ok">{ok}</Aviso>
      <p style={{ color: 'var(--color-muted)', fontSize: 13 }}>
        Los roles no son jerárquicos: son conjuntos (docs/07). Sólo el super administrador crea super administradores.
      </p>
      <div className="contenedor-tabla" style={{ margin: '10px 0' }}>
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
            {cargandoUsuarios && (
              <tr>
                <td colSpan={5}>
                  <span className="cargando">Cargando usuarios</span>
                </td>
              </tr>
            )}
            {usuarios.map((u) => (
              <FilaUsuario
                key={u.id}
                u={u}
                esYo={usuario?.id === u.id}
                onToggle={(a) => {
                  setError(null); setOk(null)
                  activar.mutate({ id: u.id, a })
                }}
                onReset={(n) => { setError(null); setOk(null); resetear.mutate({ id: u.id, nueva: n }) }}
              />
            ))}
          </tbody>
        </table>
      </div>
      <FormUsuario onSubmit={(c) => { setError(null); setOk(null); crear.mutate(c) }} enCurso={crear.isPending} />
    </div>
  )
}

function FilaUsuario({
  u,
  esYo,
  onToggle,
  onReset,
}: {
  u: UsuarioLista
  esYo: boolean
  onToggle: (activo: boolean) => void
  onReset: (nueva: string) => void
}): JSX.Element {
  const [nueva, setNueva] = useState('')
  return (
    <tr>
      <td style={{ fontFamily: 'var(--font-mono)' }}>{u.usuario}</td>
      <td>{u.nombre_completo}</td>
      <td>{ROLES.find((r) => r.codigo === u.rol)?.etiqueta ?? u.rol}</td>
      <td>
        <span className={`pill ${u.is_active ? 'pill-verde' : 'pill-rojo'}`}>{u.is_active ? 'Activo' : 'Inactivo'}</span>
      </td>
      <td>
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          {!esYo && (
            <button
              className={`btn btn-compacto ${u.is_active ? 'btn-peligro' : 'btn-exito'}`}
              onClick={() => onToggle(!u.is_active)}
            >
              {u.is_active ? 'Desactivar' : 'Reactivar'}
            </button>
          )}
          <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
            <input
              type="password"
              autoComplete="new-password"
              value={nueva}
              onChange={(e) => setNueva(e.target.value)}
              placeholder="nueva contraseña"
              aria-label={`Nueva contraseña de ${u.usuario}`}
              style={{ width: 160, border: '1px solid var(--color-field-border)', borderRadius: 8, padding: '6px 8px', background: 'var(--color-field-bg)', color: 'var(--color-text)' }}
            />
            <button
              className="btn btn-compacto btn-suave"
              disabled={nueva.length < 10}
              onClick={() => { onReset(nueva); setNueva('') }}
              title="Mínimo 10 caracteres (regla PASSWORD_MIN_LENGTH)"
            >
              Fijar
            </button>
          </div>
        </div>
      </td>
    </tr>
  )
}

function FormUsuario({
  onSubmit,
  enCurso,
}: {
  onSubmit: (c: { usuario: string; nombreCompleto: string; rol: string; contrasena: string }) => void
  enCurso: boolean
}): JSX.Element {
  const [usuario, setUsuario] = useState('')
  const [nombres, setNombres] = useState('')
  const [rol, setRol] = useState('OPERATOR')
  const [clave, setClave] = useState('')
  return (
    <form className="fila" onSubmit={(e) => { e.preventDefault(); onSubmit({ usuario, nombreCompleto: nombres, rol, contrasena: clave }) }}>
      <div className="campo" style={{ margin: 0 }}>
        <label htmlFor="us-u">Usuario</label>
        <input id="us-u" value={usuario} onChange={(e) => setUsuario(e.target.value)} required />
      </div>
      <div className="campo" style={{ margin: 0 }}>
        <label htmlFor="us-n">Nombre completo</label>
        <input id="us-n" value={nombres} onChange={(e) => setNombres(e.target.value)} required />
      </div>
      <div className="campo" style={{ margin: 0 }}>
        <label htmlFor="us-r">Rol</label>
        <select id="us-r" value={rol} onChange={(e) => setRol(e.target.value)}>
          {ROLES.map((r) => (
            <option key={r.codigo} value={r.codigo}>{r.etiqueta}</option>
          ))}
        </select>
      </div>
      <div className="campo" style={{ margin: 0 }}>
        <label htmlFor="us-c">Contraseña</label>
        <input id="us-c" type="password" value={clave} onChange={(e) => setClave(e.target.value)} required />
      </div>
      <button type="submit" className="btn btn-primario" disabled={enCurso || clave.length < 10}>
        {enCurso ? 'Creando…' : 'Crear usuario'}
      </button>
    </form>
  )
}

/* ------- Parqueadero ------- */

function TabSitio(): JSX.Element {
  const consulta = useQuery({ queryKey: ['sitio'], queryFn: () => admin.sitio() })
  const [datos, setDatos] = useState<DatosSitio | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [ok, setOk] = useState<string | null>(null)

  useEffect(() => {
    if (consulta.data) setDatos(consulta.data)
  }, [consulta.data])

  const guardar = useMutation({
    mutationFn: (d: DatosSitio) => admin.guardarSitio(d),
    onSuccess: () => setOk('Datos del parqueadero actualizados.'),
    onError: (e) => setError(MensajeApi(e)),
  })

  if (consulta.isLoading) return <div className="tarjeta">Cargando…</div>
  if (!datos) return <Aviso variante="error">{MensajeApi(consulta.error)}</Aviso>

  return (
    <div className="tarjeta" style={{ maxWidth: 560 }}>
      <h2>Datos del parqueadero</h2>
      <Aviso variante="error">{error}</Aviso>
      <Aviso variante="ok">{ok}</Aviso>
      <form onSubmit={(e) => { e.preventDefault(); guardar.mutate(datos) }}>
        <div className="campo">
          <label htmlFor="si-nombre">Nombre</label>
          <input id="si-nombre" value={datos.nombre} onChange={(e) => setDatos({ ...datos, nombre: e.target.value })} required />
        </div>
        <div className="fila">
          <div className="campo" style={{ margin: 0, flex: 1 }}>
            <label htmlFor="si-nit">NIT</label>
            <input id="si-nit" value={datos.nit ?? ''} onChange={(e) => setDatos({ ...datos, nit: e.target.value })} />
          </div>
          <div className="campo" style={{ margin: 0, flex: 1 }}>
            <label htmlFor="si-tel">Teléfono</label>
            <input id="si-tel" type="tel" inputMode="tel" autoComplete="tel" value={datos.telefono} onChange={(e) => setDatos({ ...datos, telefono: e.target.value })} />
          </div>
        </div>
        <div className="campo">
          <label htmlFor="si-dir">Dirección</label>
          <input id="si-dir" value={datos.direccion ?? ''} onChange={(e) => setDatos({ ...datos, direccion: e.target.value })} />
        </div>
        <div className="campo" style={{ width: 180 }}>
          <label htmlFor="si-cap">Capacidad total</label>
          <input
            id="si-cap"
            type="number"
            min={0}
            value={datos.capacidad_total}
            onChange={(e) => setDatos({ ...datos, capacidad_total: Number(e.target.value) || 0 })}
          />
        </div>
        <button type="submit" className="btn btn-primario" disabled={guardar.isPending}>
          {guardar.isPending ? 'Guardando…' : 'Guardar cambios'}
        </button>
      </form>
    </div>
  )
}

/* ------- Plantilla del recibo ------- */

function TabPlantilla(): JSX.Element {
  const consulta = useQuery({ queryKey: ['plantilla'], queryFn: () => admin.plantilla() })
  const [datos, setDatos] = useState<PlantillaRecibo | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [ok, setOk] = useState<string | null>(null)

  useEffect(() => {
    if (consulta.data) setDatos(consulta.data)
  }, [consulta.data])

  const guardar = useMutation({
    mutationFn: (d: PlantillaRecibo) => admin.guardarPlantilla(d),
    onSuccess: () => setOk('Plantilla guardada: marca en todos los comprobantes futuros.'),
    onError: (e) => setError(MensajeApi(e)),
  })

  if (consulta.isLoading) return <div className="tarjeta">Cargando…</div>
  if (!datos) return <Aviso variante="error">{MensajeApi(consulta.error)}</Aviso>

  return (
    <div className="tarjeta" style={{ maxWidth: 640 }}>
      <h2>Plantilla de comprobantes</h2>
      <Aviso variante="error">{error}</Aviso>
      <Aviso variante="ok">{ok}</Aviso>
      <form onSubmit={(e) => { e.preventDefault(); guardar.mutate(datos) }}>
        <div className="fila">
          <div className="campo" style={{ margin: 0, flex: 1 }}>
            <label htmlFor="pt-nombre">Nombre de la plantilla</label>
            <input id="pt-nombre" value={datos.nombre_plantilla} onChange={(e) => setDatos({ ...datos, nombre_plantilla: e.target.value })} />
          </div>
          <div className="campo" style={{ margin: 0, flex: 1 }}>
            <label htmlFor="pt-parq">Nombre del parqueadero</label>
            <input id="pt-parq" value={datos.nombre_parqueadero} onChange={(e) => setDatos({ ...datos, nombre_parqueadero: e.target.value })} />
          </div>
        </div>
        <div className="fila">
          <div className="campo" style={{ margin: 0, flex: 1 }}>
            <label htmlFor="pt-nit">NIT</label>
            <input id="pt-nit" value={datos.nit ?? ''} onChange={(e) => setDatos({ ...datos, nit: e.target.value })} />
          </div>
          <div className="campo" style={{ margin: 0, flex: 1 }}>
            <label htmlFor="pt-dir">Dirección</label>
            <input id="pt-dir" value={datos.direccion ?? ''} onChange={(e) => setDatos({ ...datos, direccion: e.target.value })} />
          </div>
        </div>
        <div className="campo">
          <label htmlFor="pt-encabezado">Encabezado (opcional)</label>
          <textarea id="pt-encabezado" rows={2} value={datos.encabezado ?? ''} onChange={(e) => setDatos({ ...datos, encabezado: e.target.value })} />
        </div>
        <div className="campo">
          <label htmlFor="pt-term">Términos y condiciones</label>
          <textarea id="pt-term" rows={3} value={datos.terminos ?? ''} onChange={(e) => setDatos({ ...datos, terminos: e.target.value })} />
        </div>
        <div className="campo">
          <label htmlFor="pt-pie">Pie</label>
          <textarea id="pt-pie" rows={2} value={datos.pie ?? ''} onChange={(e) => setDatos({ ...datos, pie: e.target.value })} />
        </div>
        <label style={{ display: 'flex', gap: 8, alignItems: 'center', fontSize: 14 }}>
          <input
            type="checkbox"
            checked={datos.mostrar_codigo_barras}
            onChange={(e) => setDatos({ ...datos, mostrar_codigo_barras: e.target.checked })}
          />
          Mostrar código de barras en los comprobantes
        </label>
        <label style={{ display: 'flex', gap: 8, alignItems: 'center', fontSize: 14, marginTop: 6 }}>
          <input type="checkbox" checked={datos.mostrar_qr} onChange={(e) => setDatos({ ...datos, mostrar_qr: e.target.checked })} />
          Mostrar QR de verificación pública
        </label>
        <div style={{ marginTop: 14 }}>
          <button type="submit" className="btn btn-primario" disabled={guardar.isPending}>
            {guardar.isPending ? 'Guardando…' : 'Guardar plantilla'}
          </button>
        </div>
      </form>
    </div>
  )
}

/* ------- Mi perfil ------- */

function TabPerfil(): JSX.Element {
  const [error, setError] = useState<string | null>(null)
  const [ok, setOk] = useState<string | null>(null)
  const cambio = useMutation({
    mutationFn: (v: { actual: string; nueva: string }) => auth.cambiarContrasena(v.actual, v.nueva),
    onSuccess: (r) => { setOk(r.mensaje); setError(null) },
    onError: (e) => setError(MensajeApi(e)),
  })

  return (
    <div className="tarjeta" style={{ maxWidth: 460 }}>
      <h2>Mi perfil</h2>
      <Aviso variante="error">{error}</Aviso>
      <Aviso variante="ok">{ok}</Aviso>
      <form
        onSubmit={(e) => { e.preventDefault(); setOk(null) }}
      >
        <CambiarClaveForm
          alEnviar={(actual, nueva) => {
            setOk(null)
            cambio.mutate({ actual, nueva })
          }}
          enCurso={cambio.isPending}
        />
      </form>
    </div>
  )
}

function CambiarClaveForm({ alEnviar, enCurso }: { alEnviar: (a: string, n: string) => void; enCurso: boolean }): JSX.Element {
  const [actual, setActual] = useState('')
  const [nueva, setNueva] = useState('')
  return (
    <>
      <div className="campo">
        <label htmlFor="pf-actual">Contraseña actual</label>
        <input id="pf-actual" type="password" value={actual} onChange={(e) => setActual(e.target.value)} autoComplete="current-password" />
      </div>
      <div className="campo">
        <label htmlFor="pf-nueva">Contraseña nueva (mínimo 10)</label>
        <input id="pf-nueva" type="password" value={nueva} onChange={(e) => setNueva(e.target.value)} autoComplete="new-password" required />
      </div>
      <button
        type="button"
        className="btn btn-primario"
        disabled={enCurso || nueva.length < 10}
        onClick={() => { alEnviar(actual, nueva); setActual(''); setNueva('') }}
      >
        {enCurso ? 'Cambiando…' : 'Cambiar contraseña'}
      </button>
      <p style={{ color: 'var(--color-muted)', fontSize: 12, marginTop: 10 }}>
        Al cambiarla se revocan todas tus demás sesiones (docs/04 §4.2).
      </p>
    </>
  )
}

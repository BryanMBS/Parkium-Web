import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { auth } from '../api/auth'
import { useAuth } from '../hooks/useAuth'
import { Aviso, MensajeApi } from '../components/ui/Aviso'

/** Login con cristal (docs/06 §6.8): login_bg.jpg de fondo, tarjeta 440 px,
 * radio 26, fondo en el reparto 55,5 % para que la marca se vea a la izquierda.
 * Incluye el alta del primer superusuario (/docs/04 §4.2, cerrado tras usar). */
export function LoginPage(): JSX.Element {
  const [usuario, setUsuario] = useState('')
  const [contrasena, setContrasena] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [enCurso, setEnCurso] = useState(false)

  const [primeraVez, setPrimeraVez] = useState(false)
  const [nombreCompleto, setNombreCompleto] = useState('')

  const navegar = useNavigate()
  const { iniciar } = useAuth()

  async function iniciarSesion(e: React.FormEvent): Promise<void> {
    e.preventDefault()
    setError(null)
    setEnCurso(true)
    try {
      let rol: string
      if (primeraVez) {
        const r = await auth.primerUsuario(nombreCompleto || usuario, contrasena)
        iniciar(r.usuario)
        rol = r.usuario.rol
      } else {
        const r = await auth.login(usuario, contrasena)
        iniciar(r.usuario)
        rol = r.usuario.rol
      }
      // El administrador de plataforma entra a su espacio, nunca al operativo.
      navegar(rol === 'PLATFORM_ADMIN' ? '/plataforma' : '/', { replace: true })
    } catch (err) {
      setError(MensajeApi(err))
    } finally {
      setEnCurso(false)
    }
  }

  return (
    <div className="login">
      <div className="zona-marca">
        <span>Parkium · sistema de administración de parqueaderos</span>
      </div>
      <main className="zona-tarjeta">
        <form className="cristal" onSubmit={iniciarSesion}>
          <div className="logo">
            <img src="/marca/logo.png" alt="" />
          </div>
          <h1 className="titulo">Bienvenido de nuevo</h1>
          {primeraVez ? (
            <p className="subtitulo">Primera ejecución: crea el super administrador del sistema.</p>
          ) : (
            <p className="subtitulo">Ingresa tu usuario para gestionar el parqueadero.</p>
          )}

          {primeraVez && (
            <div className="campo">
              <label htmlFor="log-nombre">Nombre completo</label>
              <input
                id="log-nombre"
                autoComplete="name"
                value={nombreCompleto}
                onChange={(e) => setNombreCompleto(e.target.value)}
              />
            </div>
          )}

          <div className="campo">
            <label htmlFor="log-usuario">Usuario</label>
            <input
              id="log-usuario"
              autoComplete="username"
              value={usuario}
              onChange={(e) => setUsuario(e.target.value)}
              required
              autoFocus
            />
          </div>

          <div className="campo">
            <label htmlFor="log-clave">Contraseña</label>
            <input
              id="log-clave"
              type="password"
              autoComplete={primeraVez ? 'new-password' : 'current-password'}
              value={contrasena}
              onChange={(e) => setContrasena(e.target.value)}
              required
            />
            {!primeraVez && (
              <span className="ayuda" style={{ color: 'rgba(255,255,255,.5)' }}>
                <Link to="/recuperar" style={{ color: 'rgba(255,255,255,.6)' }}>¿Olvidaste tu contraseña?</Link>
              </span>
            )}
          </div>

          <Aviso variante="error" anunciar="assertive">{error}</Aviso>

          <button type="submit" className="btn btn-primario" disabled={enCurso}>
            {enCurso ? 'Ingresando…' : primeraVez ? 'Crear super administrador' : 'Ingresar'}
          </button>

          <p className="pie">
            {primeraVez ? (
              <>¿Ya existe un usuario? <button type="button" className="enlace" onClick={() => setPrimeraVez(false)}>Entrar con sesión</button></>
            ) : (
              <>Primera ejecución aquí: <button type="button" className="enlace" onClick={() => setPrimeraVez(true)}>crear super administrador</button></>
            )}
          </p>
        </form>
      </main>
    </div>
  )
}

/** Nota: el cuadro de primera ejecución sólo funciona si no hay usuarios; el
 * backend responde 409 conflicto cuando ya quedó cerrado (docs/12 §2). */

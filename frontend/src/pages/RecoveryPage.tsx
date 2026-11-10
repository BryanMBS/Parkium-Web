import { Link } from 'react-router-dom'
import { Aviso } from '../components/ui/Aviso'

/** Recuperación (docs/12 §2, decisión A): NO se expone por HTTP.
 * La única vía es el servidor en consola: scripts/reset-admin.py. */
export function RecoveryPage(): JSX.Element {
  return (
    <main className="pagina" style={{ maxWidth: 640, margin: '48px auto' }}>
      <div className="tarjeta">
        <h1>Recuperación de acceso</h1>
        <Aviso variante="aviso">
          La recuperación de cuentas no se publica en la web: expone un mecanismo
          de escalado de privilegios. La decisión del proyecto (docs/12 §2) es
          ofrecerla sólo por consola del servidor.
        </Aviso>
        <p>En el servidor:</p>
        <pre style={{ background: 'var(--color-surface-alt)', padding: '12px 14px', borderRadius: 10, overflowX: 'auto' }}>
          <code>
            {`# en la carpeta backend/\npython scripts/reset-admin.py`}
          </code>
        </pre>
        <p>
          Le presentará las opciones: restablecer una contraseña puntual o
          destruir todas las sesiones activas si se sospecha de un robo de
          sesión. Requiere acceso al equipo servidor, exactamente como en un
          datacenter real.
        </p>
        <Link to="/login" className="btn btn-fantasma" style={{ marginTop: 8, display: 'inline-flex' }}>
          ← Volver al login
        </Link>
      </div>
    </main>
  )
}

import { Link } from 'react-router-dom'

export function NotFoundPage(): JSX.Element {
  return (
    <div style={{ textAlign: 'center', padding: '60px 20px' }}>
      <h1>404</h1>
      <p>La vista que buscas no existe en Parkium.</p>
      <Link to="/" className="btn btn-primario">
        Volver al Dashboard
      </Link>
    </div>
  )
}

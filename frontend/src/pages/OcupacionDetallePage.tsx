import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { historico } from '../api/historico'
import { Aviso, MensajeApi } from '../components/ui/Aviso'
import { ESTADOS_ESTADIA } from '../theme/catalogos'

/** Detalle de ocupación (docs/04 §4.5): debe contar exactamente lo mismo que
 * el gráfico — el criterio temporal (entró antes de que terminara la hora y
 * no había salido), no el estado de cobro. */
export function OcupacionDetallePage(): JSX.Element {
  const { dia = '', hora = '0' } = useParams()
  const h = Number(hora)

  const detalle = useQuery({
    queryKey: ['ocupacion-detalle', dia, h],
    queryFn: ({ signal }) => historico.ocupacionDetalle(dia, h, signal),
    enabled: h >= 0 && h <= 23,
    retry: 1,
  })

  return (
    <>
      <div className="titulo">
        <h1>
          Detalle de ocupación · {dia} {String(h).padStart(2, '0')}:00
        </h1>
      </div>

      <Link to="/" className="btn btn-fantasma" style={{ marginBottom: 14, display: 'inline-flex' }}>
        ← Volver al dashboard
      </Link>
      {(h < 0 || h > 23) && <Aviso variante="error">La hora debe estar entre 0 y 23.</Aviso>}
      {detalle.isError && <Aviso variante="error">{MensajeApi(detalle.error)}</Aviso>}

      {detalle.data && (
        <div className="contenedor-tabla">
          <table className="tabla">
            <thead>
              <tr>
                <th scope="col">Placa</th>
                <th scope="col">Tipo</th>
                <th scope="col">Celda</th>
                <th scope="col">Ingreso</th>
                <th scope="col">Horas dentro</th>
                <th scope="col">Estado</th>
              </tr>
            </thead>
            <tbody>
              {detalle.data.vehiculos.map((v) => (
                <tr key={v.estadia_id}>
                  <td style={{ fontFamily: 'var(--font-mono)', fontWeight: 700 }}>{v.placa}</td>
                  <td>{v.tipo_vehiculo}</td>
                  <td>{v.celda ?? '—'}</td>
                  <td>{v.ingreso_local}</td>
                  <td>{v.horas_dentro.toFixed(1)}</td>
                  <td>{ESTADOS_ESTADIA[v.estado] ?? v.estado}</td>
                </tr>
              ))}
              {detalle.data.vehiculos.length === 0 && (
                <tr>
                  <td colSpan={6} style={{ textAlign: 'center', color: 'var(--color-muted)' }}>
                    Ningún vehículo presente en esa franja (cuenta exactamente igual que el gráfico).
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </>
  )
}

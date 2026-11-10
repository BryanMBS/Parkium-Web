import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { reportes } from '../api/reports'
import { Aviso, MensajeApi } from '../components/ui/Aviso'
import { DatePicker, isoDe, leerFecha } from '../components/DatePicker/DatePicker'
import { dinero } from '../lib/formato'

/** Reportes (docs/04 §4.9) — sólo super administrador. Por defecto los
 * últimos 30 días. Las 5 exportaciones del contrato: CSV (BOM), JSON (importes
 * como texto), XLSX de una hoja, PDF de marca y XLSX completo (5 hojas + 2
 * gráficos). */
export function ReportsPage(): JSX.Element {
  const fechasBase = () => {
    const hasta = new Date()
    const desde = new Date()
    desde.setDate(desde.getDate() - 30)
    return { desde: isoDe(desde), hasta: isoDe(hasta) }
  }
  /** fix UX-S025: el estado se llama «rango» pero guarda desde/hasta */
  const [rango, setRango] = useState(fechasBase())
  const { desde: d0, hasta: h0 } = rango

  const d = leerFecha(d0)
  const h = leerFecha(h0)
  const rangoInvalido = d != null && h != null && d > h
  /** fix UX-S015: fecha escrita a mano no parsea → aviso y no consulta */
  const fechaInvalida = (d0.trim() !== '' && d == null) || (h0.trim() !== '' && h == null)

  const consulta = useQuery({
    queryKey: ['resumen', d, h],
    queryFn: ({ signal }) => reportes.resumen(d!, h!, signal),
    enabled: !rangoInvalido && !fechaInvalida && d != null && h != null,
  })

  const filaCSV = `/api/reports/summary.csv?desde=${d}&hasta=${h}`
  const filaJSON = `/api/reports/summary.json?desde=${d}&hasta=${h}`
  const filaXLSX = `/api/reports/summary.xlsx?desde=${d}&hasta=${h}`
  const filaPDF = `/api/reports/summary.pdf?desde=${d}&hasta=${h}`
  const filaCompleto = `/api/reports/full.xlsx?desde=${d}&hasta=${h}`

  return (
    <>
      <div className="titulo">
        <h1>Reportes</h1>
      </div>

      <div className="tarjeta" style={{ marginBottom: 14 }}>
        <div className="fila" style={{ alignItems: 'flex-end' }}>
          <div className="campo">
            <label htmlFor="rp-desde">Desde</label>
            <DatePicker id="rp-desde" etiqueta="Desde" valor={d0} alCambiar={(v) => setRango((f) => ({ ...f, desde: v }))} />
          </div>
          <div className="campo">
            <label htmlFor="rp-hasta">Hasta</label>
            <DatePicker id="rp-hasta" etiqueta="Hasta" valor={h0} alCambiar={(v) => setRango((f) => ({ ...f, hasta: v }))} />
          </div>
        </div>
        {rangoInvalido && (
          <Aviso variante="aviso">El rango es inválido: «desde» es mayor que «hasta».</Aviso>
        )}
        {fechaInvalida && (
          <Aviso variante="aviso">Hay una fecha no válida: corrígela (DD/MM/AAAA o AAAA-MM-DD).</Aviso>
        )}
        {d != null && h != null && !rangoInvalido && (
          <div className="fila" style={{ alignItems: 'flex-end' }}>
            <a href={filaCSV} className="btn btn-suave" download>
              ⤓ CSV (Excel, BOM)
            </a>
            <a href={filaJSON} className="btn btn-suave" download>
              ⤓ JSON
            </a>
            <a href={filaXLSX} className="btn btn-suave" download>
              ⤓ XLSX (una hoja)
            </a>
            <a href={filaPDF} className="btn btn-suave" download>
              ⤓ PDF (estilo de marca)
            </a>
            <a href={filaCompleto} className="btn btn-suave" download>
              ⤓ XLSX completo (5 hojas)
            </a>
          </div>
        )}
      </div>

      {consulta.isError && <Aviso variante="error">{MensajeApi(consulta.error)}</Aviso>}
      {consulta.isLoading && <div className="tarjeta cargando">Calculando el resumen</div>}

      {consulta.data && (
        <>
          <div className="rejilla rejilla-3" style={{ marginBottom: 16 }}>
            <div className="tarjeta metrica">
              <div className="etiqueta">Rotación de cobros</div>
              <div className="cifra importe">{dinero(consulta.data.rotacion)}</div>
            </div>
            <div className="tarjeta metrica">
              <div className="etiqueta">Mensualidades</div>
              <div className="cifra importe">{dinero(consulta.data.mensualidades)}</div>
            </div>
            <div className="tarjeta metrica">
              <div className="etiqueta">Total facturado</div>
              <div className="cifra importe" style={{ color: 'var(--color-primary)' }}>
                {dinero(consulta.data.total ?? String(Number(consulta.data.rotacion) + Number(consulta.data.mensualidades)))}
              </div>
            </div>
          </div>

          <div className="rejilla rejilla-2">
            <TablaCortes titulo="Por forma de pago" filas={consulta.data.por_metodo} />
            <TablaCortes titulo="Por tipo de vehículo" filas={consulta.data.por_tipo_vehiculo} />
            <TablaCortes titulo="Por empleado" filas={consulta.data.por_empleado} />
            <TablaCortes titulo="Por tarifa" filas={consulta.data.por_tarifa} />
          </div>
        </>
      )}
    </>
  )
}

function TablaCortes({
  titulo,
  filas,
}: {
  titulo: string
  filas: Array<{ etiqueta: string; valor: string; cantidad: number }>
}): JSX.Element {
  return (
    <div className="tarjeta">
      <h2>{titulo}</h2>
      <div className="contenedor-tabla">
        <table className="tabla">
          <thead>
            <tr>
              <th scope="col">Concepto</th>
              <th scope="col">Cobros</th>
              <th scope="col" style={{ textAlign: 'right' }}>Importe</th>
            </tr>
          </thead>
          <tbody>
            {(filas ?? []).map((f) => (
              <tr key={f.etiqueta}>
                <td>{f.etiqueta}</td>
                <td>{f.cantidad}</td>
                <td className="importe" style={{ textAlign: 'right' }}>
                  {dinero(f.valor)}
                </td>
              </tr>
            ))}
            {!(filas ?? []).length && (
              <tr>
                <td colSpan={3} style={{ textAlign: 'center', color: 'var(--color-muted)' }}>
                  Sin datos en el rango.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}

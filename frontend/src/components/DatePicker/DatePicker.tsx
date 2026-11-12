/** Calendario emergente (docs/06 §6.10, reglas de app/ui/calendar_popup.py).
 * - salida YYYY-MM-DD; semana empieza lunes
 * - días fuera del mes / fines de semana / fuera de rango: atenuados
 * - botones «Hoy» y «Cancelar»
 * - el campo acepta texto: 2026-10-06, 06/10/2026, 06.10.2026, 6-10-26
 *   (lectura por posición: 6-10-26 es 6 de octubre, no 26 de octubre del 2006)
 * fix UX-S005: acepta `id` para que los labels `htmlFor` ubiquen el campo.
 * fix UX-S006: Esc y clic-fuera cierran, `aria-expanded` en el disparador,
 * cada día lleva aria-label de fecha completa y `aria-current` en hoy.
 */

import { useEffect, useMemo, useRef, useState } from 'react'
import { ETIQUETAS_HORA } from '../../theme/catalogos'

const MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
  'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']

/** Parse tolerante; devuelve YYYY-MM-DD o null. */
export function leerFecha(texto: string): string | null {
  const s = texto.trim()
  if (!s) return null
  let d: number, m: number, a: number

  if (/^\d{4}[-./]\d{1,2}[-./]\d{1,2}$/.test(s)) {
    // AAAA-MM-DD (o el separador que lleve)
    const p = s.split(/[-./]/)
    a = +p[0]; m = +p[1]; d = +p[2]
  } else if (/^\d{1,2}[-./]\d{1,2}[-./]\d{2,4}$/.test(s)) {
    const p = s.split(/[-./]/)
    d = +p[0]; m = +p[1]
    a = +p[2]
    if (a < 100) a = 2000 + a
  } else {
    return null
  }
  if (m < 1 || m > 12 || d < 1 || d > 31) return null
  const fecha = new Date(a, m - 1, d)
  if (fecha.getMonth() !== m - 1 || fecha.getDate() !== d) return null // p.ej. 31/02
  return isoDe(fecha)
}

export function isoDe(f: Date): string {
  const p = (n: number) => String(n).padStart(2, '0')
  return `${f.getFullYear()}-${p(f.getMonth() + 1)}-${p(f.getDate())}`
}

function hoyFecha(): string {
  return isoDe(new Date())
}

function nombreMes(a: number, m0: number): string {
  return `${MESES[m0].charAt(0).toUpperCase() + MESES[m0].slice(1)} ${a}`
}

export function DatePicker({
  etiqueta,
  valor,
  alCambiar,
  id,
}: {
  etiqueta: string
  valor: string
  alCambiar: (iso: string) => void
  id?: string
}): JSX.Element {
  const [abierto, setAbierto] = useState(false)
  const [vista, setVista] = useState(() => {
    const base = valor || hoyFecha()
    const [a, m] = base.split('-').map(Number)
    return { anio: a, mes0: m - 1 }
  })
  const contenedor = useRef<HTMLDivElement>(null)

  const hoy = hoyFecha()
  /** hoy en número de día de semana: 0 dom … 6 sáb → desfase lunes=0 */
  const bloom = useMemo(() => {
    if (!/^(\d{4})-(\d{2})-(\d{2})$/.test(valor)) return null
    const [a, m, d] = valor.split('-').map(Number)
    return { a, m0: m - 1, d }
  }, [valor])

  /** fix UX-S015: feedback de fecha no válida (texto presente pero no parsea). */
  const textoInvalido = useMemo(
    () => valor.trim() !== '' && leerFecha(valor) === null,
    [valor],
  )

  function abrirEn(v: string): void {
    const obtenido = leerFecha(v) ?? hoy
    const [a, m] = obtenido.split('-').map(Number)
    setVista({ anio: a, mes0: m - 1 })
    setAbierto((x) => !x)
  }

  function aceptar(iso: string): void {
    alCambiar(iso)
    setAbierto(false)
  }

  function moverMes(delta: number): void {
    setVista((v) => {
      const mes = v.mes0 + delta
      return { anio: v.anio + Math.floor(mes / 12), mes0: ((mes % 12) + 12) % 12 }
    })
  }

  /** fix UX-S006: cerrar con clic fuera y con Esc. */
  useEffect(() => {
    if (!abierto) return
    const clic = (e: MouseEvent) => {
      if (contenedor.current && !contenedor.current.contains(e.target as Node)) {
        setAbierto(false)
      }
    }
    document.addEventListener('mousedown', clic)
    return () => document.removeEventListener('mousedown', clic)
  }, [abierto])

  /** matriz del mes: primer lunes de la rejilla */
  const semanas = useMemo(() => {
    const primero = new Date(vista.anio, vista.mes0, 1)
    let desfase = primero.getDay() - 1 // lunes = 0
    if (desfase < 0) desfase = 6
    const diasMes = new Date(vista.anio, vista.mes0 + 1, 0).getDate()
    const celdas: Array<{ d: number | null; finSemana: boolean }> = []
    for (let i = 0; i < desfase; i++) celdas.push({ d: null, finSemana: false })
    for (let d = 1; d <= diasMes; d++) {
      const dow = new Date(vista.anio, vista.mes0, d).getDay()
      celdas.push({ d, finSemana: dow === 0 || dow === 6 })
    }
    while (celdas.length % 7 !== 0) celdas.push({ d: null, finSemana: false })
    return celdas
  }, [vista])

  const fechaLarga = (d: number): string =>
    `${d} de ${MESES[vista.mes0]} de ${vista.anio}`

  return (
    <div
      className="picker"
      ref={contenedor}
      onKeyDown={(e) => {
        // Esc cierra el calendario aunque el foco esté en el disparador o en un día
        if (e.key === 'Escape' && abierto) {
          e.stopPropagation()
          setAbierto(false)
          contenedor.current?.querySelector('input')?.focus()
        }
      }}
    >
      <input
        type="text"
        inputMode="numeric"
        id={id}
        aria-label={etiqueta}
        aria-invalid={textoInvalido || undefined}
        placeholder="DD/MM/AAAA"
        value={valor}
        onChange={(e) => alCambiar(e.target.value)}
        onBlur={(e) => {
          const iso = leerFecha(e.target.value)
          if (iso) alCambiar(iso)
        }}
        onFocus={(e) => {
          // clic en campo vacío: abre el calendario; con texto deja el cursor
          if (e.target.value === '') abrirEn('')
        }}
      />
      <button
        type="button"
        className="glifo-calendario"
        aria-label={`Abrir calendario de ${etiqueta}`}
        aria-expanded={abierto}
        aria-haspopup="dialog"
        onClick={() => abrirEn(valor)}
      >
        ▦
      </button>
      {textoInvalido && (
        <span className="error-campo" role="alert">
          Fecha no válida: usa DD/MM/AAAA, AAAA-MM-DD o 6-10-26.
        </span>
      )}
      {abierto && (
        <div className="calendario" role="dialog" aria-label={`Calendario · ${etiqueta}`}>
          <div className="cabecera-cal">
            <button type="button" className="nav-mes" onClick={() => moverMes(-1)} aria-label="Mes anterior">
              ‹
            </button>
            <span className="mes">{nombreMes(vista.anio, vista.mes0)}</span>
            <button type="button" className="nav-mes" onClick={() => moverMes(1)} aria-label="Mes siguiente">
              ›
            </button>
          </div>
          <div className="dias">
            {ETIQUETAS_HORA.map((n) => (
              <span key={n} className="dia-semana">{n}</span>
            ))}
            {semanas.map((c, i) => (
              c.d === null ? (
                <span key={i} />
              ) : (
                <button
                  key={i}
                  type="button"
                  title={fechaLarga(c.d)}
                  className={`dia${c.finSemana ? ' atenuado' : ''}${
                    bloom && bloom.m0 === vista.mes0 && bloom.a === vista.anio && bloom.d === c.d ? ' seleccionado' : ''
                  }${hoy === isoDe(new Date(vista.anio, vista.mes0, c.d)) ? ' hoy' : ''}`}
                  aria-label={fechaLarga(c.d)}
                  aria-current={hoy === isoDe(new Date(vista.anio, vista.mes0, c.d)) ? 'date' : undefined}
                  onClick={() => aceptar(isoDe(new Date(vista.anio, vista.mes0, c.d as number)))}
                >
                  {c.d}
                </button>
              )
            ))}
          </div>
          <div className="pie-cal">
            <button type="button" className="btn btn-suave btn-compacto" onClick={() => setAbierto(false)}>
              Cancelar
            </button>
            <button type="button" className="btn btn-suave btn-compacto" onClick={() => aceptar(hoy)}>
              Hoy
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

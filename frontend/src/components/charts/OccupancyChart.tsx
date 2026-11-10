/** Gráfico de ocupación (docs/06 §6.9, reglas de app/ui/occupancy_chart.py).
 * - área de dibujo 190 px, sin ejes
 * - escala 1-2-3-5 por potencia de diec
 * - líneas de rejilla: el mayor divisor de (5,4,3,2) que divida el tope
 * - el tope NO es la capacidad; la capacidad va como línea de referencia
 * - el cursor sigue con línea vertical
 */

import { useState, type TouchEvent } from 'react'

export const ALTO_GRAFICO = 190
export const TICAS_HORA = ['00', '03', '06', '09', '12', '15', '18', '21']

interface Props {
  capacidadTotal: number
  puntos: Array<{ hora: number; ocupados: number }>
  alto?: number
}

/** Escala redonda: el mayor entero de la serie 1-2-3-5·10^k que supere el máximo. */
function escala(maximo: number): number {
  const k = Math.max(0, Math.floor(Math.log10(Math.max(maximo, 1))))
  const base = [1, 2, 3, 5].map((c) => c * 10 ** k)
  const tope = base.find((v) => v >= maximo) ?? maximo * 1.25
  return Math.max(1, tope)
}

function mejoresDivisores(tope: number): number {
  for (const n of [5, 4, 3, 2]) if (tope % n === 0) return n
  return 4
}

export function OccupancyChart({ capacidadTotal, puntos, alto = ALTO_GRAFICO }: Props): JSX.Element {
  const [cursor, setCursor] = useState<number | null>(null)

  const W = 720 // ancho virtual; el SVG escala con CSS
  const ANCHO_IZQ = 30
  const anchoPlot = W - ANCHO_IZQ - 8
  const maximo = Math.max(...puntos.map((p) => p.ocupados), 1)
  const tope = escala(maximo)
  const rejilla = mejoresDivisores(tope)
  const yDe = (v: number): number => alto - (v / tope) * alto

  const xDe = (hora: number): number =>
    ANCHO_IZQ + (hora / 23) * anchoPlot

  const capadentro = capacidadTotal <= tope

  const linea = `M ${puntos.map((p) => `${xDe(p.hora).toFixed(1)} ${yDe(p.ocupados).toFixed(1)}`).join(' L ')}`

  /** fix UX-S020: el cursor sigue el dedo (táctil) */
  function graficoTactil(e: TouchEvent): void {
    const t = e.touches[0]
    if (!t) return
    const r = e.currentTarget.getBoundingClientRect()
    const x = ((t.clientX - r.left) / r.width) * W
    const hora = Math.round(((x - ANCHO_IZQ) / anchoPlot) * 23)
    setCursor(hora >= 0 && hora <= 23 ? hora : null)
  }

  return (
    <figure
      className="grafico"
      onMouseMove={(e) => {
        const r = e.currentTarget.getBoundingClientRect()
        const x = ((e.clientX - r.left) / r.width) * W
        const hora = Math.round(((x - ANCHO_IZQ) / anchoPlot) * 23)
        setCursor(hora >= 0 && hora <= 23 ? hora : null)
      }}
      onMouseLeave={() => setCursor(null)}
    >
      <span className="rotulo-capacidad">Capacidad: {capacidadTotal}</span>
      {/* fix UX-S020: navegable con teclado (flechas mueven el seguimiento) */}
      <svg
        viewBox={`0 0 ${W} ${alto}`} role="img"
        tabIndex={0}
        aria-label={`Ocupación por hora, máximo ${maximo} de ${capacidadTotal}`}
        style={{ height: alto, touchAction: 'pan-y' }}
        onTouchStart={(e) => graficoTactil(e)}
        onTouchMove={(e) => graficoTactil(e)}
        onKeyDown={(e) => {
          if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return
          e.preventDefault()
          const delta = e.key === 'ArrowRight' ? 1 : -1
          setCursor(() => {
            const actual = cursor ?? 12
            const siguiente = Math.min(23, Math.max(0, actual + delta))
            return siguiente
          })
        }}
      >
        {/* rejilla horizontal */}
        {Array.from({ length: rejilla + 1 }, (_, i) => {
          const v = (tope / rejilla) * i
          const y = yDe(v)
          return (
            <g key={i}>
              <line x1={ANCHO_IZQ} x2={W - 8} y1={y} y2={y} stroke="var(--color-border)" strokeWidth={1} />
              <text x={ANCHO_IZQ - 4} y={y + 3} textAnchor="end" fontSize={9} fill="var(--color-muted)" fontFamily="var(--font-mono)">
                {tope / rejilla === 1 ? Math.round(v) : v % 1 === 0 ? v : v.toFixed(1)}
              </text>
            </g>
          )
        })}

        {/* capacidad como línea de referencia, sólo si cabe */}
        {capadentro && (
          <line
            x1={ANCHO_IZQ} x2={W - 8}
            y1={yDe(capacidadTotal)} y2={yDe(capacidadTotal)}
            stroke="var(--color-warning)" strokeWidth={1.2} strokeDasharray="5 4"
          />
        )}

        {/* curva + puntos */}
        <path d={linea} fill="none" stroke="var(--color-primary)" strokeWidth={2} />
        {puntos.map((p) => (
          <circle key={p.hora} cx={xDe(p.hora)} cy={yDe(p.ocupados)} r={2.6} fill="var(--color-primary)" />
        ))}

        {/* seguimiento del cursor */}
        {cursor !== null && (
          <g>
            <line
              x1={xDe(cursor)} x2={xDe(cursor)}
              y1={0} y2={alto}
              stroke="var(--color-muted)" strokeWidth={1} opacity={0.6}
            />
            <text
              x={Math.min(xDe(cursor) + 4, W - 46)} y={12}
              fontSize={11} fill="var(--color-text)" fontWeight={700}
            >
              {String(cursor).padStart(2, '0')}:00 · {puntos[cursor]?.ocupados ?? 0}
            </text>
          </g>
        )}

        {/* etiquetas de horas de 3 en 3 */}
        {TICAS_HORA.map((t0, i) => {
          const hora = i * 3
          return (
            <text key={t0} x={xDe(hora)} y={alto - 2} fontSize={10} fill="var(--color-muted)" textAnchor="middle" dy={-4} fontFamily="var(--font-mono)">
              {t0}
            </text>
          )
        })}
      </svg>
      <figcaption className="solo-lectores">
        {`Gráfico de ocupación por hora del día; usa el detalle de la hora para recorrerlas con teclado.`}
      </figcaption>
    </figure>
  )
}

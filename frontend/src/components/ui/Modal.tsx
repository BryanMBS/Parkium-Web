import { useEffect, useRef, type ReactNode } from 'react'

/** Diálogo modal operable con teclado: Esc cierra, el foco queda dentro.
 * fix UX-S001: `alCerrar` se guarda en una ref para que su identidad no
 * dispare re-efectos (el foco no se roba con cada cambio de estado del padre).
 * fix UX-S010: bloquea el scroll del fondo mientras el diálogo está abierto.
 */
export function Modal({
  titulo,
  abierto,
  alCerrar,
  children,
  ancho,
}: {
  titulo: string
  abierto: boolean
  alCerrar: () => void
  children: ReactNode
  ancho?: number
}): JSX.Element | null {
  const ref = useRef<HTMLDivElement>(null)
  const cerrarRef = useRef(alCerrar)
  cerrarRef.current = alCerrar

  useEffect(() => {
    if (!abierto) return
    const antes = document.activeElement as HTMLElement | null
    ref.current?.focus()
    const teclas = (e: KeyboardEvent) => {
      if (e.key === 'Escape') cerrarRef.current()
      if (e.key === 'Tab' && ref.current) {
        const enfocables = ref.current.querySelectorAll<HTMLElement>(
          'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
        )
        if (enfocables.length === 0) return
        const primero = enfocables[0]
        const ultimo = enfocables[enfocables.length - 1]
        if (e.shiftKey && document.activeElement === primero) {
          e.preventDefault()
          ultimo.focus()
        } else if (!e.shiftKey && document.activeElement === ultimo) {
          e.preventDefault()
          primero.focus()
        }
      }
    }
    document.addEventListener('keydown', teclas)
    const scrollPrevio = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', teclas)
      document.body.style.overflow = scrollPrevio
      antes?.focus()
    }
  }, [abierto])

  if (!abierto) return null
  return (
    <div className="fondo-dialogo" onMouseDown={(e) => e.target === e.currentTarget && alCerrar()}>
      <div className="dialogo" role="dialog" aria-modal="true" aria-label={titulo} style={ancho ? { width: ancho } : undefined}>
        <div className="cabecera-dialogo">
          <h2>{titulo}</h2>
          <button className="cerrar-dialogo" onClick={alCerrar} aria-label={`Cerrar ${titulo}`}>
            ✕
          </button>
        </div>
        <div ref={ref} tabIndex={-1} style={{ outline: 'none' }}>
          {children}
        </div>
      </div>
    </div>
  )
}

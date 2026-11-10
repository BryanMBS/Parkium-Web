/** Región aria-live para anunciar cambios y errores a lectores de pantalla
 * (docs/06 §6.11). El error siempre lleva texto + icono, no sólo color. */

import type { ReactNode } from 'react'

type Variante = 'error' | 'ok' | 'aviso'

const ICONO: Record<Variante, string> = { error: '✕', ok: '✓', aviso: '⚠' }

export function Aviso({
  variante,
  children,
  anunciar = 'polite',
}: {
  variante: Variante
  children: ReactNode
  anunciar?: 'polite' | 'assertive'
}): JSX.Element | null {
  if (!children || (typeof children === 'string' && !children.trim())) return null
  return (
    <div
      className={`aviso aviso-${variante}`}
      role={variante === 'error' ? 'alert' : 'status'}
      aria-live={anunciar}
    >
      <span className="icono" aria-hidden="true">
        {ICONO[variante]}
      </span>
      <div>{children}</div>
    </div>
  )
}

export function MensajeApi(error: unknown): string {
  if (error && typeof error === 'object' && 'mensaje' in error) {
    return String((error as { mensaje: unknown }).mensaje)
  }
  if (error instanceof Error) return error.message
  return 'Error inesperado.'
}

export type Modo = 'claro' | 'oscuro'

/**
 * Paleta del sistema de diseño (docs/06 §6.1-6.2).
 * Los tokens viven en global.css; aquí sólo se aplica el modo al <html>.
 */
export function aplicarTema(modo: Modo): void {
  document.documentElement.dataset.theme = modo
}

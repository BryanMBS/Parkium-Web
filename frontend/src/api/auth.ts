import { http } from './client'

export interface Usuario {
  id: number
  usuario: string
  nombre: string
  nombre_completo: string
  rol: string
  etiqueta_rol?: string
}

export interface LoginResponse {
  usuario: Usuario
  expira_en: string
}

/** Docs/04 §4.2: el campo de la contraseña se llama «contraseña» (con ñ). */
function cuerpoContrasena(usuario: string, contrasena: string): Record<string, string> {
  return { usuario, ['contrase\u00f1a']: contrasena }
}

export const auth = {
  login: (usuario: string, contrasena: string) =>
    http.POST<LoginResponse>('/api/auth/login', cuerpoContrasena(usuario, contrasena)),

  logout: () => http.POST<void>('/api/auth/logout'),

  me: () => http.GET<Usuario>('/api/auth/me'),

  cambiarContrasena: (actual: string, nueva: string) =>
    http.POST<{ mensaje: string }>('/api/auth/password', { actual, nueva }),

  /** Sólo la primera ejecución; queda cerrado cuando exista un usuario. */
  primerUsuario: (nombre_completo: string, contrasena: string) =>
    http.POST<LoginResponse>(
      '/api/auth/first-user',
      (() => {
        const cuerpo = cuerpoContrasena(nombre_corto(nombre_completo), contrasena)
        cuerpo['nombre_completo'] = nombre_completo
        return cuerpo
      })(),
    ),
}

function nombre_corto(nombre_completo: string): string {
  // el usuario de arranque se deriva del nombre si no se dimos otro
  return nombre_completo.toLowerCase().replace(/[^a-z]/g, '').slice(0, 12) || 'admin'
}

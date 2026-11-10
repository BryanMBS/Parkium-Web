/** Contexto de sesión (docs/02 §2.4): usuario, rol y verificación inicial. */

import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { auth, type Usuario } from '../api/auth'

interface AuthContextValue {
  usuario: Usuario | null
  cargando: boolean
  iniciar: (u: Usuario) => void
  cerrar: () => Promise<void>
}

const Ctx = createContext<AuthContextValue>({
  usuario: null,
  cargando: true,
  iniciar: () => {},
  cerrar: async () => {},
})

export function AuthProvider({ children }: { children: ReactNode }): JSX.Element {
  const [usuario, setUsuario] = useState<Usuario | null>(null)
  const [cargando, setCargando] = useState(true)

  useEffect(() => {
    let vive = true
    auth
      .me()
      .then((u) => {
        if (vive) setUsuario(u)
      })
      .catch(() => {
        if (vive) setUsuario(null)
      })
      .finally(() => {
        if (vive) setCargando(false)
      })
    return () => {
      vive = false
    }
  }, [])

  return (
    <Ctx.Provider
      value={{
        usuario,
        cargando,
        iniciar: (u) => setUsuario(u),
        cerrar: async () => {
          try {
            await auth.logout()
          } finally {
            setUsuario(null)
          }
        },
      }}
    >
      {children}
    </Ctx.Provider>
  )
}

export function useAuth(): AuthContextValue {
  return useContext(Ctx)
}

import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { aplicarTema, type Modo } from './palette'

interface ThemeContext {
  modo: Modo
  setModo: (m: Modo) => void
}

const Ctx = createContext<ThemeContext>({
  modo: 'claro',
  setModo: () => {},
})

export function ThemeProvider({ children }: { children: ReactNode }): JSX.Element {
  const [modo, setModo] = useState<Modo>(() => {
    const guardado = localStorage.getItem('parkium.tema')
    if (guardado === 'claro' || guardado === 'oscuro') return guardado
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'oscuro' : 'claro'
  })

  useEffect(() => {
    aplicarTema(modo)
    localStorage.setItem('parkium.tema', modo)
  }, [modo])

  return <Ctx.Provider value={{ modo, setModo }}>{children}</Ctx.Provider>
}

export function useTheme(): ThemeContext {
  return useContext(Ctx)
}

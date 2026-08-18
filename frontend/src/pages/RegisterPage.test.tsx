import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { App } from '../app/App'
import { AuthContext, type AuthContextValue } from '../auth/AuthContext'
import { LoginPage } from './LoginPage'
import { RegisterPage } from './RegisterPage'

const supabaseMocks = vi.hoisted(() => ({ signUp: vi.fn() }))

vi.mock('../lib/supabase', () => ({
  supabase: { auth: { signUp: supabaseMocks.signUp } },
}))

const unauthenticated: AuthContextValue = {
  isLoading: false,
  session: null,
  signIn: vi.fn(),
  signOut: vi.fn(),
}

const session = {
  access_token: 'test-token',
  refresh_token: 'test-refresh-token',
  expires_in: 3600,
  token_type: 'bearer',
  user: {
    id: 'user-id',
    email: 'new@example.com',
    app_metadata: {},
    user_metadata: {},
    aud: 'authenticated',
    created_at: '2026-08-18T10:00:00Z',
  },
}

function renderRegister(auth = unauthenticated) {
  return render(
    <AuthContext.Provider value={auth}>
      <MemoryRouter initialEntries={['/register']}>
        <Routes>
          <Route path="/register" element={<RegisterPage />} />
          <Route path="/login" element={<h1>Login destino</h1>} />
          <Route path="/" element={<h1>Inicio autenticado</h1>} />
        </Routes>
      </MemoryRouter>
    </AuthContext.Provider>,
  )
}

async function fillRegistration(password = 'secret1', confirmation = password) {
  const user = userEvent.setup()
  await user.type(screen.getByLabelText('Email'), 'new@example.com')
  await user.type(screen.getByLabelText('Contraseña'), password)
  await user.type(screen.getByLabelText('Repetir contraseña'), confirmation)
  return user
}

describe('registration with Supabase Auth', () => {
  beforeEach(() => {
    supabaseMocks.signUp.mockReset()
  })

  it('keeps /register public and renders all three fields', () => {
    render(
      <AuthContext.Provider value={unauthenticated}>
        <MemoryRouter initialEntries={['/register']}><App /></MemoryRouter>
      </AuthContext.Provider>,
    )

    expect(screen.getByRole('heading', { name: 'Crear cuenta' })).toBeInTheDocument()
    expect(screen.getByLabelText('Email')).toBeInTheDocument()
    expect(screen.getByLabelText('Contraseña')).toBeInTheDocument()
    expect(screen.getByLabelText('Repetir contraseña')).toBeInTheDocument()
  })

  it('validates matching passwords before calling Supabase', async () => {
    renderRegister()
    const user = await fillRegistration('secret1', 'secret2')

    await user.click(screen.getByRole('button', { name: 'Crear cuenta' }))

    expect(screen.getByRole('alert')).toHaveTextContent('Las contraseñas no coinciden.')
    expect(supabaseMocks.signUp).not.toHaveBeenCalled()
  })

  it('submits credentials once and blocks double submit', async () => {
    let finish!: (value: unknown) => void
    supabaseMocks.signUp.mockReturnValue(new Promise((resolve) => { finish = resolve }))
    renderRegister()
    const user = await fillRegistration()

    await user.dblClick(screen.getByRole('button', { name: 'Crear cuenta' }))

    expect(supabaseMocks.signUp).toHaveBeenCalledOnce()
    expect(supabaseMocks.signUp).toHaveBeenCalledWith({
      email: 'new@example.com',
      password: 'secret1',
    })
    expect(screen.getByRole('button', { name: 'Creando cuenta…' })).toBeDisabled()
    finish({ data: { session: null, user: { id: 'user-id' } }, error: null })
  })

  it('navigates home when Supabase returns a session', async () => {
    supabaseMocks.signUp.mockResolvedValue({ data: { session, user: session.user }, error: null })
    renderRegister()
    const user = await fillRegistration()

    await user.click(screen.getByRole('button', { name: 'Crear cuenta' }))

    expect(await screen.findByRole('heading', { name: 'Inicio autenticado' })).toBeInTheDocument()
  })

  it('shows email confirmation state and links back to login when no session exists', async () => {
    supabaseMocks.signUp.mockResolvedValue({
      data: { session: null, user: { id: 'user-id' } },
      error: null,
    })
    renderRegister()
    const user = await fillRegistration()

    await user.click(screen.getByRole('button', { name: 'Crear cuenta' }))

    expect(await screen.findByRole('heading', { name: 'Revisá tu correo' })).toBeInTheDocument()
    expect(screen.getByText(/Te enviamos un enlace para confirmar tu cuenta/)).toBeInTheDocument()
    await user.click(screen.getByRole('link', { name: 'Ir a iniciar sesión' }))
    expect(screen.getByRole('heading', { name: 'Login destino' })).toBeInTheDocument()
  })

  it.each([
    ['User already registered', 'Ya existe una cuenta con este email. Podés iniciar sesión.'],
    ['Password should be at least 6 characters', 'La contraseña no cumple los requisitos mínimos. Usá al menos 6 caracteres.'],
    ['Email address is invalid', 'Ingresá un email válido.'],
    ['Too many requests', 'Hay demasiados intentos en este momento. Esperá unos segundos e intentá nuevamente.'],
    ['Unexpected internal detail', 'No pudimos crear tu cuenta. Intentá nuevamente.'],
  ])('maps registration error %s to safe feedback', async (providerMessage, expected) => {
    supabaseMocks.signUp.mockResolvedValue({
      data: { session: null, user: null },
      error: new Error(providerMessage),
    })
    renderRegister()
    const user = await fillRegistration()

    await user.click(screen.getByRole('button', { name: 'Crear cuenta' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(expected)
    expect(document.body.textContent).not.toContain(providerMessage)
  })

  it('links login to registration', () => {
    render(
      <AuthContext.Provider value={unauthenticated}>
        <MemoryRouter><LoginPage /></MemoryRouter>
      </AuthContext.Provider>,
    )

    expect(screen.getByRole('link', { name: 'Crear cuenta' })).toHaveAttribute('href', '/register')
  })

  it('keeps protected routes redirecting unauthenticated users to login', async () => {
    render(
      <AuthContext.Provider value={unauthenticated}>
        <MemoryRouter initialEntries={['/goals/new']}><App /></MemoryRouter>
      </AuthContext.Provider>,
    )

    expect(await screen.findByRole('heading', { name: 'Ingresá a LevelMind' })).toBeInTheDocument()
    expect(supabaseMocks.signUp).not.toHaveBeenCalled()
  })
})

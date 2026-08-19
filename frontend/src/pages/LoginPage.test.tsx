import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import { AuthContext, type AuthContextValue } from '../auth/AuthContext'
import { LoginPage } from './LoginPage'

function renderLogin(signIn: AuthContextValue['signIn']) {
  const auth: AuthContextValue = {
    isLoading: false,
    session: null,
    signIn,
    signOut: vi.fn(),
  }

  return render(
    <AuthContext.Provider value={auth}>
      <MemoryRouter initialEntries={['/login']}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/" element={<h1>Inicio autenticado</h1>} />
        </Routes>
      </MemoryRouter>
    </AuthContext.Provider>,
  )
}

async function submitLogin() {
  const user = userEvent.setup()
  await user.type(screen.getByLabelText('Email'), 'user@example.com')
  await user.type(screen.getByLabelText('Contraseña'), 'secret1')
  await user.click(screen.getByRole('button', { name: 'Ingresar' }))
}

describe('login with Supabase Auth', () => {
  it.each([
    ['invalid_credentials', 'Invalid login credentials'],
    ['user_not_found', 'User not found'],
  ])('uses the same safe feedback for %s', async (code, message) => {
    const signIn = vi.fn().mockRejectedValue({ code, message, status: 400 })
    renderLogin(signIn)

    await submitLogin()

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Email o contraseña incorrectos. Revisá tus datos e intentá nuevamente.',
    )
    expect(document.body.textContent).not.toContain(message)
  })

  it.each([
    [
      { code: 'email_address_invalid', message: 'Email address is invalid', status: 400 },
      'Ingresá un email válido.',
    ],
    [
      { code: 'email_not_confirmed', message: 'Email not confirmed', status: 400 },
      'Tu email todavía no fue verificado. Revisá tu correo antes de iniciar sesión.',
    ],
    [
      { code: 'over_request_rate_limit', message: 'Too many requests', status: 429 },
      'Hay demasiados intentos en este momento. Esperá unos segundos e intentá nuevamente.',
    ],
    [
      { name: 'AuthRetryableFetchError', message: 'Failed to fetch', status: 0 },
      'No pudimos conectarnos. Revisá tu conexión e intentá nuevamente.',
    ],
    [
      { code: 'unexpected_failure', message: 'Internal provider detail', status: 500 },
      'No pudimos iniciar sesión. Intentá nuevamente.',
    ],
  ])('maps known and unexpected errors to safe feedback', async (error, expected) => {
    const signIn = vi.fn().mockRejectedValue(error)
    renderLogin(signIn)

    await submitLogin()

    expect(await screen.findByRole('alert')).toHaveTextContent(expected)
    expect(document.body.textContent).not.toContain(error.message)
  })

  it('keeps the normal login flow and trims the email', async () => {
    const signIn = vi.fn().mockResolvedValue(undefined)
    renderLogin(signIn)
    const user = userEvent.setup()
    await user.type(screen.getByLabelText('Email'), '  user@example.com  ')
    await user.type(screen.getByLabelText('Contraseña'), 'secret1')

    await user.click(screen.getByRole('button', { name: 'Ingresar' }))

    expect(signIn).toHaveBeenCalledWith('user@example.com', 'secret1')
    expect(await screen.findByRole('heading', { name: 'Inicio autenticado' })).toBeInTheDocument()
  })
})

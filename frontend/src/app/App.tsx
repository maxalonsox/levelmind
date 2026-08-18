import { Navigate, Route, Routes } from 'react-router-dom'

import { ProtectedRoute } from '../auth/ProtectedRoute'
import { GoalStartPage } from '../pages/GoalStartPage'
import { HomePage } from '../pages/HomePage'
import { LoginPage } from '../pages/LoginPage'

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<ProtectedRoute />}>
        <Route index element={<HomePage />} />
        <Route path="/goals/new" element={<GoalStartPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

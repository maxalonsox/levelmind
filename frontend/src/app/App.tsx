import { Navigate, Route, Routes } from 'react-router-dom'

import { ProtectedRoute } from '../auth/ProtectedRoute'
import { GoalStartPage } from '../pages/GoalStartPage'
import { HomePage } from '../pages/HomePage'
import { LoginPage } from '../pages/LoginPage'
import { ActivePlanPage } from '../pages/ActivePlanPage'
import { AdaptationReviewPage } from '../pages/AdaptationReviewPage'
import { PlanPreviewPage } from '../pages/PlanPreviewPage'
import { RegisterPage } from '../pages/RegisterPage'

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route element={<ProtectedRoute />}>
        <Route index element={<HomePage />} />
        <Route path="/goals/new" element={<GoalStartPage />} />
        <Route path="/goals/:goalId/plan" element={<PlanPreviewPage />} />
        <Route path="/goals/:goalId/adaptation" element={<AdaptationReviewPage />} />
        <Route path="/goals/:goalId" element={<ActivePlanPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

function requiredEnv(name: keyof ImportMetaEnv): string {
  const value = import.meta.env[name]?.trim()

  if (!value) {
    throw new Error(`Missing required environment variable: ${name}`)
  }

  return value
}

export const env = {
  apiBaseUrl: requiredEnv('VITE_API_BASE_URL').replace(/\/$/, ''),
  supabaseUrl: requiredEnv('VITE_SUPABASE_URL'),
  supabasePublishableKey: requiredEnv('VITE_SUPABASE_PUBLISHABLE_KEY'),
} as const

import os

os.environ["DATABASE_URL"] = (
    "postgresql+psycopg://test:test@localhost:5432/levelmind_test"
)
os.environ["SUPABASE_URL"] = "https://test.supabase.co"

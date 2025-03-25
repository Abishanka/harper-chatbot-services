import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# OpenAI API configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Supabase configuration
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")

# Storage configuration
TEMP_FILES_DIR = os.getenv("TEMP_FILES_DIR", "/tmp")
STORAGE_BUCKET = os.getenv("STORAGE_BUCKET", "media-bucket") 
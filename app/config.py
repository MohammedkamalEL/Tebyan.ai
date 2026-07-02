"""
الإعدادات العامة للتطبيق — مقروءة من متغيرات البيئة (.env)
نستخدم pydantic-settings لضمان التحقق من النوع (type validation) تلقائياً.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    ENV: str = "development"

    # AI Provider — Gemini 1.5 Flash (مجاني)
    # احصل على مفتاحك من: https://aistudio.google.com/app/apikey
    GEMINI_API_KEY: str = ""

    # حدود الملفات
    MAX_PDF_PAGES: int = 50
    MAX_FILE_SIZE_MB: int = 20

    # CORS — عدّل هذا لاحقاً لرابط Next.js الفعلي في production
    ALLOWED_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    # مسارات التخزين
    UPLOAD_DIR: str = "storage/uploads"
    OUTPUT_DIR: str = "storage/outputs"


settings = Settings()

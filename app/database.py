from sqlalchemy import create_engine, MetaData
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

# Use DATABASE_URL from Render, or fallback to your Postgres URL
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://raksha_360_user:IXSbIC6uSyPwpUgHc2toiijhMwYFuQle@dpg-d2rc8mv5r7bs73bru9ig-a/raksha_360"
)

# Create engine
engine = create_engine(DATABASE_URL, echo=True, future=True)

# Metadata
meta = MetaData()

# ✅ Base for models
Base = declarative_base()

# ✅ Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

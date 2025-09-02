from sqlalchemy import create_engine, MetaData
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

# Use DATABASE_URL from Render, or fallback to your Postgres URL
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://raksha_360_iyyc_user:cnmxNVfakZunRQGmY94OIog0rDxyGpZp@dpg-d2rfn1euk2gs7389acgg-a/raksha_360_iyyc"
)

# Create engine
engine = create_engine(DATABASE_URL, echo=True, future=True)

# Metadata
meta = MetaData()

# ✅ Base for models
Base = declarative_base()

# ✅ Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)



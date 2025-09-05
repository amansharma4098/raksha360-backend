from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

# ✅ Database URL (Render will provide DATABASE_URL as an environment variable)
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://raksha_360_user:IXSbIC6uSyPwpUgHc2toiijhMwYFuQle@dpg-d2rc8mv5r7bs73bru9ig-a/raksha_360"
)

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://raksha_360_iyyc_user:cnmxNVfakZunRQGmY94OIog0rDxyGpZp@dpg-d2rfn1euk2gs7389acgg-a/raksha_360_iyyc"
)

# ✅ SQLAlchemy Engine
engine = create_engine(DATABASE_URL, echo=True, future=True)

# ✅ SessionLocal for DB sessions
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# ✅ Base class for models (used in models.py)
Base = declarative_base()

# ✅ Dependency to get a DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()



from sqlalchemy import create_engine, MetaData
import os

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://raksha_360_user:IXSbIC6uSyPwpUgHc2toiijhMwYFuQle@dpg-d2rc8mv5r7bs73bru9ig-a/raksha_360")

engine = create_engine(DATABASE_URL, echo=True, future=True)
meta = MetaData()

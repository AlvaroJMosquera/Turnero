from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# 🔁 CAMBIA TUS CREDENCIALES AQUÍ
MYSQL_USER = "root"
MYSQL_PASSWORD = "Admin123"
MYSQL_HOST = "localhost"
MYSQL_PORT = "3306"
MYSQL_DB = "turnero_db"

SQLALCHEMY_DATABASE_URL = (
    f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}"
)

engine = create_engine(SQLALCHEMY_DATABASE_URL, echo=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

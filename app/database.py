from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
from app.models import Base
import streamlit as st

# إعداد الاتصال بقاعدة البيانات
def get_db_engine():
    try:
        db_config = st.secrets["db"]
        DATABASE_URL = f"postgresql://{db_config['user']}:{db_config['password']}@{db_config['host']}:{db_config['port']}/{db_config['name']}?sslmode=require"
        return create_engine(DATABASE_URL, pool_pre_ping=True)
    except Exception as e:
        st.error(f"❌ خطأ في الاتصال بقاعدة البيانات: {e}")
        return None

engine = get_db_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


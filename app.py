import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, Column, Integer, String, Date, ForeignKey, Text
from sqlalchemy.orm import sessionmaker, relationship, declarative_base, joinedload
import bcrypt
from datetime import date
import plotly.express as px
import time
import json 

# --- 1. إعدادات الصفحة ---
st.set_page_config(page_title="منصة التميز البحثي", layout="wide", page_icon="🎓")

# ==========================================
# 2. إعدادات قاعدة البيانات (ضع الرابط هنا)
# ==========================================

# 🔴🔴 هام جداً: الصق الرابط الذي نسخته من زر Connect (وضع Transaction) هنا
# استبدل [YOUR-PASSWORD] بكلمة مرورك: 8?Q4.G/iLe84d-j
# مثال على شكل الرابط: postgres://postgres.xxxx:pass@aws-0-eu-central-1.pooler.supabase.com:6543/postgres

DB_CONNECTION_STRING = "postgresql://postgres.jecmwuiqofztficcujpe:khalidcom_1981@aws-1-eu-west-2.pooler.supabase.com:6543/postgres"

# ملاحظة: قمتُ بمحاولة تخمين الرابط وتشفير كلمة السر لك في السطر أعلاه
# إذا لم يعمل، احذفه وضع الرابط الذي نسخته أنت يدوياً

try:
    # استخدام pool_pre_ping للحفاظ على الاتصال حياً
    engine = create_engine(DB_CONNECTION_STRING, pool_pre_ping=True)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base = declarative_base()
except Exception as e:
    st.error(f"خطأ في إعداد المحرك: {e}")

# --- تعريف الجداول ---
class Team(Base):
    __tablename__ = "teams"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    description = Column(String, nullable=True)
    members = relationship("User", back_populates="team")

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, index=True)
    full_name = Column(String, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, nullable=False) 
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=True)
    team = relationship("Team", back_populates="members")
    works = relationship("Work", back_populates="researcher")

class Work(Base):
    __tablename__ = "works"
    id = Column(Integer, primary_key=True)
    title = Column(Text, nullable=False)
    details = Column(Text, nullable=True) 
    activity_type = Column(String, nullable=False)
    classification = Column(String, nullable=True)
    publication_date = Column(Date, nullable=False)
    year = Column(Integer, nullable=False)
    points = Column(Integer, default=0)
    user_id = Column(Integer, ForeignKey("users.id"))
    researcher = relationship("User", back_populates="works")

# دالة إنشاء الجداول (تعمل مرة واحدة عند بدء التطبيق)
def create_tables():
    try:
        Base.metadata.create_all(bind=engine)
        session = SessionLocal()
        # التأكد من وجود البيانات الأساسية
        if not session.query(Team).first():
            teams = [Team(name="دراسات سوسيولوجية"), Team(name="علم النفس العيادي"), Team(name="تكنولوجيا التعليم")]
            session.add_all(teams)
            session.commit()
        if not session.query(User).filter_by(username="admin").first():
            hashed = bcrypt.hashpw("12345".encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            session.add(User(username="admin", full_name="المدير العام", password_hash=hashed, role="admin"))
            session.commit()
        session.close()
        return True
    except Exception as e:
        return str(e)

# ==========================================
# 3. الواجهة
# ==========================================

# تشغيل عملية إنشاء الجداول تلقائياً
if 'setup_complete' not in st.session_state:
    result = create_tables()
    if result is True:
        st.session_state['setup_complete'] = True
    else:
        st.error(f"فشل الاتصال بقاعدة البيانات: {result}")
        st.stop()

if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

if not st.session_state['logged_in']:
    c1, c2, c3 = st.columns([1, 1.5, 1])
    with c2:
        st.markdown("<br><h1 style='text-align: center; color: #1e3a8a;'>بوابة البحث العلمي</h1>", unsafe_allow_html=True)
        tab1, tab2 = st.tabs(["تسجيل الدخول", "إنشاء حساب"])
        
        with tab1:
            with st.form("login_form"):
                u = st.text_input("اسم المستخدم")
                p = st.text_input("كلمة المرور", type="password")
                if st.form_submit_button("دخول", type="primary"):
                    session = SessionLocal()
                    user = session.query(User).options(joinedload(User.team)).filter(User.username==u).first()
                    if user and bcrypt.checkpw(p.encode('utf-8'), user.password_hash.encode('utf-8')):
                        st.session_state['logged_in'] = True
                        st.session_state['user'] = {'id': user.id, 'name': user.full_name, 'role': user.role, 'team': user.team.name if user.team else ""}
                        session.close()
                        st.rerun()
                    else:
                        st.error("بيانات خاطئة")
                    session.close()

        with tab2:
            with st.form("signup_form"):
                session = SessionLocal()
                # جلب الفرق بأمان
                try: teams = [t.name for t in session.query(Team).all()]
                except: teams = []
                session.close()
                
                new_u = st.text_input("اسم المستخدم")
                new_p = st.text_input("كلمة المرور", type="password")
                full_n = st.text_input("الاسم الكامل")
                team_sel = st.selectbox("الفرقة", teams) if teams else st.warning("لا توجد فرق متاحة")
                role_sel = st.radio("الصفة", ["باحث", "رئيس فرقة", "مدير"], horizontal=True)
                code = st.text_input("كود التفعيل", type="password")
                
                if st.form_submit_button("إنشاء حساب"):
                    codes = {"باحث": "RES2025", "رئيس فرقة": "LEADER2025", "مدير": "ADMIN2025"}
                    if code == codes.get(role_sel):
                        s = SessionLocal()
                        try:
                            tm = s.query(Team).filter(Team.name == team_sel).first()
                            h_pw = bcrypt.hashpw(new_p.encode(), bcrypt.gensalt()).decode()
                            s.add(User(username=new_u, full_name=full_n, password_hash=h_pw, role="researcher", team_id=tm.id if tm else None))
                            s.commit()
                            st.success("تم الإنشاء بنجاح! يمكنك الدخول الآن.")
                        except Exception as e:
                            st.error(f"خطأ: {e}")
                        finally: s.close()
                    else:
                        st.error("الكود خاطئ")

else:
    # واجهة المستخدم بعد الدخول
    user = st.session_state['user']
    with st.sidebar:
        st.success(f"مرحباً: {user['name']}")
        if st.button("تسجيل خروج"):
            st.session_state['logged_in'] = False
            st.rerun()
            
    # بقية التطبيق (لوحات القيادة) تضعها هنا...
    st.title("📊 لوحة القيادة العامة")
    
    # جلب البيانات للعرض
    session = SessionLocal()
    df = pd.read_sql("SELECT * FROM works", engine)
    session.close()
    
    if not df.empty:
        st.dataframe(df)
    else:
        st.info("سجل الأعمال فارغ حالياً. ابدأ بإضافة نتاج علمي جديد.")



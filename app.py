import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, Column, Integer, String, Date, ForeignKey, Text
from sqlalchemy.orm import sessionmaker, relationship, declarative_base, joinedload
import bcrypt
from datetime import date
import plotly.express as px
import time
import json 
import urllib.parse
import base64
import os

# --- 1. إعدادات الصفحة ---
st.set_page_config(
    page_title="منصة التميز البحثي",
    layout="wide",
    initial_sidebar_state="expanded",
    page_icon="🎓"
)

# دالة لتحويل الشعار
def get_img_as_base64(file_path):
    try:
        with open(file_path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    except: return None

# ==========================================
# 2. إعدادات قاعدة البيانات
# ==========================================
if "db" in st.secrets:
    db_config = st.secrets["db"]
    encoded_password = urllib.parse.quote_plus(db_config["password"])
    DATABASE_URL = f"postgresql://{db_config['user']}:{encoded_password}@{db_config['host']}:{db_config['port']}/{db_config['name']}?sslmode=require"
else:
    # إعدادات افتراضية (احتياطية)
    RAW_PASS = "khalidcom_1981"
    encoded_password = urllib.parse.quote_plus(RAW_PASS)
    DATABASE_URL = f"postgresql://postgres.jecmwuiqofztficcujpe:{encoded_password}@aws-1-eu-west-2.pooler.supabase.com:6543/postgres?sslmode=require"

try:
    engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_recycle=1800)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base = declarative_base()
except Exception as e:
    st.error(f"خطأ في الاتصال: {e}")
    st.stop()

# --- تعريف الجداول (الهيكلة الجديدة) ---

class Department(Base):
    __tablename__ = "departments"
    id = Column(Integer, primary_key=True, index=True)
    dept_number = Column(Integer, unique=True) # رقم القسم
    name = Column(String, nullable=False) # اسم القسم
    latin_name = Column(String) # اسم القسم باللاتينية
    abbreviation = Column(String) # الاسم المختصر
    teams = relationship("Team", back_populates="department")

class Team(Base):
    __tablename__ = "teams"
    id = Column(Integer, primary_key=True, index=True)
    team_number = Column(Integer) # رقم الفرقة
    name = Column(String, unique=True, nullable=False) # اسم الفرقة
    abbreviation = Column(String) # الاسم المختصر للفرقة
    classification = Column(Text) # التصنيف الموضوعاتي (JSON)
    description = Column(Text) # وصف علمي لبرنامج البحث
    
    # العلاقات
    department_id = Column(Integer, ForeignKey("departments.id"))
    department = relationship("Department", back_populates="teams")
    members = relationship("User", back_populates="team")

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    full_name = Column(String, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, nullable=False) # admin, leader, researcher, phd_student
    
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=True)
    team = relationship("Team", back_populates="members")
    works = relationship("Work", back_populates="researcher")

class Work(Base):
    __tablename__ = "works"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(Text, nullable=False)
    details = Column(Text) 
    activity_type = Column(String)
    classification = Column(String)
    publication_date = Column(Date)
    year = Column(Integer)
    points = Column(Integer, default=0)
    user_id = Column(Integer, ForeignKey("users.id"))
    researcher = relationship("User", back_populates="works")

# --- دالة التهيئة (تم تحديثها لإنشاء الأقسام الستة) ---
def init_db():
    try:
        # ملاحظة: إذا تغيرت الهيكلة جذرياً قد تحتاج لحذف الجداول يدوياً من Supabase أولاً
        Base.metadata.create_all(bind=engine)
        session = SessionLocal()
        
        # 1. إنشاء الأقسام الستة
        if not session.query(Department).first():
            depts_data = [
                {"n": 1, "name": "القسم (1)", "lat": "Department 1", "abbr": "DEPT1"},
                {"n": 2, "name": "القسم (2)", "lat": "Department 2", "abbr": "DEPT2"},
                {"n": 3, "name": "القسم (3)", "lat": "Department 3", "abbr": "DEPT3"},
                {"n": 4, "name": "القسم (4)", "lat": "Department 4", "abbr": "DEPT4"},
                {"n": 5, "name": "القسم (5)", "lat": "Department 5", "abbr": "DEPT5"},
                {"n": 6, "name": "القسم (6)", "lat": "Department 6", "abbr": "DEPT6"},
            ]
            for d in depts_data:
                session.add(Department(dept_number=d["n"], name=d["name"], latin_name=d["lat"], abbreviation=d["abbr"]))
            session.commit()
            
            # إضافة فرق افتراضية وتوزيعها على الأقسام
            dept1 = session.query(Department).filter_by(dept_number=1).first()
            if dept1:
                t1 = Team(team_number=1, name="فرقة الدراسات الاجتماعية", abbreviation="SDS", department_id=dept1.id, description="تهتم بدراسة الظواهر الاجتماعية")
                session.add(t1)
            
            dept2 = session.query(Department).filter_by(dept_number=2).first()
            if dept2:
                t2 = Team(team_number=2, name="فرقة علم النفس العيادي", abbreviation="CPS", department_id=dept2.id, description="الصحة النفسية والعلاجات")
                session.add(t2)
            
            session.commit()

        # 2. إنشاء المدير
        if not session.query(User).filter_by(username="admin").first():
            hashed = bcrypt.hashpw("12345".encode(), bcrypt.gensalt()).decode()
            session.add(User(username="admin", full_name="مدير المخبر", password_hash=hashed, role="admin"))
            session.commit()
            
        session.close()
        return True
    except Exception as e:
        print(f"Init Error: {e}")
        return False

# ==========================================
# الخدمات
# ==========================================
def login_service(u, p):
    s = SessionLocal()
    try:
        user = s.query(User).options(joinedload(User.team).joinedload(Team.department)).filter(User.username==u).first()
        if user and bcrypt.checkpw(p.encode(), user.password_hash.encode()):
            return user
    except: pass
    finally: s.close()
    return None

def register_service(username, password, fullname, role, team_name):
    s = SessionLocal()
    try:
        team = s.query(Team).filter(Team.name == team_name).first()
        hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        s.add(User(username=username, full_name=fullname, password_hash=hashed, role=role, team_id=team.id if team else None))
        s.commit()
        return True
    except:
        s.rollback()
        return False
    finally: s.close()

# ==========================================
# التنسيق (RTL)
# ==========================================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;800&family=Tajawal:wght@400;500;700&display=swap');
    :root { --primary-color: #2563eb; --bg-color: #f8fafc; --text-color: #1e293b; }
    html, body, .stApp { font-family: 'Tajawal', sans-serif; direction: rtl; background-color: var(--bg-color); color: var(--text-color); text-align: right; }
    h1, h2, h3, h4 { font-family: 'Cairo', sans-serif !important; font-weight: 800; color: #1e3a8a; text-align: right; }
    .stMarkdown, .stText, p, .stButton, .stSelectbox, .stTextInput { text-align: right !important; direction: rtl !important; }
    [data-testid="stSidebar"] { background-color: #ffffff; border-left: 1px solid #e2e8f0; }
    [data-testid="stDataFrame"] table { direction: rtl; text-align: right; }
    .stTabs [data-baseweb="tab-list"] { gap: 8px; justify-content: flex-start; }
    .stTabs [data-baseweb="tab"] { font-family: 'Cairo', sans-serif; font-weight: 700; }
    div[data-testid="stToast"] { direction: rtl; text-align: right; font-family: 'Cairo'; }
    
    /* تنسيق خاص لبطاقة الفرقة */
    .team-card { background: white; padding: 20px; border-radius: 10px; border: 1px solid #e2e8f0; margin-bottom: 15px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); }
    .team-header { color: #2563eb; font-weight: bold; font-size: 18px; margin-bottom: 10px; border-bottom: 1px solid #eee; padding-bottom: 10px; }
    .team-meta { font-size: 13px; color: #64748b; margin-bottom: 5px; }
    .member-list { background: #f8fafc; padding: 10px; border-radius: 8px; margin-top: 10px; font-size: 13px; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# الواجهة
# ==========================================

if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
    init_db()

if not st.session_state['logged_in']:
    c1, c2, c3 = st.columns([1, 1.5, 1])
    with c2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        # الشعار والعنوان
        logo_html = ""
        if os.path.exists("logo.png"):
            b64 = get_img_as_base64("logo.png")
            if b64: logo_html = f'<img src="data:image/png;base64,{b64}" style="width: 150px; margin-bottom: 15px;">'
        else: logo_html = '<div style="font-size: 60px; margin-bottom: 10px;">🏛️</div>'

        st.markdown(f"""
        <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center !important; margin-bottom: 30px;">
            {logo_html}
            <h1 style="color:#1e40af; font-family:'Cairo'; font-weight: 800; margin: 0; text-align: center !important; width: 100%;">بوابة البحث العلمي</h1>
            <p style="color:#64748b; font-family:'Tajawal'; font-size: 18px; margin-top: 5px; text-align: center !important; width: 100%;">نظام إدارة المخابر الجامعية الموحد</p>
        </div>
        """, unsafe_allow_html=True)

        tab1, tab2 = st.tabs(["دخول", "تسجيل"])
        with tab1:
            with st.form("login"):
                u = st.text_input("اسم المستخدم")
                p = st.text_input("كلمة المرور", type="password")
                if st.form_submit_button("دخول", use_container_width=True):
                    with st.spinner("جاري التحقق..."):
                        user = login_service(u, p)
                        if user:
                            st.session_state['logged_in'] = True
                            st.session_state['user'] = {
                                'id': user.id, 
                                'name': user.full_name, 
                                'role': user.role, 
                                'team': user.team.name if user.team else "إدارة مركزية",
                                'team_id': user.team_id,
                                'dept': user.team.department.name if user.team and user.team.department else "-"
                            }
                            st.toast("أهلاً بك!", icon="👋")
                            time.sleep(1)
                            st.rerun()
                        else: st.error("خطأ في البيانات")
        
        with tab2:
            with st.form("new_user"):
                s = SessionLocal()
                teams = [t.name for t in s.query(Team).all()]
                s.close()
                
                nu = st.text_input("مستخدم جديد")
                np = st.text_input("كلمة السر", type="password")
                nf = st.text_input("الاسم الكامل")
                nt = st.selectbox("اختر الفرقة", teams) if teams else st.warning("لا توجد فرق متاحة")
                nr = st.radio("الصفة", ["باحث دائم", "طالب دكتوراه"], horizontal=True)
                
                if st.form_submit_button("تسجيل"):
                    role_map = {"باحث دائم": "researcher", "طالب دكتوراه": "phd_student"}
                    if register_service(nu, np, nf, role_map[nr], nt):
                        st.success("تم التسجيل! يرجى الانتظار لتفعيل الحساب.")
                    else: st.error("حدث خطأ (ربما المستخدم موجود)")

else:
    user = st.session_state['user']
    with st.sidebar:
        # الشعار في السايدبار
        logo_html_sb = ""
        if os.path.exists("logo.png"):
            b64 = get_img_as_base64("logo.png")
            if b64: logo_html_sb = f'<img src="data:image/png;base64,{b64}" style="width: 120px; margin-bottom: 10px;">'
        
        st.markdown(f"""
        <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center !important; padding-bottom: 15px; border-bottom: 1px solid #e2e8f0; margin-bottom: 15px;">
            {logo_html_sb}
            <h3 style="margin: 0; color: #1e3a8a; font-family:'Cairo'; text-align: center !important;">المركز البحثي أدرار</h3>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown(f"**👤 {user['name']}**")
        st.caption(f"الدور: {user['role']}")
        if user['team'] != "إدارة مركزية":
            st.caption(f"الفرقة: {user['team']}")
            st.caption(f"القسم: {user['dept']}")
        
        menu = ["الرئيسية", "الهيكل التنظيمي", "تسجيل نتاج", "سجل الأعمال"]
        if user['role'] == 'admin': menu.insert(1, "إدارة الأقسام والفرق")
        
        choice = st.sidebar.radio("القائمة", menu)
        
        if st.sidebar.button("خروج"):
            st.session_state['logged_in'] = False
            st.rerun()

    # --- محتوى الصفحات ---
    
    if choice == "الرئيسية":
        st.title("📊 لوحة القيادة")
        # بطاقات إحصائية بسيطة (يمكن توسيعها لاحقاً)
        c1, c2, c3 = st.columns(3)
        s = SessionLocal()
        with c1:
            st.metric("عدد الأقسام", s.query(Department).count())
        with c2:
            st.metric("عدد الفرق", s.query(Team).count())
        with c3:
            st.metric("عدد الباحثين", s.query(User).count())
        s.close()

    elif choice == "الهيكل التنظيمي":
        st.title("🏢 الهيكل التنظيمي للمخبر")
        st.markdown("---")
        
        s = SessionLocal()
        # جلب الأقسام مع فرقها وأعضائها (Eager Loading لتحسين الأداء)
        departments = s.query(Department).options(
            joinedload(Department.teams).joinedload(Team.members),
            joinedload(Department.teams).joinedload(Team.works)
        ).order_by(Department.dept_number).all()
        
        for dept in departments:
            with st.expander(f"📁 {dept.name} ({dept.abbreviation})", expanded=True):
                st.info(f"الاسم اللاتيني: {dept.latin_name}")
                
                # عرض فرق القسم
                if not dept.teams:
                    st.warning("لا توجد فرق في هذا القسم حالياً.")
                else:
                    for team in dept.teams:
                        # تصنيف الأعضاء
                        permanent = [m.full_name for m in team.members if m.role in ['researcher', 'leader']]
                        phd = [m.full_name for m in team.members if m.role == 'phd_student']
                        leader = next((m.full_name for m in team.members if m.role == 'leader'), "غير محدد")
                        
                        st.markdown(f"""
                        <div class="team-card">
                            <div class="team-header">🔹 {team.name} ({team.abbreviation or '-'})</div>
                            <div class="team-meta"><b>رئيس الفرقة:</b> {leader}</div>
                            <div class="team-meta"><b>التصنيف:</b> {team.classification or 'غير محدد'}</div>
                            <div style="font-size:13px; color:#333; margin: 8px 0;">{team.description or 'لا يوجد وصف.'}</div>
                            <div style="display: flex; gap: 10px;">
                                <div class="member-list" style="flex:1;">
                                    <b>👨‍🏫 الأعضاء الدائمون ({len(permanent)}):</b><br>{', '.join(permanent) if permanent else '-'}
                                </div>
                                <div class="member-list" style="flex:1;">
                                    <b>🎓 طلبة الدكتوراه ({len(phd)}):</b><br>{', '.join(phd) if phd else '-'}
                                </div>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
        s.close()

    elif choice == "إدارة الأقسام والفرق" and user['role'] == 'admin':
        st.title("⚙️ إدارة الهيكل")
        
        t1, t2 = st.tabs(["إضافة فرقة جديدة", "تحديث بيانات فرقة"])
        
        s = SessionLocal()
        depts = s.query(Department).all()
        dept_names = {d.name: d.id for d in depts}
        
        with t1:
            with st.form("add_team"):
                st.subheader("إضافة فرقة جديدة")
                d_select = st.selectbox("القسم التابع له", list(dept_names.keys()))
                t_name = st.text_input("اسم الفرقة")
                t_abbr = st.text_input("الاسم المختصر")
                t_num = st.number_input("رقم الفرقة", min_value=1, step=1)
                t_class = st.text_area("الكلمات المفتاحية / التصنيف")
                t_desc = st.text_area("وصف برنامج البحث")
                
                if st.form_submit_button("حفظ الفرقة"):
                    new_team = Team(
                        name=t_name, 
                        abbreviation=t_abbr, 
                        team_number=t_num,
                        classification=t_class,
                        description=t_desc,
                        department_id=dept_names[d_select]
                    )
                    s.add(new_team)
                    s.commit()
                    st.success("تمت الإضافة بنجاح")
                    time.sleep(1)
                    st.rerun()
        s.close()

    elif choice == "تسجيل نتاج":
        # (نفس الكود السابق مع التأكد من ربط العمل بالباحث الحالي)
        st.title("📝 تسجيل عمل جديد")
        # ... (يمكنك استخدام الكود السابق هنا)
        st.info("خاصية التسجيل متاحة (استخدم الكود السابق هنا)")

    elif choice == "سجل الأعمال":
        st.title("🗂️ سجل الأعمال")
        # ... (جدول العرض)

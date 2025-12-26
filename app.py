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
st.set_page_config(page_title="منصة التميز البحثي", layout="wide", page_icon="🎓")

# --- دالة الشعار ---
def get_img_as_base64(file_path):
    try:
        with open(file_path, "rb") as f: data = f.read()
        return base64.b64encode(data).decode()
    except: return None

# ==========================================
# 2. إعدادات قاعدة البيانات
# ==========================================
if "db" not in st.secrets:
    st.error("❌ ملف الأسرار غير موجود.")
    st.stop()

@st.cache_resource
def get_db_engine():
    try:
        db_config = st.secrets["db"]
        encoded_password = urllib.parse.quote_plus(db_config["password"])
        DATABASE_URL = f"postgresql://{db_config['user']}:{encoded_password}@{db_config['host']}:{db_config['port']}/{db_config['name']}?sslmode=require"
        return create_engine(DATABASE_URL, pool_pre_ping=True, pool_recycle=1800)
    except Exception as e: return None

engine = get_db_engine()
if not engine: st.stop()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# ==========================================
# 3. تعريف الجداول (الهيكلة الجديدة) 🏗️
# ==========================================

# 1. جدول الأقسام (الجديد)
class Department(Base):
    __tablename__ = "departments"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False) # القسم 1، القسم 2...
    teams = relationship("Team", back_populates="department")

# 2. جدول الفرق (المطور)
class Team(Base):
    __tablename__ = "teams"
    id = Column(Integer, primary_key=True, index=True)
    
    # البيانات الأساسية
    department_id = Column(Integer, ForeignKey("departments.id"))
    team_number = Column(String, nullable=True) # رقم الفرقة
    name = Column(String, unique=True, nullable=False) # اسم الفرقة
    short_name = Column(String, nullable=True) # الاسم المختصر
    leader_name = Column(String, nullable=True) # رئيس الفرقة (نصي أو رابط)
    
    # البيانات العلمية
    thematic_classification = Column(Text, nullable=True) # التصنيف (ميادين، كلمات مفتاحية)
    scientific_description = Column(Text, nullable=True) # وصف برنامج البحث
    
    # العلاقات
    department = relationship("Department", back_populates="teams")
    members = relationship("User", back_populates="team")

# 3. جدول المستخدمين (المطور)
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    full_name = Column(String, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, nullable=False) # admin, leader, researcher
    
    # نوع العضوية (جديد)
    member_type = Column(String, nullable=True) # "دائم" أو "طالب دكتوراه"
    
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=True)
    team = relationship("Team", back_populates="members")
    works = relationship("Work", back_populates="researcher")

class Work(Base):
    __tablename__ = "works"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(Text, nullable=False)
    details = Column(Text, nullable=True) 
    activity_type = Column(String, nullable=False)
    classification = Column(String, nullable=True)
    publication_date = Column(Date, nullable=False)
    year = Column(Integer, nullable=False)
    points = Column(Integer, default=0)
    user_id = Column(Integer, ForeignKey("users.id"))
    researcher = relationship("User", back_populates="works")

# --- دالة التهيئة الأولية ---
def init_db():
    try:
        Base.metadata.create_all(bind=engine)
        session = SessionLocal()
        
        # 1. إنشاء الأقسام الستة
        if not session.query(Department).first():
            depts = [Department(name=f"القسم ({i})") for i in range(1, 7)]
            session.add_all(depts)
            session.commit()
            
        # 2. إنشاء فرق افتراضية (مثال)
        if not session.query(Team).first():
            dept1 = session.query(Department).filter_by(name="القسم (1)").first()
            if dept1:
                t1 = Team(
                    name="فرقة تكنولوجيا التعليم والرقمنة",
                    short_name="EdTech",
                    team_number="01",
                    leader_name="أ.د محمد الفاتح",
                    thematic_classification="تكنولوجيا التعليم، الذكاء الاصطناعي، الرقمنة",
                    scientific_description="تهتم الفرقة بدراسة أثر الرقمنة على التحصيل العلمي...",
                    department_id=dept1.id
                )
                session.add(t1)
                session.commit()

        # 3. إنشاء المدير
        if not session.query(User).filter_by(username="admin").first():
            hashed = bcrypt.hashpw("12345".encode(), bcrypt.gensalt()).decode()
            session.add(User(username="admin", full_name="المدير العام", password_hash=hashed, role="admin", member_type="دائم"))
            session.commit()
            
        session.close()
        return True
    except Exception as e:
        print(f"Init Error: {e}")
        return False

# ==========================================
# 4. الخدمات (Services)
# ==========================================
def auth_user(u, p):
    s = SessionLocal()
    try:
        user = s.query(User).options(joinedload(User.team)).filter(User.username == u).first()
        if user and bcrypt.checkpw(p.encode(), user.password_hash.encode()): return user
    except: pass
    finally: s.close()
    return None

def register_service(u, p, f, role, team_id, m_type):
    s = SessionLocal()
    try:
        h = bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()
        s.add(User(username=u, full_name=f, password_hash=h, role=role, team_id=team_id, member_type=m_type))
        s.commit()
        return True
    except:
        s.rollback()
        return False
    finally: s.close()

def add_work_service(uid, title, details, type_, cls, date_, pts):
    s = SessionLocal()
    try:
        s.add(Work(user_id=uid, title=title, details=details, activity_type=type_, classification=cls, publication_date=date_, year=date_.year, points=pts))
        s.commit()
        return True
    except: return False
    finally: s.close()

def get_works_df():
    q = """
    SELECT w.title, w.activity_type, w.publication_date, u.full_name, t.name as team_name, d.name as dept_name
    FROM works w 
    JOIN users u ON w.user_id = u.id 
    LEFT JOIN teams t ON u.team_id = t.id
    LEFT JOIN departments d ON t.department_id = d.id
    ORDER BY w.publication_date DESC
    """
    try: return pd.read_sql(q, engine)
    except: return pd.DataFrame()

# ==========================================
# 5. التنسيق (CSS)
# ==========================================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;800&family=Tajawal:wght@400;500;700&display=swap');
    html, body, .stApp { font-family: 'Tajawal', sans-serif; direction: rtl; text-align: right; }
    h1, h2, h3, h4 { font-family: 'Cairo', sans-serif !important; text-align: right; }
    .stMarkdown, p, div { text-align: right; }
    [data-testid="stSidebar"] { border-left: 1px solid #e2e8f0; }
    .stTextInput input, .stSelectbox div { text-align: right; direction: rtl; }
    
    /* تنسيق بطاقة الفرقة */
    .team-card { background: #f8fafc; padding: 20px; border-radius: 10px; border: 1px solid #e2e8f0; margin-bottom: 20px; }
    .team-header { color: #1e3a8a; font-family: 'Cairo'; font-size: 1.2rem; font-weight: bold; border-bottom: 2px solid #2563eb; padding-bottom: 10px; margin-bottom: 10px; }
    .team-info-row { display: flex; justify-content: space-between; margin-bottom: 8px; border-bottom: 1px dashed #cbd5e1; padding-bottom: 5px; }
    .team-label { font-weight: bold; color: #64748b; margin-left: 10px; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 6. الواجهة
# ==========================================

if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
    init_db()

if not st.session_state['logged_in']:
    c1, c2, c3 = st.columns([1, 1.5, 1])
    with c2:
        logo_html = '<div style="font-size: 60px; margin-bottom: 10px;">🏛️</div>'
        if os.path.exists("logo.png"):
            b64 = get_img_as_base64("logo.png")
            if b64: logo_html = f'<img src="data:image/png;base64,{b64}" style="width: 180px; margin-bottom: 20px;">'
            
        st.markdown(f"""
        <div style="display: flex; flex-direction: column; align-items: center; text-align: center !important; margin-bottom: 30px;">
            {logo_html}
            <h1 style="color:#1e40af; font-family:'Cairo'; text-align: center !important;">بوابة البحث العلمي</h1>
            <p style="color:#64748b; text-align: center !important;">نظام إدارة المخابر الجامعية الموحد</p>
        </div>""", unsafe_allow_html=True)
        
        tab1, tab2 = st.tabs(["دخول", "تسجيل"])
        with tab1:
            with st.form("login"):
                u = st.text_input("المستخدم")
                p = st.text_input("كلمة المرور", type="password")
                if st.form_submit_button("دخول", use_container_width=True):
                    usr = auth_user(u, p)
                    if usr:
                        st.session_state['logged_in'] = True
                        st.session_state['user'] = {'id': usr.id, 'name': usr.full_name, 'role': usr.role, 'team': usr.team.name if usr.team else ""}
                        st.rerun()
                    else: st.error("بيانات خاطئة")
        
        with tab2:
            with st.form("signup"):
                s = SessionLocal()
                # جلب الأقسام والفرق للهيكلة
                depts = s.query(Department).all()
                dept_names = [d.name for d in depts]
                
                c_s1, c_s2 = st.columns(2)
                with c_s1: sel_dept = st.selectbox("القسم", dept_names)
                
                # فلترة الفرق حسب القسم المختار (محاكاة)
                selected_dept_id = next((d.id for d in depts if d.name == sel_dept), None)
                teams = s.query(Team).filter(Team.department_id == selected_dept_id).all()
                team_dict = {t.name: t.id for t in teams}
                
                with c_s2: sel_team = st.selectbox("الفرقة", list(team_dict.keys()) if teams else [])
                
                nu = st.text_input("المستخدم")
                np = st.text_input("كلمة المرور", type="password")
                nf = st.text_input("الاسم الكامل")
                
                # اختيار نوع العضوية
                m_type = st.radio("نوع العضوية", ["عضو دائم", "طالب دكتوراه"], horizontal=True)
                role = "leader" if st.checkbox("أنا رئيس الفرقة") else "researcher"
                
                code = st.text_input("كود التفعيل", type="password")
                
                if st.form_submit_button("إنشاء حساب"):
                    valid_code = "LEADER2025" if role == "leader" else "RES2025"
                    if code == valid_code:
                        if sel_team:
                            if register_service(nu, np, nf, role, team_dict[sel_team], m_type):
                                st.success("تم!")
                            else: st.error("المستخدم موجود")
                        else: st.error("يرجى اختيار فرقة")
                    else: st.error("الكود خاطئ")
                s.close()

else:
    user = st.session_state['user']
    with st.sidebar:
        # الشعار الجانبي
        if os.path.exists("logo.png"):
            b64 = get_img_as_base64("logo.png")
            if b64: st.markdown(f'<div style="text-align:center"><img src="data:image/png;base64,{b64}" style="width: 140px; margin-bottom:10px"></div>', unsafe_allow_html=True)
        
        st.markdown(f"""<div style="text-align: center !important;">
            <h3 style="margin:0; color:#1e3a8a; text-align: center !important;">المركز البحثي أدرار</h3>
            <span style="font-size:12px; color:#64748b; text-align: center !important;">منصة التميز البحثي</span>
        </div>""", unsafe_allow_html=True)
        st.divider()
        
        menu = {
            "🏠 الرئيسية": "main",
            "👥 هيكل المخبر (الفرق)": "structure",
            "📝 تسجيل نتاج": "add",
            "📊 الإحصائيات": "stats"
        }
        sel = st.radio("القائمة", list(menu.keys()))
        choice = menu[sel]
        
        st.divider()
        if st.button("خروج"):
            st.session_state['logged_in'] = False
            st.rerun()

    # --- الصفحات ---
    if choice == "main":
        st.title("🏠 لوحة القيادة العامة")
        # عرض سريع للإحصائيات
        s = SessionLocal()
        users_count = s.query(User).count()
        teams_count = s.query(Team).count()
        works_count = s.query(Work).count()
        s.close()
        
        c1, c2, c3 = st.columns(3)
        c1.metric("إجمالي الباحثين", users_count)
        c2.metric("عدد الفرق", teams_count)
        c3.metric("النتاج العلمي", works_count)

    elif choice == "structure":
        st.title("👥 الهيكلة التنظيمية للمخبر")
        
        session = SessionLocal()
        departments = session.query(Department).all()
        
        if not departments:
            st.info("لا توجد أقسام معرفة بعد. قم بتهيئة قاعدة البيانات.")
        
        # عرض الأقسام والفرق
        for dept in departments:
            with st.expander(f"📂 {dept.name} (عدد الفرق: {len(dept.teams)})"):
                for team in dept.teams:
                    # بطاقة تعريف الفرقة
                    st.markdown(f"""
                    <div class="team-card">
                        <div class="team-header">🔹 {team.name} (رقم: {team.team_number or 'غير محدد'})</div>
                        <div class="team-info-row"><span class="team-label">الاسم المختصر:</span> <span>{team.short_name or '-'}</span></div>
                        <div class="team-info-row"><span class="team-label">رئيس الفرقة:</span> <span>{team.leader_name or 'غير معين'}</span></div>
                        <div class="team-info-row"><span class="team-label">التصنيف الموضوعاتي:</span> <span>{team.thematic_classification or '-'}</span></div>
                        <div style="margin-top:10px;"><strong>📄 وصف البرنامج العلمي:</strong><br><p>{team.scientific_description or 'لا يوجد وصف'}</p></div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # قوائم الأعضاء
                    c_m1, c_m2 = st.columns(2)
                    with c_m1:
                        st.caption("👨‍🏫 الأعضاء الدائمون")
                        permanent = [m.full_name for m in team.members if m.member_type == "عضو دائم"]
                        if permanent:
                            for p in permanent: st.markdown(f"- {p}")
                        else: st.markdown("_لا يوجد_")
                        
                    with c_m2:
                        st.caption("🎓 طلبة الدكتوراه")
                        phd = [m.full_name for m in team.members if m.member_type == "طالب دكتوراه"]
                        if phd:
                            for p in phd: st.markdown(f"- {p}")
                        else: st.markdown("_لا يوجد_")
                    
                    st.divider()
        session.close()

    elif choice == "add":
        st.title("📝 تسجيل نتاج علمي جديد")
        with st.form("add_work"):
            title = st.text_input("عنوان العمل")
            w_type = st.selectbox("نوع العمل", ["مقال", "مداخلة", "كتاب"])
            submit = st.form_submit_button("حفظ")
            if submit and title:
                # هنا يتم الحفظ (تبسيط للكود)
                add_work_service(user['id'], title, "{}", w_type, "A", date.today(), 100)
                st.toast("تم الحفظ بنجاح", icon="✅")

    elif choice == "stats":
        st.title("📊 الإحصائيات")
        df = get_works_df()
        if not df.empty:
            st.dataframe(df)
            fig = px.pie(df, names='activity_type', title='توزيع الأنشطة')
            st.plotly_chart(fig)
        else:
            st.info("لا توجد بيانات للعرض")

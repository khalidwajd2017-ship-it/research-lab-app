import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, Column, Integer, String, Date, ForeignKey, Text, inspect
from sqlalchemy.orm import sessionmaker, relationship, declarative_base, joinedload
import bcrypt
from datetime import date
import plotly.express as px
import time
import json 
import base64
import os
import io

# --- 1. إعدادات الصفحة ---
st.set_page_config(
    page_title="URSH - بوابة البحث العلمي",
    layout="wide",
    initial_sidebar_state="expanded",
    page_icon="🎓"
)

# --- الثوابت ---
ACTIVATION_CODES = {
    "admin": "ADMIN2025",
    "dept_head": "HEAD2025",
    "leader": "LEAD2025",
    "researcher": "RES2025"
}

ACTIVITY_TYPES = [
    "مقال في مجلة علمية", "مداخلة في مؤتمر", "تأليف كتاب", 
    "فصل في كتاب", "براءة اختراع", "تأطير مذكرة", "مشروع بحث"
]

MEMBER_TYPES = {
    "permanent": "عضو دائم",
    "phd_student": "طالب دكتوراه",
    "affiliate": "ملحق بحث",
    "associate": "عضو مشارك"
}

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
        encoded_password = db_config["password"].replace("@", "%40") 
        DATABASE_URL = f"postgresql://{db_config['user']}:{encoded_password}@{db_config['host']}:{db_config['port']}/{db_config['name']}?sslmode=require"
        return create_engine(DATABASE_URL, pool_pre_ping=True)
    except: return None

engine = get_db_engine()
if not engine: st.stop()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- النماذج (Tables) ---
class Department(Base):
    __tablename__ = "departments"
    id = Column(Integer, primary_key=True)
    name_ar = Column(String)
    name_la = Column(String)
    short_name = Column(String)
    head_name = Column(String)
    teams = relationship("Team", back_populates="department")
    users = relationship("User", back_populates="department")

class Team(Base):
    __tablename__ = "teams"
    id = Column(Integer, primary_key=True)
    name = Column(String)
    name_en = Column(String)
    short_name = Column(String)
    head_name = Column(String)
    description = Column(Text)
    classification = Column(String)
    domains = Column(String)
    keywords = Column(String)
    program_desc = Column(Text)
    
    department_id = Column(Integer, ForeignKey("departments.id"))
    department = relationship("Department", back_populates="teams")
    members = relationship("User", back_populates="team")

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True)
    full_name = Column(String)
    password_hash = Column(String)
    role = Column(String) 
    member_type = Column(String)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=True)
    team = relationship("Team", back_populates="members")
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=True)
    department = relationship("Department", back_populates="users")
    works = relationship("Work", back_populates="researcher")

class Work(Base):
    __tablename__ = "works"
    id = Column(Integer, primary_key=True)
    title = Column(Text)
    details = Column(Text) 
    activity_type = Column(String)
    classification = Column(String)
    publication_date = Column(Date)
    year = Column(Integer)
    points = Column(Integer)
    user_id = Column(Integer, ForeignKey("users.id"))
    researcher = relationship("User", back_populates="works")

# ==========================================
# 3. الخدمات والدوال المساعدة
# ==========================================
def auto_init_system():
    try:
        inspector = inspect(engine)
        if not inspector.has_table("users"):
            Base.metadata.create_all(bind=engine)
        
        session = SessionLocal()
        
        departments_data = [
            {"id": 1, "ar": "الدراسات الفلسفية النظرية", "la": "Theoretical Philosophical Studies", "sh": "TPS", "head": "أ.د. عبد اللاوي عبد الله", "user": "head_tps"},
            {"id": 2, "ar": "الدراسات الفلسفية التطبيقية", "la": "Applied Philosophical Studies", "sh": "APS", "head": "أ.د. دراس شهر زاد", "user": "head_aps"},
            {"id": 3, "ar": "الدراسات الدينية والاتجاهات الروحية", "la": "Religious Studies and Spiritual Trends", "sh": "RSST", "head": "أ.د. رزقي بن عومر", "user": "head_rsst"},
            {"id": 4, "ar": "الدراسات السوسيولوجية", "la": "Sociological Studies", "sh": "SS", "head": "أ.د. شنافي فوزية", "user": "head_ss"},
            {"id": 5, "ar": "الدراسات الأنثروبولوجية", "la": "Anthropological studies", "sh": "AS", "head": "أ.د. مباركة بلحسن", "user": "head_as"},
            {"id": 6, "ar": "الدراسات الإنسانية، اللغات، والترجمة", "la": "Humanities, Languages, and Translation", "sh": "HLT", "head": "د. جميل نسيمة", "user": "head_hlt"}
        ]

        pw_hash = bcrypt.hashpw("12345".encode(), bcrypt.gensalt()).decode()

        for d_data in departments_data:
            dept = session.query(Department).filter_by(id=d_data["id"]).first()
            if not dept:
                dept = Department(
                    id=d_data["id"], name_ar=d_data["ar"], name_la=d_data["la"], 
                    short_name=d_data["sh"], head_name=d_data["head"]
                )
                session.add(dept)
                session.flush()
                
                t1 = Team(
                    name=f"فرقة بحث {d_data['sh']} - النموذجية",
                    name_en=f"Research Team {d_data['sh']} - Standard",
                    short_name=f"{d_data['sh']}-A",
                    head_name="د. باحث رئيسي",
                    description="فرقة تعنى بالدراسات المعمقة في التخصص وتطوير المناهج العلمية الحديثة.",
                    classification="بحث أساسي وتطبيقي",
                    domains="العلوم الإنسانية، الفلسفة، المجتمع",
                    keywords="مجتمع، هوية، تراث، حداثة",
                    program_desc="مشروع بحثي يهدف إلى دراسة التحولات الاجتماعية والثقافية في المجتمع الجزائري.",
                    department_id=dept.id
                )
                session.add(t1)
                session.commit()
            
            if not session.query(User).filter_by(username=d_data["user"]).first():
                session.add(User(
                    username=d_data["user"], full_name=d_data["head"], password_hash=pw_hash,
                    role="dept_head", member_type="permanent", department_id=dept.id
                ))
                session.commit()

        if not session.query(User).filter_by(username="admin").first():
            session.add(User(username="admin", full_name="المدير العام", password_hash=pw_hash, role="admin", member_type="admin"))
            session.commit()
            
        session.close()
    except Exception as e:
        print(f"Init Error: {e}")

auto_init_system()

def auth_user(u, p):
    s = SessionLocal()
    try:
        user = s.query(User).options(joinedload(User.team), joinedload(User.department)).filter(User.username == u).first()
        if user and bcrypt.checkpw(p.encode(), user.password_hash.encode()): return user
    except: pass
    finally: s.close()
    return None

def register_user_secure(u, f, p, role, code, t_id, d_id, m_type):
    if code != ACTIVATION_CODES.get(role): return False, "⛔ كود التفعيل غير صحيح!"
    s = SessionLocal()
    try:
        if s.query(User).filter(User.username == u).first(): return False, "⚠️ اسم المستخدم موجود"
        h = bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()
        s.add(User(username=u, full_name=f, password_hash=h, role=role, team_id=t_id, department_id=d_id, member_type=m_type))
        s.commit()
        return True, "✅ تم الإنشاء"
    except Exception as e:
        s.rollback(); return False, f"خطأ: {str(e)}"
    finally: s.close()

def add_user_manual(u, f, p, role, t_id, d_id, m_type):
    s = SessionLocal()
    try:
        if s.query(User).filter(User.username == u).first(): return False, "موجود مسبقاً"
        h = bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()
        s.add(User(username=u, full_name=f, password_hash=h, role=role, team_id=t_id, department_id=d_id, member_type=m_type))
        s.commit()
        return True, "تمت الإضافة"
    except: s.rollback(); return False, "خطأ"
    finally: s.close()

def add_work_service(uid, title, details_json, atype, cls, date_obj, pts):
    s = SessionLocal()
    try:
        s.add(Work(user_id=uid, title=title, details=details_json, activity_type=atype, classification=cls, publication_date=date_obj, year=date_obj.year, points=pts))
        s.commit()
        return True
    except: s.rollback(); return False
    finally: s.close()

def update_work_service(wid, title, date_obj):
    s = SessionLocal()
    try:
        w = s.query(Work).filter(Work.id == wid).first()
        w.title = title; w.publication_date = date_obj; w.year = date_obj.year
        s.commit()
        return True
    except: s.rollback(); return False
    finally: s.close()

def delete_work_service(wid):
    s = SessionLocal()
    try:
        s.query(Work).filter(Work.id == wid).delete()
        s.commit()
        return True
    except: s.rollback(); return False
    finally: s.close()

def change_password(uid, new_p):
    s = SessionLocal()
    try:
        user = s.query(User).filter(User.id == uid).first()
        user.password_hash = bcrypt.hashpw(new_p.encode(), bcrypt.gensalt()).decode()
        s.commit()
        return True
    except: s.rollback(); return False
    finally: s.close()

def get_img_as_base64(file_path):
    try:
        with open(file_path, "rb") as f: data = f.read()
        return base64.b64encode(data).decode()
    except: return None

def get_smart_data(user):
    base_q = """
    SELECT 
        w.id, w.user_id, w.title, w.activity_type, w.publication_date, w.year, w.points, w.classification, w.details,
        u.full_name as researcher, 
        t.name as team, 
        d.name_ar as department
    FROM works w
    JOIN users u ON w.user_id = u.id
    LEFT JOIN teams t ON u.team_id = t.id
    LEFT JOIN departments d ON u.department_id = d.id 
    """
    try:
        df = pd.read_sql(base_q, engine)
        df['department'] = df['department'].fillna('غير محدد')
        df['team'] = df['team'].fillna('غير محدد')
        df['activity_type'] = df['activity_type'].fillna('غير محدد')
        df['publication_date'] = pd.to_datetime(df['publication_date']).dt.date
        
        if df.empty: return df
        if user.role == 'admin': return df
        elif user.role == 'dept_head': 
            if user.department: return df[df['department'] == user.department.name_ar]
            return pd.DataFrame()
        elif user.role == 'leader': 
            if user.team: return df[df['team'] == user.team.name]
            return pd.DataFrame()
        else: return df[df['user_id'] == user.id]
    except Exception as e: 
        return pd.DataFrame()

def to_excel(df):
    try:
        output = io.BytesIO()
        export_df = df.copy()
        if 'details' in export_df.columns:
            export_df['تفاصيل'] = export_df['details'].apply(lambda x: " | ".join([f"{k}:{v}" for k,v in json.loads(x).items() if v]) if x else "")
        cols_map = {'title': 'العنوان', 'activity_type': 'النوع', 'publication_date': 'التاريخ', 'points': 'النقاط', 'researcher': 'الباحث', 'team': 'الفرقة'}
        export_df = export_df.rename(columns=cols_map)
        final_cols = [c for c in cols_map.values() if c in export_df.columns] + ['تفاصيل']
        export_df = export_df[final_cols] if not export_df.empty else export_df
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            export_df.to_excel(writer, index=False, sheet_name='التقرير')
        return output.getvalue()
    except: return None

# ==========================================
# 4. التنسيق (CSS)
# ==========================================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;800&family=Tajawal:wght@400;500;700&display=swap');
    :root { --primary: #2563eb; --bg: #f8fafc; }
    html, body, .stApp { font-family: 'Tajawal', sans-serif; direction: rtl; background-color: #fcfcfc; text-align: right; }
    h1, h2, h3, h4, h5 { font-family: 'Cairo'; font-weight: 800; color: #1e3a8a; text-align: right !important; }
    [data-testid="stSidebar"] { background: #fff; border-left: 1px solid #e2e8f0; }
    .stTextInput input, .stSelectbox div, .stTextArea textarea, .stDateInput input { text-align: right; direction: rtl; border-radius: 8px; font-family: 'Tajawal'; }
    
    .kpi-container { background-color: white; padding: 20px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.04); border: 1px solid #f1f5f9; border-right: 4px solid #3b82f6; display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; transition: transform 0.2s; }
    .kpi-container:hover { transform: translateY(-3px); }
    .kpi-value { font-family: 'Cairo'; font-size: 28px; font-weight: 800; color: #0f172a; line-height: 1.2; }
    .kpi-label { font-size: 13px; color: #64748b; font-weight: 600; }
    .kpi-icon { width: 45px; height: 45px; background-color: #eff6ff; border-radius: 10px; display: flex; align-items: center; justify-content: center; font-size: 22px; color: #3b82f6; }
    .chart-container { background-color: white; padding: 20px; border-radius: 15px; border: 1px solid #e2e8f0; box-shadow: 0 2px 4px rgba(0,0,0,0.02); margin-bottom: 20px; }
    .stButton>button { width: 100%; border-radius: 8px; font-family: 'Cairo'; font-weight: bold; }
    [data-testid="stForm"] { background: white; padding: 25px; border-radius: 12px; border: 1px solid #e5e7eb; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05); }
    .rtl-header { text-align: right; direction: rtl; width: 100%; display: block; font-family: 'Cairo'; font-weight: 700; color: #1f2937; margin-bottom: 10px; font-size: 18px; }
    
    [data-testid="stExpander"] { direction: rtl !important; text-align: right !important; border: 1px solid #e2e8f0; border-radius: 8px; margin-bottom: 10px; background: #fff; }
    [data-testid="stExpander"] summary { flex-direction: row-reverse !important; justify-content: flex-end !important; text-align: right !important; font-family: 'Cairo', sans-serif !important; font-weight: 700; color: #1e3a8a; padding: 10px !important; }
    [data-testid="stExpander"] summary p { text-align: right !important; margin: 0 !important; padding-right: 10px !important; }
    [data-testid="stExpander"] summary:hover { background-color: #f8fafc; color: #2563eb !important; }
    [data-testid="stExpander"] > div { direction: rtl !important; text-align: right !important; padding: 15px !important; border-top: 1px solid #f1f5f9; }
    
    .dept-card { background: #fff; padding: 20px; border-radius: 10px; border: 1px solid #e5e7eb; margin-bottom: 15px; border-right: 5px solid #2563eb; }
    .dept-title { font-family: 'Cairo'; color: #1e40af; font-size: 18px; font-weight: bold; }
    .dept-info { font-size: 14px; color: #4b5563; margin-top: 5px; }
    .team-header { background: #f1f5f9; padding: 15px; border-radius: 8px; border-right: 4px solid #10b981; margin-bottom: 10px; text-align: right; }
    .field-label { font-weight: bold; color: #1f2937; display: block; margin-bottom: 2px; }
    .field-val { color: #4b5563; margin-bottom: 10px; display: block; font-size: 14px; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 5. التطبيق
# ==========================================

if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False

if not st.session_state['logged_in']:
    c1, c2, c3 = st.columns([1, 1.5, 1])
    with c2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        logo_path = "logo.png"
        logo_html = '<div style="font-size: 60px; margin-bottom: 10px; text-align:center;">🏛️</div>'
        if os.path.exists(logo_path):
            img = get_img_as_base64(logo_path)
            if img: logo_html = f'<div style="display: flex; justify-content: center;"><img src="data:image/png;base64,{img}" style="width: 150px; margin-bottom: 20px;"></div>'

        st.markdown(logo_html, unsafe_allow_html=True)
        st.markdown("""<div style="display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; width: 100%; margin-bottom: 30px;"><h1 style="color:#1e40af; font-family:'Cairo'; margin: 0;">بوابة البحث العلمي</h1><p style="color:#64748b; margin-top: 5px;">نظام إدارة المخابر الجامعية الموحد</p></div>""", unsafe_allow_html=True)
        
        tab_login, tab_signup = st.tabs(["🔐 تسجيل الدخول", "📝 حساب جديد (بالكود)"])
        
        with tab_login:
            with st.form("login"):
                u = st.text_input("اسم المستخدم")
                p = st.text_input("كلمة المرور", type="password")
                if st.form_submit_button("دخول", type="primary", use_container_width=True):
                    user = auth_user(u, p)
                    if user:
                        st.session_state['logged_in'] = True
                        st.session_state['user_id'] = user.id
                        st.rerun()
                    else: st.error("بيانات خاطئة")

        with tab_signup:
            st.markdown("##### 🆕 إنشاء حساب باستخدام كود التفعيل")
            c_a, c_b = st.columns(2)
            new_name = c_a.text_input("الاسم الكامل")
            new_user = c_b.text_input("اسم المستخدم (للدخول)")
            c_pass, c_role = st.columns(2)
            new_pass = c_pass.text_input("كلمة المرور", type="password")
            role_key = c_role.selectbox("الصفة", list(ACTIVATION_CODES.keys()))
            
            m_type_key = "permanent"
            if role_key in ['leader', 'researcher']:
                m_type_key = st.selectbox("نوع العضوية", list(MEMBER_TYPES.keys()), format_func=lambda x: MEMBER_TYPES[x])
            
            session = SessionLocal()
            depts = session.query(Department).all()
            d_map = {d.name_ar: d.id for d in depts}
            sel_dept_id = None
            sel_team_id = None
            
            if role_key != 'admin':
                d_name = st.selectbox("القسم", list(d_map.keys()))
                sel_dept_id = d_map[d_name]
                if role_key in ['leader', 'researcher']:
                    teams = session.query(Team).filter_by(department_id=sel_dept_id).all()
                    if teams:
                        t_map = {t.name: t.id for t in teams}
                        t_name = st.selectbox("الفرقة", list(t_map.keys()))
                        sel_team_id = t_map[t_name]
                    else: st.warning("⚠️ لا توجد فرق.")
            session.close()

            act_code = st.text_input("🔑 كود التفعيل", type="password")
            
            if st.button("إنشاء الحساب", type="primary", use_container_width=True):
                if new_user and new_pass and act_code:
                    success, msg = register_user_secure(new_user, new_name, new_pass, role_key, act_code, sel_team_id, sel_dept_id, m_type_key)
                    if success: st.success(msg)
                    else: st.error(msg)
                else: st.warning("جميع الحقول مطلوبة")

# --- النظام الداخلي ---
else:
    session = SessionLocal()
    user = session.query(User).options(joinedload(User.team), joinedload(User.department)).filter(User.id == st.session_state['user_id']).first()
    
    with st.sidebar:
        logo_path = "logo.png"
        sb_logo = ""
        if os.path.exists(logo_path):
            img = get_img_as_base64(logo_path)
            if img: sb_logo = f'<div style="text-align:center;"><img src="data:image/png;base64,{img}" style="width: 130px; margin-bottom: 15px;"></div>'
        st.markdown(sb_logo, unsafe_allow_html=True)
        
        st.markdown(f"""
        <div style="display: flex; justify-content: center; align-items: center; text-align: center; width: 100%; margin-bottom: 20px;">
            <h3 style="color:#1e3a8a; font-family:'Cairo'; margin:0; font-size:16px; line-height:1.4;">وحدة البحث في علوم الإنسان<br>للدراسات الفلسفية، الاجتماعية والإنسانية</h3>
        </div>
        """, unsafe_allow_html=True)
        
        st.info(f"👤 مرحباً: {user.full_name}")
        
        menu = {
            "لوحة القيادة": "📊 لوحة القيادة",
            "الهيكل التنظيمي": "🏢 الهيكل التنظيمي",
            "تسجيل نتاج": "📝 تسجيل نتاج جديد",
            "إدارة الأنشطة": "🗂️ إدارة الأنشطة",
            "أعمالي": "📂 سجل أعمالي",
            "الإعدادات": "⚙️ الإعدادات"
        }
        if user.role == 'admin': menu["إدارة المستخدمين"] = "👥 إدارة المستخدمين (يدوي)"
            
        sel = st.sidebar.radio("القائمة", list(menu.values()), label_visibility="collapsed")
        selection = [k for k, v in menu.items() if v == sel][0]
        
        st.markdown("---")
        if st.button("تسجيل الخروج"):
            st.session_state['logged_in'] = False
            st.rerun()

    # --- 1. لوحة القيادة ---
    if selection == "لوحة القيادة":
        st.markdown(f"## 📊 لوحة القيادة والتحليل البياني")
        df = get_smart_data(user)
        if not df.empty:
            with st.expander("🔍 تصفية البيانات", expanded=True):
                col_d1, col_d2 = st.columns(2)
                min_date = df['publication_date'].min()
                max_date = df['publication_date'].max()
                d_from = col_d1.date_input("من تاريخ", min_date)
                d_to = col_d2.date_input("إلى تاريخ", max_date)
                
                available_years = sorted(df['year'].unique().tolist(), reverse=True)
                selected_year = st.selectbox("أو اختر سنة محددة (تتجاوز التاريخ)", ["الكل"] + available_years)

                c1, c2, c3 = st.columns(3)
                depts = sorted(df['department'].unique().tolist())
                sel_dept = c1.selectbox("القسم", ["الكل"] + depts)
                if sel_dept != "الكل":
                    teams = sorted(df[df['department'] == sel_dept]['team'].unique().tolist())
                else:
                    teams = sorted(df['team'].unique().tolist())
                sel_team = c2.selectbox("الفرقة", ["الكل"] + teams)
                types = sorted(df['activity_type'].unique().tolist())
                sel_type = c3.selectbox("نوع النشاط", ["الكل"] + types)

            if selected_year != "الكل":
                filtered = df[df['year'] == selected_year]
            else:
                filtered = df[(df['publication_date'] >= d_from) & (df['publication_date'] <= d_to)]
            
            if sel_dept != "الكل": filtered = filtered[filtered['department'] == sel_dept]
            if sel_team != "الكل": filtered = filtered[filtered['team'] == sel_team]
            if sel_type != "الكل": filtered = filtered[filtered['activity_type'] == sel_type]

            excel_data = to_excel(filtered)
            if excel_data: st.download_button("📥 تحميل التقرير (Excel)", excel_data, f"report_{date.today()}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

            st.markdown("<br>", unsafe_allow_html=True)
            k1, k2, k3, k4 = st.columns(4)
            with k4: st.markdown(f'<div class="kpi-container"><div class="kpi-info"><div class="kpi-value">{len(filtered)}</div><div class="kpi-label">إجمالي النتاج</div></div><div class="kpi-icon">📚</div></div>', unsafe_allow_html=True)
            with k3: st.markdown(f'<div class="kpi-container"><div class="kpi-info"><div class="kpi-value">{filtered["researcher"].nunique()}</div><div class="kpi-label">الباحثون</div></div><div class="kpi-icon">👥</div></div>', unsafe_allow_html=True)
            with k2: st.markdown(f'<div class="kpi-container"><div class="kpi-info"><div class="kpi-value">{filtered["points"].sum()}</div><div class="kpi-label">النقاط</div></div><div class="kpi-icon">⭐</div></div>', unsafe_allow_html=True)
            with k1: 
                yr = filtered['year'].mode()[0] if not filtered.empty else "-"
                st.markdown(f'<div class="kpi-container"><div class="kpi-info"><div class="kpi-value">{yr}</div><div class="kpi-label">السنة النشطة</div></div><div class="kpi-icon">📅</div></div>', unsafe_allow_html=True)

            # --- القسم الجديد: مؤشرات الأداء والتميز ---
            st.markdown("---")
            st.markdown("### 🏆 مؤشرات الأداء والتميز")
            
            c1, c2 = st.columns(2)
            with c1:
                st.markdown('<div class="chart-container">', unsafe_allow_html=True)
                # Leaderboard
                top_res = filtered.groupby('researcher')['points'].sum().reset_index().sort_values('points', ascending=False).head(5)
                fig_lead = px.bar(top_res, x='points', y='researcher', orientation='h', title="🥇 أكثر الباحثين تميزاً (حسب النقاط)", text_auto=True, color_discrete_sequence=['#fbbf24'])
                st.plotly_chart(fig_lead, use_container_width=True)
                st.markdown('</div>', unsafe_allow_html=True)
            
            with c2:
                st.markdown('<div class="chart-container">', unsafe_allow_html=True)
                # Sunburst
                if not filtered.empty and 'department' in filtered.columns and 'team' in filtered.columns:
                    fig_sun = px.sunburst(filtered, path=['department', 'team'], values='points', title="🧬 مساهمة الهياكل في الحصيلة العلمية", color_discrete_sequence=px.colors.qualitative.Pastel)
                    st.plotly_chart(fig_sun, use_container_width=True)
                st.markdown('</div>', unsafe_allow_html=True)
            # -------------------------------------------

            c1, c2 = st.columns(2)
            with c1:
                st.markdown('<div class="chart-container">', unsafe_allow_html=True)
                st.markdown("##### 📊 توزيع الأنشطة")
                if not filtered.empty:
                    fig = px.pie(filtered, names='activity_type', hole=0.5, color_discrete_sequence=px.colors.sequential.Blues_r)
                    st.plotly_chart(fig, use_container_width=True)
                st.markdown('</div>', unsafe_allow_html=True)
            with c2:
                st.markdown('<div class="chart-container">', unsafe_allow_html=True)
                st.markdown("##### 📈 التطور السنوي")
                if not filtered.empty:
                    daily = filtered.groupby('year').size().reset_index(name='count')
                    fig2 = px.bar(daily, x='year', y='count', text_auto=True, color_discrete_sequence=['#2563eb'])
                    st.plotly_chart(fig2, use_container_width=True)
                st.markdown('</div>', unsafe_allow_html=True)
        else: st.info("لا توجد بيانات متاحة لعرضها.")

    # --- 2. الهيكل التنظيمي ---
    elif selection == "الهيكل التنظيمي":
        st.title("🏢 الهيكل التنظيمي (التفصيلي)")
        session = SessionLocal()
        
        def show_team_details(t):
            st.markdown(f"""
            <div class="team-header" style="background:#e0f2fe; border-right:5px solid #0284c7; text-align: right; direction: rtl;">
                🧬 <b>{t.name}</b>
            </div>
            """, unsafe_allow_html=True)
            
            tab_info, tab_prog, tab_members = st.tabs(["📋 بطاقة الفرقة", "🔬 البرنامج العلمي", "👥 القوائم الاسمية"])
            
            with tab_info:
                c_a, c_b = st.columns(2)
                
                def field(label, value):
                    return f'<div style="text-align: right; direction: rtl; margin-bottom: 5px;"><b>{label}:</b> {value}</div>'

                with c_a:
                    st.markdown(field("رقم الفرقة", t.id), unsafe_allow_html=True)
                    st.markdown(field("الاسم بالعربية", t.name), unsafe_allow_html=True)
                    st.markdown(field("الاسم بالإنجليزية", t.name_en or '-'), unsafe_allow_html=True)
                    st.markdown(field("المختصر", t.short_name or '-'), unsafe_allow_html=True)
                
                with c_b:
                    st.markdown(field("رئيس الفرقة", t.head_name or '-'), unsafe_allow_html=True)
                    st.markdown(field("التصنيف", t.classification or '-'), unsafe_allow_html=True)
                    st.markdown(field("الميادين", t.domains or '-'), unsafe_allow_html=True)
                    st.markdown(field("الكلمات المفتاحية", t.keywords or '-'), unsafe_allow_html=True)
                
                st.markdown("---")
                st.markdown(f'<div style="text-align: justify; text-align-last: right; direction: rtl;"><b>التعريف بالفرقة:</b><br>{t.description or "لا يوجد وصف"}</div>', unsafe_allow_html=True)

            with tab_prog:
                st.markdown(f'<div style="text-align: justify; direction: rtl; background-color: #e0f7fa; padding: 10px; border-radius: 5px;">{t.program_desc or "لم يتم إدخال وصف البرنامج العلمي بعد."}</div>', unsafe_allow_html=True)

            with tab_members:
                m_perm = [m for m in t.members if m.member_type == 'permanent']
                m_phd = [m for m in t.members if m.member_type == 'phd_student']
                m_aff = [m for m in t.members if m.member_type == 'affiliate']
                m_assoc = [m for m in t.members if m.member_type == 'associate']
                
                def get_rank(member):
                    name = member.full_name.strip() if member.full_name else ""
                    if name.startswith("أ.د"): return 1
                    if name.startswith("د."): return 2
                    if name.startswith("ط"): return 3
                    return 4

                m_perm.sort(key=lambda x: (get_rank(x), x.full_name))
                m_phd.sort(key=lambda x: (get_rank(x), x.full_name))
                m_aff.sort(key=lambda x: (get_rank(x), x.full_name))
                m_assoc.sort(key=lambda x: (get_rank(x), x.full_name))

                c1, c2, c3, c4 = st.columns(4)
                
                def list_members(title, members, icon):
                    html = f'<div style="text-align: right; direction: rtl;"><h6 style="color:#1e3a8a;">{icon} {title}</h6>'
                    if members:
                        for m in members:
                            html += f'<div style="margin-right: 10px;">- {m.full_name}</div>'
                    else:
                        html += '<div style="color: gray; margin-right: 10px;">فارغ</div>'
                    html += '</div>'
                    st.markdown(html, unsafe_allow_html=True)

                with c1: list_members("الدائمون", m_perm, "🏛️")
                with c2: list_members("طلبة الدكتوراه", m_phd, "🎓")
                with c3: list_members("ملحق بحث", m_aff, "🤝")
                with c4: list_members("عضو مشارك", m_assoc, "🌍")

        def show_dept_details(d):
            st.markdown(f"""
            <div class="dept-card" style="text-align: right; direction: rtl;">
                <div class="dept-title">📂 {d.name_ar}</div>
                <div class="dept-info"><b>اللاتينية:</b> {d.name_la or '-'} | <b>المختصر:</b> {d.short_name or '-'} | <b>الرقم:</b> {d.id}</div>
                <div class="dept-info" style="color:#b91c1c;"><b>رئيس القسم:</b> {d.head_name or '-'}</div>
            </div>
            """, unsafe_allow_html=True)

        if user.role == 'admin':
            depts = session.query(Department).options(joinedload(Department.teams).joinedload(Team.members)).order_by(Department.id).all()
            for d in depts:
                with st.expander(f"{d.name_ar}", expanded=False):
                    show_dept_details(d)
                    st.markdown('<h5 style="text-align: right; direction: rtl; margin-top: 10px;">🔽 الفرق التابعة:</h5>', unsafe_allow_html=True)
                    for t in d.teams:
                        with st.expander(f"الفرقة: {t.name}"):
                            show_team_details(t)

        elif user.role == 'dept_head':
            if user.department_id:
                d = session.query(Department).options(joinedload(Department.teams).joinedload(Team.members)).filter(Department.id == user.department_id).first()
                if d:
                    show_dept_details(d)
                    st.markdown("#### 🔽 الفرق التابعة لقسمك:")
                    for t in d.teams:
                        with st.expander(f"الفرقة: {t.name}"):
                            show_team_details(t)
            else: st.warning("غير مرتبط بقسم")

        elif user.role in ['leader', 'researcher']:
            if user.team_id:
                t = session.query(Team).options(joinedload(Team.members), joinedload(Team.department)).filter(Team.id == user.team_id).first()
                if t:
                    st.success(f"أنت عضو في قسم: {t.department.name_ar}")
                    show_team_details(t)
            else: st.warning("غير مرتبط بفرقة")
            
        session.close()

    # --- 3. تسجيل نتاج ---
    elif selection == "تسجيل نتاج":
        st.title("📝 تسجيل نتاج علمي جديد")
        st.markdown('<div class="rtl-header">📌 اختر نوع النشاط لتخصيص الحقول:</div>', unsafe_allow_html=True)
        w_type = st.selectbox("", ACTIVITY_TYPES, label_visibility="collapsed")
        st.markdown("---")
        st.markdown(f'<div class="rtl-header">📄 تفاصيل: {w_type}</div>', unsafe_allow_html=True)
        if 'fid' not in st.session_state: st.session_state['fid'] = int(time.time())
        with st.form(key=f"w_form_{st.session_state['fid']}"):
            c1, c2 = st.columns([3, 1])
            title = c1.text_input("العنوان الكامل للعمل *", key=f"t_{w_type}")
            date_pub = c2.date_input("التاريخ *", key=f"d_{w_type}")
            lang = st.selectbox("اللغة", ["العربية", "الإنجليزية", "الفرنسية"], key=f"l_{w_type}")
            details = {"lang": lang}
            pts, cls = 10, "غير مصنف"
            if w_type == "مقال في مجلة علمية":
                c1, c2 = st.columns(2)
                j = c1.text_input("اسم المجلة *")
                issn = c2.text_input("ISSN")
                cls = st.selectbox("التصنيف", ["A", "B", "C", "Q1", "Q2", "Q3", "Q4"])
                idx = st.multiselect("الفهرسة", ["ASJP", "Scopus", "WoS"])
                details.update({"journal": j, "issn": issn, "indexing": idx})
                pts = 100 if cls in ["A", "Q1"] else (75 if cls in ["B", "Q2"] else 50)
            elif w_type == "مداخلة في مؤتمر":
                c1, c2 = st.columns(2)
                conf = c1.text_input("اسم الملتقى *")
                org = c2.text_input("الجهة المنظمة")
                scope = st.selectbox("النطاق", ["وطني", "دولي"])
                details.update({"conf": conf, "organizer": org, "scope": scope})
                pts = 50 if scope == "دولي" else 25
            elif w_type in ["تأليف كتاب", "فصل في كتاب"]:
                c1, c2 = st.columns(2)
                pub = c1.text_input("دار النشر *")
                isbn = c2.text_input("ISBN")
                details.update({"publisher": pub, "isbn": isbn})
                pts = 80 if w_type == "تأليف كتاب" else 40
            elif w_type == "تأطير مذكرة":
                c1, c2 = st.columns(2)
                stud = c1.text_input("اسم الطالب")
                lvl = c2.selectbox("المستوى", ["ماستر", "دكتوراه"])
                details.update({"student": stud, "level": lvl})
                pts = 20
            elif w_type == "مشروع بحث":
                c1, c2 = st.columns(2)
                code = c1.text_input("رمز المشروع")
                role = c2.selectbox("الصفة", ["رئيس", "عضو"])
                details.update({"code": code, "role": role})
                pts = 60
            elif w_type == "براءة اختراع":
                c1, c2 = st.columns(2)
                num = c1.text_input("رقم البراءة")
                body = c2.text_input("الهيئة المانحة")
                details.update({"number": num, "body": body})
                pts = 150
            if st.form_submit_button("💾 حفظ البيانات", type="primary", use_container_width=True):
                if title:
                    add_work_service(user.id, title, json.dumps(details), w_type, cls, date_pub, pts)
                    st.toast("✅ تم الحفظ بنجاح!", icon="🎉"); time.sleep(1); st.session_state['fid'] = int(time.time()); st.rerun()
                else: st.warning("يرجى إدخال عنوان العمل")

    # --- 4. إدارة الأنشطة ---
    elif selection == "إدارة الأنشطة":
        st.title("🗂️ إدارة الأنشطة البحثية")
        search = st.text_input("🔎 بحث سريع (العنوان، الباحث)...")
        df = get_smart_data(user)
        if not df.empty:
            if search:
                df = df[df['title'].str.contains(search, na=False) | df['researcher'].str.contains(search, na=False)]
            st.info(f"عدد السجلات: {len(df)}")
            for i, row in df.iterrows():
                with st.expander(f"{row['activity_type']} | {row['title']} (👤 {row['researcher']})"):
                    c1, c2 = st.columns([3, 1])
                    nt = c1.text_input("تعديل العنوان", row['title'], key=f"edt_{row['id']}")
                    nd = c2.date_input("تعديل التاريخ", pd.to_datetime(row['publication_date']).date(), key=f"edd_{row['id']}")
                    b1, b2 = st.columns(2)
                    if b1.button("حفظ التعديلات", key=f"sv_{row['id']}"):
                        update_work_service(row['id'], nt, nd); st.toast("تم التعديل"); time.sleep(1); st.rerun()
                    if b2.button("حذف نهائي", key=f"dl_{row['id']}"):
                        delete_work_service(row['id']); st.toast("تم الحذف"); time.sleep(1); st.rerun()
        else: st.info("لا توجد بيانات.")

    # --- 5. إدارة المستخدمين ---
    elif selection == "إدارة المستخدمين":
        st.title("👥 إدارة المستخدمين (إضافة يدوية)")
        c1, c2 = st.columns(2)
        name = c1.text_input("الاسم الكامل")
        uname = c2.text_input("اسم الدخول")
        c3, c4 = st.columns(2)
        pas = c3.text_input("كلمة المرور", type="password")
        role = c4.selectbox("الصفة", ["رئيس قسم", "رئيس فرقة", "باحث"])
        
        m_type = "permanent"
        if role in ["رئيس فرقة", "باحث"]:
            m_type = st.selectbox("نوع العضوية", list(MEMBER_TYPES.keys()), format_func=lambda x: MEMBER_TYPES[x])

        session = SessionLocal()
        depts = session.query(Department).all()
        d_map = {d.name_ar: d.id for d in depts}
        sel_d_id = None
        sel_t_id = None
        if role != "رئيس قسم":
            d_name = st.selectbox("القسم", list(d_map.keys()))
            sel_d_id = d_map[d_name]
            if role in ["رئيس فرقة", "باحث"]:
                teams = session.query(Team).filter_by(department_id=sel_d_id).all()
                if teams:
                    t_map = {t.name: t.id for t in teams}
                    t_name = st.selectbox("الفرقة", list(t_map.keys()))
                    sel_t_id = t_map[t_name]
                else: st.warning("⚠️ هذا القسم فارغ من الفرق")
        session.close()
        if st.button("إضافة المستخدم", type="primary", use_container_width=True):
            r_code = "dept_head" if role == "رئيس قسم" else ("leader" if role == "رئيس فرقة" else "researcher")
            if add_user_manual(uname, name, pas, r_code, sel_t_id, sel_d_id, m_type):
                st.success("تمت الإضافة بنجاح")
            else: st.error("خطأ: اسم المستخدم موجود مسبقاً")

    # --- صفحات العرض ---
    elif selection == "أعمالي":
        st.title("📂 سجل أعمالي")
        df = get_smart_data(user)
        if not df.empty:
            display_cols = ['title', 'activity_type', 'publication_date', 'points']
            if user.role != 'researcher':
                display_cols.insert(0, 'researcher')
            final_cols = [c for c in display_cols if c in df.columns]
            st.dataframe(df[final_cols], use_container_width=True)
        else:
            st.info("لا توجد أعمال مسجلة لك.")

    elif selection == "الإعدادات":
        st.title("⚙️ الإعدادات")
        with st.form("pwd"):
            st.subheader("تغيير كلمة المرور")
            p1 = st.text_input("كلمة المرور الجديدة", type="password")
            p2 = st.text_input("تأكيد كلمة المرور", type="password")
            if st.form_submit_button("تغيير كلمة المرور"):
                if p1 == p2 and len(p1) > 0:
                    change_password(user.id, p1); st.success("تم التغيير بنجاح")
                else: st.warning("كلمات المرور غير متطابقة")

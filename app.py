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

# --- ثوابت النظام (أكواد التفعيل) ---
ACTIVATION_CODES = {
    "admin": "ADMIN2025",      # كود المدير
    "dept_head": "HEAD2025",   # كود رئيس القسم
    "leader": "LEAD2025",      # كود رئيس الفرقة
    "researcher": "RES2025"    # كود الباحث/الطالب
}

ACTIVITY_TYPES = [
    "مقال في مجلة علمية", "مداخلة في مؤتمر", "تأليف كتاب", 
    "فصل في كتاب", "براءة اختراع", "تأطير مذكرة", "مشروع بحث"
]

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
    teams = relationship("Team", back_populates="department")
    users = relationship("User", back_populates="department")

class Team(Base):
    __tablename__ = "teams"
    id = Column(Integer, primary_key=True)
    name = Column(String)
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
# 3. الخدمات والدوال
# ==========================================
def auto_init_system():
    try:
        inspector = inspect(engine)
        if not inspector.has_table("users"):
            Base.metadata.create_all(bind=engine)
        session = SessionLocal()
        if not session.query(User).filter_by(username="admin").first():
            # إنشاء الهيكل
            depts_data = ["الدراسات السوسيولوجية", "علم النفس", "علوم التربية", "الأرطوفونيا", "الفلسفة", "التاريخ"]
            for name in depts_data:
                if not session.query(Department).filter_by(name_ar=name).first():
                    d = Department(name_ar=name)
                    session.add(d)
                    session.flush()
                    session.add(Team(name=f"فرقة بحث {name}", department_id=d.id))
            
            pw = bcrypt.hashpw("12345".encode(), bcrypt.gensalt()).decode()
            session.add(User(username="admin", full_name="المدير العام", password_hash=pw, role="admin", member_type="admin"))
            session.commit()
        session.close()
    except Exception: pass

auto_init_system()

def auth_user(u, p):
    s = SessionLocal()
    try:
        user = s.query(User).options(joinedload(User.team), joinedload(User.department)).filter(User.username == u).first()
        if user and bcrypt.checkpw(p.encode(), user.password_hash.encode()): return user
    except: pass
    finally: s.close()
    return None

def register_user_secure(u, f, p, role, code, t_id, d_id):
    # التحقق من كود التفعيل
    if code != ACTIVATION_CODES.get(role):
        return False, "⛔ كود التفعيل غير صحيح لهذه الصلاحية!"
    
    s = SessionLocal()
    try:
        if s.query(User).filter(User.username == u).first():
            return False, "⚠️ اسم المستخدم موجود مسبقاً"
        
        h = bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()
        s.add(User(username=u, full_name=f, password_hash=h, role=role, team_id=t_id, department_id=d_id, member_type="permanent"))
        s.commit()
        return True, "✅ تم إنشاء الحساب بنجاح"
    except Exception as e:
        s.rollback()
        return False, f"خطأ: {str(e)}"
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
        if w:
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

# دالة جلب البيانات الذكية (المصححة للرسوم البيانية)
def get_smart_data(user):
    base_q = """
    SELECT 
        w.id, w.title, w.activity_type, w.publication_date, w.year, w.points, w.classification, w.details,
        u.full_name as researcher, 
        t.name as team, 
        d.name_ar as department
    FROM works w
    JOIN users u ON w.user_id = u.id
    LEFT JOIN teams t ON u.team_id = t.id
    LEFT JOIN departments d ON t.department_id = d.id
    """
    try:
        df = pd.read_sql(base_q, engine)
        
        # ✅ تنظيف البيانات (السر في منع الخطأ)
        df['department'] = df['department'].fillna('غير محدد')
        df['team'] = df['team'].fillna('غير محدد')
        df['activity_type'] = df['activity_type'].fillna('غير محدد')
        
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
    .stTextInput input, .stSelectbox div, .stTextArea textarea, .stDateInput input { 
        text-align: right; direction: rtl; border-radius: 8px; font-family: 'Tajawal';
    }
    
    .kpi-container {
        background-color: white; padding: 20px; border-radius: 12px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.04); border: 1px solid #f1f5f9;
        border-right: 4px solid #3b82f6;
        display: flex; justify-content: space-between; align-items: center;
        margin-bottom: 10px; transition: transform 0.2s;
    }
    .kpi-container:hover { transform: translateY(-3px); }
    .kpi-value { font-family: 'Cairo'; font-size: 28px; font-weight: 800; color: #0f172a; line-height: 1.2; }
    .kpi-label { font-size: 13px; color: #64748b; font-weight: 600; }
    .kpi-icon { width: 45px; height: 45px; background-color: #eff6ff; border-radius: 10px; display: flex; align-items: center; justify-content: center; font-size: 22px; color: #3b82f6; }
    
    .chart-container { background-color: white; padding: 20px; border-radius: 15px; border: 1px solid #e2e8f0; box-shadow: 0 2px 4px rgba(0,0,0,0.02); margin-bottom: 20px; }
    .stButton>button { width: 100%; border-radius: 8px; font-family: 'Cairo'; font-weight: bold; }
    [data-testid="stForm"] { background: white; padding: 25px; border-radius: 12px; border: 1px solid #e5e7eb; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05); }
    
    /* محاذاة العناوين يمين */
    .rtl-header { text-align: right; direction: rtl; width: 100%; display: block; font-family: 'Cairo'; font-weight: 700; color: #1f2937; margin-bottom: 10px; font-size: 18px; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 5. التطبيق
# ==========================================

if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False

# --- شاشة الدخول والتسجيل ---
if not st.session_state['logged_in']:
    c1, c2, c3 = st.columns([1, 1.5, 1])
    with c2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        logo_path = "logo.png"
        logo_html = '<div style="font-size: 60px; margin-bottom: 10px; text-align:center;">🏛️</div>'
        if os.path.exists(logo_path):
            img = get_img_as_base64(logo_path)
            if img: logo_html = f'<div style="text-align:center;"><img src="data:image/png;base64,{img}" style="width: 150px; margin-bottom: 20px;"></div>'

        st.markdown(logo_html, unsafe_allow_html=True)
        st.markdown("""<div style="text-align: center; margin-bottom: 30px;"><h1 style="color:#1e40af; font-family:'Cairo'; margin: 0;">بوابة البحث العلمي</h1><p style="color:#64748b;">نظام إدارة المخابر الجامعية الموحد</p></div>""", unsafe_allow_html=True)
        
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
            with st.form("signup"):
                st.markdown("##### 🆕 إنشاء حساب باستخدام كود التفعيل")
                c_a, c_b = st.columns(2)
                new_name = c_a.text_input("الاسم الكامل")
                new_user = c_b.text_input("اسم المستخدم (للدخول)")
                new_pass = st.text_input("كلمة المرور", type="password")
                
                role_labels = {"admin": "مدير المخبر", "dept_head": "رئيس قسم", "leader": "رئيس فرقة", "researcher": "باحث/طالب"}
                role_key = st.selectbox("الصفة", list(role_labels.keys()), format_func=lambda x: role_labels[x])
                
                # جلب الأقسام والفرق
                session = SessionLocal()
                depts = session.query(Department).all()
                d_map = {d.name_ar: d.id for d in depts}
                
                sel_dept_id = None
                sel_team_id = None
                
                # إخفاء خيارات القسم والفرقة للمدير
                if role_key != 'admin':
                    d_name = st.selectbox("القسم", list(d_map.keys()))
                    sel_dept_id = d_map[d_name]
                    
                    if role_key in ['leader', 'researcher']:
                        teams = session.query(Team).filter_by(department_id=sel_dept_id).all()
                        t_map = {t.name: t.id for t in teams}
                        if t_map:
                            t_name = st.selectbox("الفرقة", list(t_map.keys()))
                            sel_team_id = t_map[t_name]
                        else: st.warning("لا توجد فرق في هذا القسم")
                session.close()

                act_code = st.text_input("🔑 كود التفعيل (Activation Code)", type="password", help="اطلب الكود من الإدارة")
                
                if st.form_submit_button("إنشاء الحساب", use_container_width=True):
                    if new_user and new_pass and act_code:
                        success, msg = register_user_secure(new_user, new_name, new_pass, role_key, act_code, sel_team_id, sel_dept_id, "permanent")
                        if success: st.success(msg)
                        else: st.error(msg)
                    else: st.warning("يرجى ملء جميع الحقول")

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
        st.markdown(f"""<div style="text-align: center; margin-bottom: 20px;"><h3 style="color:#1e3a8a; font-family:'Cairo'; margin:0;">المركز البحثي أدرار</h3></div>""", unsafe_allow_html=True)
        
        role_map_display = {"admin": "المدير العام", "dept_head": "رئيس قسم", "leader": "رئيس فرقة", "researcher": "باحث"}
        st.info(f"👤 مرحباً: {user.full_name}\n\n🏷️ الصلاحية: {role_map_display.get(user.role, user.role)}")
        
        menu = {
            "لوحة القيادة": "📊 لوحة القيادة",
            "تسجيل نتاج": "📝 تسجيل نتاج جديد",
            "إدارة الأنشطة": "🗂️ إدارة الأنشطة (تعديل/حذف)",
            "أعمالي": "📂 سجل أعمالي",
            "الإعدادات": "⚙️ الإعدادات"
        }
        if user.role == 'admin': menu["إدارة المستخدمين"] = "👥 إدارة المستخدمين (إضافة يدوية)"
            
        sel = st.sidebar.radio("القائمة", list(menu.values()), label_visibility="collapsed")
        selection = [k for k, v in menu.items() if v == sel][0]
        
        st.markdown("---")
        if st.button("تسجيل الخروج"):
            st.session_state['logged_in'] = False
            st.rerun()

    # --- 1. لوحة القيادة (المحسنة مع فلاتر مترابطة) ---
    if selection == "لوحة القيادة":
        st.markdown(f"## 📊 لوحة القيادة العامة")
        
        df = get_smart_data(user)
        
        if not df.empty:
            # 💡 الفلاتر المترابطة (Cascading Filters)
            with st.expander("🔍 تصفية البيانات (Advanced Filters)", expanded=True):
                c1, c2, c3, c4 = st.columns(4)
                
                # 1. السنة
                years = sorted(df['year'].unique().tolist(), reverse=True)
                sel_year = c1.selectbox("السنة", ["الكل"] + years)
                
                # 2. القسم
                depts = sorted(df['department'].unique().tolist())
                sel_dept = c2.selectbox("القسم", ["الكل"] + depts)
                
                # 3. الفرقة (تعتمد على القسم)
                if sel_dept != "الكل":
                    teams_list = sorted(df[df['department'] == sel_dept]['team'].unique().tolist())
                else:
                    teams_list = sorted(df['team'].unique().tolist())
                sel_team = c3.selectbox("الفرقة", ["الكل"] + teams_list)
                
                # 4. النوع
                types = sorted(df['activity_type'].unique().tolist())
                sel_type = c4.selectbox("نوع النشاط", ["الكل"] + types)

            # تطبيق الفلاتر
            filtered = df.copy()
            if sel_year != "الكل": filtered = filtered[filtered['year'] == sel_year]
            if sel_dept != "الكل": filtered = filtered[filtered['department'] == sel_dept]
            if sel_team != "الكل": filtered = filtered[filtered['team'] == sel_team]
            if sel_type != "الكل": filtered = filtered[filtered['activity_type'] == sel_type]

            # زر التصدير
            excel_file = to_excel(filtered)
            st.download_button("📥 تحميل التقرير (Excel)", excel_file, f"report_{date.today()}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            
            st.markdown("<br>", unsafe_allow_html=True)
            k1, k2, k3, k4 = st.columns(4)
            with k4: st.markdown(f'<div class="kpi-container"><div class="kpi-info"><div class="kpi-value">{len(filtered)}</div><div class="kpi-label">إجمالي النتاج</div></div><div class="kpi-icon">📚</div></div>', unsafe_allow_html=True)
            with k3: st.markdown(f'<div class="kpi-container"><div class="kpi-info"><div class="kpi-value">{filtered["researcher"].nunique()}</div><div class="kpi-label">الباحثون</div></div><div class="kpi-icon">👥</div></div>', unsafe_allow_html=True)
            with k2: st.markdown(f'<div class="kpi-container"><div class="kpi-info"><div class="kpi-value">{filtered["points"].sum()}</div><div class="kpi-label">النقاط</div></div><div class="kpi-icon">⭐</div></div>', unsafe_allow_html=True)
            with k1: 
                yr = filtered['year'].mode()[0] if not filtered.empty else "-"
                st.markdown(f'<div class="kpi-container"><div class="kpi-info"><div class="kpi-value">{yr}</div><div class="kpi-label">السنة النشطة</div></div><div class="kpi-icon">📅</div></div>', unsafe_allow_html=True)

            c1, c2 = st.columns(2)
            with c1:
                st.markdown('<div class="chart-container">', unsafe_allow_html=True)
                st.markdown("##### 📊 توزيع الأنشطة")
                if not filtered.empty:
                    fig = px.pie(filtered, names='activity_type', hole=0.5, color_discrete_sequence=px.colors.sequential.Blues_r)
                    st.plotly_chart(fig, use_container_width=True)
                else: st.caption("لا توجد بيانات للرسم")
                st.markdown('</div>', unsafe_allow_html=True)
                
            with c2:
                st.markdown('<div class="chart-container">', unsafe_allow_html=True)
                st.markdown("##### 📈 التطور السنوي")
                if not filtered.empty:
                    daily = filtered.groupby('year').size().reset_index(name='count')
                    fig2 = px.bar(daily, x='year', y='count', text_auto=True, color_discrete_sequence=['#2563eb'])
                    st.plotly_chart(fig2, use_container_width=True)
                else: st.caption("لا توجد بيانات للرسم")
                st.markdown('</div>', unsafe_allow_html=True)
        else: st.info("لا توجد بيانات متاحة لعرضها.")

    # --- 2. تسجيل نتاج ---
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

            # --- الحقول الديناميكية (لكل الأنواع) ---
            if w_type == "مقال في مجلة علمية":
                c1, c2 = st.columns(2)
                j = c1.text_input("اسم المجلة *", key=f"jn_{w_type}")
                issn = c2.text_input("ISSN", key=f"is_{w_type}")
                cls = st.selectbox("التصنيف", ["A", "B", "C", "Q1", "Q2", "Q3", "Q4"], key=f"cl_{w_type}")
                idx = st.multiselect("الفهرسة", ["ASJP", "Scopus", "WoS"], key=f"ix_{w_type}")
                details.update({"journal": j, "issn": issn, "indexing": idx})
                pts = 100 if cls in ["A", "Q1"] else (75 if cls in ["B", "Q2"] else 50)

            elif w_type == "مداخلة في مؤتمر":
                c1, c2 = st.columns(2)
                conf = c1.text_input("اسم الملتقى *", key=f"cn_{w_type}")
                org = c2.text_input("الجهة المنظمة", key=f"og_{w_type}")
                scope = st.selectbox("النطاق", ["وطني", "دولي"], key=f"sc_{w_type}")
                loc = st.text_input("المكان", key=f"lc_{w_type}")
                details.update({"conf": conf, "organizer": org, "scope": scope, "location": loc})
                pts = 50 if scope == "دولي" else 25

            elif w_type in ["تأليف كتاب", "فصل في كتاب"]:
                c1, c2 = st.columns(2)
                pub = c1.text_input("دار النشر *", key=f"pb_{w_type}")
                isbn = c2.text_input("ISBN", key=f"sb_{w_type}")
                if w_type == "فصل في كتاب":
                    book_title = st.text_input("عنوان الكتاب", key=f"bk_{w_type}")
                    details.update({"book_title": book_title})
                details.update({"publisher": pub, "isbn": isbn})
                pts = 80 if w_type == "تأليف كتاب" else 40

            elif w_type == "تأطير مذكرة":
                c1, c2 = st.columns(2)
                stud = c1.text_input("اسم الطالب", key=f"st_{w_type}")
                lvl = c2.selectbox("المستوى", ["ماستر", "دكتوراه"], key=f"lv_{w_type}")
                details.update({"student": stud, "level": lvl})
                pts = 20

            elif w_type == "مشروع بحث":
                c1, c2 = st.columns(2)
                code = c1.text_input("رمز المشروع", key=f"cd_{w_type}")
                role = c2.selectbox("الصفة", ["رئيس", "عضو"], key=f"rl_{w_type}")
                details.update({"code": code, "role": role})
                pts = 60
            
            elif w_type == "براءة اختراع":
                c1, c2 = st.columns(2)
                num = c1.text_input("رقم البراءة", key=f"nm_{w_type}")
                body = c2.text_input("الهيئة المانحة", key=f"bd_{w_type}")
                details.update({"number": num, "body": body})
                pts = 150

            if st.form_submit_button("💾 حفظ البيانات", type="primary", use_container_width=True):
                if title:
                    add_work_service(user.id, title, json.dumps(details), w_type, cls, date_pub, pts)
                    st.toast("✅ تم الحفظ بنجاح!", icon="🎉")
                    time.sleep(1)
                    st.session_state['fid'] = int(time.time())
                    st.rerun()
                else: st.warning("يرجى إدخال عنوان العمل")

    # --- 3. إدارة الأنشطة ---
    elif selection == "إدارة الأنشطة":
        st.title("🗂️ إدارة الأنشطة البحثية")
        search = st.text_input("🔎 ابحث عن عمل (العنوان، الباحث)...")
        df = get_smart_data(user)
        
        if not df.empty:
            if search:
                df = df[df['title'].str.contains(search, na=False) | df['researcher'].str.contains(search, na=False)]
            
            st.info(f"النتائج: {len(df)}")
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

    # --- 4. User Management ---
    elif selection == "إدارة المستخدمين":
        st.title("👥 إدارة المستخدمين (إضافة يدوية)")
        with st.form("add_u"):
            st.subheader("إضافة حساب مسؤول / باحث")
            c1, c2 = st.columns(2)
            name = c1.text_input("الاسم الكامل")
            uname = c2.text_input("اسم الدخول (Unique)")
            pas = st.text_input("كلمة المرور", type="password")
            role = st.selectbox("الصفة", ["رئيس قسم", "رئيس فرقة", "باحث"])
            
            depts = session.query(Department).all()
            d_map = {d.name_ar: d.id for d in depts}
            sel_d = st.selectbox("القسم", list(d_map.keys())) if d_map else None
            
            sel_t_id = None
            if role != "رئيس قسم" and sel_d:
                teams = session.query(Team).filter_by(department_id=d_map[sel_d]).all()
                t_map = {t.name: t.id for t in teams}
                if t_map:
                    sel_t = st.selectbox("الفرقة", list(t_map.keys()))
                    sel_t_id = t_map[sel_t]
                else: st.warning("لا توجد فرق في هذا القسم")
            
            if st.form_submit_button("إضافة المستخدم"):
                r_code = "dept_head" if role == "رئيس قسم" else ("leader" if role == "رئيس فرقة" else "researcher")
                if add_user_service(uname, name, pas, r_code, sel_t_id, d_map.get(sel_d)):
                    st.success("تمت الإضافة بنجاح")
                else: st.error("خطأ: اسم المستخدم موجود مسبقاً")

    # --- View Pages ---
    elif selection == "أعمالي":
        st.title("📂 سجل أعمالي")
        df = get_smart_data(user)
        df_my = df[df['user_id'] == user.id]
        if not df_my.empty: st.dataframe(df_my[['title', 'activity_type', 'publication_date', 'points']], use_container_width=True)
        else: st.info("لا توجد أعمال مسجلة لك.")

    elif selection == "الإعدادات":
        st.title("⚙️ الإعدادات")
        with st.form("pwd"):
            st.subheader("تغيير كلمة المرور")
            p1 = st.text_input("كلمة المرور الجديدة", type="password")
            p2 = st.text_input("تأكيد كلمة المرور", type="password")
            if st.form_submit_button("تحديث"):
                if p1 == p2 and len(p1) > 0:
                    change_password(user.id, p1); st.success("تم التغيير بنجاح")
                else: st.warning("كلمات المرور غير متطابقة")

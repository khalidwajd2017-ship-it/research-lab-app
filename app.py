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
import random

# --- 1. إعدادات الصفحة ---
st.set_page_config(
    page_title="المركز البحثي أدرار",
    layout="wide",
    initial_sidebar_state="expanded",
    page_icon="🎓"
)

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
        # إصلاح ترميز كلمة المرور
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
    role = Column(String) # admin, dept_head, leader, researcher
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
# 🚀 3. التهيئة التلقائية (Auto-Fix)
# ==========================================
def auto_init_system():
    """تقوم بإنشاء الجداول والحسابات الأساسية إذا لم تكن موجودة"""
    try:
        inspector = inspect(engine)
        # إذا لم يكن جدول المستخدمين موجوداً، نعيد بناء كل شيء
        if not inspector.has_table("users"):
            Base.metadata.create_all(bind=engine)
            
        session = SessionLocal()
        # التحقق من وجود المدير
        admin = session.query(User).filter_by(username="admin").first()
        if not admin:
            # 1. إنشاء الأقسام
            depts_data = ["الدراسات السوسيولوجية", "علم النفس", "علوم التربية", "الأرطوفونيا", "الفلسفة", "التاريخ"]
            depts = []
            for name in depts_data:
                if not session.query(Department).filter_by(name_ar=name).first():
                    d = Department(name_ar=name)
                    session.add(d)
                    depts.append(d)
            session.commit() # لحفظ الأقسام والحصول على IDs

            # 2. إنشاء فرق افتراضية
            all_depts = session.query(Department).all()
            for d in all_depts:
                t_name = f"فرقة بحث {d.name_ar}"
                if not session.query(Team).filter_by(name=t_name).first():
                    session.add(Team(name=t_name, department_id=d.id))
            session.commit()

            # 3. إنشاء المدير
            pw = bcrypt.hashpw("12345".encode(), bcrypt.gensalt()).decode()
            admin = User(username="admin", full_name="المدير العام", password_hash=pw, role="admin", member_type="admin")
            session.add(admin)
            session.commit()
            print("✅ تم تهيئة النظام وإنشاء المدير.")
            
        session.close()
    except Exception as e:
        print(f"Init Error: {e}")

# استدعاء التهيئة فوراً عند التشغيل
auto_init_system()

# --- الخدمات ---
def auth_user(u, p):
    s = SessionLocal()
    try:
        user = s.query(User).options(joinedload(User.team), joinedload(User.department)).filter(User.username == u).first()
        if user and bcrypt.checkpw(p.encode(), user.password_hash.encode()): return user
    except: pass
    finally: s.close()
    return None

def add_user_service(u, f, p, r, t_id, d_id):
    s = SessionLocal()
    try:
        h = bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()
        s.add(User(username=u, full_name=f, password_hash=h, role=r, team_id=t_id, department_id=d_id, member_type="permanent"))
        s.commit()
        return True
    except: s.rollback(); return False
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

# دالة جلب البيانات الذكية (حسب الصلاحية)
def get_smart_data(user):
    base_q = """
    SELECT w.*, u.full_name, t.name as team_name, d.name_ar as dept_name
    FROM works w
    JOIN users u ON w.user_id = u.id
    LEFT JOIN teams t ON u.team_id = t.id
    LEFT JOIN departments d ON t.department_id = d.id
    """
    df = pd.read_sql(base_q, engine)
    
    if user.role == 'admin': return df
    elif user.role == 'dept_head': return df[df['dept_name'] == user.department.name_ar]
    elif user.role == 'leader': return df[df['team_name'] == user.team.name]
    else: return df[df['user_id'] == user.id]

# ==========================================
# 4. التنسيق (CSS)
# ==========================================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;800&family=Tajawal:wght@400;500;700&display=swap');
    :root { --primary: #2563eb; --bg: #f8fafc; }
    html, body, .stApp { font-family: 'Tajawal', sans-serif; direction: rtl; background-color: #fcfcfc; text-align: right; }
    h1, h2, h3, h4 { font-family: 'Cairo'; font-weight: 800; color: #1e3a8a; text-align: right !important; }
    [data-testid="stSidebar"] { background: #fff; border-left: 1px solid #e2e8f0; }
    .stTextInput input, .stSelectbox div, .stTextArea textarea, .stDateInput input { text-align: right; direction: rtl; border-radius: 8px; }
    .kpi-container { background-color: white; padding: 20px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.04); border: 1px solid #f1f5f9; border-right: 4px solid #3b82f6; display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; transition: transform 0.2s; }
    .kpi-container:hover { transform: translateY(-3px); }
    .kpi-value { font-family: 'Cairo'; font-size: 28px; font-weight: 800; color: #0f172a; line-height: 1.2; }
    .kpi-label { font-family: 'Tajawal'; font-size: 13px; color: #64748b; font-weight: 600; }
    .kpi-icon { width: 45px; height: 45px; background-color: #eff6ff; border-radius: 10px; display: flex; align-items: center; justify-content: center; font-size: 22px; color: #3b82f6; }
    .stButton>button { width: 100%; border-radius: 8px; font-family: 'Cairo'; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 5. التطبيق
# ==========================================

if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False

# --- تسجيل الدخول ---
if not st.session_state['logged_in']:
    c1, c2, c3 = st.columns([1, 1.5, 1])
    with c2:
        st.markdown("<br>", unsafe_allow_html=True)
        # الشعار
        logo_path = "logo.png"
        logo_html = '<div style="font-size: 60px; margin-bottom: 10px;">🏛️</div>'
        if os.path.exists(logo_path):
            img = get_img_as_base64(logo_path)
            if img: logo_html = f'<img src="data:image/png;base64,{img}" style="width: 180px; margin-bottom: 20px;">'

        st.markdown(f"""
        <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center !important; margin-bottom: 30px;">
            {logo_html}
            <h1 style="color:#1e40af; font-family:'Cairo'; margin: 0; text-align: center !important;">بوابة البحث العلمي</h1>
            <p style="color:#64748b; text-align: center !important;">نظام إدارة المخابر الجامعية الموحد</p>
        </div>
        """, unsafe_allow_html=True)
        
        with st.form("login"):
            u = st.text_input("اسم المستخدم")
            p = st.text_input("كلمة المرور", type="password")
            if st.form_submit_button("دخول", type="primary"):
                user = auth_user(u, p)
                if user:
                    st.session_state['logged_in'] = True
                    st.session_state['user'] = user # تخزين الكائن كاملاً (مؤقتاً للوصول للسمات)
                    st.rerun()
                else: st.toast("خطأ في البيانات", icon="❌")

# --- النظام الداخلي ---
else:
    # إعادة تحميل المستخدم من الجلسة لضمان استمرار الاتصال
    user_id = st.session_state['user'].id
    session = SessionLocal()
    user = session.query(User).options(joinedload(User.team), joinedload(User.department)).filter(User.id == user_id).first()
    
    with st.sidebar:
        logo_path = "logo.png"
        sb_logo = ""
        if os.path.exists(logo_path):
            img = get_img_as_base64(logo_path)
            if img: sb_logo = f'<img src="data:image/png;base64,{img}" style="width: 140px; margin-bottom: 15px;">'
        
        st.markdown(f"""<div style="text-align: center;">{sb_logo}<h3 style="color:#1e3a8a; font-family:'Cairo';">المركز البحثي أدرار</h3></div>""", unsafe_allow_html=True)
        
        role_map = {"admin": "المدير العام", "dept_head": "رئيس قسم", "leader": "رئيس فرقة", "researcher": "باحث"}
        st.info(f"👤 {user.full_name}\n\n🏷️ {role_map.get(user.role, user.role)}")
        
        menu = {
            "لوحة القيادة": "📊 لوحة القيادة",
            "إدارة الأنشطة": "🗂️ إدارة الأنشطة (تعديل/حذف)",
            "تسجيل نتاج": "📝 تسجيل نتاج جديد",
            "أعمالي": "📂 سجل أعمالي",
            "الإعدادات": "⚙️ الإعدادات"
        }
        # إضافة خيار "إدارة المستخدمين" للمدير فقط
        if user.role == 'admin':
            menu["إدارة المستخدمين"] = "👥 إدارة المستخدمين (إضافة حسابات)"
            
        sel = st.sidebar.radio("القائمة", list(menu.values()), label_visibility="collapsed")
        selection = [k for k, v in menu.items() if v == sel][0]
        
        if st.button("خروج"):
            st.session_state['logged_in'] = False
            st.rerun()

    # ============================================
    #  1. لوحة القيادة الذكية (حسب الصلاحية)
    # ============================================
    if selection == "لوحة القيادة":
        role_title = role_map.get(user.role, "")
        target_name = ""
        if user.role == "dept_head" and user.department: target_name = f": {user.department.name_ar}"
        elif user.role == "leader" and user.team: target_name = f": {user.team.name}"
        
        st.markdown(f"## 📊 لوحة القيادة {role_title}{target_name}")
        
        df = get_smart_data(user)
        
        if not df.empty:
            k1, k2, k3, k4 = st.columns(4)
            with k4: st.markdown(f'<div class="kpi-container"><div class="kpi-info"><div class="kpi-value">{len(df)}</div><div class="kpi-label">الأعمال</div></div><div class="kpi-icon">📚</div></div>', unsafe_allow_html=True)
            with k3: st.markdown(f'<div class="kpi-container"><div class="kpi-info"><div class="kpi-value">{df["user_id"].nunique()}</div><div class="kpi-label">الباحثون</div></div><div class="kpi-icon">👥</div></div>', unsafe_allow_html=True)
            with k2: st.markdown(f'<div class="kpi-container"><div class="kpi-info"><div class="kpi-value">{df["points"].sum()}</div><div class="kpi-label">النقاط</div></div><div class="kpi-icon">⭐</div></div>', unsafe_allow_html=True)
            with k1: st.markdown(f'<div class="kpi-container"><div class="kpi-info"><div class="kpi-value">{df["year"].max()}</div><div class="kpi-label">آخر نشاط</div></div><div class="kpi-icon">📅</div></div>', unsafe_allow_html=True)
            
            c1, c2 = st.columns(2)
            with c1:
                fig = px.pie(df, names='activity_type', title="توزيع الأنشطة", hole=0.5)
                st.plotly_chart(fig, use_container_width=True)
            with c2:
                daily = df.groupby('year').size().reset_index(name='count')
                fig2 = px.bar(daily, x='year', y='count', title="التطور السنوي")
                st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("لا توجد بيانات متاحة لعرضها.")

    # ============================================
    #  2. إدارة المستخدمين (للمدير فقط) 🆕
    # ============================================
    elif selection == "إدارة المستخدمين":
        st.title("👥 إدارة المستخدمين والهيكل التنظيمي")
        
        with st.form("add_user"):
            st.subheader("إضافة حساب مسؤول جديد")
            c1, c2 = st.columns(2)
            new_name = c1.text_input("الاسم الكامل")
            new_user = c2.text_input("اسم المستخدم (للدخول)")
            new_pass = st.text_input("كلمة المرور", type="password")
            
            role_type = st.selectbox("الصفة الإدارية", ["رئيس قسم", "رئيس فرقة", "باحث"])
            
            # جلب القوائم
            depts = session.query(Department).all()
            dept_names = {d.name_ar: d.id for d in depts}
            
            selected_dept = st.selectbox("القسم التابع له", list(dept_names.keys()))
            selected_dept_id = dept_names[selected_dept]
            
            selected_team_id = None
            if role_type in ["رئيس فرقة", "باحث"]:
                teams = session.query(Team).filter_by(department_id=selected_dept_id).all()
                team_names = {t.name: t.id for t in teams}
                if teams:
                    t_name = st.selectbox("الفرقة", list(team_names.keys()))
                    selected_team_id = team_names[t_name]
                else:
                    st.warning("لا توجد فرق في هذا القسم")
            
            if st.form_submit_button("إضافة المستخدم"):
                r_code = "dept_head" if role_type == "رئيس قسم" else ("leader" if role_type == "رئيس فرقة" else "researcher")
                if add_user_service(new_user, new_name, new_pass, r_code, selected_team_id, selected_dept_id):
                    st.success(f"تم إضافة {new_name} بنجاح!")
                else:
                    st.error("خطأ: ربما اسم المستخدم مكرر")

    # ============================================
    #  3. إدارة الأنشطة (تعديل/حذف)
    # ============================================
    elif selection == "إدارة الأنشطة":
        st.title("🗂️ إدارة الأنشطة (تعديل وحذف)")
        df = get_smart_data(user)
        
        if not df.empty:
            for i, row in df.iterrows():
                with st.expander(f"{row['title']} | {row['activity_type']}"):
                    c1, c2 = st.columns([3, 1])
                    new_t = c1.text_input("العنوان", row['title'], key=f"t_{row['id']}")
                    new_d = c2.date_input("التاريخ", pd.to_datetime(row['publication_date']).date(), key=f"d_{row['id']}")
                    
                    b1, b2 = st.columns(2)
                    if b1.button("حفظ التعديل", key=f"sav_{row['id']}"):
                        update_work_service(row['id'], new_t, new_d)
                        st.toast("تم التعديل"); time.sleep(1); st.rerun()
                    
                    if b2.button("حذف نهائي", key=f"del_{row['id']}"):
                        delete_work_service(row['id'])
                        st.toast("تم الحذف"); time.sleep(1); st.rerun()
        else: st.info("لا توجد بيانات.")

    # ============================================
    #  4. تسجيل نتاج جديد (النموذج الكامل)
    # ============================================
    elif selection == "تسجيل نتاج":
        st.title("📝 تسجيل نتاج علمي")
        w_type = st.selectbox("نوع النشاط", ["مقال في مجلة علمية", "مداخلة في مؤتمر", "تأليف كتاب", "فصل في كتاب", "مشروع بحث"])
        
        if 'fid' not in st.session_state: st.session_state['fid'] = 0
        with st.form(key=f"f_{st.session_state['fid']}"):
            title = st.text_input("العنوان *")
            date_pub = st.date_input("التاريخ *")
            
            # تفاصيل ديناميكية مختصرة للمثال
            details = {}
            if w_type == "مقال في مجلة علمية":
                details['journal'] = st.text_input("اسم المجلة")
                cls = st.selectbox("التصنيف", ["A", "B", "C"])
                pts = 100 if cls=="A" else 75
            else:
                pts = 50
                cls = "غير مصنف"
            
            if st.form_submit_button("حفظ"):
                if title:
                    add_work_service(user.id, title, json.dumps(details), w_type, cls, date_pub, pts)
                    st.success("تم الحفظ"); st.session_state['fid'] += 1; st.rerun()

    # --- الصفحات الأخرى ---
    elif selection == "أعمالي":
        st.title("📂 أعمالي")
        df = get_smart_data(user)
        df_my = df[df['user_id'] == user.id]
        if not df_my.empty: st.dataframe(df_my[['title', 'activity_type', 'points']])
        else: st.info("فارغ")

    elif selection == "الإعدادات":
        st.title("⚙️ الإعدادات")
        with st.form("pwd"):
            p = st.text_input("كلمة المرور الجديدة", type="password")
            if st.form_submit_button("تغيير"):
                change_password(user.id, p); st.success("تم")

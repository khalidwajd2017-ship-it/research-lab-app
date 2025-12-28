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

# --- قائمة أنواع الأنشطة (للتوحيد) ---
ACTIVITY_TYPES = [
    "مقال في مجلة علمية",
    "مداخلة في مؤتمر",
    "تأليف كتاب",
    "فصل في كتاب",
    "براءة اختراع",
    "تأطير مذكرة",
    "مشروع بحث"
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
    try:
        inspector = inspect(engine)
        if not inspector.has_table("users"):
            Base.metadata.create_all(bind=engine)
            
        session = SessionLocal()
        admin = session.query(User).filter_by(username="admin").first()
        if not admin:
            # 1. الأقسام
            depts_data = ["الدراسات السوسيولوجية", "علم النفس", "علوم التربية", "الأرطوفونيا", "الفلسفة", "التاريخ"]
            depts_objs = []
            for name in depts_data:
                d = session.query(Department).filter_by(name_ar=name).first()
                if not d:
                    d = Department(name_ar=name)
                    session.add(d)
                depts_objs.append(d)
            session.commit()

            # 2. الفرق (فرقة لكل قسم للتجربة)
            for d in depts_objs:
                t_name = f"فرقة بحث {d.name_ar}"
                if not session.query(Team).filter_by(name=t_name).first():
                    session.add(Team(name=t_name, department_id=d.id))
            session.commit()

            # 3. المدير
            pw = bcrypt.hashpw("12345".encode(), bcrypt.gensalt()).decode()
            admin = User(username="admin", full_name="المدير العام", password_hash=pw, role="admin", member_type="admin")
            session.add(admin)
            session.commit()
            
        session.close()
    except Exception as e:
        print(f"Init Error: {e}")

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

def get_smart_data(user):
    base_q = """
    SELECT w.*, u.full_name, t.name as team_name, d.name_ar as dept_name
    FROM works w
    JOIN users u ON w.user_id = u.id
    LEFT JOIN teams t ON u.team_id = t.id
    LEFT JOIN departments d ON t.department_id = d.id
    """
    try:
        df = pd.read_sql(base_q, engine)
        if df.empty: return df
        if user.role == 'admin': return df
        elif user.role == 'dept_head': 
            if user.department: return df[df['dept_name'] == user.department.name_ar]
            return df[df['dept_name'] == 'xxxx'] # Empty
        elif user.role == 'leader': 
            if user.team: return df[df['team_name'] == user.team.name]
            return df[df['team_name'] == 'xxxx']
        else: return df[df['user_id'] == user.id]
    except: return pd.DataFrame()

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
    .chart-container { background-color: white; padding: 20px; border-radius: 15px; border: 1px solid #e2e8f0; box-shadow: 0 2px 4px rgba(0,0,0,0.02); margin-bottom: 20px; }
    .stButton>button { width: 100%; border-radius: 8px; font-family: 'Cairo'; font-weight: bold; }
    
    /* تنسيق خاص للنموذج الديناميكي */
    [data-testid="stForm"] { background: white; padding: 25px; border-radius: 12px; border: 1px solid #e5e7eb; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05); }
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
                    st.session_state['user_id'] = user.id # نخزن الـ ID فقط ونستدعيه لاحقاً
                    st.rerun()
                else: st.toast("بيانات خاطئة", icon="❌")

# --- النظام الداخلي ---
else:
    # تحميل بيانات المستخدم المحدثة
    session = SessionLocal()
    user = session.query(User).options(joinedload(User.team), joinedload(User.department)).filter(User.id == st.session_state['user_id']).first()
    
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
            "تسجيل نتاج": "📝 تسجيل نتاج جديد",
            "إدارة الأنشطة": "🗂️ إدارة الأنشطة (تعديل/حذف)",
            "أعمالي": "📂 سجل أعمالي",
            "الإعدادات": "⚙️ الإعدادات"
        }
        if user.role == 'admin':
            menu["إدارة المستخدمين"] = "👥 إدارة المستخدمين"
            
        sel = st.sidebar.radio("القائمة", list(menu.values()), label_visibility="collapsed")
        selection = [k for k, v in menu.items() if v == sel][0]
        
        if st.button("خروج"):
            st.session_state['logged_in'] = False
            st.rerun()

    # ============================================
    #  1. لوحة القيادة
    # ============================================
    if selection == "لوحة القيادة":
        target_name = ""
        if user.role == "dept_head" and user.department: target_name = f": {user.department.name_ar}"
        elif user.role == "leader" and user.team: target_name = f": {user.team.name}"
        
        st.markdown(f"## 📊 لوحة القيادة {target_name}")
        
        df = get_smart_data(user)
        
        if not df.empty:
            k1, k2, k3, k4 = st.columns(4)
            with k4: st.markdown(f'<div class="kpi-container"><div class="kpi-info"><div class="kpi-value">{len(df)}</div><div class="kpi-label">الأعمال</div></div><div class="kpi-icon">📚</div></div>', unsafe_allow_html=True)
            with k3: st.markdown(f'<div class="kpi-container"><div class="kpi-info"><div class="kpi-value">{df["user_id"].nunique()}</div><div class="kpi-label">الباحثون</div></div><div class="kpi-icon">👥</div></div>', unsafe_allow_html=True)
            with k2: st.markdown(f'<div class="kpi-container"><div class="kpi-info"><div class="kpi-value">{df["points"].sum()}</div><div class="kpi-label">النقاط</div></div><div class="kpi-icon">⭐</div></div>', unsafe_allow_html=True)
            with k1: 
                yr = df['year'].mode()[0] if not df.empty else "-"
                st.markdown(f'<div class="kpi-container"><div class="kpi-info"><div class="kpi-value">{yr}</div><div class="kpi-label">الأكثر نشاطاً</div></div><div class="kpi-icon">📅</div></div>', unsafe_allow_html=True)

            c_g1, c_g2 = st.columns([1, 1])
            with c_g2:
                st.markdown('<div class="chart-container">', unsafe_allow_html=True)
                st.markdown("##### 📊 توزيع الأنشطة")
                fig_d = px.pie(df, names='activity_type', hole=0.5, color_discrete_sequence=px.colors.sequential.Blues_r)
                st.plotly_chart(fig_d, use_container_width=True)
                st.markdown('</div>', unsafe_allow_html=True)
            with c_g1:
                st.markdown('<div class="chart-container">', unsafe_allow_html=True)
                st.markdown("##### 📈 التطور السنوي")
                y_df = df.groupby('year').size().reset_index(name='count')
                fig_b = px.bar(y_df, x='year', y='count', text_auto=True, color_discrete_sequence=['#2563eb'])
                st.plotly_chart(fig_b, use_container_width=True)
                st.markdown('</div>', unsafe_allow_html=True)
        else: st.warning("لا توجد بيانات.")

    # ============================================
    #  2. تسجيل نتاج (الديناميكي + الهيكلي)
    # ============================================
    elif selection == "تسجيل نتاج":
        st.title("📝 تسجيل نتاج علمي جديد")
        
        # 1. الاختيار خارج النموذج (للديناميكية)
        st.markdown("##### 📌 اختر نوع النشاط لتخصيص الحقول:")
        w_type = st.selectbox("", ACTIVITY_TYPES, label_visibility="collapsed")
        st.markdown("---")
        
        if 'form_id' not in st.session_state: st.session_state['form_id'] = int(time.time())
        
        with st.form(key=f"w_form_{st.session_state['form_id']}"):
            col_main1, col_main2 = st.columns([3, 1])
            with col_main1: w_title = st.text_input("العنوان الكامل للعمل *", key=f"t_{w_type}")
            with col_main2: w_date = st.date_input("تاريخ النشر *", key=f"d_{w_type}")
            w_lang = st.selectbox("لغة العمل", ["العربية", "الإنجليزية", "الفرنسية"], key=f"l_{w_type}")

            st.markdown(f"**📄 تفاصيل: {w_type}**")
            details_data = {"language": w_lang}
            w_class, w_points = "غير مصنف", 10

            # الحقول الديناميكية
            if w_type == "مقال في مجلة علمية":
                c1, c2 = st.columns(2)
                with c1:
                    journal = st.text_input("اسم المجلة *", key=f"j_{w_type}")
                    issn = st.text_input("الرقم التسلسلي (ISSN)", key=f"i_{w_type}")
                    url_link = st.text_input("رابط المقال", key=f"u_{w_type}")
                with c2:
                    w_class = st.selectbox("تصنيف المجلة", ["A", "B", "C", "Q1", "Q2", "Q3", "Q4"], key=f"c_{w_type}")
                    indexing = st.multiselect("الفهرسة", ["ASJP", "Scopus", "Web of Science"], key=f"x_{w_type}")
                    vol_issue = st.text_input("المجلد (Vol) / العدد (No)", key=f"v_{w_type}")
                
                details_data.update({"journal": journal, "issn": issn, "indexing": indexing, "volume_issue": vol_issue, "url": url_link})
                if w_class in ["A", "Q1"]: w_points = 100
                elif w_class in ["B", "Q2"]: w_points = 75
                elif w_class == "C": w_points = 50
                else: w_points = 25

            elif w_type == "مداخلة في مؤتمر":
                c1, c2 = st.columns(2)
                with c1:
                    conf_name = st.text_input("اسم الملتقى *", key=f"cnf_{w_type}")
                    organizer = st.text_input("الجهة المنظمة", key=f"org_{w_type}")
                with c2:
                    scope = st.selectbox("النطاق", ["وطني", "دولي"], key=f"sc_{w_type}")
                    location = st.text_input("مكان الانعقاد", key=f"loc_{w_type}")
                
                details_data.update({"conference": conf_name, "organizer": organizer, "scope": scope, "location": location})
                w_class = scope
                w_points = 50 if scope == "دولي" else 25

            elif w_type in ["تأليف كتاب", "فصل في كتاب"]:
                c1, c2 = st.columns(2)
                with c1:
                    publisher = st.text_input("دار النشر *", key=f"pub_{w_type}")
                    isbn = st.text_input("ISBN", key=f"isbn_{w_type}")
                with c2:
                    pages = st.text_input("عدد الصفحات", key=f"pg_{w_type}")
                details_data.update({"publisher": publisher, "isbn": isbn, "pages": pages})
                w_points = 80

            elif w_type == "مشروع بحث":
                c1, c2 = st.columns(2)
                with c1:
                    code = st.text_input("رمز المشروع", key=f"cod_{w_type}")
                    role = st.selectbox("الصفة", ["رئيس", "عضو"], key=f"rol_{w_type}")
                with c2:
                    kind = st.selectbox("النوع", ["PRFU", "PNR", "CNEPRU"], key=f"knd_{w_type}")
                details_data.update({"code": code, "role": role, "kind": kind})
                w_points = 60

            st.markdown("---")
            if st.form_submit_button("💾 حفظ البيانات"):
                if w_title:
                    json_details = json.dumps(details_data, ensure_ascii=False)
                    if add_work_service(user.id, w_title, json_details, w_type, w_class, w_date, w_points):
                        st.toast("✅ تم الحفظ بنجاح!", icon="🎉")
                        time.sleep(1)
                        st.session_state['form_id'] = int(time.time())
                        st.rerun()
                    else: st.error("خطأ في الاتصال")
                else: st.warning("العنوان مطلوب")

    # ============================================
    #  3. إدارة المستخدمين (للمدير)
    # ============================================
    elif selection == "إدارة المستخدمين":
        st.title("👥 إدارة المستخدمين")
        with st.form("add_u"):
            c1, c2 = st.columns(2)
            name = c1.text_input("الاسم الكامل")
            uname = c2.text_input("اسم الدخول")
            pas = st.text_input("كلمة المرور", type="password")
            role = st.selectbox("الصفة", ["رئيس قسم", "رئيس فرقة", "باحث"])
            
            depts = session.query(Department).all()
            d_map = {d.name_ar: d.id for d in depts}
            sel_d = st.selectbox("القسم", list(d_map.keys()))
            
            sel_t_id = None
            if role != "رئيس قسم":
                teams = session.query(Team).filter_by(department_id=d_map[sel_d]).all()
                if teams:
                    t_map = {t.name: t.id for t in teams}
                    sel_t = st.selectbox("الفرقة", list(t_map.keys()))
                    sel_t_id = t_map[sel_t]
                else: st.warning("لا توجد فرق في هذا القسم")
            
            if st.form_submit_button("إضافة"):
                r_code = "dept_head" if role == "رئيس قسم" else ("leader" if role == "رئيس فرقة" else "researcher")
                if add_user_service(uname, name, pas, r_code, sel_t_id, d_map[sel_d]):
                    st.success("تمت الإضافة")
                else: st.error("المستخدم موجود")

    # ============================================
    #  4. إدارة الأنشطة (تعديل وحذف)
    # ============================================
    elif selection == "إدارة الأنشطة":
        st.title("🗂️ إدارة الأنشطة")
        df = get_smart_data(user)
        if not df.empty:
            for i, row in df.iterrows():
                with st.expander(f"{row['activity_type']} | {row['title']}"):
                    c1, c2 = st.columns([3, 1])
                    nt = c1.text_input("العنوان", row['title'], key=f"ett_{row['id']}")
                    nd = c2.date_input("التاريخ", pd.to_datetime(row['publication_date']).date(), key=f"etd_{row['id']}")
                    b1, b2 = st.columns(2)
                    if b1.button("حفظ التعديل", key=f"sav_{row['id']}"):
                        update_work_service(row['id'], nt, nd); st.toast("تم"); time.sleep(1); st.rerun()
                    if b2.button("حذف", key=f"del_{row['id']}"):
                        delete_work_service(row['id']); st.toast("حذف"); time.sleep(1); st.rerun()
        else: st.info("لا توجد بيانات")

    # --- صفحات العرض ---
    elif selection == "أعمالي":
        st.title("📂 أعمالي")
        df = get_smart_data(user)
        my_df = df[df['user_id'] == user.id]
        if not my_df.empty: st.dataframe(my_df[['title', 'activity_type', 'points']], use_container_width=True)
        else: st.info("فارغ")

    elif selection == "الإعدادات":
        st.title("⚙️ الإعدادات")
        with st.form("pwd"):
            p = st.text_input("كلمة المرور الجديدة", type="password")
            if st.form_submit_button("تغيير"):
                change_password(user.id, p); st.success("تم")

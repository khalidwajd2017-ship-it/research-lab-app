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
    page_title="المركز البحثي أدرار",
    layout="wide",
    initial_sidebar_state="expanded",
    page_icon="🎓"
)

# --- قائمة أنواع الأنشطة ---
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
        if not session.query(User).filter_by(username="admin").first():
            # إنشاء الهيكل الأساسي
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
            return df[df['dept_name'] == 'xxxx']
        elif user.role == 'leader': 
            if user.team: return df[df['team_name'] == user.team.name]
            return df[df['team_name'] == 'xxxx']
        else: return df[df['user_id'] == user.id]
    except: return pd.DataFrame()

# 🆕 دالة تحويل البيانات لملف Excel
def to_excel(df):
    output = io.BytesIO()
    # تنظيف البيانات قبل التصدير (إزالة أعمدة غير هامة)
    export_df = df.copy()
    if 'details' in export_df.columns:
        # محاولة استخراج معلومات مفيدة من JSON
        export_df['تفاصيل_إضافية'] = export_df['details'].apply(lambda x: " | ".join([f"{k}:{v}" for k,v in json.loads(x).items()]) if x else "")
    
    cols_map = {
        'title': 'العنوان', 'activity_type': 'النوع', 'publication_date': 'التاريخ', 
        'points': 'النقاط', 'full_name': 'الباحث', 'team_name': 'الفرقة', 'dept_name': 'القسم'
    }
    export_df = export_df.rename(columns=cols_map)
    # الاحتفاظ بالأعمدة العربية فقط
    final_cols = [c for c in cols_map.values() if c in export_df.columns] + ['تفاصيل_إضافية']
    export_df = export_df[final_cols]
    
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
    [data-testid="stForm"] { background: white; padding: 25px; border-radius: 12px; border: 1px solid #e5e7eb; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05); }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 5. التطبيق
# ==========================================

if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False

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
                    st.session_state['user_id'] = user.id
                    st.rerun()
                else: st.toast("بيانات خاطئة", icon="❌")

else:
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
            "إدارة الأنشطة": "🗂️ إدارة الأنشطة (تعديل/حذف)",
            "تسجيل نتاج": "📝 تسجيل نتاج جديد",
            "أعمالي": "📂 سجل أعمالي",
            "الإعدادات": "⚙️ الإعدادات"
        }
        if user.role == 'admin': menu["إدارة المستخدمين"] = "👥 إدارة المستخدمين"
            
        sel = st.sidebar.radio("القائمة", list(menu.values()), label_visibility="collapsed")
        selection = [k for k, v in menu.items() if v == sel][0]
        
        if st.button("خروج"):
            st.session_state['logged_in'] = False
            st.rerun()

    # ============================================
    #  1. لوحة القيادة
    # ============================================
    if selection == "لوحة القيادة":
        st.markdown(f"## 📊 لوحة القيادة")
        df = get_smart_data(user)
        
        if not df.empty:
            # 🆕 زر التصدير (Export)
            excel_data = to_excel(df)
            st.download_button(
                label="📥 تحميل التقرير الكامل (Excel)",
                data=excel_data,
                file_name=f'report_{date.today()}.xlsx',
                mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            )
            
            k1, k2, k3, k4 = st.columns(4)
            with k4: st.markdown(f'<div class="kpi-container"><div class="kpi-info"><div class="kpi-value">{len(df)}</div><div class="kpi-label">الأعمال</div></div><div class="kpi-icon">📚</div></div>', unsafe_allow_html=True)
            with k3: st.markdown(f'<div class="kpi-container"><div class="kpi-info"><div class="kpi-value">{df["user_id"].nunique()}</div><div class="kpi-label">الباحثون</div></div><div class="kpi-icon">👥</div></div>', unsafe_allow_html=True)
            with k2: st.markdown(f'<div class="kpi-container"><div class="kpi-info"><div class="kpi-value">{df["points"].sum()}</div><div class="kpi-label">النقاط</div></div><div class="kpi-icon">⭐</div></div>', unsafe_allow_html=True)
            with k1: 
                yr = df['year'].mode()[0] if not df.empty else "-"
                st.markdown(f'<div class="kpi-container"><div class="kpi-info"><div class="kpi-value">{yr}</div><div class="kpi-label">السنة النشطة</div></div><div class="kpi-icon">📅</div></div>', unsafe_allow_html=True)

            c1, c2 = st.columns(2)
            with c1:
                fig = px.pie(df, names='activity_type', title="توزيع الأنشطة", hole=0.5, color_discrete_sequence=px.colors.sequential.Blues_r)
                st.plotly_chart(fig, use_container_width=True)
            with c2:
                daily = df.groupby('year').size().reset_index(name='count')
                fig2 = px.bar(daily, x='year', y='count', title="التطور السنوي", text_auto=True)
                st.plotly_chart(fig2, use_container_width=True)
        else: st.info("لا توجد بيانات.")

    # ============================================
    #  2. تسجيل نتاج (الديناميكي الكامل)
    # ============================================
    elif selection == "تسجيل نتاج":
        st.title("📝 تسجيل نتاج علمي جديد")
        
        # اختيار النوع خارج النموذج (للتحديث الفوري)
        w_type = st.selectbox("📌 نوع النشاط", ACTIVITY_TYPES)
        st.markdown("---")
        
        if 'fid' not in st.session_state: st.session_state['fid'] = int(time.time())
        
        with st.form(key=f"f_{st.session_state['fid']}"):
            c1, c2 = st.columns([3, 1])
            title = c1.text_input("العنوان الكامل *", key=f"t_{w_type}")
            date_pub = c2.date_input("التاريخ *", key=f"d_{w_type}")
            lang = st.selectbox("اللغة", ["العربية", "الإنجليزية", "الفرنسية"], key=f"l_{w_type}")
            
            st.markdown(f"**📄 تفاصيل: {w_type}**")
            details = {"lang": lang}
            pts, cls = 10, "غير مصنف"

            # الحقول الديناميكية
            if w_type == "مقال في مجلة علمية":
                col_a, col_b = st.columns(2)
                with col_a:
                    j = st.text_input("اسم المجلة", key=f"jn_{w_type}")
                    issn = st.text_input("ISSN", key=f"is_{w_type}")
                with col_b:
                    cls = st.selectbox("التصنيف", ["A", "B", "C", "Q1", "Q2", "Q3", "Q4"], key=f"cl_{w_type}")
                    idx = st.multiselect("الفهرسة", ["ASJP", "Scopus", "Web of Science"], key=f"ix_{w_type}")
                details.update({"journal": j, "issn": issn, "indexing": idx})
                pts = 100 if cls in ["A", "Q1"] else (75 if cls in ["B", "Q2"] else 50)

            elif w_type == "مداخلة في مؤتمر":
                conf = st.text_input("اسم الملتقى", key=f"cn_{w_type}")
                scope = st.selectbox("النطاق", ["وطني", "دولي"], key=f"sc_{w_type}")
                details.update({"conf": conf, "scope": scope})
                pts = 50 if scope == "دولي" else 25

            elif w_type in ["تأليف كتاب", "فصل في كتاب"]:
                pub = st.text_input("دار النشر", key=f"pb_{w_type}")
                isbn = st.text_input("ISBN", key=f"sb_{w_type}")
                details.update({"publisher": pub, "isbn": isbn})
                pts = 80

            if st.form_submit_button("💾 حفظ البيانات"):
                if title:
                    add_work_service(user.id, title, json.dumps(details), w_type, cls, date_pub, pts)
                    st.toast("تم الحفظ!", icon="✅"); time.sleep(1); st.session_state['fid'] = int(time.time()); st.rerun()
                else: st.error("العنوان مطلوب")

    # ============================================
    #  3. إدارة الأنشطة (بحث + تعديل + حذف)
    # ============================================
    elif selection == "إدارة الأنشطة":
        st.title("🗂️ إدارة الأنشطة البحثية")
        
        # 🆕 شريط البحث
        search_term = st.text_input("🔎 بحث (العنوان، اسم الباحث، النوع)...")
        
        df = get_smart_data(user)
        if not df.empty:
            # تصفية الجدول بناءً على البحث
            if search_term:
                df = df[df['title'].str.contains(search_term, na=False) | 
                        df['full_name'].str.contains(search_term, na=False) |
                        df['activity_type'].str.contains(search_term, na=False)]
            
            st.info(f"عدد النتائج: {len(df)}")
            
            for i, row in df.iterrows():
                # استخراج التفاصيل لعرضها
                det_txt = ""
                try: 
                    d = json.loads(row['details'])
                    det_txt = " | ".join([f"{k}: {v}" for k, v in d.items() if v])
                except: pass

                with st.expander(f"{row['activity_type']} - {row['title']} (👤 {row['full_name']})"):
                    st.caption(f"📅 {row['publication_date']} | ⭐ {row['points']} نقطة | 🏷️ {det_txt}")
                    
                    c1, c2 = st.columns([3, 1])
                    new_t = c1.text_input("تعديل العنوان", row['title'], key=f"et_{row['id']}")
                    new_d = c2.date_input("تعديل التاريخ", pd.to_datetime(row['publication_date']).date(), key=f"ed_{row['id']}")
                    
                    b1, b2 = st.columns(2)
                    if b1.button("حفظ التعديلات", key=f"sv_{row['id']}"):
                        update_work_service(row['id'], new_t, new_d); st.toast("تم التعديل"); time.sleep(1); st.rerun()
                    if b2.button("حذف نهائي", key=f"dl_{row['id']}"):
                        delete_work_service(row['id']); st.toast("تم الحذف"); time.sleep(1); st.rerun()
        else: st.info("لا توجد بيانات.")

    # ============================================
    #  4. إدارة المستخدمين (Admin)
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
            sel_d = st.selectbox("القسم", list(d_map.keys())) if d_map else None
            
            sel_t_id = None
            if role != "رئيس قسم" and sel_d:
                teams = session.query(Team).filter_by(department_id=d_map[sel_d]).all()
                t_map = {t.name: t.id for t in teams}
                if t_map:
                    sel_t = st.selectbox("الفرقة", list(t_map.keys()))
                    sel_t_id = t_map[sel_t]
            
            if st.form_submit_button("إضافة"):
                r_code = "dept_head" if role == "رئيس قسم" else ("leader" if role == "رئيس فرقة" else "researcher")
                if add_user_service(uname, name, pas, r_code, sel_t_id, d_map.get(sel_d)):
                    st.success("تمت الإضافة")
                else: st.error("خطأ (ربما المستخدم مكرر)")

    elif selection == "أعمالي":
        st.title("📂 أعمالي")
        df = get_smart_data(user)
        df_my = df[df['user_id'] == user.id]
        if not df_my.empty: st.dataframe(df_my[['title', 'activity_type', 'points']])
        else: st.info("لا توجد أعمال")

    elif selection == "الإعدادات":
        st.title("⚙️ الإعدادات")
        with st.form("pwd"):
            p = st.text_input("كلمة المرور الجديدة", type="password")
            if st.form_submit_button("تغيير"):
                change_password(user.id, p); st.success("تم")

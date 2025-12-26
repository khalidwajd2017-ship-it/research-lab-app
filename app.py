import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, Column, Integer, String, Date, ForeignKey, Text, Enum
from sqlalchemy.orm import sessionmaker, relationship, declarative_base, joinedload
import bcrypt
from datetime import date, datetime
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

# ==========================================
# 2. دوال مساعدة (صور + أسرار)
# ==========================================
def get_img_as_base64(file_path):
    try:
        with open(file_path, "rb") as f:
            data = f.read()
        return base64.b64encode(data).decode()
    except: return None

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
# 3. تعريف الجداول (الهيكلية الجديدة) 🏗️
# ==========================================

# جدول الأقسام (الجديد)
class Department(Base):
    __tablename__ = "departments"
    id = Column(Integer, primary_key=True, index=True)
    dept_number = Column(Integer, unique=True, nullable=False) # رقم القسم
    name_ar = Column(String, nullable=False) # اسم القسم بالعربية
    name_lat = Column(String, nullable=True) # اسم القسم باللاتينية
    short_name = Column(String, nullable=True) # الاسم المختصر
    teams = relationship("Team", back_populates="department")

# جدول الفرق (المطور)
class Team(Base):
    __tablename__ = "teams"
    id = Column(Integer, primary_key=True, index=True)
    department_id = Column(Integer, ForeignKey("departments.id")) # ارتباط بالقسم
    team_number = Column(Integer, nullable=True) # رقم الفرقة
    name = Column(String, unique=True, nullable=False) # اسم الفرقة
    short_name = Column(String, nullable=True) # الاسم المختصر للفرقة
    leader_name = Column(String, nullable=True) # رئيس الفرقة (نصي أو يمكن ربطه بجدول المستخدمين)
    thematic_fields = Column(Text, nullable=True) # الميادين / الكلمات المفتاحية
    scientific_desc = Column(Text, nullable=True) # وصف علمي لبرنامج البحث
    
    department = relationship("Department", back_populates="teams")
    members = relationship("User", back_populates="team")

# جدول المستخدمين (مع تصنيف العضوية)
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    full_name = Column(String, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, nullable=False) # admin, leader, researcher
    member_type = Column(String, default="permanent") # permanent (دائم) / phd_student (طالب دكتوراه)
    
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

# ==========================================
# 4. دوال النظام والتهيئة
# ==========================================
def init_db():
    try:
        Base.metadata.create_all(bind=engine)
        session = SessionLocal()
        
        # 1. تهيئة الأقسام الـ 6 (إذا لم تكن موجودة)
        if not session.query(Department).first():
            depts = []
            for i in range(1, 7):
                depts.append(Department(
                    dept_number=i,
                    name_ar=f"القسم ({i})",
                    name_lat=f"Department {i}",
                    short_name=f"Dept-{i}"
                ))
            session.add_all(depts)
            session.commit()
            
            # 2. إضافة فرق افتراضية للقسم الأول (كمثال)
            first_dept = session.query(Department).filter_by(dept_number=1).first()
            if first_dept:
                teams = [
                    Team(
                        name="فرقة علم النفس العيادي", 
                        short_name="CP Team", 
                        team_number=1, 
                        department_id=first_dept.id,
                        leader_name="أ.د محمد علي",
                        thematic_fields="الصحة النفسية، العلاج السلوكي",
                        scientific_desc="دراسة الاضطرابات السلوكية في الوسط المدرسي"
                    ),
                    Team(
                        name="فرقة تكنولوجيا التعليم", 
                        short_name="EdTech", 
                        team_number=2, 
                        department_id=first_dept.id,
                        leader_name="د. سعاد أحمد",
                        thematic_fields="التعليم الإلكتروني، الرقمنة",
                        scientific_desc="تطوير منصات تعليمية ذكية"
                    )
                ]
                session.add_all(teams)
                session.commit()

        # 3. حساب المدير
        if not session.query(User).filter_by(username="admin").first():
            hashed_pw = bcrypt.hashpw("12345".encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            session.add(User(username="admin", full_name="المدير العام", password_hash=hashed_pw, role="admin"))
            session.commit()
            
        session.close()
        return True
    except Exception as e:
        print(e)
        return False

# خدمات قاعدة البيانات
def auth_user(u, p):
    s = SessionLocal()
    try:
        user = s.query(User).options(joinedload(User.team)).filter(User.username == u).first()
        if user and bcrypt.checkpw(p.encode(), user.password_hash.encode()): return user
    except: pass
    finally: s.close()
    return None

def register_user(u, p, f, r, t_name, m_type):
    s = SessionLocal()
    try:
        team = s.query(Team).filter(Team.name == t_name).first()
        h = bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()
        s.add(User(username=u, full_name=f, password_hash=h, role=r, team_id=team.id if team else None, member_type=m_type))
        s.commit()
        return True
    except:
        s.rollback()
        return False
    finally: s.close()

def add_work(uid, title, details, atype, cls, date_obj, pts):
    s = SessionLocal()
    try:
        s.add(Work(user_id=uid, title=title, details=details, activity_type=atype, classification=cls, publication_date=date_obj, year=date_obj.year, points=pts))
        s.commit()
        return True
    except:
        s.rollback()
        return False
    finally: s.close()

def get_data_df():
    try: return pd.read_sql("""
        SELECT w.id, w.title, w.activity_type, w.classification, w.publication_date, w.year, w.points,
               u.full_name, t.name as team_name, d.name_ar as dept_name
        FROM works w 
        JOIN users u ON w.user_id = u.id 
        LEFT JOIN teams t ON u.team_id = t.id
        LEFT JOIN departments d ON t.department_id = d.id
        ORDER BY w.publication_date DESC
    """, engine)
    except: return pd.DataFrame()

# ==========================================
# 5. التنسيق (CSS) - RTL
# ==========================================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;800&family=Tajawal:wght@400;500;700&display=swap');
    :root { --primary-color: #2563eb; --bg-color: #f8fafc; --text-color: #1e293b; }
    html, body, .stApp { font-family: 'Tajawal', sans-serif; direction: rtl; background-color: var(--bg-color); color: var(--text-color); text-align: right; }
    h1, h2, h3, h4, h5, h6 { font-family: 'Cairo', sans-serif !important; font-weight: 800; color: #1e3a8a; text-align: right !important; }
    .stMarkdown, .stText, p { text-align: right !important; direction: rtl !important; }
    [data-testid="stSidebar"] { background-color: #ffffff; border-left: 1px solid #e2e8f0; min-width: 300px !important; }
    [data-testid="stDataFrame"] table { direction: rtl !important; text-align: right !important; }
    [data-testid="stDataFrame"] th { text-align: right !important; background-color: #f1f5f9 !important; font-family: 'Cairo', sans-serif; }
    .stTabs [data-baseweb="tab-list"] { gap: 8px; justify-content: flex-start; }
    .stTabs [data-baseweb="tab"] { height: 45px; font-family: 'Cairo', sans-serif; font-weight: 700; }
    .kpi-card { background: #ffffff; padding: 20px; border-radius: 12px; box-shadow: 0 2px 10px rgba(0,0,0,0.03); border: 1px solid #e2e8f0; position: relative; }
    .kpi-card::before { content: ""; position: absolute; right: 0; top: 0; bottom: 0; width: 4px; background: var(--primary-color); border-radius: 0 12px 12px 0; }
    .kpi-value { font-family: 'Cairo', sans-serif; font-size: 28px; font-weight: 800; color: #0f172a; }
    .kpi-title { font-size: 13px; color: #64748b; font-weight: 500; text-align: right; }
    .stTextInput input, .stSelectbox div, .stTextArea textarea { text-align: right; direction: rtl; }
    div[data-testid="stToast"] { direction: rtl; text-align: right; font-family: 'Cairo'; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 6. واجهة التطبيق
# ==========================================

if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
    init_db()

if not st.session_state['logged_in']:
    c1, c2, c3 = st.columns([1, 1.5, 1])
    with c2:
        st.markdown("<br>", unsafe_allow_html=True)
        # شعار الصفحة الرئيسية
        logo_path = "logo.png"
        logo_html = '<div style="font-size: 60px; margin-bottom: 10px;">🏛️</div>'
        if os.path.exists(logo_path):
            img = get_img_as_base64(logo_path)
            if img: logo_html = f'<img src="data:image/png;base64,{img}" style="width: 180px; margin-bottom: 20px;">'

        st.markdown(f"""
        <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center !important; margin-bottom: 30px;">
            {logo_html}
            <h1 style="color:#1e40af; font-family:'Cairo'; margin: 0; text-align: center !important; width: 100%;">بوابة البحث العلمي</h1>
            <p style="color:#64748b; text-align: center !important; width: 100%;">نظام إدارة المخابر الجامعية الموحد</p>
        </div>
        """, unsafe_allow_html=True)
        
        with st.container(border=True):
            tab1, tab2 = st.tabs(["🔐 دخول", "✨ تسجيل"])
            with tab1:
                with st.form("login"):
                    u = st.text_input("اسم المستخدم")
                    p = st.text_input("كلمة المرور", type="password")
                    if st.form_submit_button("دخول", type="primary", use_container_width=True):
                        with st.spinner("جاري التحقق..."):
                            user = auth_user(u, p)
                            if user:
                                st.session_state['logged_in'] = True
                                st.session_state['user'] = {'id': user.id, 'name': user.full_name, 'role': user.role, 'team': user.team.name if user.team else "", 'team_id': user.team_id}
                                st.toast("أهلاً بك!", icon="👋")
                                time.sleep(1)
                                st.rerun()
                            else: st.toast("بيانات خاطئة", icon="❌")
            with tab2:
                with st.form("signup"):
                    s = SessionLocal()
                    try: tn = [t.name for t in s.query(Team).all()]
                    except: tn = []
                    s.close()
                    
                    nu = st.text_input("اسم المستخدم")
                    np = st.text_input("كلمة المرور", type="password")
                    nf = st.text_input("الاسم الكامل")
                    nt = st.selectbox("الفرقة", tn) if tn else st.warning("لا توجد فرق")
                    m_type = st.radio("نوع العضوية", ["عضو دائم", "طالب دكتوراه"], horizontal=True)
                    rc = st.radio("الصلاحية", ["باحث", "رئيس فرقة"], horizontal=True)
                    co = st.text_input("كود التفعيل", type="password")
                    
                    if st.form_submit_button("إنشاء حساب", use_container_width=True):
                        codes = {"باحث": "RES2025", "رئيس فرقة": "LEADER2025"}
                        role_map = {"باحث": "researcher", "رئيس فرقة": "leader"}
                        type_map = {"عضو دائم": "permanent", "طالب دكتوراه": "phd_student"}
                        
                        if co == codes.get(rc):
                            with st.spinner("جاري التسجيل..."):
                                if register_user(nu, np, nf, role_map[rc], nt, type_map[m_type]):
                                    st.toast("تم التسجيل بنجاح!", icon="✅")
                                else: st.toast("المستخدم موجود مسبقاً", icon="⚠️")
                        else: st.toast("كود خاطئ", icon="⛔")

else:
    user = st.session_state['user']
    with st.sidebar:
        # شعار السايدبار
        logo_path = "logo.png"
        sb_logo = ""
        if os.path.exists(logo_path):
            img = get_img_as_base64(logo_path)
            if img: sb_logo = f'<img src="data:image/png;base64,{img}" style="width: 140px; margin-bottom: 15px;">'
        
        st.markdown(f"""
        <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center !important; padding-bottom: 20px; border-bottom: 1px solid #e5e7eb; margin-bottom: 20px;">
            {sb_logo}
            <h3 style="margin: 0; color: #1e3a8a; font-family:'Cairo'; text-align: center !important;">المركز البحثي أدرار</h3>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown(f"""<div style="background: #f8fafc; padding: 10px; border-radius: 8px; border: 1px solid #e2e8f0; text-align: center; margin-bottom: 20px;"><b>👤 {user['name']}</b><br><span style="font-size: 12px; color: #64748b;">{user['role']}</span></div>""", unsafe_allow_html=True)

        menu = {"تسجيل نتاج جديد": "📝 تسجيل نتاج جديد", "أعمالي": "👤 أعمالي", "الهيكل التنظيمي": "🏢 الهيكل التنظيمي (الفرق)"}
        if user['role'] == 'admin': menu["لوحة القيادة"] = "📊 لوحة القيادة العامة"
        
        sel = st.sidebar.radio("القائمة", list(menu.values()), label_visibility="collapsed")
        selection = [k for k, v in menu.items() if v == sel][0]

        if st.button("خروج"):
            st.session_state['logged_in'] = False
            st.rerun()

    # --- المحتوى ---
    if selection == "الهيكل التنظيمي":
        st.title("🏢 الهيكل التنظيمي للمخبر")
        session = SessionLocal()
        
        # جلب الأقسام
        depts = session.query(Department).order_by(Department.dept_number).all()
        
        for dept in depts:
            with st.expander(f"📂 {dept.name_ar} ({dept.name_lat}) - {dept.short_name}", expanded=False):
                teams = session.query(Team).filter_by(department_id=dept.id).all()
                if teams:
                    for team in teams:
                        st.markdown(f"### 🔹 {team.name}")
                        c1, c2 = st.columns(2)
                        with c1:
                            st.info(f"**رئيس الفرقة:** {team.leader_name or 'غير محدد'}")
                            st.write(f"**الرمز:** {team.short_name}")
                        with c2:
                            st.write(f"**الميادين:** {team.thematic_fields or '---'}")
                        
                        st.markdown(f"**📝 وصف البرنامج:** {team.scientific_desc or '---'}")
                        
                        # الأعضاء
                        members = session.query(User).filter_by(team_id=team.id).all()
                        perm = [m.full_name for m in members if m.member_type == 'permanent']
                        phd = [m.full_name for m in members if m.member_type == 'phd_student']
                        
                        tc1, tc2 = st.columns(2)
                        with tc1:
                            st.markdown("**👨‍🏫 الأعضاء الدائمون:**")
                            if perm: 
                                for p in perm: st.markdown(f"- {p}")
                            else: st.caption("لا يوجد")
                        with tc2:
                            st.markdown("**🎓 طلبة الدكتوراه:**")
                            if phd:
                                for p in phd: st.markdown(f"- {p}")
                            else: st.caption("لا يوجد")
                        st.divider()
                else:
                    st.warning("لا توجد فرق مسجلة في هذا القسم حالياً.")
        session.close()

    elif selection == "تسجيل نتاج جديد":
        st.title("📝 إضافة نتاج علمي")
        # (نفس كود الإضافة السابق مع التحسينات)
        # ... (للإيجاز، استخدم نفس نموذج الإضافة من الكود السابق، فهو متوافق)
        with st.form("add_work"):
            title = st.text_input("العنوان")
            atype = st.selectbox("النوع", ["مقال", "مداخلة", "كتاب"])
            date_pub = st.date_input("التاريخ")
            if st.form_submit_button("حفظ"):
                with st.spinner("جاري الحفظ..."):
                    if add_work(user['id'], title, "{}", atype, "A", date_pub, 100):
                        st.toast("تم الحفظ!", icon="✅")
                    else: st.toast("خطأ", icon="❌")

    elif selection == "أعمالي":
        st.title("👤 سجل أعمالي")
        df = get_works_dataframe()
        my_df = df[df['full_name'] == user['name']]
        if not my_df.empty:
            st.dataframe(my_df[['publication_date', 'activity_type', 'title', 'points']])
        else:
            st.info("لا توجد أعمال مسجلة.")

    elif selection == "لوحة القيادة":
        st.title("📊 الإحصائيات العامة")
        df = get_works_dataframe()
        if not df.empty:
            c1, c2, c3 = st.columns(3)
            c1.metric("إجمالي الأعمال", len(df))
            c2.metric("عدد الباحثين", df['full_name'].nunique())
            c3.metric("النقاط", df['points'].sum())
            
            st.subheader("توزيع الأعمال حسب الأقسام")
            # نحتاج دمج البيانات لعرض الأعمال حسب القسم
            fig = px.pie(df, names='dept_name', hole=0.4)
            st.plotly_chart(fig, use_container_width=True)

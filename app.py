import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, Column, Integer, String, Date, ForeignKey, Text
from sqlalchemy.orm import sessionmaker, relationship, declarative_base, joinedload
import bcrypt
from datetime import date
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
# 2. دوال مساعدة + قاعدة البيانات
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

# --- تعريف الجداول ---
class Team(Base):
    __tablename__ = "teams"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    description = Column(String, nullable=True)
    department_id = Column(Integer, ForeignKey("departments.id"))
    department = relationship("Department", back_populates="teams")
    members = relationship("User", back_populates="team")

class Department(Base):
    __tablename__ = "departments"
    id = Column(Integer, primary_key=True, index=True)
    dept_number = Column(Integer, unique=True)
    name_ar = Column(String)
    teams = relationship("Team", back_populates="department")

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    full_name = Column(String)
    password_hash = Column(String)
    role = Column(String) 
    member_type = Column(String)
    team_id = Column(Integer, ForeignKey("teams.id"))
    team = relationship("Team", back_populates="members")
    works = relationship("Work", back_populates="researcher")

class Work(Base):
    __tablename__ = "works"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(Text, nullable=False)
    details = Column(Text, nullable=True) # هنا سنخزن كل التفاصيل الدقيقة كـ JSON
    activity_type = Column(String, nullable=False)
    classification = Column(String, nullable=True)
    publication_date = Column(Date, nullable=False)
    year = Column(Integer, nullable=False)
    points = Column(Integer, default=0)
    user_id = Column(Integer, ForeignKey("users.id"))
    researcher = relationship("User", back_populates="works")

# --- دالة التهيئة ---
def init_db():
    try:
        Base.metadata.create_all(bind=engine)
        session = SessionLocal()
        # (نفس كود التهيئة السابق لإنشاء الأقسام والمدير...)
        if not session.query(User).filter_by(username="admin").first():
            hashed_pw = bcrypt.hashpw("12345".encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            session.add(User(username="admin", full_name="المدير العام", password_hash=hashed_pw, role="admin"))
            session.commit()
        session.close()
    except: pass

# --- الخدمات ---
def auth_user(u, p):
    s = SessionLocal()
    try:
        user = s.query(User).options(joinedload(User.team)).filter(User.username == u).first()
        if user and bcrypt.checkpw(p.encode(), user.password_hash.encode()): return user
    except: pass
    finally: s.close()
    return None

def register_user(u, p, f, r, t_name, m_type):
    # (نفس كود التسجيل السابق)
    s = SessionLocal()
    try:
        team = s.query(Team).filter(Team.name == t_name).first()
        h = bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()
        s.add(User(username=u, full_name=f, password_hash=h, role=r, team_id=team.id if team else None, member_type=m_type))
        s.commit()
        return True
    except:
        s.rollback(); return False
    finally: s.close()

def add_work_service(uid, title, details_json, atype, cls, date_obj, pts):
    s = SessionLocal()
    try:
        s.add(Work(user_id=uid, title=title, details=details_json, activity_type=atype, classification=cls, publication_date=date_obj, year=date_obj.year, points=pts))
        s.commit()
        return True
    except:
        s.rollback(); return False
    finally: s.close()

def get_works_dataframe():
    try: return pd.read_sql("SELECT * FROM works", engine) # (مبسط للعرض)
    except: return pd.DataFrame()

# ==========================================
# 4. التنسيق (CSS) - RTL
# ==========================================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;800&family=Tajawal:wght@400;500;700&display=swap');
    :root { --primary-color: #2563eb; --bg-color: #f8fafc; --text-color: #1e293b; }
    html, body, .stApp { font-family: 'Tajawal', sans-serif; direction: rtl; background-color: var(--bg-color); color: var(--text-color); text-align: right; }
    h1, h2, h3, h4, h5, h6 { font-family: 'Cairo', sans-serif !important; font-weight: 800; color: #1e3a8a; text-align: right !important; }
    .stMarkdown, .stText, p { text-align: right !important; direction: rtl !important; }
    [data-testid="stSidebar"] { background-color: #ffffff; border-left: 1px solid #e2e8f0; min-width: 300px !important; }
    .stTextInput input, .stSelectbox div, .stTextArea textarea, .stDateInput input, .stNumberInput input { text-align: right; direction: rtl; border-radius: 8px; }
    div[data-testid="stToast"] { direction: rtl; text-align: right; font-family: 'Cairo'; }
    .stButton>button { width: 100%; border-radius: 8px; font-weight: bold; font-family: 'Cairo'; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 5. واجهة المستخدم
# ==========================================

if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
    init_db()

if not st.session_state['logged_in']:
    # (كود تسجيل الدخول - لم يتغير)
    c1, c2, c3 = st.columns([1, 1.5, 1])
    with c2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        # الشعار والعنوان (كما طلبت سابقاً)
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
        
        with st.form("login"):
            u = st.text_input("اسم المستخدم")
            p = st.text_input("كلمة المرور", type="password")
            if st.form_submit_button("دخول", type="primary"):
                user = auth_user(u, p)
                if user:
                    st.session_state['logged_in'] = True
                    st.session_state['user'] = {'id': user.id, 'name': user.full_name, 'role': user.role, 'team': user.team.name if user.team else ""}
                    st.rerun()
                else: st.toast("خطأ في البيانات", icon="❌")

else:
    user = st.session_state['user']
    with st.sidebar:
        # الشعار في السايدبار (كما طلبت)
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
        
        st.info(f"مرحباً بك: {user['name']}")
        
        menu = {"تسجيل نتاج جديد": "📝 تسجيل نتاج جديد", "أعمالي": "👤 أعمالي"}
        if user['role'] == 'admin': menu["لوحة القيادة"] = "📊 لوحة القيادة"
        
        sel = st.sidebar.radio("القائمة", list(menu.values()), label_visibility="collapsed")
        selection = [k for k, v in menu.items() if v == sel][0]
        
        if st.button("تسجيل الخروج"):
            st.session_state['logged_in'] = False
            st.rerun()

    # ==========================================
    # 🌟 الصفحة المطورة: تسجيل نتاج جديد (شاملة)
    # ==========================================
    if selection == "تسجيل نتاج جديد":
        st.title("📝 إضافة نتاج علمي جديد")
        st.markdown("---")

        if 'form_id' not in st.session_state: st.session_state['form_id'] = 0

        # النموذج الرئيسي
        with st.form(key=f"work_form_{st.session_state['form_id']}"):
            
            # 1. البيانات الأساسية المشتركة
            st.subheader("1️⃣ البيانات الأساسية")
            col_main1, col_main2 = st.columns([2, 1])
            with col_main1: 
                w_title = st.text_input("العنوان الكامل للعمل (Title) *")
            with col_main2: 
                w_lang = st.selectbox("لغة العمل", ["العربية", "الإنجليزية", "الفرنسية"])

            col_sub1, col_sub2 = st.columns(2)
            with col_sub1:
                w_type = st.selectbox("نوع النشاط البحثي *", 
                    ["مقال في مجلة علمية", "مداخلة في مؤتمر", "تأليف كتاب", "فصل في كتاب", "براءة اختراع", "تأطير مذكرة", "مشروع بحث"])
            with col_sub2:
                w_date = st.date_input("تاريخ النشر / المناقشة *")

            st.markdown("---")
            
            # 2. البيانات التفصيلية (ديناميكية حسب النوع)
            st.subheader(f"2️⃣ تفاصيل: {w_type}")
            
            details_data = {"language": w_lang} # قاموس لتخزين التفاصيل
            w_class = "غير مصنف" # قيمة افتراضية للتصنيف
            w_points = 10 # نقاط افتراضية

            # --- حالة: مقال علمي ---
            if w_type == "مقال في مجلة علمية":
                c1, c2 = st.columns(2)
                with c1:
                    journal = st.text_input("اسم المجلة (Journal Name)")
                    issn = st.text_input("الرقم التسلسلي (ISSN)")
                    url_link = st.text_input("رابط المقال (URL)")
                with c2:
                    w_class = st.selectbox("تصنيف المجلة", ["A", "B", "C", "Q1", "Q2", "Q3", "Q4", "غير مصنف"])
                    indexing = st.multiselect("الفهرسة (Indexing)", ["ASJP", "Scopus", "Web of Science", "Erih Plus"])
                    vol_issue = st.text_input("المجلد (Vol) / العدد (No)")
                
                details_data.update({"journal": journal, "issn": issn, "indexing": indexing, "volume_issue": vol_issue, "url": url_link})
                # حساب النقاط التقريبي
                if w_class in ["A", "Q1"]: w_points = 100
                elif w_class in ["B", "Q2"]: w_points = 75
                elif w_class == "C": w_points = 50
                else: w_points = 25

            # --- حالة: مداخلة مؤتمر ---
            elif w_type == "مداخلة في مؤتمر":
                c1, c2 = st.columns(2)
                with c1:
                    conf_name = st.text_input("اسم الملتقى / المؤتمر")
                    organizer = st.text_input("الجهة المنظمة")
                with c2:
                    scope = st.selectbox("النطاق", ["وطني", "دولي"])
                    part_type = st.selectbox("نوع المشاركة", ["شخصية (شفهية)", "عن بعد (Online)", "ملصق (Poster)"])
                    location = st.text_input("مكان الانعقاد (المدينة/البلد)")
                
                details_data.update({"conference": conf_name, "organizer": organizer, "scope": scope, "participation": part_type, "location": location})
                w_class = scope
                w_points = 50 if scope == "دولي" else 25

            # --- حالة: كتاب أو فصل ---
            elif w_type in ["تأليف كتاب", "فصل في كتاب"]:
                c1, c2 = st.columns(2)
                with c1:
                    publisher = st.text_input("دار النشر")
                    isbn = st.text_input("الرقم الدولي (ISBN)")
                with c2:
                    pages = st.text_input("عدد الصفحات / نطاق الصفحات")
                    edition = st.text_input("رقم الطبعة / سنة الإصدار")
                
                details_data.update({"publisher": publisher, "isbn": isbn, "pages": pages, "edition": edition})
                w_points = 80 if w_type == "تأليف كتاب" else 40

            # --- حالة: براءة اختراع ---
            elif w_type == "براءة اختراع":
                c1, c2 = st.columns(2)
                with c1:
                    patent_num = st.text_input("رقم البراءة")
                with c2:
                    granting_body = st.text_input("الهيئة المانحة (مثل INAPI)")
                
                details_data.update({"patent_number": patent_num, "body": granting_body})
                w_points = 150

            # --- حالة: تأطير ---
            elif w_type == "تأطير مذكرة":
                c1, c2 = st.columns(2)
                with c1:
                    student_name = st.text_input("اسم الطالب المؤطر")
                with c2:
                    level = st.selectbox("المستوى", ["ماستر", "دكتوراه لمد", "دكتوراه علوم"])
                
                details_data.update({"student": student_name, "level": level})
                w_points = 20

            # --- حالة: مشروع بحث ---
            elif w_type == "مشروع بحث":
                c1, c2 = st.columns(2)
                with c1:
                    proj_code = st.text_input("رمز المشروع (Code)")
                    proj_role = st.selectbox("الصفة في المشروع", ["رئيس مشروع", "عضو"])
                with c2:
                    proj_kind = st.selectbox("نوع المشروع", ["PRFU", "PNR", "CNEPRU", "تعاون دولي"])
                
                details_data.update({"code": proj_code, "role": proj_role, "kind": proj_kind})
                w_points = 60

            st.markdown("---")
            
            # زر الحفظ
            submit_btn = st.form_submit_button("💾 حفظ البيانات في السجل", type="primary", use_container_width=True)

            if submit_btn:
                if w_title:
                    # تحويل التفاصيل لنص JSON
                    json_details = json.dumps(details_data, ensure_ascii=False)
                    
                    with st.spinner("جاري معالجة البيانات وحفظها..."):
                        success = add_work_service(
                            uid=user['id'],
                            title=w_title,
                            details_json=json_details,
                            atype=w_type,
                            cls=w_class,
                            date_obj=w_date,
                            pts=w_points
                        )
                        
                        if success:
                            st.toast("✅ تمت العملية بنجاح! تم حفظ النتاج.", icon="🎉")
                            time.sleep(1)
                            st.session_state['form_id'] += 1
                            st.rerun()
                        else:
                            st.toast("حدث خطأ أثناء الاتصال بقاعدة البيانات", icon="🚨")
                else:
                    st.toast("يرجى كتابة عنوان العمل على الأقل", icon="⚠️")

    # (باقي الصفحات مثل "أعمالي" و "لوحة القيادة" تبقى كما هي أو يمكن تحسينها لاحقاً)
    elif selection == "أعمالي":
        st.title("👤 سجل أعمالي")
        # يمكن إضافة كود عرض الجدول هنا

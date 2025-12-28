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
        return create_engine(DATABASE_URL, pool_pre_ping=True)
    except: return None

engine = get_db_engine()
if not engine: st.stop()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- النماذج (Tables) ---
class Team(Base):
    __tablename__ = "teams"
    id = Column(Integer, primary_key=True)
    name = Column(String)
    department_id = Column(Integer, ForeignKey("departments.id"))
    department = relationship("Department", back_populates="teams")
    members = relationship("User", back_populates="team")

class Department(Base):
    __tablename__ = "departments"
    id = Column(Integer, primary_key=True)
    name_ar = Column(String)
    teams = relationship("Team", back_populates="department")

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String)
    full_name = Column(String)
    password_hash = Column(String)
    role = Column(String) 
    member_type = Column(String)
    team_id = Column(Integer, ForeignKey("teams.id"))
    team = relationship("Team", back_populates="members")
    works = relationship("Work", back_populates="researcher")

class Work(Base):
    __tablename__ = "works"
    id = Column(Integer, primary_key=True)
    title = Column(Text)
    details = Column(Text) # هنا نخزن التفاصيل الدقيقة JSON
    activity_type = Column(String)
    classification = Column(String)
    publication_date = Column(Date)
    year = Column(Integer)
    points = Column(Integer)
    user_id = Column(Integer, ForeignKey("users.id"))
    researcher = relationship("User", back_populates="works")

# --- الخدمات ---
def auth_user(u, p):
    s = SessionLocal()
    try:
        user = s.query(User).options(joinedload(User.team)).filter(User.username == u).first()
        if user:
            if u == "admin" and p == "12345": return user
            if bcrypt.checkpw(p.encode(), user.password_hash.encode()): return user
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

# ==========================================
# 4. التنسيق (CSS) - RTL
# ==========================================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;800&family=Tajawal:wght@400;500;700&display=swap');
    :root { --primary: #2563eb; --bg: #f8fafc; }
    
    html, body, .stApp { font-family: 'Tajawal', sans-serif; direction: rtl; background-color: var(--bg); text-align: right; }
    h1, h2, h3, h4 { font-family: 'Cairo'; font-weight: 800; color: #1e3a8a; text-align: right !important; }
    
    [data-testid="stSidebar"] { background: #fff; border-left: 1px solid #e2e8f0; }
    .stTextInput input, .stSelectbox div, .stTextArea textarea, .stDateInput input { text-align: right; direction: rtl; border-radius: 8px; }
    
    /* تنسيق خاص للنماذج */
    .stForm { background-color: white; padding: 20px; border-radius: 15px; border: 1px solid #e2e8f0; box-shadow: 0 4px 6px rgba(0,0,0,0.02); }
    
    div[data-testid="stToast"] { direction: rtl; text-align: right; font-family: 'Cairo'; }
    .stButton>button { width: 100%; border-radius: 8px; font-family: 'Cairo'; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 5. التطبيق
# ==========================================

if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False

# --- شاشة الدخول ---
if not st.session_state['logged_in']:
    c1, c2, c3 = st.columns([1, 1.5, 1])
    with c2:
        st.markdown("<br><br>", unsafe_allow_html=True)
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
        
        tab1, tab2 = st.tabs(["🔐 دخول", "✨ تسجيل"])
        with tab1:
            with st.form("login"):
                u = st.text_input("اسم المستخدم")
                p = st.text_input("كلمة المرور", type="password")
                if st.form_submit_button("دخول", type="primary", use_container_width=True):
                    user = auth_user(u, p)
                    if user:
                        st.session_state['logged_in'] = True
                        st.session_state['user'] = {'id': user.id, 'name': user.full_name, 'role': user.role, 'team': user.team.name if user.team else ""}
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
                nt = st.selectbox("الفرقة", tn) if tn else st.write("لا توجد فرق")
                mt = st.radio("العضوية", ["عضو دائم", "طالب دكتوراه"], horizontal=True)
                rc = st.radio("الصفة", ["باحث", "رئيس فرقة"], horizontal=True)
                co = st.text_input("كود التفعيل", type="password")
                if st.form_submit_button("تسجيل", use_container_width=True):
                    codes = {"باحث": "RES2025", "رئيس فرقة": "LEADER2025"}
                    if co == codes.get(rc):
                        if register_user(nu, np, nf, "researcher" if rc=="باحث" else "leader", nt, "permanent" if mt=="عضو دائم" else "phd"):
                            st.success("تم التسجيل!")
                        else: st.error("المستخدم موجود")
                    else: st.error("الكود خاطئ")

# --- النظام الداخلي ---
else:
    user = st.session_state['user']
    
    with st.sidebar:
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
        
        st.info(f"مرحباً: {user['name']}")
        
        menu = {
            "تسجيل نتاج جديد": "📝 تسجيل نتاج جديد",
            "أعمالي": "📂 سجل أعمالي",
            "الملف الشخصي": "👤 الملف الشخصي",
            "الإعدادات": "⚙️ الإعدادات"
        }
        if user['role'] == 'admin': menu["لوحة القيادة"] = "📊 لوحة القيادة"
        
        sel = st.sidebar.radio("القائمة", list(menu.values()), label_visibility="collapsed")
        selection = [k for k, v in menu.items() if v == sel][0]
        
        if st.button("تسجيل الخروج"):
            st.session_state['logged_in'] = False
            st.rerun()

    # ============================================
    #  صفحة تسجيل نتاج علمي (النسخة الاحترافية)
    # ============================================
    if selection == "تسجيل نتاج جديد":
        st.title("📝 تسجيل نتاج علمي جديد")
        st.markdown("---")
        
        if 'form_id' not in st.session_state: st.session_state['form_id'] = 0
        
        with st.form(key=f"work_form_{st.session_state['form_id']}"):
            
            # --- القسم 1: البيانات الأساسية ---
            st.markdown("##### 📌 البيانات العامة للعمل")
            col_main1, col_main2 = st.columns([3, 1])
            with col_main1:
                w_title = st.text_input("العنوان الكامل (Title) *")
            with col_main2:
                w_lang = st.selectbox("لغة العمل", ["العربية", "الإنجليزية", "الفرنسية"])

            col_sub1, col_sub2 = st.columns(2)
            with col_sub1:
                w_type = st.selectbox("نوع النشاط البحثي *", 
                    ["مقال في مجلة علمية", "مداخلة في مؤتمر", "تأليف كتاب", "فصل في كتاب", "براءة اختراع", "تأطير مذكرة", "مشروع بحث"])
            with col_sub2:
                w_date = st.date_input("تاريخ النشر / المناقشة *")

            st.markdown("---")
            
            # --- القسم 2: التفاصيل الديناميكية (Dynamic Fields) ---
            st.markdown(f"##### 📄 تفاصيل خاصة بـ: {w_type}")
            
            details_data = {"language": w_lang}
            w_class = "غير مصنف"
            w_points = 10

            # 1. حالة المقال العلمي
            if w_type == "مقال في مجلة علمية":
                c1, c2 = st.columns(2)
                with c1:
                    journal = st.text_input("اسم المجلة (Journal Name)")
                    issn = st.text_input("الرقم التسلسلي (ISSN)")
                    url_link = st.text_input("رابط المقال (URL)")
                with c2:
                    w_class = st.selectbox("تصنيف المجلة", ["A", "B", "C", "Q1", "Q2", "Q3", "Q4", "غير مصنف"])
                    indexing = st.multiselect("القواعد المفهرسة (Indexing)", ["ASJP", "Scopus", "Web of Science", "Erih Plus"])
                    vol_issue = st.text_input("المجلد (Vol) / العدد (No)")
                
                details_data.update({"journal": journal, "issn": issn, "indexing": indexing, "volume_issue": vol_issue, "url": url_link})
                # حساب النقاط التقريبي
                if w_class in ["A", "Q1"]: w_points = 100
                elif w_class in ["B", "Q2"]: w_points = 75
                elif w_class == "C": w_points = 50
                else: w_points = 25

            # 2. حالة المداخلة (مؤتمر)
            elif w_type == "مداخلة في مؤتمر":
                c1, c2 = st.columns(2)
                with c1:
                    conf_name = st.text_input("اسم التظاهرة العلمية")
                    organizer = st.text_input("الجهة المنظمة")
                with c2:
                    scope = st.selectbox("النطاق", ["وطني", "دولي"])
                    part_type = st.selectbox("نوع المشاركة", ["شخصية (شفهية)", "عن بعد (Online)", "ملصق (Poster)"])
                    location = st.text_input("مكان الانعقاد")
                
                details_data.update({"conference": conf_name, "organizer": organizer, "scope": scope, "participation": part_type, "location": location})
                w_class = scope
                w_points = 50 if scope == "دولي" else 25

            # 3. حالة الكتاب
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

            # 4. حالة براءة الاختراع
            elif w_type == "براءة اختراع":
                c1, c2 = st.columns(2)
                with c1:
                    patent_num = st.text_input("رقم البراءة")
                with c2:
                    granting_body = st.text_input("الهيئة المانحة (مثل INAPI)")
                
                details_data.update({"patent_number": patent_num, "body": granting_body})
                w_points = 150

            # 5. حالة مشروع البحث
            elif w_type == "مشروع بحث":
                c1, c2 = st.columns(2)
                with c1:
                    proj_code = st.text_input("رمز المشروع (Code)")
                    proj_role = st.selectbox("صفتك في المشروع", ["رئيس مشروع", "عضو"])
                with c2:
                    proj_kind = st.selectbox("نوع المشروع", ["PRFU", "PNR", "CNEPRU", "شراكة دولية"])
                
                details_data.update({"code": proj_code, "role": proj_role, "kind": proj_kind})
                w_points = 60

            # 6. حالة التأطير
            elif w_type == "تأطير مذكرة":
                c1, c2 = st.columns(2)
                with c1:
                    student_name = st.text_input("اسم الطالب")
                with c2:
                    level = st.selectbox("المستوى", ["ماستر", "دكتوراه"])
                details_data.update({"student": student_name, "level": level})
                w_points = 20

            st.markdown("---")
            submitted = st.form_submit_button("💾 حفظ البيانات في السجل", type="primary", use_container_width=True)
            
            if submitted:
                if w_title:
                    json_details = json.dumps(details_data, ensure_ascii=False)
                    with st.spinner("جاري الحفظ..."):
                        if add_work_service(user['id'], w_title, json_details, w_type, w_class, w_date, w_points):
                            st.toast("✅ تم الحفظ بنجاح!", icon="🎉")
                            time.sleep(1)
                            st.session_state['form_id'] += 1
                            st.rerun()
                        else: st.toast("حدث خطأ", icon="🚨")
                else: st.toast("يرجى كتابة العنوان", icon="⚠️")

    # ============================================
    #  صفحة لوحة القيادة (للمدير)
    # ============================================
    elif selection == "لوحة القيادة":
        st.title("📊 لوحة القيادة العامة")
        df = pd.read_sql("SELECT * FROM works", engine)
        if not df.empty:
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("إجمالي الأعمال", len(df))
            c2.metric("عدد الباحثين", df["user_id"].nunique())
            c3.metric("مجموع النقاط", df["points"].sum())
            c4.metric("آخر نشاط", df["year"].max())
            st.markdown("---")
            col_g1, col_g2 = st.columns(2)
            with col_g1:
                st.subheader("توزيع الأنشطة")
                fig1 = px.pie(df, names='activity_type', hole=0.5)
                st.plotly_chart(fig1, use_container_width=True)
            with col_g2:
                st.subheader("التطور السنوي")
                yc = df.groupby('year').size().reset_index(name='count')
                fig2 = px.bar(yc, x='year', y='count')
                st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("لا توجد بيانات كافية.")

    # ============================================
    #  صفحة سجل أعمالي
    # ============================================
    elif selection == "أعمالي":
        st.title("📂 سجل أعمالي")
        query = f"SELECT * FROM works WHERE user_id = {user['id']} ORDER BY publication_date DESC"
        my_df = pd.read_sql(query, engine)
        
        if not my_df.empty:
            # تحسين عرض الجدول
            display_df = my_df[['title', 'activity_type', 'classification', 'publication_date', 'points']].copy()
            display_df.columns = ['العنوان', 'النوع', 'التصنيف', 'التاريخ', 'النقاط']
            st.dataframe(display_df, use_container_width=True)
        else:
            st.info("لم تقم بإضافة أي أعمال بعد.")

    # ============================================
    #  صفحة الملف الشخصي
    # ============================================
    elif selection == "الملف الشخصي":
        st.title("👤 الملف الشخصي")
        with st.container(border=True):
            col_p1, col_p2 = st.columns([1, 3])
            with col_p1:
                st.markdown(f"""<div style="background:#eff6ff; width:100px; height:100px; border-radius:50%; display:flex; align-items:center; justify-content:center; font-size:40px; color:#2563eb; margin:auto;">{user['name'][0]}</div>""", unsafe_allow_html=True)
            with col_p2:
                st.subheader(user['name'])
                st.write(f"**الرتبة:** {user['role']}")
                st.write(f"**الفرقة:** {user['team']}")
                st.write(f"**اسم المستخدم:** {st.session_state['user'].get('username', '---')}")

    # ============================================
    #  صفحة الإعدادات
    # ============================================
    elif selection == "الإعدادات":
        st.title("⚙️ الإعدادات")
        with st.container(border=True):
            st.subheader("تغيير كلمة المرور")
            with st.form("pwd_change"):
                p1 = st.text_input("كلمة المرور الجديدة", type="password")
                p2 = st.text_input("تأكيد كلمة المرور", type="password")
                if st.form_submit_button("تحديث"):
                    if p1 == p2 and len(p1) > 0:
                        if change_password(user['id'], p1):
                            st.success("تم تغيير كلمة المرور بنجاح.")
                            time.sleep(2)
                            st.session_state['logged_in'] = False
                            st.rerun()
                        else: st.error("حدث خطأ")
                    else: st.warning("كلمات المرور غير متطابقة")

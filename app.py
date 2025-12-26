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

RAW_PASS = "khalidcom_1981"
DB_USER = "postgres.jecmwuiqofztficcujpe"
DB_HOST = "aws-1-eu-west-2.pooler.supabase.com"
DB_PORT = "6543"
DB_NAME = "postgres"

encoded_password = urllib.parse.quote_plus(RAW_PASS)

DATABASE_URL = f"postgresql://{DB_USER}:{encoded_password}@{DB_HOST}:{DB_PORT}/{DB_NAME}?sslmode=require"

try:
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base = declarative_base()
except Exception as e:
    st.error(f"خطأ في الاتصال بقاعدة البيانات: {e}")

# --- تعريف الجداول ---
class Team(Base):
    __tablename__ = "teams"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    description = Column(String, nullable=True)
    members = relationship("User", back_populates="team")

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    full_name = Column(String, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, nullable=False) 
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

def init_db():
    try:
        Base.metadata.create_all(bind=engine)
        session = SessionLocal()
        if not session.query(Team).first():
            teams = [Team(name="دراسات سوسيولوجية"), Team(name="علم النفس العيادي"), Team(name="تكنولوجيا التعليم")]
            session.add_all(teams)
            session.commit()
        if not session.query(User).filter_by(username="admin").first():
            hashed_pw = bcrypt.hashpw("12345".encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            session.add(User(username="admin", full_name="المدير العام", password_hash=hashed_pw, role="admin"))
            session.commit()
        session.close()
        return True
    except Exception as e:
        print(f"Init Warning: {e}")
        return False

# ==========================================
# 3. الخدمات (Services)
# ==========================================
def auth_user(username, password):
    db = SessionLocal()
    try:
        user = db.query(User).options(joinedload(User.team)).filter(User.username == username).first()
        if user and bcrypt.checkpw(password.encode('utf-8'), user.password_hash.encode('utf-8')):
            return user
    except: pass
    finally: db.close()
    return None

def register_user_service(username, password, full_name, role, team_name):
    db = SessionLocal()
    try:
        team = db.query(Team).filter(Team.name == team_name).first()
        hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        db.add(User(username=username, full_name=full_name, password_hash=hashed, role=role, team_id=team.id if team else None))
        db.commit()
        return True
    except:
        db.rollback()
        return False
    finally: db.close()

def add_work_service(user_id, title, details_json, type_, class_, date_obj, points):
    db = SessionLocal()
    try:
        db.add(Work(user_id=user_id, title=title, details=details_json, activity_type=type_, classification=class_, publication_date=date_obj, year=date_obj.year, points=points))
        db.commit()
    except: db.rollback()
    finally: db.close()

def change_password_service(user_id, new_password):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            user.password_hash = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            db.commit()
            return True
        return False
    finally: db.close()

def get_works_dataframe():
    query = """
    SELECT w.id, w.title, w.activity_type, w.classification, w.publication_date, w.year, w.points, w.details,
           u.full_name as researcher_name, t.name as team_name
    FROM works w JOIN users u ON w.user_id = u.id LEFT JOIN teams t ON u.team_id = t.id
    ORDER BY w.publication_date DESC
    """
    try: return pd.read_sql(query, engine)
    except: return pd.DataFrame()

# ==========================================
# 4. التنسيق (CSS) - RTL
# ==========================================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;800&family=Tajawal:wght@400;500;700&display=swap');
    
    :root {
        --primary-color: #2563eb; 
        --bg-color: #f8fafc;
        --text-color: #1e293b;
    }

    html, body, .stApp {
        font-family: 'Tajawal', sans-serif;
        direction: rtl; 
        background-color: var(--bg-color);
        color: var(--text-color);
        text-align: right;
    }
    
    /* العناوين العامة */
    h1, h2, h3, h4, h5, h6 {
        font-family: 'Cairo', sans-serif !important;
        font-weight: 800;
        color: #1e3a8a;
        text-align: right;
    }

    .stMarkdown, .stText, p {
        text-align: right !important;
        direction: rtl !important;
    }

    /* إصلاح السايدبار */
    [data-testid="stSidebar"] {
        background-color: #ffffff;
        border-left: 1px solid #e2e8f0;
        min-width: 300px !important;
        max-width: 320px !important;
    }
    
    /* تنسيق الجداول */
    [data-testid="stDataFrame"] { border-radius: 10px; overflow: hidden; box-shadow: 0 2px 5px rgba(0,0,0,0.05); }
    [data-testid="stDataFrame"] table { direction: rtl !important; text-align: right !important; }
    [data-testid="stDataFrame"] th { text-align: right !important; background-color: #f1f5f9 !important; font-family: 'Cairo', sans-serif; }
    
    /* تنسيق التبويبات */
    .stTabs [data-baseweb="tab-list"] { gap: 8px; justify-content: flex-start; }
    .stTabs [data-baseweb="tab"] {
        height: 45px; white-space: pre-wrap; background-color: #fff; border-radius: 8px 8px 0 0;
        gap: 1px; padding-top: 8px; padding-bottom: 8px; font-family: 'Cairo', sans-serif; font-weight: 700; font-size: 14px;
    }
    .stTabs [aria-selected="true"] { background-color: #eff6ff; color: #2563eb; border-bottom: 2px solid #2563eb; }

    /* بطاقات KPI */
    .kpi-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 15px; margin-bottom: 25px; direction: rtl; }
    .kpi-card { background: #ffffff; padding: 20px; border-radius: 12px; box-shadow: 0 2px 10px rgba(0,0,0,0.03); border: 1px solid #e2e8f0; position: relative; overflow: hidden; transition: all 0.3s ease; }
    
    .kpi-card::before { content: ""; position: absolute; right: 0; top: 0; bottom: 0; width: 4px; background: var(--primary-color); border-radius: 0 12px 12px 0; }
    
    .kpi-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
    .kpi-icon { width: 40px; height: 40px; background: #eff6ff; color: var(--primary-color); border-radius: 10px; display: flex; align-items: center; justify-content: center; font-size: 20px; }
    .kpi-value { font-family: 'Cairo', sans-serif; font-size: 28px; font-weight: 800; color: #0f172a; line-height: 1; }
    .kpi-title { font-size: 13px; color: #64748b; font-weight: 500; margin-top: 5px; text-align: right; }

    .stButton>button { font-family: 'Cairo', sans-serif !important; font-weight: 700; border-radius: 8px; height: 45px; }
    
    .stTextInput input, .stSelectbox div, .stTextArea textarea, .stDateInput input { text-align: right; direction: rtl; border-radius: 8px; }
    .stRadio { direction: rtl; text-align: right; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 5. واجهة المستخدم
# ==========================================

if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
    init_db()

if not st.session_state['logged_in']:
    c1, c2, c3 = st.columns([1, 1.5, 1])
    with c2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        # ✅ هذا هو الجزء المسؤول عن التوسط (تم استخدام Flexbox)
        st.markdown("""
        <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center !important; margin-bottom: 30px;">
            <div style="font-size: 60px; margin-bottom: 10px;">🏛️</div>
            <h1 style="color:#1e40af; font-family:'Cairo'; font-weight: 800; margin: 0; text-align: center !important; width: 100%;">بوابة البحث العلمي</h1>
            <p style="color:#64748b; font-family:'Tajawal'; font-size: 18px; margin-top: 5px; text-align: center !important; width: 100%;">نظام إدارة المخابر الجامعية الموحد</p>
        </div>
        """, unsafe_allow_html=True)
        
        with st.container(border=True):
            tab1, tab2 = st.tabs(["🔐 دخول الأعضاء", "✨ حساب جديد"])
            with tab1:
                with st.form("login"):
                    u = st.text_input("اسم المستخدم")
                    p = st.text_input("كلمة المرور", type="password")
                    if st.form_submit_button("تسجيل الدخول", use_container_width=True, type="primary"):
                        user = auth_user(u, p)
                        if user:
                            st.session_state['logged_in'] = True
                            st.session_state['user'] = {'id': user.id, 'name': user.full_name, 'role': user.role, 'team': user.team.name if user.team else "إدارة مركزية", 'username': user.username}
                            st.rerun()
                        else: st.error("خطأ في البيانات")
            with tab2:
                with st.form("signup"):
                    session = SessionLocal()
                    tn = ["جاري التحميل..."]
                    try:
                        teams_data = session.query(Team).all()
                        if teams_data: tn = [t.name for t in teams_data]
                        else: tn = ["لا توجد فرق"]
                    except: pass
                    session.close()
                    
                    nu = st.text_input("اسم المستخدم")
                    np = st.text_input("كلمة المرور", type="password")
                    nf = st.text_input("الاسم الكامل")
                    nt = st.selectbox("الفرقة", tn)
                    rc = st.radio("الصفة", ["باحث", "رئيس فرقة", "مدير"], horizontal=True)
                    co = st.text_input("كود التفعيل", type="password")
                    if st.form_submit_button("إنشاء حساب", use_container_width=True):
                        rm = {"باحث": "researcher", "رئيس فرقة": "leader", "مدير": "admin"}
                        cm = {"researcher": "RES2025", "leader": "LEADER2025", "admin": "ADMIN2025"}
                        if co == cm.get(rm.get(rc, ""), ""):
                            if register_user_service(nu, np, nf, rm[rc], nt): st.success("تم الإنشاء!")
                            else: st.error("المستخدم موجود")
                        else: st.error("الكود خاطئ")

else:
    user = st.session_state['user']
    with st.sidebar:
        # ✅ توسيط اللوغو والعنوان في السايدبار أيضاً
        st.markdown("""
        <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center !important; padding-bottom: 20px; border-bottom: 1px solid #e5e7eb; margin-bottom: 20px;">
            <div style="font-size: 40px;">🎓</div>
            <h3 style="margin: 5px 0 0 0; color: #1e3a8a; font-family:'Cairo'; text-align: center !important;">المركز البحثي أدرار</h3>
            <span style="font-size: 12px; color: #64748b; display: block; text-align: center !important;">منصة التميز البحثي</span>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown(f"""<div style="display: flex; align-items: center; background: #f8fafc; padding: 12px; border-radius: 12px; margin-bottom: 20px; border: 1px solid #e2e8f0; direction: rtl;"><div style="width: 40px; height: 40px; background: #2563eb; color: white; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: bold; font-family: 'Cairo'; margin-left: 10px;">{user['name'][0]}</div><div><div style="font-weight: bold; font-size: 14px; color: #334155;">{user['name']}</div><div style="font-size: 11px; color: #94a3b8;">{user['role']}</div></div></div>""", unsafe_allow_html=True)

        menu_options = {
            "admin": {"لوحة القيادة العامة": "📊 لوحة القيادة العامة", "السجل العلمي للمخبر": "🗂️ السجل العلمي للمخبر"},
            "leader": {"لوحة قيادة الفرقة": "📈 لوحة قيادة الفرقة", "سجل أعمال الفرقة": "📂 سجل أعمال الفرقة"},
            "common": {"تسجيل نتاج جديد": "📝 تسجيل نتاج جديد", "أعمالي الشخصية": "👤 أعمالي الشخصية", "الإعدادات": "⚙️ الإعدادات"}
        }
        
        final_menu = {}
        if user['role'] == 'admin': final_menu.update(menu_options["admin"])
        if user['role'] == 'leader': final_menu.update(menu_options["leader"])
        final_menu.update(menu_options["common"])
        
        selection_key = st.sidebar.radio("القائمة:", list(final_menu.values()), label_visibility="collapsed")
        try: selection = [k for k, v in final_menu.items() if v == selection_key][0]
        except: selection = "أعمالي الشخصية"

        st.divider()
        if st.button("تسجيل الخروج"): 
            st.session_state['logged_in'] = False
            st.rerun()

    if selection in ["لوحة القيادة العامة", "لوحة قيادة الفرقة"]:
        st.title(selection_key)
        df = get_works_dataframe()
        current_df = df
        filter_title = "تصفية البيانات العامة"
        if selection == "لوحة قيادة الفرقة":
            current_df = df[df['team_name'] == user['team']]
            filter_title = f"تصفية بيانات: {user['team']}"

        with st.expander(f"🔍 {filter_title}", expanded=True):
            c_f1, c_f2 = st.columns(2)
            with c_f1: 
                years = sorted(current_df['year'].unique(), reverse=True) if not current_df.empty else []
                sel_y = st.multiselect("السنة:", years, default=years)
            with c_f2:
                types = sorted(current_df['activity_type'].unique()) if not current_df.empty else []
                sel_t = st.multiselect("نوع النشاط:", types, default=types)
            if sel_y: current_df = current_df[current_df['year'].isin(sel_y)]
            if sel_t: current_df = current_df[current_df['activity_type'].isin(sel_t)]

        if not current_df.empty:
            total_works = len(current_df)
            total_researchers = current_df['researcher_name'].nunique()
            total_points = current_df['points'].sum()
            top_year = current_df['year'].mode()[0] if not current_df.empty else "-"

            st.markdown(f"""
            <div class="kpi-grid">
                <div class="kpi-card"><div class="kpi-header"><div class="kpi-icon">📚</div><div class="kpi-value">{total_works}</div></div><div class="kpi-title">إجمالي النتاج العلمي</div></div>
                <div class="kpi-card"><div class="kpi-header"><div class="kpi-icon">👥</div><div class="kpi-value">{total_researchers}</div></div><div class="kpi-title">الباحثون النشطون</div></div>
                <div class="kpi-card"><div class="kpi-header"><div class="kpi-icon">⭐</div><div class="kpi-value">{total_points}</div></div><div class="kpi-title">مجموع نقاط التقييم</div></div>
                <div class="kpi-card"><div class="kpi-header"><div class="kpi-icon">📅</div><div class="kpi-value">{top_year}</div></div><div class="kpi-title">السنة الأكثر نشاطاً</div></div>
            </div>""", unsafe_allow_html=True)

            col_g1, col_g2 = st.columns(2)
            with col_g1:
                with st.container(border=True):
                    st.markdown("##### 📊 توزيع الأنشطة")
                    fig1 = px.pie(current_df, names='activity_type', hole=0.5, color_discrete_sequence=px.colors.sequential.Blues_r)
                    st.plotly_chart(fig1, use_container_width=True)
            with col_g2:
                with st.container(border=True):
                    st.markdown("##### 📈 التطور السنوي")
                    yc = current_df.groupby('year').size().reset_index(name='count')
                    fig2 = px.bar(yc, x='year', y='count', text_auto=True)
                    fig2.update_traces(marker_color='#2563eb', width=0.4)
                    st.plotly_chart(fig2, use_container_width=True)
        else: st.warning("لا توجد بيانات مطابقة للفلترة.")

    elif selection == "تسجيل نتاج جديد":
        st.title(selection_key)
        st.markdown("##### 📌 اختر نوع النشاط لتخصيص الحقول:")
        w_type = st.selectbox("", ["مقال علمي", "مداخلة دولية", "مداخلة وطنية", "كتاب", "مشروع بحث"], label_visibility="collapsed")
        st.markdown("---")

        with st.form("dynamic_form"):
            col_main1, col_main2 = st.columns([3, 1])
            with col_main1: w_title = st.text_input("العنوان الكامل للعمل")
            with col_main2: w_date = st.date_input("تاريخ النشر / الإنجاز")

            # ✅ فرض المحاذاة لليمين للنص الديناميكي
            st.markdown(f"<div style='text-align: right; direction: rtl; font-weight: bold;'>📄 تفاصيل خاصة بـ: {w_type}</div>", unsafe_allow_html=True)
            
            extra_data = {}
            w_class = "غير مصنف"

            if w_type == "مقال علمي":
                c1, c2 = st.columns(2)
                with c1:
                    journal_name = st.text_input("اسم المجلة")
                    url_link = st.text_input("رابط المقال")
                with c2:
                    w_class = st.selectbox("تصنيف المجلة", ["A", "B", "C", "Q1", "Q2", "Q3", "Q4", "غير مصنف"])
                    vol_iss = st.text_input("المجلد / العدد")
                extra_data = {"المجلة": journal_name, "العدد": vol_iss, "رابط": url_link}
            elif "مداخلة" in w_type:
                c1, c2 = st.columns(2)
                with c1:
                    conf_name = st.text_input("اسم التظاهرة العلمية")
                    organizer = st.text_input("الجهة المنظمة")
                with c2:
                    location = st.text_input("مكان الانعقاد")
                    participation_type = st.selectbox("نوع المشاركة", ["حضورية", "عن بعد"])
                extra_data = {"التظاهرة": conf_name, "المنظم": organizer, "المكان": location, "المشاركة": participation_type}
            elif w_type == "كتاب":
                c1, c2 = st.columns(2)
                with c1:
                    publisher = st.text_input("دار النشر")
                    isbn = st.text_input("رقم الردمك (ISBN)")
                with c2:
                    pages = st.number_input("عدد الصفحات", min_value=10)
                    edition = st.text_input("رقم الطبعة")
                extra_data = {"الناشر": publisher, "ISBN": isbn, "الصفحات": pages, "الطبعة": edition}
            elif w_type == "مشروع بحث":
                c1, c2 = st.columns(2)
                with c1:
                    proj_code = st.text_input("رمز المشروع (Code)")
                    proj_role = st.selectbox("صفتك في المشروع", ["رئيس مشروع", "عضو"])
                with c2:
                    proj_kind = st.selectbox("نوع المشروع", ["PRFU", "PNR", "CNEPRU", "شراكة دولية"])
                    duration = st.text_input("مدة المشروع")
                extra_data = {"الرمز": proj_code, "الصفة": proj_role, "النوع": proj_kind, "المدة": duration}

            st.write("")
            submitted = st.form_submit_button("💾 حفظ المعلومات في السجل", type="primary", use_container_width=True)
            
            if submitted:
                if w_title:
                    pts = 0
                    if w_class in ["A", "Q1"]: pts = 100
                    elif w_class in ["B", "Q2"]: pts = 75
                    elif w_class == "C": pts = 50
                    elif "دولي" in w_type: pts = 40
                    elif "وطني" in w_type: pts = 25
                    elif w_type == "كتاب": pts = 60
                    elif w_type == "مشروع بحث": pts = 80
                    else: pts = 10
                    json_str = json.dumps(extra_data, ensure_ascii=False)
                    add_work_service(user['id'], w_title, json_str, w_type, w_class, w_date, pts)
                    st.success("✅ تمت الإضافة بنجاح!")
                    time.sleep(1)
                    st.rerun()
                else: st.error("يرجى إدخال العنوان")

    elif selection in ["السجل العلمي للمخبر", "سجل أعمال الفرقة", "أعمالي الشخصية"]:
        st.title(selection_key)
        df = get_works_dataframe()
        
        if selection == "أعمالي الشخصية": df = df[df['researcher_name'] == user['name']]
        elif selection == "سجل أعمال الفرقة": df = df[df['team_name'] == user['team']]
        
        if not df.empty:
            df['publication_date'] = pd.to_datetime(df['publication_date']).dt.strftime('%Y-%m-%d')
            def parse_details(row):
                try: return json.loads(row) if row else {}
                except: return {}
            df['details_dict'] = df['details'].apply(parse_details)

            with st.expander("🔍 بحث متقدم وتصفية", expanded=True):
                col_s1, col_s2, col_s3, col_s4, col_s5 = st.columns(5)
                with col_s1: search_txt = st.text_input("بحث بعنوان العمل:")
                with col_s2: 
                    all_types = sorted(df['activity_type'].unique())
                    type_fil = st.multiselect("نوع النشاط:", all_types)
                with col_s3: 
                    all_years = sorted(df['year'].unique(), reverse=True)
                    year_fil = st.multiselect("السنة:", all_years)
                with col_s4:
                    all_classes = sorted([x for x in df['classification'].unique() if x])
                    class_fil = st.multiselect("التصنيف:", all_classes)
                researcher_fil = []
                if selection != "أعمالي الشخصية":
                    with col_s5: 
                        all_researchers = sorted(df['researcher_name'].unique())
                        researcher_fil = st.multiselect("اسم الباحث:", all_researchers)
                
                if search_txt: df = df[df['title'].str.contains(search_txt, na=False)]
                if type_fil: df = df[df['activity_type'].isin(type_fil)]
                if year_fil: df = df[df['year'].isin(year_fil)]
                if class_fil: df = df[df['classification'].isin(class_fil)]
                if researcher_fil: df = df[df['researcher_name'].isin(researcher_fil)]

            st.markdown(f"**عدد النتائج المطابقة:** {len(df)}")

            tab_all, tab_art, tab_conf, tab_book, tab_proj = st.tabs(["📋 الكل", "📰 المقالات", "🎤 المداخلات", "📚 الكتب", "🔬 المشاريع"])

            with tab_all:
                st.dataframe(df[['publication_date', 'researcher_name', 'team_name', 'activity_type', 'title', 'classification', 'points']].rename(columns={'publication_date': 'التاريخ', 'researcher_name': 'الباحث', 'team_name': 'الفرقة', 'activity_type': 'النوع', 'title': 'العنوان', 'classification': 'التصنيف', 'points': 'النقاط'}), use_container_width=True, hide_index=True, column_config={"التاريخ": st.column_config.TextColumn("التاريخ", width="medium"), "العنوان": st.column_config.TextColumn("العنوان", width="large"), "النقاط": st.column_config.ProgressColumn("التقييم", format="%d", min_value=0, max_value=100)})

            with tab_art:
                df_art = df[df['activity_type'] == "مقال علمي"].copy()
                if not df_art.empty:
                    df_art['المجلة'] = df_art['details_dict'].apply(lambda x: x.get('المجلة', '-'))
                    df_art['العدد'] = df_art['details_dict'].apply(lambda x: x.get('العدد', '-'))
                    st.dataframe(df_art[['publication_date', 'researcher_name', 'title', 'classification', 'المجلة', 'العدد', 'points']].rename(columns={'publication_date': 'تاريخ النشر', 'researcher_name': 'الباحث', 'title': 'عنوان المقال', 'classification': 'التصنيف', 'points': 'النقاط'}), use_container_width=True, hide_index=True, column_config={"تاريخ النشر": st.column_config.TextColumn(width="medium"), "عنوان المقال": st.column_config.TextColumn(width="large")})
                else: st.info("لا توجد مقالات مطابقة للبحث.")

            with tab_conf:
                df_conf = df[df['activity_type'].str.contains("مداخلة")].copy()
                if not df_conf.empty:
                    df_conf['التظاهرة'] = df_conf['details_dict'].apply(lambda x: x.get('التظاهرة', '-'))
                    df_conf['المكان'] = df_conf['details_dict'].apply(lambda x: x.get('المكان', '-'))
                    st.dataframe(df_conf[['publication_date', 'researcher_name', 'title', 'التظاهرة', 'المكان', 'points']].rename(columns={'publication_date': 'تاريخ الانعقاد', 'researcher_name': 'الباحث', 'title': 'عنوان المداخلة', 'points': 'النقاط'}), use_container_width=True, hide_index=True, column_config={"تاريخ الانعقاد": st.column_config.TextColumn(width="medium"), "عنوان المداخلة": st.column_config.TextColumn(width="large")})
                else: st.info("لا توجد مداخلات مطابقة للبحث.")

            with tab_book:
                df_book = df[df['activity_type'] == "كتاب"].copy()
                if not df_book.empty:
                    df_book['الناشر'] = df_book['details_dict'].apply(lambda x: x.get('الناشر', '-'))
                    df_book['ISBN'] = df_book['details_dict'].apply(lambda x: x.get('ISBN', '-'))
                    st.dataframe(df_book[['publication_date', 'researcher_name', 'title', 'الناشر', 'ISBN', 'points']].rename(columns={'publication_date': 'تاريخ النشر', 'researcher_name': 'الباحث', 'title': 'عنوان الكتاب', 'points': 'النقاط'}), use_container_width=True, hide_index=True)
                else: st.info("لا توجد كتب مطابقة للبحث.")

            with tab_proj:
                df_proj = df[df['activity_type'] == "مشروع بحث"].copy()
                if not df_proj.empty:
                    df_proj['الرمز'] = df_proj['details_dict'].apply(lambda x: x.get('الرمز', '-'))
                    df_proj['الصفة'] = df_proj['details_dict'].apply(lambda x: x.get('الصفة', '-'))
                    df_proj['النوع'] = df_proj['details_dict'].apply(lambda x: x.get('النوع', '-'))
                    st.dataframe(df_proj[['publication_date', 'researcher_name', 'title', 'الرمز', 'النوع', 'الصفة', 'points']].rename(columns={'publication_date': 'تاريخ البداية', 'researcher_name': 'الباحث', 'title': 'عنوان المشروع', 'points': 'النقاط'}), use_container_width=True, hide_index=True)
                else: st.info("لا توجد مشاريع مطابقة للبحث.")
        else: st.warning("السجل فارغ")

    elif selection == "الإعدادات":
        st.title(selection_key)
        tab_sec, tab_prof = st.tabs(["🔐 الأمان", "👤 الملف الشخصي"])
        with tab_sec:
            with st.container(border=True):
                st.subheader("تغيير كلمة المرور")
                with st.form("pwd_chg"):
                    p1 = st.text_input("كلمة المرور الجديدة", type="password")
                    p2 = st.text_input("تأكيد كلمة المرور", type="password")
                    if st.form_submit_button("تحديث", type="primary"):
                        if p1 == p2 and len(p1) > 0:
                            if change_password_service(user['id'], p1):
                                st.success("تم التحديث! سجل الدخول مجدداً.")
                                time.sleep(2)
                                st.session_state['logged_in'] = False
                                st.rerun()
                            else: st.error("خطأ")
                        else: st.error("كلمات المرور غير متطابقة")
        with tab_prof:
            with st.container(border=True):
                st.info(f"الاسم: {user['name']}")
                st.info(f"الدور: {user['role']}")
                st.info(f"الفرقة: {user['team']}")

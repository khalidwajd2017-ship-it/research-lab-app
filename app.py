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
    details = Column(Text) 
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

def get_analytics_data():
    query = """
    SELECT 
        w.id, w.title, w.activity_type, w.publication_date, w.year, w.points, w.classification,
        u.full_name as researcher, 
        t.name as team, 
        d.name_ar as department
    FROM works w
    JOIN users u ON w.user_id = u.id
    LEFT JOIN teams t ON u.team_id = t.id
    LEFT JOIN departments d ON t.department_id = d.id
    """
    try:
        df = pd.read_sql(query, engine)
        df['department'] = df['department'].fillna('غير محدد')
        df['team'] = df['team'].fillna('غير محدد')
        return df
    except Exception as e:
        return pd.DataFrame()

# ==========================================
# 4. التنسيق (CSS) - مطابق للصورة المرفقة
# ==========================================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;800&family=Tajawal:wght@400;500;700&display=swap');
    :root { --primary: #2563eb; --bg: #f8fafc; }
    
    html, body, .stApp { font-family: 'Tajawal', sans-serif; direction: rtl; background-color: #fcfcfc; text-align: right; }
    h1, h2, h3, h4 { font-family: 'Cairo'; font-weight: 800; color: #1e3a8a; text-align: right !important; }
    
    [data-testid="stSidebar"] { background: #fff; border-left: 1px solid #e2e8f0; }
    .stTextInput input, .stSelectbox div, .stTextArea textarea, .stDateInput input { text-align: right; direction: rtl; border-radius: 8px; }
    
    /* تصميم البطاقات العلوية (KPI Cards) - مطابق للصورة */
    .kpi-container {
        background-color: white;
        padding: 20px;
        border-radius: 12px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.04);
        border: 1px solid #f1f5f9;
        border-right: 4px solid #3b82f6; /* الخط الأزرق على اليمين */
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 10px;
        transition: transform 0.2s;
    }
    .kpi-container:hover { transform: translateY(-3px); }
    .kpi-info { text-align: right; }
    .kpi-value { font-family: 'Cairo'; font-size: 28px; font-weight: 800; color: #0f172a; line-height: 1.2; }
    .kpi-label { font-family: 'Tajawal'; font-size: 13px; color: #64748b; font-weight: 600; }
    .kpi-icon { 
        width: 45px; height: 45px; 
        background-color: #eff6ff; 
        border-radius: 10px; 
        display: flex; align-items: center; justify-content: center; 
        font-size: 22px; color: #3b82f6; 
    }

    /* تصميم حاويات الرسوم البيانية */
    .chart-container {
        background-color: white;
        padding: 20px;
        border-radius: 15px;
        border: 1px solid #e2e8f0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.02);
        margin-bottom: 20px;
    }
    
    /* أزرار */
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
        
        with st.form("login"):
            u = st.text_input("اسم المستخدم")
            p = st.text_input("كلمة المرور", type="password")
            if st.form_submit_button("دخول", type="primary"):
                user = auth_user(u, p)
                if user:
                    st.session_state['logged_in'] = True
                    st.session_state['user'] = {'id': user.id, 'name': user.full_name, 'role': user.role, 'team': user.team.name if user.team else ""}
                    st.rerun()
                else: st.toast("بيانات خاطئة", icon="❌")

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
            "لوحة القيادة": "📊 لوحة القيادة العامة",
            "تسجيل نتاج جديد": "📝 تسجيل نتاج جديد",
            "أعمالي": "📂 سجل أعمالي",
            "الملف الشخصي": "👤 الملف الشخصي",
            "الإعدادات": "⚙️ الإعدادات"
        }
        
        sel = st.sidebar.radio("القائمة", list(menu.values()), label_visibility="collapsed")
        selection = [k for k, v in menu.items() if v == sel][0]
        
        if st.button("تسجيل الخروج"):
            st.session_state['logged_in'] = False
            st.rerun()

    # ============================================
    #  🌟 لوحة القيادة (مطابقة للصورة المرفقة)
    # ============================================
    if selection == "لوحة القيادة":
        st.markdown("""
        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 20px;">
            <h2 style="font-family:'Cairo'; color:#1e3a8a; margin:0;">📊 لوحة القيادة العامة</h2>
        </div>
        """, unsafe_allow_html=True)
        
        # 1. جلب البيانات
        df = get_analytics_data()
        
        if not df.empty:
            # الفلاتر (في Expander نظيف)
            with st.expander("🔍 تصفية البيانات العامة", expanded=True):
                c1, c2, c3 = st.columns(3)
                with c1: 
                    years = sorted(df['year'].unique().tolist(), reverse=True)
                    sel_year = st.selectbox("السنة", ["الكل"] + years)
                with c2: 
                    depts = sorted(df['department'].unique().tolist())
                    sel_dept = st.selectbox("القسم", ["الكل"] + depts)
                with c3:
                    types = sorted(df['activity_type'].unique().tolist())
                    sel_type = st.selectbox("نوع النشاط", ["الكل"] + types)

            # تطبيق الفلترة
            filtered_df = df.copy()
            if sel_year != "الكل": filtered_df = filtered_df[filtered_df['year'] == sel_year]
            if sel_dept != "الكل": filtered_df = filtered_df[filtered_df['department'] == sel_dept]
            if sel_type != "الكل": filtered_df = filtered_df[filtered_df['activity_type'] == sel_type]

            st.write("") # فاصل

            # 2. البطاقات العلوية (KPIs) - تصميم مطابق للصورة
            k1, k2, k3, k4 = st.columns(4)
            
            # حساب القيم
            total_works = len(filtered_df)
            total_researchers = filtered_df['researcher'].nunique()
            total_points = filtered_df['points'].sum()
            active_year = filtered_df['year'].mode()[0] if not filtered_df.empty else datetime.now().year

            with k4:
                st.markdown(f"""
                <div class="kpi-container">
                    <div class="kpi-info">
                        <div class="kpi-value">{total_works}</div>
                        <div class="kpi-label">إجمالي النتاج العلمي</div>
                    </div>
                    <div class="kpi-icon">📚</div>
                </div>
                """, unsafe_allow_html=True)
            
            with k3:
                st.markdown(f"""
                <div class="kpi-container">
                    <div class="kpi-info">
                        <div class="kpi-value">{total_researchers}</div>
                        <div class="kpi-label">الباحثون النشطون</div>
                    </div>
                    <div class="kpi-icon">👥</div>
                </div>
                """, unsafe_allow_html=True)

            with k2:
                st.markdown(f"""
                <div class="kpi-container">
                    <div class="kpi-info">
                        <div class="kpi-value">{total_points}</div>
                        <div class="kpi-label">مجموع نقاط التقييم</div>
                    </div>
                    <div class="kpi-icon">⭐</div>
                </div>
                """, unsafe_allow_html=True)

            with k1:
                st.markdown(f"""
                <div class="kpi-container">
                    <div class="kpi-info">
                        <div class="kpi-value">{active_year}</div>
                        <div class="kpi-label">السنة الأكثر نشاطاً</div>
                    </div>
                    <div class="kpi-icon">📅</div>
                </div>
                """, unsafe_allow_html=True)

            # 3. الرسوم البيانية (Charts) - مطابقة للصورة
            chart_col1, chart_col2 = st.columns([1, 1])
            
            with chart_col2:
                st.markdown('<div class="chart-container">', unsafe_allow_html=True)
                st.markdown("##### 📊 توزيع الأنشطة")
                # رسم حلقي (Donut Chart)
                fig_donut = px.pie(
                    filtered_df, names='activity_type', 
                    hole=0.5, 
                    color_discrete_sequence=px.colors.sequential.Blues_r
                )
                fig_donut.update_layout(showlegend=True, margin=dict(t=0, b=0, l=0, r=0), height=300)
                st.plotly_chart(fig_donut, use_container_width=True)
                st.markdown('</div>', unsafe_allow_html=True)

            with chart_col1:
                st.markdown('<div class="chart-container">', unsafe_allow_html=True)
                st.markdown("##### 📈 التطور السنوي")
                # رسم عمودي (Bar Chart)
                if not filtered_df.empty:
                    yearly_data = filtered_df.groupby('year').size().reset_index(name='count')
                    fig_bar = px.bar(
                        yearly_data, x='year', y='count', 
                        text_auto=True,
                        color_discrete_sequence=['#2563eb']
                    )
                    fig_bar.update_layout(
                        xaxis_title="", yaxis_title="", 
                        margin=dict(t=10, b=10, l=10, r=10), 
                        height=300,
                        plot_bgcolor='white'
                    )
                    st.plotly_chart(fig_bar, use_container_width=True)
                st.markdown('</div>', unsafe_allow_html=True)

        else:
            st.warning("⚠️ لا توجد بيانات متاحة حالياً.")

    # ============================================
    #  صفحة تسجيل نتاج جديد (الديناميكية)
    # ============================================
    elif selection == "تسجيل نتاج جديد":
        st.title("📝 تسجيل نتاج علمي جديد")
        
        st.markdown("### 1️⃣ نوع النشاط البحثي")
        w_type = st.selectbox(
            "اختر نوع النشاط لتخصيص الحقول:", 
            ["مقال في مجلة علمية", "مداخلة في مؤتمر", "تأليف كتاب", "فصل في كتاب", "براءة اختراع", "تأطير مذكرة", "مشروع بحث"]
        )
        st.markdown("---")
        
        if 'form_id' not in st.session_state: st.session_state['form_id'] = 0
        
        with st.form(key=f"work_form_{st.session_state['form_id']}"):
            col_main1, col_main2 = st.columns([3, 1])
            with col_main1: w_title = st.text_input("العنوان الكامل للعمل *")
            with col_main2: w_date = st.date_input("تاريخ النشر *")
            w_lang = st.selectbox("اللغة", ["العربية", "الإنجليزية", "الفرنسية"])

            st.markdown(f"**تفاصيل: {w_type}**")
            details_data = {"language": w_lang}
            w_class, w_points = "غير مصنف", 10

            if w_type == "مقال في مجلة علمية":
                c1, c2 = st.columns(2)
                with c1:
                    journal = st.text_input("اسم المجلة")
                    issn = st.text_input("ISSN")
                    url_link = st.text_input("رابط المقال")
                with c2:
                    w_class = st.selectbox("تصنيف المجلة", ["A", "B", "C", "Q1", "Q2", "Q3", "Q4", "غير مصنف"])
                    indexing = st.multiselect("الفهرسة", ["ASJP", "Scopus", "Web of Science"])
                    vol_issue = st.text_input("المجلد/العدد")
                details_data.update({"journal": journal, "issn": issn, "indexing": indexing, "volume_issue": vol_issue, "url": url_link})
                if w_class in ["A", "Q1"]: w_points = 100
                elif w_class in ["B", "Q2"]: w_points = 75
                elif w_class == "C": w_points = 50
                else: w_points = 25

            elif w_type == "مداخلة في مؤتمر":
                c1, c2 = st.columns(2)
                with c1:
                    conf_name = st.text_input("اسم الملتقى")
                    organizer = st.text_input("الجهة المنظمة")
                with c2:
                    scope = st.selectbox("النطاق", ["وطني", "دولي"])
                    location = st.text_input("المكان")
                details_data.update({"conference": conf_name, "organizer": organizer, "scope": scope, "location": location})
                w_class = scope
                w_points = 50 if scope == "دولي" else 25

            elif w_type in ["تأليف كتاب", "فصل في كتاب"]:
                c1, c2 = st.columns(2)
                with c1:
                    publisher = st.text_input("دار النشر")
                    isbn = st.text_input("ISBN")
                with c2:
                    pages = st.text_input("عدد الصفحات")
                details_data.update({"publisher": publisher, "isbn": isbn, "pages": pages})
                w_points = 80 if w_type == "تأليف كتاب" else 40

            st.markdown("---")
            if st.form_submit_button("💾 حفظ البيانات"):
                if w_title:
                    json_details = json.dumps(details_data, ensure_ascii=False)
                    with st.spinner("جاري الحفظ..."):
                        if add_work_service(user['id'], w_title, json_details, w_type, w_class, w_date, w_points):
                            st.toast("✅ تم الحفظ!", icon="🎉")
                            time.sleep(1); st.session_state['form_id'] += 1; st.rerun()
                        else: st.toast("خطأ", icon="🚨")
                else: st.toast("أدخل العنوان", icon="⚠️")

    # ============================================
    #  باقي الصفحات
    # ============================================
    elif selection == "أعمالي":
        st.title("📂 سجل أعمالي")
        try:
            query = f"SELECT * FROM works WHERE user_id = {user['id']} ORDER BY publication_date DESC"
            my_df = pd.read_sql(query, engine)
            if not my_df.empty: st.dataframe(my_df[['title', 'activity_type', 'publication_date', 'points']], use_container_width=True)
            else: st.info("لا توجد أعمال.")
        except: pass

    elif selection == "الملف الشخصي":
        st.title("👤 الملف الشخصي")
        with st.container(border=True):
            st.subheader(user['name'])
            st.write(f"**الرتبة:** {user['role']}")
            st.write(f"**الفرقة:** {user['team']}")

    elif selection == "الإعدادات":
        st.title("⚙️ الإعدادات")
        with st.form("pwd"):
            p1 = st.text_input("كلمة المرور الجديدة", type="password")
            if st.form_submit_button("تغيير"):
                if change_password(user['id'], p1): st.success("تم!")

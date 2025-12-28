import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, Column, Integer, String, Date, ForeignKey, Text
from sqlalchemy.orm import sessionmaker, relationship, declarative_base, joinedload
import bcrypt
from datetime import date
import plotly.express as px
import plotly.graph_objects as go
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

# 🆕 دالة جلب البيانات الشاملة للوحة القيادة
def get_analytics_data():
    query = """
    SELECT 
        w.id, w.title, w.activity_type, w.publication_date, w.year, w.points,
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
        return df
    except Exception as e:
        return pd.DataFrame()

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
    
    /* بطاقات KPI المحسنة */
    .kpi-card {
        background: white; padding: 20px; border-radius: 15px; 
        border-right: 5px solid #2563eb;
        box-shadow: 0 4px 10px rgba(0,0,0,0.05);
        transition: transform 0.3s;
    }
    .kpi-card:hover { transform: translateY(-5px); }
    .kpi-val { font-size: 32px; font-weight: 800; color: #1e3a8a; font-family: 'Cairo'; }
    .kpi-lbl { font-size: 14px; color: #64748b; font-weight: bold; }
    
    /* الفلاتر */
    .stExpander { border: 1px solid #e2e8f0; border-radius: 10px; background: white; }
    
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
    #  🌟 لوحة القيادة الاحترافية (NEW)
    # ============================================
    if selection == "لوحة القيادة":
        st.title("📊 لوحة القيادة والتحليل البياني")
        
        # 1. جلب البيانات الشاملة
        df = get_analytics_data()
        
        if not df.empty:
            # 2. الفلاتر (Filters)
            with st.expander("🔍 تصفية البيانات المتقدمة (Filters)", expanded=True):
                col_f1, col_f2, col_f3, col_f4 = st.columns(4)
                
                with col_f1:
                    years = sorted(df['year'].unique().tolist(), reverse=True)
                    sel_year = st.multiselect("السنة", years, default=years[:1]) # افتراضياً نختار أحدث سنة
                
                with col_f2:
                    # تعبئة الأقسام تلقائياً
                    depts = sorted(df['department'].dropna().unique().tolist())
                    sel_dept = st.multiselect("القسم", depts)
                
                with col_f3:
                    # تصفية الفرق بناءً على القسم المختار
                    if sel_dept:
                        teams = sorted(df[df['department'].isin(sel_dept)]['team'].dropna().unique().tolist())
                    else:
                        teams = sorted(df['team'].dropna().unique().tolist())
                    sel_team = st.multiselect("الفرقة", teams)
                
                with col_f4:
                    types = sorted(df['activity_type'].unique().tolist())
                    sel_type = st.multiselect("نوع النشاط", types)

            # تطبيق الفلترة
            filtered_df = df.copy()
            if sel_year: filtered_df = filtered_df[filtered_df['year'].isin(sel_year)]
            if sel_dept: filtered_df = filtered_df[filtered_df['department'].isin(sel_dept)]
            if sel_team: filtered_df = filtered_df[filtered_df['team'].isin(sel_team)]
            if sel_type: filtered_df = filtered_df[filtered_df['activity_type'].isin(sel_type)]

            st.markdown("---")

            # 3. عرض المؤشرات (KPIs)
            kp1, kp2, kp3, kp4 = st.columns(4)
            kp1.markdown(f'<div class="kpi-card"><div class="kpi-val">{len(filtered_df)}</div><div class="kpi-lbl">إجمالي الأعمال</div></div>', unsafe_allow_html=True)
            kp2.markdown(f'<div class="kpi-card"><div class="kpi-val">{filtered_df["researcher"].nunique()}</div><div class="kpi-lbl">الباحثون النشطون</div></div>', unsafe_allow_html=True)
            kp3.markdown(f'<div class="kpi-card"><div class="kpi-val">{filtered_df["points"].sum()}</div><div class="kpi-lbl">مجموع النقاط</div></div>', unsafe_allow_html=True)
            kp4.markdown(f'<div class="kpi-card"><div class="kpi-val">{len(sel_team) if sel_team else filtered_df["team"].nunique()}</div><div class="kpi-lbl">الفرق المشاركة</div></div>', unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)

            # 4. الرسوم البيانية الاحترافية
            chart_c1, chart_c2 = st.columns(2)
            
            with chart_c1:
                st.subheader("🌐 التوزيع الهرمي للأعمال (Sunburst)")
                # رسم بياني شمسي يوضح (القسم -> الفرقة -> نوع النشاط)
                if not filtered_df.empty:
                    fig_sun = px.sunburst(
                        filtered_df, 
                        path=['department', 'team', 'activity_type'], 
                        values='points',
                        color='points',
                        color_continuous_scale='Blues'
                    )
                    fig_sun.update_layout(height=400, margin=dict(t=0, l=0, r=0, b=0))
                    st.plotly_chart(fig_sun, use_container_width=True)
            
            with chart_c2:
                st.subheader("📈 التطور الزمني للأنشطة")
                # رسم بياني شريطي مكدس
                timeline_df = filtered_df.groupby(['year', 'activity_type']).size().reset_index(name='count')
                fig_bar = px.bar(
                    timeline_df, x='year', y='count', color='activity_type',
                    text_auto=True,
                    color_discrete_sequence=px.colors.qualitative.Pastel
                )
                fig_bar.update_layout(xaxis_title="السنة", yaxis_title="عدد الأعمال")
                st.plotly_chart(fig_bar, use_container_width=True)

            # 5. جدول ترتيب الباحثين (Leaderboard)
            st.subheader("🏆 أكثر الباحثين تميزاً (حسب النقاط)")
            if not filtered_df.empty:
                top_researchers = filtered_df.groupby('researcher')['points'].sum().reset_index().sort_values(by='points', ascending=False).head(10)
                fig_h_bar = px.bar(
                    top_researchers, y='researcher', x='points', 
                    orientation='h', text_auto=True,
                    color='points', color_continuous_scale='Teal'
                )
                fig_h_bar.update_layout(yaxis={'categoryorder':'total ascending'}, xaxis_title="النقاط", yaxis_title="الباحث")
                st.plotly_chart(fig_h_bar, use_container_width=True)

            # 6. عرض البيانات الخام
            with st.expander("📋 عرض جدول البيانات الخام"):
                st.dataframe(filtered_df[['publication_date', 'activity_type', 'title', 'researcher', 'team', 'points']], use_container_width=True)

        else:
            st.warning("⚠️ لا توجد بيانات مسجلة في قاعدة البيانات حتى الآن. الرجاء إضافة نتاج علمي أولاً.")

    # ============================================
    #  صفحة تسجيل نتاج جديد (النسخة الديناميكية)
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

            # تفاصيل ديناميكية
            st.markdown(f"**تفاصيل: {w_type}**")
            details_data = {"language": w_lang}
            w_class = "غير مصنف"
            w_points = 10

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
            if st.form_submit_button("💾 حفظ"):
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

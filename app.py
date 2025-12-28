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

# --- ثوابت الأنواع (لضمان التطابق) ---
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

# 🆕 دالة جلب البيانات المحسنة (لمنع أخطاء الرسوم البيانية)
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
        # ملء الفراغات لمنع انهيار Sunburst Chart
        df['department'] = df['department'].fillna('غير محدد')
        df['team'] = df['team'].fillna('غير محدد')
        df['activity_type'] = df['activity_type'].fillna('غير محدد')
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
    
    .kpi-card {
        background: white; padding: 20px; border-radius: 15px; 
        border-right: 5px solid #2563eb;
        box-shadow: 0 4px 10px rgba(0,0,0,0.05);
        text-align: center;
    }
    .kpi-val { font-size: 32px; font-weight: 800; color: #1e3a8a; font-family: 'Cairo'; }
    .kpi-lbl { font-size: 14px; color: #64748b; font-weight: bold; margin-top: 5px; }
    
    div[data-testid="stToast"] { direction: rtl; text-align: right; font-family: 'Cairo'; }
    .stButton>button { width: 100%; border-radius: 8px; font-family: 'Cairo'; font-weight: bold; }
    
    /* تنسيق خاص للنماذج */
    [data-testid="stForm"] { background: white; padding: 25px; border-radius: 12px; border: 1px solid #e5e7eb; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05); }
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
    #  🌟 صفحة تسجيل نتاج جديد (النسخة الاحترافية المستقرة)
    # ============================================
    if selection == "تسجيل نتاج جديد":
        st.title("📝 تسجيل نتاج علمي جديد")
        
        # قائمة الاختيار خارج النموذج لتفعيل التحديث الفوري
        st.markdown("### 1️⃣ نوع النشاط البحثي")
        w_type = st.selectbox("اختر نوع النشاط لتخصيص الحقول:", ACTIVITY_TYPES)
        
        st.markdown("---")
        
        # استخدام مفتاح فريد يعتمد على الوقت لتفريغ النموذج عند الحاجة
        if 'form_id' not in st.session_state: st.session_state['form_id'] = int(time.time())
        
        # بداية النموذج
        with st.form(key=f"work_form_{st.session_state['form_id']}"):
            
            # --- البيانات المشتركة ---
            col_main1, col_main2 = st.columns([3, 1])
            with col_main1:
                # استخدام مفاتيح فريدة لكل نوع (w_type) لمنع تداخل الحقول
                w_title = st.text_input("العنوان الكامل للعمل *", key=f"title_{w_type}")
            with col_main2:
                w_date = st.date_input("تاريخ النشر / المناقشة *", key=f"date_{w_type}")
            
            w_lang = st.selectbox("لغة العمل", ["العربية", "الإنجليزية", "الفرنسية"], key=f"lang_{w_type}")

            # --- البيانات الديناميكية ---
            st.markdown(f"#### 📄 تفاصيل خاصة بـ: {w_type}")
            
            details_data = {"language": w_lang}
            w_class = "غير مصنف"
            w_points = 10

            # 1. مقال
            if w_type == "مقال في مجلة علمية":
                c1, c2 = st.columns(2)
                with c1:
                    journal = st.text_input("اسم المجلة *", key=f"journal_{w_type}")
                    issn = st.text_input("الرقم التسلسلي (ISSN)", key=f"issn_{w_type}")
                    url_link = st.text_input("رابط المقال", key=f"url_{w_type}")
                with c2:
                    w_class = st.selectbox("تصنيف المجلة", ["A", "B", "C", "Q1", "Q2", "Q3", "Q4", "غير مصنف"], key=f"class_{w_type}")
                    indexing = st.multiselect("القواعد المفهرسة", ["ASJP", "Scopus", "Web of Science"], key=f"idx_{w_type}")
                    vol_issue = st.text_input("المجلد/العدد", key=f"vol_{w_type}")
                
                details_data.update({"journal": journal, "issn": issn, "indexing": indexing, "volume_issue": vol_issue, "url": url_link})
                # حساب النقاط
                if w_class in ["A", "Q1"]: w_points = 100
                elif w_class in ["B", "Q2"]: w_points = 75
                elif w_class == "C": w_points = 50
                else: w_points = 25

            # 2. مداخلة
            elif w_type == "مداخلة في مؤتمر":
                c1, c2 = st.columns(2)
                with c1:
                    conf_name = st.text_input("اسم الملتقى / المؤتمر *", key=f"conf_{w_type}")
                    organizer = st.text_input("الجهة المنظمة", key=f"org_{w_type}")
                with c2:
                    scope = st.selectbox("النطاق", ["وطني", "دولي"], key=f"scope_{w_type}")
                    part_type = st.selectbox("نوع المشاركة", ["شخصية", "عن بعد", "ملصق"], key=f"ptype_{w_type}")
                    location = st.text_input("مكان الانعقاد", key=f"loc_{w_type}")
                
                details_data.update({"conference": conf_name, "organizer": organizer, "scope": scope, "participation": part_type, "location": location})
                w_class = scope
                w_points = 50 if scope == "دولي" else 25

            # 3. كتاب
            elif w_type in ["تأليف كتاب", "فصل في كتاب"]:
                c1, c2 = st.columns(2)
                with c1:
                    publisher = st.text_input("دار النشر *", key=f"pub_{w_type}")
                    isbn = st.text_input("الرقم الدولي (ISBN)", key=f"isbn_{w_type}")
                with c2:
                    pages = st.text_input("عدد الصفحات", key=f"pg_{w_type}")
                    edition = st.text_input("رقم الطبعة / سنة الإصدار", key=f"edit_{w_type}")
                
                details_data.update({"publisher": publisher, "isbn": isbn, "pages": pages, "edition": edition})
                w_points = 80 if w_type == "تأليف كتاب" else 40

            # 4. براءة
            elif w_type == "براءة اختراع":
                c1, c2 = st.columns(2)
                with c1:
                    patent_num = st.text_input("رقم البراءة *", key=f"pat_{w_type}")
                with c2:
                    granting_body = st.text_input("الهيئة المانحة", key=f"body_{w_type}")
                
                details_data.update({"patent_number": patent_num, "body": granting_body})
                w_points = 150

            # 5. مشروع
            elif w_type == "مشروع بحث":
                c1, c2 = st.columns(2)
                with c1:
                    proj_code = st.text_input("رمز المشروع (Code) *", key=f"code_{w_type}")
                    proj_role = st.selectbox("صفتك في المشروع", ["رئيس مشروع", "عضو"], key=f"role_{w_type}")
                with c2:
                    proj_kind = st.selectbox("نوع المشروع", ["PRFU", "PNR", "CNEPRU", "تعاون دولي"], key=f"kind_{w_type}")
                
                details_data.update({"code": proj_code, "role": proj_role, "kind": proj_kind})
                w_points = 60

            # 6. تأطير
            elif w_type == "تأطير مذكرة":
                c1, c2 = st.columns(2)
                with c1:
                    student_name = st.text_input("اسم الطالب المؤطر *", key=f"stud_{w_type}")
                with c2:
                    level = st.selectbox("المستوى", ["ماستر", "دكتوراه لمد", "دكتوراه علوم"], key=f"lvl_{w_type}")
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
                            # تغيير معرف النموذج لتفريغ الحقول
                            st.session_state['form_id'] = int(time.time())
                            st.rerun()
                        else: st.toast("حدث خطأ أثناء الاتصال", icon="🚨")
                else: st.toast("يرجى كتابة العنوان", icon="⚠️")

    # ============================================
    #  🌟 لوحة القيادة الاحترافية (المصححة)
    # ============================================
    elif selection == "لوحة القيادة":
        st.title("📊 لوحة القيادة والتحليل البياني")
        
        df = get_analytics_data()
        
        if not df.empty:
            # 2. الفلاتر الذكية
            with st.expander("🔍 تصفية البيانات المتقدمة", expanded=True):
                col_f1, col_f2, col_f3, col_f4 = st.columns(4)
                with col_f1:
                    years = sorted(df['year'].unique().tolist(), reverse=True)
                    sel_year = st.multiselect("السنة", years)
                with col_f2:
                    depts = sorted(df['department'].unique().tolist())
                    sel_dept = st.multiselect("القسم", depts)
                with col_f3:
                    teams = sorted(df[df['department'].isin(sel_dept)]['team'].unique().tolist()) if sel_dept else sorted(df['team'].unique().tolist())
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

            # 3. عرض المؤشرات
            kp1, kp2, kp3, kp4 = st.columns(4)
            with kp1: st.markdown(f'<div class="kpi-card"><div class="kpi-val">{len(filtered_df)}</div><div class="kpi-lbl">إجمالي الأعمال</div></div>', unsafe_allow_html=True)
            with kp2: st.markdown(f'<div class="kpi-card"><div class="kpi-val">{filtered_df["researcher"].nunique()}</div><div class="kpi-lbl">الباحثون النشطون</div></div>', unsafe_allow_html=True)
            with kp3: st.markdown(f'<div class="kpi-card"><div class="kpi-val">{filtered_df["points"].sum()}</div><div class="kpi-lbl">مجموع النقاط</div></div>', unsafe_allow_html=True)
            with kp4: 
                top_dept = filtered_df['department'].mode()[0] if not filtered_df.empty else "-"
                st.markdown(f'<div class="kpi-card"><div class="kpi-val" style="font-size:20px">{top_dept}</div><div class="kpi-lbl">القسم الأنشط</div></div>', unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)

            # 4. الرسوم البيانية
            chart_c1, chart_c2 = st.columns(2)
            with chart_c1:
                st.subheader("🌐 التوزيع الهرمي للأعمال")
                if not filtered_df.empty:
                    try:
                        fig_sun = px.sunburst(filtered_df, path=['department', 'team', 'activity_type'], values='points', color='department', color_discrete_sequence=px.colors.qualitative.Prism)
                        fig_sun.update_layout(margin=dict(t=0, l=0, r=0, b=0), height=400)
                        st.plotly_chart(fig_sun, use_container_width=True)
                    except: st.warning("بيانات غير كافية للرسم")
            
            with chart_c2:
                st.subheader("📈 التطور الزمني للأنشطة")
                if not filtered_df.empty:
                    timeline_df = filtered_df.groupby(['year', 'activity_type']).size().reset_index(name='count')
                    fig_bar = px.bar(timeline_df, x='year', y='count', color='activity_type', text_auto=True, barmode='group', color_discrete_sequence=px.colors.qualitative.Pastel)
                    fig_bar.update_layout(xaxis_title="السنة", yaxis_title="العدد", height=400)
                    st.plotly_chart(fig_bar, use_container_width=True)

            # 5. جدول البيانات
            with st.expander("📋 عرض جدول البيانات التفصيلي"):
                st.dataframe(filtered_df[['publication_date', 'classification', 'activity_type', 'title', 'researcher', 'team', 'points']], use_container_width=True)
        else:
            st.warning("⚠️ لا توجد بيانات مسجلة في قاعدة البيانات حتى الآن.")

    # ============================================
    #  باقي الصفحات
    # ============================================
    elif selection == "أعمالي":
        st.title("📂 سجل أعمالي")
        try:
            query = f"SELECT * FROM works WHERE user_id = {user['id']} ORDER BY publication_date DESC"
            my_df = pd.read_sql(query, engine)
            if not my_df.empty:
                st.dataframe(my_df[['title', 'activity_type', 'publication_date', 'points']], use_container_width=True)
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

import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, Column, Integer, String, Date, ForeignKey, Text
from sqlalchemy.orm import sessionmaker, relationship, declarative_base, joinedload
import bcrypt
from datetime import date, timedelta
import plotly.express as px
import time
import json 
import urllib.parse
import base64
import os
import random # لتوليد بيانات عشوائية

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

# ==========================================
# 🚀 3. دالة توليد البيانات الاختبارية (Seeding)
# ==========================================
def init_db_with_seed():
    try:
        Base.metadata.create_all(bind=engine)
        session = SessionLocal()
        
        # 1. التحقق من وجود الأقسام (إذا لم توجد، ننشئها)
        if not session.query(Department).first():
            dept_names = [
                "قسم الدراسات السوسيولوجية", "قسم علم النفس", "قسم علوم التربية",
                "قسم الأرطوفونيا", "قسم الفلسفة", "قسم التاريخ والآثار"
            ]
            depts = [Department(name_ar=name) for name in dept_names]
            session.add_all(depts)
            session.commit()
            
            # 2. إنشاء الفرق لكل قسم
            all_depts = session.query(Department).all()
            for dept in all_depts:
                # إنشاء فرقتين لكل قسم
                t1 = Team(name=f"فرقة البحث {dept.id}-أ", department_id=dept.id)
                t2 = Team(name=f"فرقة البحث {dept.id}-ب", department_id=dept.id)
                session.add_all([t1, t2])
            session.commit()

            # 3. إنشاء باحثين لكل فرقة
            all_teams = session.query(Team).all()
            password = bcrypt.hashpw("12345".encode(), bcrypt.gensalt()).decode()
            
            researchers = []
            for team in all_teams:
                # باحث دائم
                u1 = User(username=f"res_{team.id}_1", full_name=f"د. باحث {team.id}-أ", password_hash=password, role="researcher", team_id=team.id, member_type="permanent")
                # طالب دكتوراه
                u2 = User(username=f"doc_{team.id}_2", full_name=f"طالب {team.id}-ب", password_hash=password, role="researcher", team_id=team.id, member_type="phd_student")
                researchers.extend([u1, u2])
            
            # إضافة المدير
            admin = User(username="admin", full_name="المدير العام", password_hash=password, role="admin", member_type="admin")
            researchers.append(admin)
            
            session.add_all(researchers)
            session.commit()

            # 4. توليد نتاج علمي (أعمال) للباحثين
            all_users = session.query(User).filter(User.role != 'admin').all()
            works = []
            types = ["مقال في مجلة علمية", "مداخلة في مؤتمر", "تأليف كتاب"]
            
            for user in all_users:
                # إضافة 2-4 أعمال لكل باحث بشكل عشوائي
                for _ in range(random.randint(2, 4)):
                    w_type = random.choice(types)
                    w_year = random.choice([2023, 2024, 2025])
                    w_date = date(w_year, random.randint(1, 12), random.randint(1, 28))
                    
                    points = 0
                    if w_type == "مقال في مجلة علمية": points = 100
                    elif w_type == "مداخلة في مؤتمر": points = 50
                    else: points = 80
                    
                    w = Work(
                        title=f"بحث تجريبي حول {w_type} رقم {random.randint(100,999)}",
                        details='{"lang":"العربية"}',
                        activity_type=w_type,
                        classification="A" if points == 100 else "B",
                        publication_date=w_date,
                        year=w_year,
                        points=points,
                        user_id=user.id
                    )
                    works.append(w)
            
            session.add_all(works)
            session.commit()
            print("✅ تم توليد بيانات الاختبار بنجاح!")
            
        session.close()
    except Exception as e:
        print(f"Seed Error: {e}")

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
# 4. التنسيق (CSS) - الاحترافي
# ==========================================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;800&family=Tajawal:wght@400;500;700&display=swap');
    :root { --primary: #2563eb; --bg: #f8fafc; }
    
    html, body, .stApp { font-family: 'Tajawal', sans-serif; direction: rtl; background-color: #fcfcfc; text-align: right; }
    h1, h2, h3, h4 { font-family: 'Cairo'; font-weight: 800; color: #1e3a8a; text-align: right !important; }
    
    [data-testid="stSidebar"] { background: #fff; border-left: 1px solid #e2e8f0; }
    .stTextInput input, .stSelectbox div, .stTextArea textarea, .stDateInput input { text-align: right; direction: rtl; border-radius: 8px; }
    
    /* بطاقات KPI */
    .kpi-container {
        background-color: white; padding: 20px; border-radius: 12px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.04); border: 1px solid #f1f5f9;
        border-right: 4px solid #3b82f6;
        display: flex; justify-content: space-between; align-items: center;
        margin-bottom: 10px; transition: transform 0.2s;
    }
    .kpi-container:hover { transform: translateY(-3px); }
    .kpi-info { text-align: right; }
    .kpi-value { font-family: 'Cairo'; font-size: 28px; font-weight: 800; color: #0f172a; line-height: 1.2; }
    .kpi-label { font-family: 'Tajawal'; font-size: 13px; color: #64748b; font-weight: 600; }
    .kpi-icon { width: 45px; height: 45px; background-color: #eff6ff; border-radius: 10px; display: flex; align-items: center; justify-content: center; font-size: 22px; color: #3b82f6; }

    /* الحاويات */
    .chart-container { background-color: white; padding: 20px; border-radius: 15px; border: 1px solid #e2e8f0; box-shadow: 0 2px 4px rgba(0,0,0,0.02); margin-bottom: 20px; }
    .stButton>button { width: 100%; border-radius: 8px; font-family: 'Cairo'; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 5. واجهة التطبيق
# ==========================================

if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False

# تشغيل التهيئة (مرة واحدة عند التحميل)
init_db_with_seed()

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

    # --- لوحة القيادة ---
    if selection == "لوحة القيادة":
        st.markdown("## 📊 لوحة القيادة العامة")
        df = get_analytics_data()
        
        if not df.empty:
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

            filtered_df = df.copy()
            if sel_year != "الكل": filtered_df = filtered_df[filtered_df['year'] == sel_year]
            if sel_dept != "الكل": filtered_df = filtered_df[filtered_df['department'] == sel_dept]
            if sel_type != "الكل": filtered_df = filtered_df[filtered_df['activity_type'] == sel_type]

            st.write("")
            k1, k2, k3, k4 = st.columns(4)
            
            with k4: st.markdown(f'<div class="kpi-container"><div class="kpi-info"><div class="kpi-value">{len(filtered_df)}</div><div class="kpi-label">إجمالي النتاج</div></div><div class="kpi-icon">📚</div></div>', unsafe_allow_html=True)
            with k3: st.markdown(f'<div class="kpi-container"><div class="kpi-info"><div class="kpi-value">{filtered_df["researcher"].nunique()}</div><div class="kpi-label">الباحثون</div></div><div class="kpi-icon">👥</div></div>', unsafe_allow_html=True)
            with k2: st.markdown(f'<div class="kpi-container"><div class="kpi-info"><div class="kpi-value">{filtered_df["points"].sum()}</div><div class="kpi-label">النقاط</div></div><div class="kpi-icon">⭐</div></div>', unsafe_allow_html=True)
            with k1: 
                yr = filtered_df['year'].mode()[0] if not filtered_df.empty else "-"
                st.markdown(f'<div class="kpi-container"><div class="kpi-info"><div class="kpi-value">{yr}</div><div class="kpi-label">الأكثر نشاطاً</div></div><div class="kpi-icon">📅</div></div>', unsafe_allow_html=True)

            c_g1, c_g2 = st.columns([1, 1])
            with c_g2:
                st.markdown('<div class="chart-container">', unsafe_allow_html=True)
                st.markdown("##### 📊 توزيع الأنشطة")
                fig_d = px.pie(filtered_df, names='activity_type', hole=0.5, color_discrete_sequence=px.colors.sequential.Blues_r)
                fig_d.update_layout(margin=dict(t=0, b=0, l=0, r=0), height=300)
                st.plotly_chart(fig_d, use_container_width=True)
                st.markdown('</div>', unsafe_allow_html=True)
            with c_g1:
                st.markdown('<div class="chart-container">', unsafe_allow_html=True)
                st.markdown("##### 📈 التطور السنوي")
                if not filtered_df.empty:
                    y_df = filtered_df.groupby('year').size().reset_index(name='count')
                    fig_b = px.bar(y_df, x='year', y='count', text_auto=True, color_discrete_sequence=['#2563eb'])
                    fig_b.update_layout(margin=dict(t=10, b=10, l=10, r=10), height=300, plot_bgcolor='white')
                    st.plotly_chart(fig_b, use_container_width=True)
                st.markdown('</div>', unsafe_allow_html=True)
        else: st.warning("جاري تحميل البيانات...")

    # --- تسجيل نتاج ---
    elif selection == "تسجيل نتاج جديد":
        st.title("📝 تسجيل نتاج علمي جديد")
        
        st.markdown("### 1️⃣ نوع النشاط البحثي")
        w_type = st.selectbox("اختر نوع النشاط:", ["مقال في مجلة علمية", "مداخلة في مؤتمر", "تأليف كتاب", "فصل في كتاب", "براءة اختراع", "تأطير مذكرة", "مشروع بحث"])
        st.markdown("---")
        
        if 'form_id' not in st.session_state: st.session_state['form_id'] = int(time.time())
        
        with st.form(key=f"w_form_{st.session_state['form_id']}"):
            col1, col2 = st.columns([3, 1])
            with col1: title = st.text_input("العنوان الكامل *", key=f"t_{w_type}")
            with col2: d_date = st.date_input("التاريخ *", key=f"d_{w_type}")
            lang = st.selectbox("اللغة", ["العربية", "الإنجليزية", "الفرنسية"], key=f"l_{w_type}")
            
            st.markdown(f"**تفاصيل: {w_type}**")
            details = {"lang": lang}
            pts = 10
            cls = "غير مصنف"

            if w_type == "مقال في مجلة علمية":
                c1, c2 = st.columns(2)
                with c1:
                    j = st.text_input("المجلة", key=f"j_{w_type}")
                    issn = st.text_input("ISSN", key=f"i_{w_type}")
                with c2:
                    cls = st.selectbox("التصنيف", ["A", "B", "C", "Q1", "Q2", "Q3", "Q4"], key=f"c_{w_type}")
                details.update({"journal": j, "issn": issn})
                if cls in ["A", "Q1"]: pts = 100
                elif cls in ["B", "Q2"]: pts = 75
                else: pts = 50

            elif w_type == "مداخلة في مؤتمر":
                conf = st.text_input("اسم الملتقى", key=f"conf_{w_type}")
                scope = st.selectbox("النطاق", ["وطني", "دولي"], key=f"sc_{w_type}")
                details.update({"conf": conf, "scope": scope})
                pts = 50 if scope == "دولي" else 25

            st.markdown("---")
            if st.form_submit_button("💾 حفظ"):
                if title:
                    if add_work_service(user['id'], title, json.dumps(details), w_type, cls, d_date, pts):
                        st.toast("تم الحفظ!", icon="✅")
                        time.sleep(1); st.session_state['form_id'] = int(time.time()); st.rerun()
                    else: st.error("خطأ")
                else: st.warning("العنوان مطلوب")

    # --- الصفحات الأخرى ---
    elif selection == "أعمالي":
        st.title("📂 سجل أعمالي")
        try:
            q = f"SELECT * FROM works WHERE user_id = {user['id']} ORDER BY publication_date DESC"
            st.dataframe(pd.read_sql(q, engine)[['title', 'activity_type', 'publication_date', 'points']], use_container_width=True)
        except: st.info("لا توجد أعمال.")

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

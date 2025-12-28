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
import random

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

# --- النماذج (Tables) - محدثة للصلاحيات الهرمية ---
class Department(Base):
    __tablename__ = "departments"
    id = Column(Integer, primary_key=True)
    name_ar = Column(String)
    teams = relationship("Team", back_populates="department")
    users = relationship("User", back_populates="department") # للعلاقة مع رئيس القسم

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
    
    # ربط المستخدم بفرقة (للباحث ورئيس الفرقة)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=True)
    team = relationship("Team", back_populates="members")
    
    # ربط المستخدم بقسم (لرئيس القسم)
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
# 🚀 3. دالة التهيئة الذكية (إعادة بناء)
# ==========================================
def init_db_structured():
    try:
        # ملاحظة: في البيئة الحقيقية لا نستخدم drop_all إلا عند التأسيس
        # هنا نستخدمها لضمان تطبيق التغييرات الهيكلية الجديدة
        Base.metadata.drop_all(bind=engine) 
        Base.metadata.create_all(bind=engine)
        
        session = SessionLocal()
        
        # 1. إنشاء الأقسام
        dept_names = ["الدراسات السوسيولوجية", "علم النفس", "علوم التربية", "الأرطوفونيا", "الفلسفة", "التاريخ"]
        depts_objs = []
        for name in dept_names:
            d = Department(name_ar=name)
            session.add(d)
            depts_objs.append(d)
        session.commit()
        
        # 2. إنشاء الفرق (2 لكل قسم)
        teams_objs = []
        for dept in depts_objs:
            t1 = Team(name=f"فرقة {dept.name_ar} (أ)", department_id=dept.id)
            t2 = Team(name=f"فرقة {dept.name_ar} (ب)", department_id=dept.id)
            session.add_all([t1, t2])
            teams_objs.extend([t1, t2])
        session.commit()

        # 3. إنشاء الحسابات القيادية (كلمة السر الموحدة: 12345)
        pw = bcrypt.hashpw("12345".encode(), bcrypt.gensalt()).decode()
        
        # أ. مدير المخبر (Admin)
        admin = User(username="admin", full_name="المدير العام", password_hash=pw, role="admin", member_type="admin")
        session.add(admin)

        # ب. رؤساء الأقسام (Dept Heads)
        for dept in depts_objs:
            head = User(
                username=f"head_{dept.id}", 
                full_name=f"رئيس قسم {dept.name_ar}", 
                password_hash=pw, 
                role="dept_head", 
                department_id=dept.id, # ربط بالقسم مباشرة
                member_type="permanent"
            )
            session.add(head)

        # ج. رؤساء الفرق (Team Leaders)
        for team in teams_objs:
            leader = User(
                username=f"leader_{team.id}",
                full_name=f"رئيس {team.name}",
                password_hash=pw,
                role="leader",
                team_id=team.id,
                department_id=team.department_id, # يرث القسم
                member_type="permanent"
            )
            session.add(leader)
            
            # د. باحثين عاديين (Researchers)
            res = User(
                username=f"res_{team.id}",
                full_name=f"باحث في {team.name}",
                password_hash=pw,
                role="researcher",
                team_id=team.id,
                department_id=team.department_id,
                member_type="phd_student"
            )
            session.add(res)
            
            # إضافة نتاج علمي للباحث ولرئيس الفرقة
            for u in [leader, res]:
                for _ in range(3):
                    w = Work(
                        title=f"بحث تجريبي {random.randint(100,999)}",
                        details='{"lang":"العربية"}',
                        activity_type=random.choice(["مقال في مجلة علمية", "مداخلة في مؤتمر"]),
                        classification="A",
                        publication_date=date(2024, random.randint(1,12), 1),
                        year=2024,
                        points=100,
                        user_id=u.id # سيتم تحديثه بعد الـ commit، لكن هنا نستخدم session.flush لو أردنا
                    )
                    # ملاحظة: في SQLAlchemy يجب إضافة المستخدم أولاً للحصول على ID
                    # لذا سنقوم بالحفظ الجزئي
        
        session.commit()
        
        # إضافة الأعمال الآن بعد أن حصل المستخدمون على IDs
        users = session.query(User).filter(User.role.in_(['leader', 'researcher'])).all()
        works = []
        for u in users:
            for _ in range(random.randint(2, 5)):
                w_type = random.choice(["مقال في مجلة علمية", "مداخلة في مؤتمر"])
                pts = 100 if w_type == "مقال في مجلة علمية" else 50
                works.append(Work(
                    title=f"نشاط علمي حول الموضوع {random.randint(1,50)}",
                    details='{"journal":"مجلة الباحث"}',
                    activity_type=w_type,
                    classification="A",
                    publication_date=date(2025, random.randint(1,5), random.randint(1,28)),
                    year=2025,
                    points=pts,
                    user_id=u.id
                ))
        session.add_all(works)
        session.commit()
        
        session.close()
        return True
    except Exception as e:
        print(e)
        return False

# --- الخدمات ---
def auth_user(u, p):
    s = SessionLocal()
    try:
        user = s.query(User).options(joinedload(User.team), joinedload(User.department)).filter(User.username == u).first()
        if user and bcrypt.checkpw(p.encode(), user.password_hash.encode()): return user
    except: pass
    finally: s.close()
    return None

def add_work_service(uid, title, details_json, atype, cls, date_obj, pts):
    s = SessionLocal()
    try:
        s.add(Work(user_id=uid, title=title, details=details_json, activity_type=atype, classification=cls, publication_date=date_obj, year=date_obj.year, points=pts))
        s.commit()
        return True
    except: s.rollback(); return False
    finally: s.close()

def delete_work_service(work_id):
    s = SessionLocal()
    try:
        s.query(Work).filter(Work.id == work_id).delete()
        s.commit()
        return True
    except: s.rollback(); return False
    finally: s.close()

def update_work_service(work_id, title, date_obj):
    s = SessionLocal()
    try:
        w = s.query(Work).filter(Work.id == work_id).first()
        w.title = title
        w.publication_date = date_obj
        w.year = date_obj.year
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

# 🆕 دالة جلب البيانات المفلترة حسب الصلاحية (The Core Logic)
def get_filtered_data(user_role, user_id, user_dept_id, user_team_id):
    base_query = """
    SELECT 
        w.id, w.title, w.activity_type, w.publication_date, w.year, w.points,
        u.full_name as researcher, 
        t.name as team, 
        d.name_ar as department,
        d.id as dept_id,
        t.id as team_id,
        u.id as user_id_val
    FROM works w
    JOIN users u ON w.user_id = u.id
    LEFT JOIN teams t ON u.team_id = t.id
    LEFT JOIN departments d ON t.department_id = d.id
    """
    
    df = pd.read_sql(base_query, engine)
    
    # 🛡️ تطبيق الصلاحيات
    if user_role == 'admin':
        return df # يرى كل شيء
    elif user_role == 'dept_head':
        return df[df['dept_id'] == user_dept_id] # يرى قسمه فقط
    elif user_role == 'leader':
        return df[df['team_id'] == user_team_id] # يرى فرقته فقط
    else:
        return df[df['user_id_val'] == user_id] # يرى نفسه فقط

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
                    st.session_state['user'] = {
                        'id': user.id, 'name': user.full_name, 'role': user.role, 
                        'team_id': user.team_id, 'dept_id': user.department_id,
                        'team_name': user.team.name if user.team else (user.department.name_ar if user.department else "الإدارة")
                    }
                    st.rerun()
                else: st.toast("بيانات خاطئة", icon="❌")
        
        with st.expander("🛠️ إعداد النظام (لأول مرة)"):
            if st.button("إعادة تهيئة قاعدة البيانات وإنشاء الحسابات"):
                with st.spinner("جاري بناء النظام..."):
                    if init_db_structured():
                        st.success("تم بنجاح! جرب الدخول بـ: admin / 12345")
                    else: st.error("فشل")

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
        
        # عرض معلومات المستخدم وصلاحيته
        role_labels = {"admin": "المدير العام", "dept_head": "رئيس قسم", "leader": "رئيس فرقة", "researcher": "باحث"}
        st.info(f"مرحباً: {user['name']}\n\nالصلاحية: {role_labels.get(user['role'], user['role'])}")
        
        menu = {
            "لوحة القيادة": "📊 لوحة القيادة",
            "إدارة الأنشطة": "🗂️ إدارة الأنشطة (تعديل/حذف)",
            "تسجيل نتاج جديد": "📝 تسجيل نتاج جديد",
            "أعمالي": "📂 سجل أعمالي",
            "الإعدادات": "⚙️ الإعدادات"
        }
        
        sel = st.sidebar.radio("القائمة", list(menu.values()), label_visibility="collapsed")
        selection = [k for k, v in menu.items() if v == sel][0]
        
        if st.button("تسجيل الخروج"):
            st.session_state['logged_in'] = False
            st.rerun()

    # ============================================
    #  🌟 1. لوحة القيادة (ذكية حسب الصلاحية)
    # ============================================
    if selection == "لوحة القيادة":
        st.markdown(f"## 📊 لوحة القيادة: {role_labels.get(user['role'], '')}")
        
        # جلب البيانات حسب الصلاحية
        df = get_filtered_data(user['role'], user['id'], user['dept_id'], user['team_id'])
        
        if not df.empty:
            # بطاقات الأداء
            k1, k2, k3, k4 = st.columns(4)
            with k4: st.markdown(f'<div class="kpi-container"><div class="kpi-info"><div class="kpi-value">{len(df)}</div><div class="kpi-label">إجمالي الأعمال</div></div><div class="kpi-icon">📚</div></div>', unsafe_allow_html=True)
            with k3: st.markdown(f'<div class="kpi-container"><div class="kpi-info"><div class="kpi-value">{df["researcher"].nunique()}</div><div class="kpi-label">الباحثون</div></div><div class="kpi-icon">👥</div></div>', unsafe_allow_html=True)
            with k2: st.markdown(f'<div class="kpi-container"><div class="kpi-info"><div class="kpi-value">{df["points"].sum()}</div><div class="kpi-label">النقاط</div></div><div class="kpi-icon">⭐</div></div>', unsafe_allow_html=True)
            with k1: 
                yr = df['year'].mode()[0] if not df.empty else "-"
                st.markdown(f'<div class="kpi-container"><div class="kpi-info"><div class="kpi-value">{yr}</div><div class="kpi-label">الأكثر نشاطاً</div></div><div class="kpi-icon">📅</div></div>', unsafe_allow_html=True)

            # الرسوم البيانية
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
        else: st.warning("لا توجد بيانات متاحة لعرضها ضمن صلاحياتك.")

    # ============================================
    #  🌟 2. إدارة الأنشطة (CRUD - تعديل وحذف)
    # ============================================
    elif selection == "إدارة الأنشطة":
        st.title("🗂️ إدارة الأنشطة البحثية")
        st.markdown("يمكنك هنا استعراض، تعديل، أو حذف الأنشطة التي تقع ضمن صلاحياتك.")
        
        # جلب البيانات حسب الصلاحية
        df = get_filtered_data(user['role'], user['id'], user['dept_id'], user['team_id'])
        
        if not df.empty:
            # عرض تفاعلي للبيانات
            for index, row in df.iterrows():
                with st.expander(f"{row['activity_type']}: {row['title']} | 👤 {row['researcher']}"):
                    c1, c2, c3 = st.columns([2, 1, 1])
                    with c1:
                        new_title = st.text_input("العنوان", value=row['title'], key=f"t_{row['id']}")
                    with c2:
                        # تحويل التاريخ من نص إلى كائن date
                        d_val = pd.to_datetime(row['publication_date']).date()
                        new_date = st.date_input("التاريخ", value=d_val, key=f"d_{row['id']}")
                    
                    with c3:
                        st.write("")
                        st.write("")
                        col_btn1, col_btn2 = st.columns(2)
                        with col_btn1:
                            if st.button("💾 تعديل", key=f"upd_{row['id']}", type="primary"):
                                if update_work_service(row['id'], new_title, new_date):
                                    st.toast("تم التعديل!", icon="✅")
                                    time.sleep(1)
                                    st.rerun()
                        with col_btn2:
                            if st.button("🗑️ حذف", key=f"del_{row['id']}"):
                                if delete_work_service(row['id']):
                                    st.toast("تم الحذف!", icon="🗑️")
                                    time.sleep(1)
                                    st.rerun()
        else:
            st.info("لا توجد أنشطة لإدارتها.")

    # --- تسجيل نتاج جديد ---
    elif selection == "تسجيل نتاج جديد":
        st.title("📝 تسجيل نتاج علمي جديد")
        w_type = st.selectbox("اختر نوع النشاط:", ["مقال في مجلة علمية", "مداخلة في مؤتمر", "تأليف كتاب", "مشروع بحث"])
        st.markdown("---")
        
        with st.form(key=f"add_form"):
            title = st.text_input("العنوان الكامل *")
            d_date = st.date_input("التاريخ *")
            lang = st.selectbox("اللغة", ["العربية", "الإنجليزية", "الفرنسية"])
            
            # تفاصيل مبسطة للمثال
            details = {"lang": lang}
            pts, cls = 10, "غير مصنف"
            
            if w_type == "مقال في مجلة علمية":
                j = st.text_input("المجلة")
                cls = st.selectbox("التصنيف", ["A", "B", "C"])
                if cls == "A": pts = 100
                elif cls == "B": pts = 75
                else: pts = 50
                details['journal'] = j
            
            if st.form_submit_button("💾 حفظ"):
                if title:
                    if add_work_service(user['id'], title, json.dumps(details), w_type, cls, d_date, pts):
                        st.toast("تم الحفظ!", icon="✅")
                        st.rerun()
                    else: st.error("خطأ")
                else: st.warning("العنوان مطلوب")

    # --- الصفحات الأخرى ---
    elif selection == "أعمالي":
        st.title("📂 سجل أعمالي")
        try:
            q = f"SELECT * FROM works WHERE user_id = {user['id']} ORDER BY publication_date DESC"
            st.dataframe(pd.read_sql(q, engine)[['title', 'activity_type', 'publication_date', 'points']], use_container_width=True)
        except: st.info("لا توجد أعمال.")

    elif selection == "الإعدادات":
        st.title("⚙️ الإعدادات")
        with st.form("pwd"):
            p1 = st.text_input("كلمة المرور الجديدة", type="password")
            if st.form_submit_button("تغيير"):
                if change_password(user['id'], p1): st.success("تم!")

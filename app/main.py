import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'app')))
import streamlit as st
from app.auth import auth_user, register_user_secure
from app.services import get_smart_data, add_work_service, update_work_service, delete_work_service
from app.pdf_utils import generate_cv_pdf
from app.database import SessionLocal
from app.utils import get_img_as_base64

# إعدادات الصفحة
st.set_page_config(page_title="URSH - بوابة البحث العلمي", layout="wide", initial_sidebar_state="expanded", page_icon="🎓")

# --- الدخول والتسجيل ---
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

if not st.session_state['logged_in']:
    c1, c2, c3 = st.columns([1, 1.5, 1])
    with c2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        logo_path = "assets/logo.png"
        logo_html = '<div style="font-size: 80px; margin-bottom: 10px; text-align:center;">🏛️</div>'
        if os.path.exists(logo_path):
            img = get_img_as_base64(logo_path)
            if img: 
                logo_html = f'<div style="display: flex; justify-content: center;"><img src="data:image/png;base64,{img}" style="width: 150px; margin-bottom: 20px;"></div>'

        st.markdown(logo_html, unsafe_allow_html=True)
        st.markdown("""<div style="display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; width: 100%; margin-bottom: 30px;">
                        <h1 style="color:#2563eb; font-family:'Cairo'; margin: 0; font-size: 2.5rem;">بوابة البحث العلمي</h1>
                        <p style="opacity: 0.7; font-size: 1.1rem; margin-top: 5px;">نظام إدارة المخابر الجامعية الموحد</p>
                      </div>""", unsafe_allow_html=True)
        
        tab_login, tab_signup = st.tabs(["🔐 تسجيل الدخول", "📝 حساب جديد (بالكود)"])
        
        with tab_login:
            with st.form("login"):
                u = st.text_input("اسم المستخدم")
                p = st.text_input("كلمة المرور", type="password")
                if st.form_submit_button("دخول", type="primary", use_container_width=True):
                    user = auth_user(u, p)
                    if user:
                        st.session_state['logged_in'] = True
                        st.session_state['user_id'] = user.id
                        st.rerun()
                    else: 
                        st.error("بيانات خاطئة")

        with tab_signup:
            st.markdown("##### 🆕 إنشاء حساب باستخدام كود التفعيل")
            c_a, c_b = st.columns(2)
            new_name = c_a.text_input("الاسم الكامل")
            new_user = c_b.text_input("اسم المستخدم (للدخول)")
            c_pass, c_role = st.columns(2)
            new_pass = c_pass.text_input("كلمة المرور", type="password")
            role_key = c_role.selectbox("الصفة", list(ACTIVATION_CODES.keys()))
            
            m_type_key = "permanent"
            if role_key in ['leader', 'researcher']:
                m_type_key = st.selectbox("نوع العضوية", list(MEMBER_TYPES.keys()), format_func=lambda x: MEMBER_TYPES[x])
            
            session = SessionLocal()
            depts = session.query(Department).all()
            d_map = {d.name_ar: d.id for d in depts}
            sel_dept_id = None
            sel_team_id = None
            
            if role_key != 'admin':
                d_name = st.selectbox("القسم", list(d_map.keys()))
                sel_dept_id = d_map[d_name]
                if role_key in ['leader', 'researcher']:
                    teams = session.query(Team).filter_by(department_id=sel_dept_id).all()
                    if teams:
                        t_map = {t.name: t.id for t in teams}
                        t_name = st.selectbox("الفرقة", list(t_map.keys()))
                        sel_team_id = t_map[t_name]
                    else: st.warning("⚠️ لا توجد فرق.")
            session.close()

            act_code = st.text_input("🔑 كود التفعيل", type="password")
            
            if st.button("إنشاء الحساب", type="primary", use_container_width=True):
                if new_user and new_pass and act_code:
                    success, msg = register_user_secure(new_user, new_name, new_pass, role_key, act_code, sel_team_id, sel_dept_id, m_type_key)
                    if success: 
                        st.success(msg)
                    else: 
                        st.error(msg)
                else: 
                    st.warning("جميع الحقول مطلوبة")

# --- النظام الداخلي ---
else:
    session = SessionLocal()
    user = session.query(User).filter(User.id == st.session_state['user_id']).first()
    
    with st.sidebar:
        logo_path = "assets/logo.png"
        sb_logo = ""
        if os.path.exists(logo_path):
            img = get_img_as_base64(logo_path)
            if img: 
                sb_logo = f'<div style="text-align:center;"><img src="data:image/png;base64,{img}" style="width: 140px; margin-bottom: 20px;"></div>'
        st.markdown(sb_logo, unsafe_allow_html=True)
        
        st.markdown(f"""
        <div style="display: flex; justify-content: center; align-items: center; text-align: center; width: 100%; margin-bottom: 30px;">
            <h3 style="color:#2563eb; font-family:'Cairo'; margin:0; font-size:16px; line-height:1.5; font-weight: 700;">وحدة البحث في علوم الإنسان<br>للدراسات الفلسفية، الاجتماعية والإنسانية</h3>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown(f"<div style='text-align: center; margin-bottom: 20px; font-weight: bold; opacity: 0.7;'>مرحباً بك: {user.full_name} 👋</div>", unsafe_allow_html=True)
        
        # --- القائمة الجانبية ---
        menu_options = {
            "📊 لوحة القيادة": "لوحة القيادة",
            "🏢 الهيكل التنظيمي": "الهيكل التنظيمي",
            "🗂️ إدارة الأنشطة": "إدارة الأنشطة",
            "⚙️ الإعدادات": "الإعدادات"
        }
        
        if user.role in ['leader', 'researcher']:
            menu_options["📝 تسجيل نتاج جديد"] = "تسجيل نتاج"
            menu_options["📂 سجل أعمالي"] = "أعمالي"
            
        if user.role == 'admin': 
            menu_options["👥 إدارة المستخدمين (يدوي)"] = "إدارة المستخدمين"
        
        selected_label = st.sidebar.radio("القائمة", list(menu_options.keys()), label_visibility="collapsed")
        
        # الحصول على القيمة الفعلية
        selection = menu_options[selected_label]
        
        st.markdown("---")
        if st.button("تسجيل الخروج", type="secondary"):
            st.session_state['logged_in'] = False
            st.rerun()

    # --- لوحة القيادة ---
    if selection == "لوحة القيادة":
        st.markdown(f"## 📊 لوحة القيادة والتحليل البياني")
        df = get_smart_data(user)
        if not df.empty:
            with st.expander("🔍 تصفية البيانات", expanded=True):
                col_d1, col_d2 = st.columns(2)
                min_date = df['publication_date'].min()
                max_date = df['publication_date'].max()
                d_from = col_d1.date_input("من تاريخ", min_date)
                d_to = col_d2.date_input("إلى تاريخ", max_date)
                
                available_years = sorted(df['year'].unique().tolist(), reverse=True)
                selected_year = st.selectbox("أو اختر سنة محددة (تتجاوز التاريخ)", ["الكل"] + available_years)

                c1, c2, c3 = st.columns(3)
                depts = sorted(df['department'].unique().tolist())
                sel_dept = c1.selectbox("القسم", ["الكل"] + depts)
                if sel_dept != "الكل":
                    teams = sorted(df[df['department'] == sel_dept]['team'].unique().tolist())
                else:
                    teams = sorted(df['team'].unique().tolist())
                sel_team = c2.selectbox("الفرقة", ["الكل"] + teams)
                types = sorted(df['activity_type'].unique().tolist())
                sel_type = c3.selectbox("نوع النشاط", ["الكل"] + types)

            if selected_year != "الكل":
                filtered = df[df['year'] == selected_year]
            else:
                filtered = df[(df['publication_date'] >= d_from) & (df['publication_date'] <= d_to)]
            
            if sel_dept != "الكل": 
                filtered = filtered[filtered['department'] == sel_dept]
            if sel_team != "الكل": 
                filtered = filtered[filtered['team'] == sel_team]
            if sel_type != "الكل": 
                filtered = filtered[filtered['activity_type'] == sel_type]

            excel_data = to_excel(filtered)
            if excel_data: 
                st.download_button("📥 تحميل التقرير (Excel)", excel_data, f"report_{date.today()}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

            st.markdown("<br>", unsafe_allow_html=True)
            k1, k2, k3, k4 = st.columns(4)
            with k4: 
                st.markdown(f'<div class="kpi-container"><div class="kpi-info"><div class="kpi-value">{len(filtered)}</div><div class="kpi-label">إجمالي النتاج</div></div><div class="kpi-icon">📚</div></div>', unsafe_allow_html=True)
            with k3: 
                st.markdown(f'<div class="kpi-container"><div class="kpi-info"><div class="kpi-value">{filtered["researcher"].nunique()}</div><div class="kpi-label">الباحثون</div></div><div class="kpi-icon">👥</div></div>', unsafe_allow_html=True)
            with k2: 
                st.markdown(f'<div class="kpi-container"><div class="kpi-info"><div class="kpi-value">{filtered["points"].sum()}</div><div class="kpi-label">النقاط</div></div><div class="kpi-icon">⭐</div></div>', unsafe_allow_html=True)
            with k1: 
                yr = filtered['year'].mode()[0] if not filtered.empty else "-"
                st.markdown(f'<div class="kpi-container"><div class="kpi-info"><div class="kpi-value">{yr}</div><div class="kpi-label">السنة النشطة</div></div><div class="kpi-icon">📅</div></div>', unsafe_allow_html=True)

            st.markdown("---")
            st.markdown("### 🏆 مؤشرات الأداء والتميز")
            
            c1, c2 = st.columns(2)
            with c1:
                st.markdown('<div class="chart-container">', unsafe_allow_html=True)
                top_res = filtered.groupby('researcher')['points'].sum().reset_index().sort_values('points', ascending=False).head(5)
                fig_lead = px.bar(top_res, x='points', y='researcher', orientation='h', title="🥇 أكثر الباحثين تميزاً (حسب النقاط)", text_auto=True, color_discrete_sequence=['#fbbf24'])
                st.plotly_chart(fig_lead, use_container_width=True)
                st.markdown('</div>', unsafe_allow_html=True)
            
            with c2:
                st.markdown('<div class="chart-container">', unsafe_allow_html=True)
                if not filtered.empty and 'department' in filtered.columns and 'team' in filtered.columns:
                    tree_data = filtered.groupby(['department', 'team'])['points'].sum().reset_index()
                    fig_tree = px.treemap(
                        tree_data, 
                        path=['department', 'team'], 
                        values='points', 
                        title="🧬 مساهمة الهياكل (خريطة شجرية)", 
                        color='department',
                        color_discrete_sequence=px.colors.qualitative.Prism
                    )
                    fig_tree.update_traces(textinfo="label+value+percent entry")
                    st.plotly_chart(fig_tree, use_container_width=True)
                st.markdown('</div>', unsafe_allow_html=True)

            c1, c2 = st.columns(2)
            with c1:
                st.markdown('<div class="chart-container">', unsafe_allow_html=True)
                st.markdown("##### 📊 توزيع الأنشطة")
                if not filtered.empty:
                    fig = px.pie(filtered, names='activity_type', hole=0.5, color_discrete_sequence=px.colors.sequential.Blues_r)
                    st.plotly_chart(fig, use_container_width=True)
                st.markdown('</div>', unsafe_allow_html=True)
            with c2:
                st.markdown('<div class="chart-container">', unsafe_allow_html=True)
                st.markdown("##### 📈 التطور السنوي")
                if not filtered.empty:
                    daily = filtered.groupby('year').size().reset_index(name='count')
                    fig2 = px.bar(daily, x='year', y='count', text_auto=True, color_discrete_sequence=['#2563eb'])
                    st.plotly_chart(fig2, use_container_width=True)
                st.markdown('</div>', unsafe_allow_html=True)
        else: 
            st.info("لا توجد بيانات متاحة لعرضها.")

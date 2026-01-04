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
    # قسم تسجيل الدخول
    pass  # استكمال الكود كما هو

else:
    session = SessionLocal()
    user = session.query(User).filter(User.id == st.session_state['user_id']).first()
    with st.sidebar:
        # إدارة القائمة الجانبية
        pass  # استكمال الكود كما هو


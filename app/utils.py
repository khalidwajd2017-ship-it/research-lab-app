import base64
import os

# تحويل صورة إلى base64 لتضمينها في المستندات أو التقارير
def get_img_as_base64(file_path):
    try:
        with open(file_path, "rb") as f:
            data = f.read()
        return base64.b64encode(data).decode()
    except Exception as e:
        return None

# دالة لاستخراج البيانات من ملف Excel وتصفية النتائج بناءً على معايير معينة
def filter_data_from_excel(file):
    import pandas as pd
    try:
        # قراءة البيانات من الملف
        df = pd.read_excel(file)
        
        # إضافة تصفية أو معالجة للبيانات هنا (حسب الحاجة)
        # مثلا: حذف الصفوف التي تحتوي على قيم مفقودة
        df.dropna(inplace=True)
        
        return df
    except Exception as e:
        return None

# دالة لحساب النقاط الإجمالية
def calculate_total_points(works_df):
    try:
        return works_df['points'].sum()
    except Exception as e:
        return 0

# دالة لتحويل النص إلى PDF
def text_to_pdf(text, filename="output.pdf"):
    from fpdf import FPDF
    
    # إنشاء ملف PDF جديد
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    # إعداد النص
    pdf.set_font("Arial", size=12)
    pdf.multi_cell(0, 10, text)
    
    # حفظ الملف
    pdf.output(filename)
    return filename

# دالة لتحميل البيانات من URL كملف (مثلاً صورة أو مستند)
def download_file_from_url(url, file_path):
    import requests
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            with open(file_path, "wb") as f:
                f.write(response.content)
            return file_path
        else:
            return None
    except Exception as e:
        return None

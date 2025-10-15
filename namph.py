import streamlit as st
import requests
import pandas as pd
import json
import time
import pytz
import os 
from urllib.request import Request, urlopen # Dùng để gọi API

# --- CẤU HÌNH TIMEZONE ---
VN_TIMEZONE = pytz.timezone('Asia/Ho_Chi_Minh')

# --- THÔNG SỐ CẤU HÌNH THINGSPEAK ---
# LƯU Ý: ĐÂY LÀ READ API KEY, KHÔNG PHẢI WRITE API KEY
CHANNEL_ID = "3096685"
READ_API_KEY = "QZJHRD0BRKMYFOWI"
THING_SPEAK_URL = f"https://api.thingspeak.com/channels/{CHANNEL_ID}/feeds.json?api_key={READ_API_KEY}&results=20"
REFRESH_INTERVAL_SECONDS = 5

# --- CẤU HÌNH GEMINI AI ---
GEMINI_API_KEY = "AIzaSyAvgpBrMsA2pCjB3Hng-Mjyo1ir-KO_kgQ"
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-05-20:generateContent"
# 🍄 PROMPT MỚI: CHỈ SỬ DỤNG 1 QUY TẮC VÀNG TỔNG HỢP 🍄
SYSTEM_PROMPT = """Bạn là một chuyên gia về nuôi trồng nấm (Mycologist) với kiến thức chuyên sâu về nấm Bào Ngư.
QUY TẮC VÀNG TỔNG HỢP cho NẤM BÀO NGƯ (Mọi giai đoạn):
1. Môi trường Lý tưởng Tổng thể: Nhiệt độ 20°C - 28°C, Độ ẩm 70% - 95%.
2. Nguy hiểm: T > 30°C (Quá nóng) hoặc H < 65% (Quá khô).

Nhiệm vụ của bạn là phân tích dữ liệu hiện tại, đối chiếu với Quy tắc Vàng Tổng hợp và đưa ra các gợi ý hành động để tối ưu hóa sự phát triển. Khi trò chuyện, hãy trả lời ngắn gọn, thân thiện và sử dụng dữ liệu thực tế được cung cấp."""

# Kiểm tra và khởi tạo lịch sử chat (cho tính năng Chatbot)
if "messages" not in st.session_state:
    st.session_state["messages"] = [{"role": "model", "parts": [{"text": "Chào mừng đến với hệ thống cố vấn nấm học AI. Bạn có thể hỏi tôi về môi trường hiện tại hoặc các vấn đề của nấm!"}]}]
if "latest_climate_data" not in st.session_state:
    st.session_state["latest_climate_data"] = {}
# Khởi tạo thời gian làm mới cuối cùng
if "last_refresh_time" not in st.session_state:
    st.session_state["last_refresh_time"] = time.time()


def calculate_mushroom_health_index(temp, hum_percent):
    """Tính toán Chỉ số Sức khỏe Nấm (MHI).
    MHI càng thấp càng tốt. Phạm vi lý tưởng: T 20-28C, H 70-95%.
    """
    try:
        # Mục tiêu tối ưu cho Bào Ngư (Tổng hợp): T = 24C, H = 85%
        temp_ideal = 24.0
        hum_ideal = 85.0
        
        # Tính độ lệch T (penalty cho T quá cao/thấp)
        temp_penalty = abs(temp - temp_ideal)
        
        # Tính độ lệch H (penalty cho H quá thấp - nguy hiểm hơn H quá cao)
        if hum_percent < 70.0:
            hum_penalty = (70.0 - hum_percent) * 2 # Penalty gấp đôi nếu H quá thấp
        else:
            hum_penalty = abs(hum_percent - hum_ideal) / 5
            
        # MHI = (Trọng số T * Penalty T) + (Trọng số H * Penalty H)
        MHI = (temp_penalty * 0.6) + (hum_penalty * 0.4)
        return MHI
    except Exception:
        return None

def generate_ai_suggestion(temp, hum, mhi_index):
    """Gọi Gemini API cho GỢI Ý TỰ ĐỘNG."""
    if GEMINI_API_KEY == "ĐẶT KHÓA API CỦA BẠN VÀO ĐÂY":
        return "⚠️ Cảnh báo: Vui lòng cung cấp khóa API thực tế để kích hoạt AI."

    prompt_for_suggestion = (
        f"Dữ liệu môi trường hiện tại trong trại nấm: Nhiệt độ {temp:.1f}°C, Độ ẩm {hum:.1f}%, Chỉ số MHI {mhi_index:.2f}. "
        f"Hãy phân tích và đưa ra một lời khuyên ngắn gọn (tối đa 2 câu) và trực tiếp về hành động nên làm (ví dụ: 'Bật quạt thông gió' hoặc 'Phun sương ngay')."
    )
    
    payload = {
        "contents": [{"parts": [{"text": prompt_for_suggestion}]}],
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
    }
    
    try:
        headers = {'Content-Type': 'application/json'}
        full_url = f"{GEMINI_API_URL}?key={GEMINI_API_KEY}" 
        
        response = requests.post(full_url, headers=headers, data=json.dumps(payload))
        response.raise_for_status()
        
        result = response.json()
        suggestion = result.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', 'Không nhận được gợi ý từ AI.')
        return suggestion
    
    except requests.exceptions.RequestException as e:
        return f"Lỗi gọi Gemini API: {e}. Kiểm tra API Key và kết nối mạng."
    except Exception as e:
        return f"Lỗi xử lý phản hồi AI: {e}"

def chat_with_gemini(user_prompt):
    """Gọi Gemini API cho CHẾ ĐỘ TRÒ CHUYỆN (sử dụng lịch sử chat)."""
    if GEMINI_API_KEY == "ĐẶT KHÓA API CỦA BẠN VÀO ĐÂY":
        return "Vui lòng cấu hình API Key để trò chuyện."
    
    # Lấy MHI
    mhi_index = st.session_state.latest_climate_data.get('mhi', 'N/A')
    
    latest_data_context = (
        f"Ngữ cảnh hiện tại (Trại Nấm): "
        f"Nhiệt độ {st.session_state.latest_climate_data.get('temp', 'N/A')}°C, "
        f"Độ ẩm {st.session_state.latest_climate_data.get('hum', 'N/A')}%, "
        f"Trạng thái Bơm {st.session_state.latest_climate_data.get('pump', 'N/A')}, "
        f"Trạng thái Quạt {st.session_state.latest_climate_data.get('fan', 'N/A')}, "
        f"Chỉ số MHI {mhi_index:.2f}. "
    )
    
    chat_history = [{"role": m["role"], "parts": [{"text": m["parts"][0]["text"]}]} for m in st.session_state.messages]
    
    if chat_history and chat_history[-1]["role"] == "user":
        current_prompt = chat_history[-1]["parts"][0]["text"]
        chat_history[-1]["parts"][0]["text"] = f"{latest_data_context} Người dùng hỏi: {current_prompt}"
    
    payload = {
        "contents": chat_history,
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
    }

    try:
        headers = {'Content-Type': 'application/json'}
        full_url = f"{GEMINI_API_URL}?key={GEMINI_API_KEY}" 
        
        response = requests.post(full_url, headers=headers, data=json.dumps(payload))
        response.raise_for_status()
        
        result = response.json()
        return result.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', 'Lỗi phản hồi.')
        
    except requests.exceptions.RequestException as e:
        return f"Lỗi gọi API: {e}. Vui lòng kiểm tra lại."
    except Exception as e:
        return "Lỗi xử lý phản hồi chat."


def fetch_data():
    """Lấy dữ liệu JSON từ ThingSpeak API."""
    try:
        response = requests.get(THING_SPEAK_URL)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Lỗi khi kết nối đến ThingSpeak: {e}")
        return None

def process_data(json_data):
    """Xử lý dữ liệu JSON thành DataFrame và trích xuất dữ liệu mới nhất."""
    if not json_data or 'feeds' not in json_data:
        return None, None

    feeds = json_data['feeds']
    df = pd.DataFrame(feeds)
    
    df = df.rename(columns={
        'created_at': 'Thời gian',
        'field1': 'Độ ẩm (%)',
        'field2': 'Nhiệt độ (°C)',
        'field3': 'Trạng thái Bơm', 
        'field4': 'Trạng thái Quạt'  # THÊM FIELD 4
    })
    
    df['Thời gian'] = pd.to_datetime(df['Thời gian'])
    df['Thời gian'] = df['Thời gian'].dt.tz_convert(VN_TIMEZONE)
    
    df['Độ ẩm (%)'] = pd.to_numeric(df['Độ ẩm (%)'], errors='coerce')
    df['Nhiệt độ (°C)'] = pd.to_numeric(df['Nhiệt độ (°C)'], errors='coerce')
    df['Trạng thái Bơm'] = pd.to_numeric(df['Trạng thái Bơm'], errors='coerce')
    df['Trạng thái Quạt'] = pd.to_numeric(df['Trạng thái Quạt'], errors='coerce') # CHUYỂN ĐỔI FIELD 4
    
    df = df.sort_values('Thời gian', ascending=False).reset_index(drop=True)
    latest_data = df.iloc[0] if not df.empty else None
    
    return df, latest_data

# 💡 LOGIC LÀM MỚI (RERUN) AN TOÀN - THAY THẾ WHILE TRUE
def check_and_rerun():
    """Kiểm tra thời gian và tự động làm mới Streamlit."""
    current_time = time.time()
    if current_time - st.session_state["last_refresh_time"] >= REFRESH_INTERVAL_SECONDS:
        st.session_state["last_refresh_time"] = current_time # Cập nhật thời gian làm mới
        st.rerun() # Kích hoạt làm mới script

# ⚠️ HÀM HIỂN THỊ CẢNH BÁO TỰ ĐỘNG
def display_alerts(temp, hum):
    """Kiểm tra các ngưỡng nguy hiểm và hiển thị cảnh báo."""
    alerts = []
    
    # 1. Cảnh báo Lỗi dữ liệu (NaN)
    if pd.isna(temp) or pd.isna(hum):
        alerts.append("❌ DỮ LIỆU LỖI: Không đọc được Nhiệt độ hoặc Độ ẩm. Vui lòng kiểm tra cảm biến DHT22.")
    
    # 2. Cảnh báo Nguy hiểm Quá nhiệt (> 30C)
    if temp > 30.0:
        alerts.append(f"🔥 NGUY HIỂM: Nhiệt độ quá cao ({temp:.1f}°C). Nguy cơ chết sợi nấm!")

    # 3. Cảnh báo Nguy hiểm Độ ẩm thấp (< 65%)
    if hum < 75.0:
        alerts.append(f"💧 CẢNH BÁO: Độ ẩm quá thấp ({hum:.1f}%). Cần phun sương gấp để tránh chai nấm.")
    
    # 4. Cảnh báo Độ ẩm Quá cao (Nguy cơ nấm mốc)
    if hum > 95.0:
        alerts.append(f"💧 CẢNH BÁO: Độ ẩm quá cao ({hum:.1f}%). Nguy cơ ngưng tụ và nấm mốc bùng phát.")

    if alerts:
        for alert in alerts:
            st.error(alert) # Dùng st.error để hiển thị nổi bật
        return True
    return False


# --- GIAO DIỆN STREAMLIT ---

# 1. BẬT WIDE LAYOUT ĐỂ DÙNG HẾT CHIỀU RỘNG MÀN HÌNH
st.set_page_config(
    page_title="Cố vấn Khí hậu Trại Nấm",
    layout="wide" # Dùng toàn bộ chiều rộng
)

st.title("🍄 Hệ thống Cố vấn & Phân tích Khí hậu Trại Nấm (AI)")

# Thiết lập Chatbot ở Sidebar
with st.sidebar:
    st.header("Trợ lý AI Nấm học")
    
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["parts"][0]["text"])

    if prompt := st.chat_input("Hỏi tôi về môi trường nấm..."):
        st.session_state.messages.append({"role": "user", "parts": [{"text": prompt}]})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("model"):
            with st.spinner("AI đang phân tích..."):
                response = chat_with_gemini(prompt)
                st.markdown(response)
        st.session_state.messages.append({"role": "model", "parts": [{"text": response}]})


# --- THỰC THI CHÍNH ---
# LẤY DỮ LIỆU CHỈ MỘT LẦN KHI SCRIPT ĐƯỢC GỌI
json_data = fetch_data()
df, latest_data = process_data(json_data)

# Tính toán MHI 
mhi_index = None
if latest_data is not None:
    temp = latest_data['Nhiệt độ (°C)']
    hum = latest_data['Độ ẩm (%)']
    pump = latest_data['Trạng thái Bơm'] # Lấy trạng thái Bơm
    fan = latest_data['Trạng thái Quạt'] # Lấy trạng thái Quạt
    mhi_index = calculate_mushroom_health_index(temp, hum)
    # LƯU TRỮ TRẠNG THÁI MỚI NHẤT CHO AI TRÒ CHUYỆN
    st.session_state.latest_climate_data = {"temp": temp, "hum": hum, "mhi": mhi_index, "pump": pump, "fan": fan}


# --- 0. HIỂN THỊ CẢNH BÁO NỔI BẬT ---
if latest_data is not None:
    display_alerts(latest_data['Nhiệt độ (°C)'], latest_data['Độ ẩm (%)'])


# --- 1. HIỂN THỊ DỮ LIỆU THÔ VÀ TÍNH TOÁN MHI ---
with st.container(border=True):
    st.subheader("📊 Dữ liệu Cập nhật Mới nhất")
    
    if latest_data is None:
        st.warning("Không thể tải hoặc không có dữ liệu để hiển thị.")
    else:
        temp = latest_data['Nhiệt độ (°C)']
        hum = latest_data['Độ ẩm (%)']
        pump_status = latest_data['Trạng thái Bơm']
        fan_status = latest_data['Trạng thái Quạt'] # LẤY TRẠNG THÁI QUẠT
        
        # 2. KHẮC PHỤC LỖI CẮT CHỮ METRICS BẰNG CÁCH SỬ DỤNG 6 CỘT ĐỀU NHAU
        col1, col2, col3, col4, col5, col6 = st.columns(6)
        
        # Cột 1: Thời gian
        col1.metric(label="⏰ Giờ VN", value=latest_data['Thời gian'].strftime("%H:%M:%S"))
        # Cột 2: Nhiệt độ
        col2.metric(label="🌡 Nhiệt độ", value=f"{temp:.1f} °C", delta_color="off")
        # Cột 3: Độ ẩm
        col3.metric(label="💧 Độ ẩm", value=f"{hum:.1f} %", delta_color="off")
        
        # Cột 4: Trạng thái Bơm/Phun sương (Rút gọn label)
        pump_text = "ON" if pump_status == 1 else "OFF"
        pump_color = "inverse" if pump_status == 1 else "off"
        col4.metric(label="💦 Phun Sương", value=pump_text, delta_color=pump_color)
        
        # Cột 5: Trạng thái Quạt (Rút gọn label)
        fan_text = "ON" if fan_status == 1 else "OFF"
        fan_color = "inverse" if fan_status == 1 else "off"
        col5.metric(label="💨 Thông gió", value=fan_text, delta_color=fan_color)

        # Cột 6: Chỉ số MHI
        if mhi_index is not None:
            mhi_color = "inverse" if mhi_index > 2.0 else "off"
            col6.metric(label="💚 Sức khỏe Nấm", value=f"{mhi_index:.2f}", delta_color=mhi_color)


# --- 2. KHU VỰC HIỂN THỊ GỢI Ý AI TỰ ĐỘNG ---
with st.container(border=True):
    st.subheader("💡 Gợi ý Tối ưu Môi trường Tự động")
    
    if latest_data is not None and mhi_index is not None:
        ai_suggestion = generate_ai_suggestion(temp, hum, mhi_index)
        
        # KHẮC PHỤC LỖI CHỮ BỊ CHÌM: Tăng cường độ tương phản màu sắc
        st.markdown(f"""
            <div style="background-color: #f0f2f6; padding: 15px; border-radius: 10px; border-left: 5px solid #2e7d32; color: #1f1f1f;">
                <p style="font-size: 16px; margin: 0; font-weight: bold; color: #2e7d32;">Lời khuyên từ Cố vấn AI:</p>
                <p style="font-size: 18px; margin: 5px 0 0 0; color: #1f1f1f;">{ai_suggestion}</p>
            </div>
        """, unsafe_allow_html=True)
    else:
         st.info("Đang chờ dữ liệu ThingSpeak hợp lệ để tạo gợi ý AI...")


# --- 3. KHU VỰC HIỂN THỊ BIỂU ĐỒ ---
with st.container(border=True):
    st.subheader("📈 Biểu đồ 20 lần đọc gần nhất")
    if df is not None:
        # Chỉ vẽ Nhiệt độ và Độ ẩm cho biểu đồ line
        chart_data = df[['Thời gian', 'Nhiệt độ (°C)', 'Độ ẩm (%)']].set_index('Thời gian').sort_index()
        # Sử dụng Biểu đồ cột/đường để đẹp hơn
        st.line_chart(chart_data, height=300) 
    
    with st.expander("Xem dữ liệu thay đổi cụ thể"):
        st.dataframe(df)

# GỌI HÀM LÀM MỚI AN TOÀN
check_and_rerun()

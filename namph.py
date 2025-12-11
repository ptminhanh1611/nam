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
CHANNEL_ID = "3097264"
READ_API_KEY = "QZJHRD0BRKMYFOWI"
THING_SPEAK_URL = f"https://api.thingspeak.com/channels/{CHANNEL_ID}/feeds.json?api_key={READ_API_KEY}&results=20"
REFRESH_INTERVAL_SECONDS = 5

# --- CẤU HÌNH GEMINI AI ---
GEMINI_API_KEY = "AIzaSyAvgpBrMsA2pCjB3Hng-Mjyo1ir-KO_kgQ"
GEMINI_API_URL = "Khóa_API_MỚI_CỦA_BẠN"
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
    mhi_index = st.session_state.latest_climate_data.get('mhi', 0.0) # Mặc định là 0.0 nếu chưa có
    
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
        'field1': 'Nhiệt độ (°C)',
        'field2': 'Độ ẩm (%)',
        'field3': 'Trạng thái Bơm', 
        'field4': 'Trạng thái Quạt'
    })
    
    df['Thời gian'] = pd.to_datetime(df['Thời gian'])
    df['Thời gian'] = df['Thời gian'].dt.tz_convert(VN_TIMEZONE)
    
    df['Độ ẩm (%)'] = pd.to_numeric(df['Độ ẩm (%)'], errors='coerce')
    df['Nhiệt độ (°C)'] = pd.to_numeric(df['Nhiệt độ (°C)'], errors='coerce')
    df['Trạng thái Bơm'] = pd.to_numeric(df['Trạng thái Bơm'], errors='coerce')
    df['Trạng thái Quạt'] = pd.to_numeric(df['Trạng thái Quạt'], errors='coerce')
    
    df = df.sort_values('Thời gian', ascending=False).reset_index(drop=True)
    latest_data = df.iloc[0] if not df.empty else None
    
    return df, latest_data

def check_and_rerun():
    """Kiểm tra thời gian và tự động làm mới Streamlit."""
    current_time = time.time()
    if current_time - st.session_state["last_refresh_time"] >= REFRESH_INTERVAL_SECONDS:
        st.session_state["last_refresh_time"] = current_time
        st.rerun()

def display_alerts(temp, hum):
    """Kiểm tra các ngưỡng nguy hiểm và hiển thị cảnh báo."""
    alerts = []
    
    if pd.isna(temp) or pd.isna(hum):
        alerts.append("❌ DỮ LIỆU LỖI: Không đọc được Nhiệt độ hoặc Độ ẩm. Vui lòng kiểm tra cảm biến DHT22.")
    
    if temp > 30.0:
        alerts.append(f"🔥 NGUY HIỂM: Nhiệt độ quá cao ({temp:.1f}°C). Nguy cơ chết sợi nấm!")

    if hum < 75.0:
        alerts.append(f"💧 CẢNH BÁO: Độ ẩm quá thấp ({hum:.1f}%). Cần phun sương gấp để tránh chai nấm.")
    
    if hum > 95.0:
        alerts.append(f"💧 CẢNH BÁO: Độ ẩm quá cao ({hum:.1f}%). Nguy cơ ngưng tụ và nấm mốc bùng phát.")

    if alerts:
        for alert in alerts:
            st.error(alert)
        return True
    return False


# --- GIAO DIỆN STREAMLIT ---

st.set_page_config(
    page_title="Cố vấn Khí hậu Trại Nấm",
    layout="wide"
)

st.title("🍄 Hệ thống Cố vấn & Phân tích Khí hậu Trại Nấm (AI)")

# --- CHIA BỐ CỤC MỚI ---
# Cột chính (2/3) và Cột chat (1/3)
main_col, chat_col = st.columns([2, 1])

# --- CỘT CHATBOT BÊN PHẢI ---
with chat_col:
    with st.container(height=800, border=True): # Tạo khung chứa cho chatbot
        st.header("Trợ lý AI Nấm học")
        
        # Vùng hiển thị tin nhắn
        message_container = st.container()
        for message in st.session_state.messages:
            with message_container.chat_message(message["role"]):
                st.markdown(message["parts"][0]["text"])

        # Vùng nhập liệu
        if prompt := st.chat_input("Hỏi tôi về môi trường nấm..."):
            st.session_state.messages.append({"role": "user", "parts": [{"text": prompt}]})
            with message_container.chat_message("user"):
                st.markdown(prompt)

            with message_container.chat_message("model"):
                with st.spinner("AI đang phân tích..."):
                    response = chat_with_gemini(prompt)
                    st.markdown(response)
            st.session_state.messages.append({"role": "model", "parts": [{"text": response}]})

# --- CỘT HIỂN THỊ CHÍNH BÊN TRÁI ---
with main_col:
    # Lấy và xử lý dữ liệu
    json_data = fetch_data()
    df, latest_data = process_data(json_data)

    mhi_index = None
    if latest_data is not None:
        temp = latest_data['Nhiệt độ (°C)']
        hum = latest_data['Độ ẩm (%)']
        pump = latest_data['Trạng thái Bơm']
        fan = latest_data['Trạng thái Quạt']
        mhi_index = calculate_mushroom_health_index(temp, hum)
        st.session_state.latest_climate_data = {"temp": temp, "hum": hum, "mhi": mhi_index, "pump": pump, "fan": fan}

    # Hiển thị cảnh báo
    if latest_data is not None:
        display_alerts(latest_data['Nhiệt độ (°C)'], latest_data['Độ ẩm (%)'])

    # Hiển thị dữ liệu mới nhất
    with st.container(border=True):
        st.subheader("📊 Dữ liệu Cập nhật Mới nhất")
        
        if latest_data is None:
            st.warning("Không thể tải hoặc không có dữ liệu để hiển thị.")
        else:
            temp = latest_data['Nhiệt độ (°C)']
            hum = latest_data['Độ ẩm (%)']
            pump_status = latest_data['Trạng thái Bơm']
            fan_status = latest_data['Trạng thái Quạt']
            
            col1, col2, col3, col4, col5, col6 = st.columns(6)
            
            col1.metric(label="⏰ Giờ VN", value=latest_data['Thời gian'].strftime("%H:%M:%S"))
            col2.metric(label="🌡 Nhiệt độ", value=f"{temp:.1f} °C", delta_color="off")
            col3.metric(label="💧 Độ ẩm", value=f"{hum:.1f} %", delta_color="off")
            
            pump_text = "ON" if pump_status == 1 else "OFF"
            pump_color = "inverse" if pump_status == 1 else "off"
            col4.metric(label="💦 Phun Sương", value=pump_text, delta_color=pump_color)
            
            fan_text = "ON" if fan_status == 1 else "OFF"
            fan_color = "inverse" if fan_status == 1 else "off"
            col5.metric(label="💨 Thông gió", value=fan_text, delta_color=fan_color)

            if mhi_index is not None:
                mhi_color = "inverse" if mhi_index > 2.0 else "off"
                col6.metric(label="💚 Sức khỏe Nấm", value=f"{mhi_index:.2f}", delta_color=mhi_color)

    # Gợi ý AI tự động
    with st.container(border=True):
        st.subheader("💡 Gợi ý Tối ưu Môi trường Tự động")
        
        if latest_data is not None and mhi_index is not None:
            ai_suggestion = generate_ai_suggestion(temp, hum, mhi_index)
            
            st.markdown(f"""
                <div style="background-color: #f0f2f6; padding: 15px; border-radius: 10px; border-left: 5px solid #2e7d32; color: #1f1f1f;">
                    <p style="font-size: 16px; margin: 0; font-weight: bold; color: #2e7d32;">Lời khuyên từ Cố vấn AI:</p>
                    <p style="font-size: 18px; margin: 5px 0 0 0; color: #1f1f1f;">{ai_suggestion}</p>
                </div>
            """, unsafe_allow_html=True)
        else:
            st.info("Đang chờ dữ liệu ThingSpeak hợp lệ để tạo gợi ý AI...")

    # Biểu đồ
    with st.container(border=True):
        st.subheader("📈 Biểu đồ 20 lần đọc gần nhất")
        if df is not None:
            chart_data = df[['Thời gian', 'Nhiệt độ (°C)', 'Độ ẩm (%)']].set_index('Thời gian').sort_index()
            st.line_chart(chart_data, height=300) 
        
        with st.expander("Xem dữ liệu thay đổi cụ thể"):
            st.dataframe(df)

# GỌI HÀM LÀM MỚI
check_and_rerun()




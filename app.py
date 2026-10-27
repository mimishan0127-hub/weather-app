import streamlit as st
import requests
import folium
from streamlit_folium import st_folium
import pandas as pd
from streamlit_js_eval import get_geolocation
import math

# 頁面配置
st.set_page_config(
    page_title="即時天氣觀測 & 生活行動指南",
    page_icon="🌤️",
    layout="wide"
)

# 台灣主要縣市座標對照
COUNTY_COORDS = {
    "臺北市": [25.0330, 121.5654],
    "新北市": [25.0125, 121.4657],
    "基隆市": [25.1276, 121.7392],
    "桃園市": [24.9936, 121.3010],
    "新竹市": [24.8138, 120.9675],
    "新竹縣": [24.8387, 121.0177],
    "苗栗縣": [24.5602, 120.8214],
    "臺中市": [24.1477, 120.6736],
    "彰化縣": [24.0816, 120.5385],
    "南投縣": [23.9099, 120.6845],
    "雲林縣": [23.7092, 120.4313],
    "嘉義市": [23.4800, 120.4491],
    "嘉義縣": [23.4518, 120.2559],
    "臺南市": [22.9997, 120.2270],
    "高雄市": [22.6273, 120.3014],
    "屏東縣": [22.6762, 120.4879],
    "宜蘭縣": [24.7570, 121.7530],
    "花蓮縣": [23.9872, 121.6016],
    "臺東縣": [22.7583, 121.1444],
    "澎湖縣": [23.5711, 119.5793],
    "金門縣": [24.4492, 118.3766],
    "連江縣": [26.1505, 119.9499]
}

# WMO 天氣代碼與生動圖示對照
WEATHER_ICONS = {
    0: ("☀️", "晴朗無雲"),
    1: ("🌤️", "主要多雲"),
    2: ("⛅", "多雲時晴"),
    3: ("☁️", "陰天多雲"),
    45: ("🌫️", "有霧"),
    48: ("🌫️", "結霜霧"),
    51: ("🌦️", "微量細雨"),
    53: ("🌦️", "偶有小雨"),
    55: ("🌧️", "密集小雨"),
    61: ("🌧️", "局部陣雨"),
    63: ("🌧️", "持續性中雨"),
    65: ("🌧️", "大雨來襲"),
    80: ("🌦️", "短暫陣雨"),
    81: ("🌧️", "強陣雨"),
    82: ("⛈️", "狂暴豪雨"),
    95: ("⛈️", "雷雨交加"),
    96: ("⛈️", "雷雨伴隨局部冰雹"),
    99: ("⛈️", "強烈雷暴雨")
}

def get_weather_desc(code):
    return WEATHER_ICONS.get(code, ("🌤️", "多雲時晴"))

# 計算兩經緯度距離以找出最近縣市
def find_closest_county(user_lat, user_lon):
    closest_name = "臺北市"
    min_dist = float("inf")
    for name, coords in COUNTY_COORDS.items():
        dist = math.sqrt((user_lat - coords[0])**2 + (user_lon - coords[1])**2)
        if dist < min_dist:
            min_dist = dist
            closest_name = name
    return closest_name

# 獲取即時天氣與未來預報
@st.cache_data(ttl=1800)
def fetch_weather(lat, lon):
    url = (
        f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
        f"&current=temperature_2m,relative_humidity_2m,weather_code,apparent_temperature"
        f"&hourly=temperature_2m,precipitation_probability,weather_code"
        f"&forecast_days=1&timezone=Asia%2FTaipei"
    )
    try:
        res = requests.get(url, timeout=8).json()
        return res
    except Exception:
        return None

# 獲取空污指標
@st.cache_data(ttl=1800)
def fetch_air_quality(county_name):
    if "MOENV_API_KEY" in st.secrets:
        try:
            url = "https://data.moenv.gov.tw/api/v2/aqx_p_432"
            params = {"api_key": st.secrets["MOENV_API_KEY"], "limit": 100, "format": "json"}
            res = requests.get(url, params=params, timeout=5).json()
            for r in res.get("records", []):
                if county_name in r.get("county", ""):
                    return {"aqi": r.get("aqi", "35"), "status": r.get("status", "普通")}
        except Exception:
            pass
    return {"aqi": "35", "status": "良好"}

# 生成穿搭與生活決策
def generate_ai_advice(temp, rain_prob, humidity, aqi):
    advice = []
    if temp >= 28:
        advice.append("🩳 **穿搭指引**：天氣炎熱！請穿著透氣涼爽短袖，紫外線偏高請準備遮陽帽或墨鏡。")
    elif 20 <= temp < 28:
        advice.append("👔 **穿搭指引**：氣溫宜人舒适，短袖加件薄襯衫或薄外套即可輕鬆出門。")
    else:
        advice.append("🧥 **穿搭指引**：早晚氣溫較涼，請務必外加風衣、連帽外套或毛衣保暖。")

    if rain_prob < 30 and humidity < 75:
        advice.append("🧺 **生活行動**：降雨機率低，通風良好，非常適合室外曬衣、洗車或踏青。")
    elif rain_prob >= 50:
        advice.append("☔ **外出提醒**：即將有高機率降雨，外出請隨身攜帶雨傘或雨衣，衣物建議室內陰乾。")
    else:
        advice.append("⛅ **生活行動**：濕度稍高或有局部陣雨，戶外活動建議備一把折傘。")

    try:
        aqi_val = int(aqi)
    except ValueError:
        aqi_val = 35

    if aqi_val > 100:
        advice.append("😷 **運動與空污**：空氣品質較差，呼吸道敏感族群外出建議配戴口罩，避免激烈跑步。")
    else:
        advice.append("🚴 **運動與空污**：空氣品質清新，戶外跑步、騎單車運動非常合適！")

    return advice

# --- 主程式排版 ---
st.title("🌈 智慧即時天氣 & 生活指南")

# 1. 抓取設備真實 GPS 定位 (前端 Geolocation)
location_info = get_geolocation()
auto_detected_city = None

if location_info and "coords" in location_info:
    user_lat = location_info["coords"]["latitude"]
    user_lon = location_info["coords"]["longitude"]
    auto_detected_city = find_closest_county(user_lat, user_lon)
    st.toast(f"📍 已取得設備 GPS 定位：目前位於 {auto_detected_city} 附近！", icon="🎯")

county_list = list(COUNTY_COORDS.keys())
default_index = county_list.index(auto_detected_city) if auto_detected_city in county_list else 0

selected_county = st.selectbox(
    "🗺️ 選擇或切換查詢區域：",
    options=county_list,
    index=default_index,
    help="允許瀏覽器存取位置即可自動切換至目前位置"
)

lat, lon = COUNTY_COORDS[selected_county]

# 抓取即時數據
weather_data = fetch_weather(lat, lon)
aqi_data = fetch_air_quality(selected_county)

if weather_data:
    current = weather_data.get("current", {})
    temp = current.get("temperature_2m", 24.0)
    feels_like = current.get("apparent_temperature", temp)
    humidity = current.get("relative_humidity_2m", 60)
    wcode = current.get("weather_code", 0)
    icon, condition = get_weather_desc(wcode)

    hourly = weather_data.get("hourly", {})
    hourly_times = [t.split("T")[1] for t in hourly.get("time", [])[:6]]
    hourly_temps = hourly.get("temperature_2m", [])[:6]
    hourly_rains = hourly.get("precipitation_probability", [])[:6]
    hourly_codes = hourly.get("weather_code", [])[:6]
    current_rain = hourly_rains[0] if hourly_rains else 10
else:
    temp, feels_like, humidity, icon, condition, current_rain = 25.0, 26.0, 60, "🌤️", "多雲時晴", 10
    hourly_times = ["12:00", "13:00", "14:00", "15:00", "16:00", "17:00"]
    hourly_temps = [25.0] * 6
    hourly_rains = [10] * 6
    hourly_codes = [1] * 6

# 上半部：地圖與彩色資訊卡
col_map, col_details = st.columns([1.1, 1.2])

with col_map:
    st.markdown(f"#### 📍 {selected_county} 衛星與地圖標示")
    m = folium.Map(location=[lat, lon], zoom_start=11, tiles="OpenStreetMap")
    folium.Marker(
        [lat, lon],
        popup=f"{selected_county}：{temp}°C",
        tooltip=f"{selected_county} {icon} {condition}",
        icon=folium.Icon(color="red", icon="info-sign")
    ).add_to(m)
    st_folium(m, width=540, height=360, returned_objects=[])

with col_details:
    # 頂部大天氣圖示與現況橫幅
    st.markdown(f"""
    <div style="background: linear-gradient(135deg, #6B73FF 0%, #000DFF 100%); padding: 18px; border-radius: 12px; color: white; margin-bottom: 15px;">
        <h2 style="margin: 0; color: white;">{icon} {condition} · {temp}°C</h2>
        <p style="margin: 5px 0 0 0; opacity: 0.9;">體感溫度 {feels_like}°C ｜ 相對濕度 {humidity}% ｜ 觀測地點：{selected_county}</p>
    </div>
    """, unsafe_allow_html=True)

    # 三大指標卡
    m1, m2, m3 = st.columns(3)
    m1.metric("🌡️ 即時氣溫", f"{temp} °C", delta=f"體感 {feels_like}°C")
    m2.metric("💧 降雨機率", f"{current_rain} %")
    m3.metric("🍃 空氣品質", f"{aqi_data['aqi']}", delta=aqi_data['status'], delta_color="off")

    st.markdown("#### 💡 AI 智慧生活建議")
    advices = generate_ai_advice(temp, current_rain, humidity, aqi_data["aqi"])
    for tip in advices:
        st.markdown(tip)

# 下半部：近 6 小時視覺化小卡 + 曲線圖
st.divider()
st.markdown("#### ⏱️ 未來 6 小時即時天氣預測")

# 橫向排列未來 6 小時微型天氣卡片
h_cols = st.columns(6)
for i in range(6):
    h_time = hourly_times[i]
    h_t = hourly_temps[i]
    h_r = hourly_rains[i]
    h_icon, _ = get_weather_desc(hourly_codes[i])
    with h_cols[i]:
        st.markdown(f"""
        <div style="border: 1px solid #e0e0e0; border-radius: 8px; padding: 8px; text-align: center; background-color: #fafafa;">
            <div style="font-size: 13px; color: #666;">{h_time}</div>
            <div style="font-size: 26px; margin: 4px 0;">{h_icon}</div>
            <div style="font-weight: bold; font-size: 15px;">{h_t}°C</div>
            <div style="font-size: 12px; color: #1E88E5;">💧 {h_r}%</div>
        </div>
        """, unsafe_allow_html=True)

st.write("")
chart_df = pd.DataFrame({
    "時間": hourly_times,
    "氣溫 (°C)": hourly_temps,
    "降雨機率 (%)": hourly_rain if 'hourly_rain' in locals() else hourly_rains
}).set_index("時間")

st.line_chart(chart_df)

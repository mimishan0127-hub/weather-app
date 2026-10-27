import streamlit as st
import requests
import folium
from streamlit_folium import st_folium
import pandas as pd

# 頁面基礎設定
st.set_page_config(
    page_title="台灣即時天氣看板 & 生活行動指南",
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

# 1. 偵測使用者所在位置 (IP 定位)
@st.cache_data(ttl=3600)
def detect_user_location():
    try:
        res = requests.get("https://ipapi.co/json/", timeout=4).json()
        city = res.get("city", "Taipei")
        for name in COUNTY_COORDS.keys():
            normalized_name = name.replace("臺", "Tai").replace("市", "").replace("縣", "").lower()
            if normalized_name in city.lower():
                return name
        return "臺北市"
    except Exception:
        return "臺北市"

# 2. 獲取氣象預報資料 (Open-Meteo 免費 API)
@st.cache_data(ttl=1800)
def fetch_weather(lat, lon):
    url = (
        f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
        f"&current=temperature_2m,relative_humidity_2m"
        f"&hourly=temperature_2m,precipitation_probability"
        f"&forecast_days=1&timezone=Asia%2FTaipei"
    )
    try:
        response = requests.get(url, timeout=8)
        if response.status_code == 200:
            return response.json()
    except Exception:
        pass
    return None

# 3. 獲取空氣品質資料 (支援環境部 API 或預設值)
@st.cache_data(ttl=1800)
def fetch_air_quality(county_name):
    if "MOENV_API_KEY" in st.secrets:
        try:
            url = "https://data.moenv.gov.tw/api/v2/aqx_p_432"
            params = {
                "api_key": st.secrets["MOENV_API_KEY"],
                "limit": 100,
                "format": "json"
            }
            res = requests.get(url, params=params, timeout=6).json()
            records = res.get("records", [])
            for r in records:
                if county_name in r.get("county", ""):
                    return {
                        "aqi": r.get("aqi", "40"),
                        "status": r.get("status", "普通"),
                        "pm25": r.get("pm2.5_avg", "15")
                    }
        except Exception:
            pass
    return {"aqi": "35", "status": "良好", "pm25": "10"}

# 4. 產生智慧生活指引
def generate_ai_advice(temp, rain_prob, humidity, aqi):
    advice = []
    
    # 穿搭指引
    if temp >= 28:
        advice.append("👕 **穿搭指引**：天氣炎熱，穿著排汗透氣短袖，戶外活動注意防曬。")
    elif 20 <= temp < 28:
        advice.append("👔 **穿搭指引**：體感舒適，穿著短袖搭配薄襯衫或薄外套即可。")
    else:
        advice.append("🧣 **穿搭指引**：氣溫偏低，建議穿著保暖長袖衣物或厚外套。")
    
    # 曬衣與防雨
    if rain_prob < 30 and humidity < 75:
        advice.append("🧺 **曬衣與防雨**：降雨機率低，非常適合戶外曬衣及戶外洗車。")
    elif rain_prob >= 50:
        advice.append("☔ **曬衣與防雨**：未來時段降雨機率偏高，外出請攜帶雨具，建議室內陰乾衣物。")
    else:
        advice.append("🌤️ **曬衣與防雨**：濕度稍高或有局部微雨可能，外出曬衣請留意天氣變化。")

    # 運動與空污
    try:
        aqi_val = int(aqi)
    except ValueError:
        aqi_val = 35

    if aqi_val > 100:
        advice.append("😷 **運動與空污**：空氣品質較差，敏感族群建議減少劇烈戶外運動並配戴口罩。")
    else:
        advice.append("🏃 **運動與空污**：空氣品質良好，非常適合跑步、騎車等各類戶外運動。")

    return advice

# --- 主畫面渲染 ---
st.title("🌤️ 台灣即時天氣看板 & 生活行動指南")

default_city = detect_user_location()
county_list = list(COUNTY_COORDS.keys())

selected_county = st.selectbox(
    "請選擇查詢區域：",
    options=county_list,
    index=county_list.index(default_city) if default_city in county_list else 0
)

lat, lon = COUNTY_COORDS[selected_county]

# 抓取天氣與 AQI
weather_data = fetch_weather(lat, lon)
aqi_data = fetch_air_quality(selected_county)

if weather_data:
    current = weather_data.get("current", {})
    current_temp = current.get("temperature_2m", 25.0)
    current_humidity = current.get("relative_humidity_2m", 60)

    hourly = weather_data.get("hourly", {})
    hourly_times = [t.split("T")[1] for t in hourly.get("time", [])[:6]]
    hourly_temps = hourly.get("temperature_2m", [])[:6]
    hourly_rain = hourly.get("precipitation_probability", [])[:6]
    current_rain_prob = hourly_rain[0] if hourly_rain else 10
else:
    current_temp = 24.0
    current_humidity = 65
    hourly_times = ["00:00", "01:00", "02:00", "03:00", "04:00", "05:00"]
    hourly_temps = [24.0] * 6
    hourly_rain = [10] * 6
    current_rain_prob = 10

# 上半部：地圖與指標排版
col_map, col_info = st.columns([1.1, 1.2])

with col_map:
    st.markdown(f"#### 📍 {selected_county} 區域標示")
    # 使用完全免費且無需 API Key 的 OpenStreetMap 底圖
    m = folium.Map(location=[lat, lon], zoom_start=11, tiles="OpenStreetMap")
    folium.Marker(
        [lat, lon],
        popup=f"{selected_county}",
        tooltip=f"{selected_county}：{current_temp}°C",
        icon=folium.Icon(color="blue", icon="info-sign")
    ).add_to(m)
    
    st_folium(m, width=550, height=380, returned_objects=[])

with col_info:
    st.markdown("#### 📊 即時觀測數據")
    c1, c2, c3 = st.columns(3)
    c1.metric("即時氣溫", f"{current_temp} °C")
    c2.metric("降雨機率", f"{current_rain_prob} %")
    c3.metric("空氣品質 (AQI)", f"{aqi_data['aqi']}")

    st.write("")
    st.markdown("#### 💡 智慧生活建議")
    advices = generate_ai_advice(current_temp, current_rain_prob, current_humidity, aqi_data["aqi"])
    for tip in advices:
        st.markdown(tip)

# 下半部：近 6 小時趨勢圖
st.divider()
st.markdown("#### ⏱️ 未來 6 小時氣溫與降雨趨勢")

chart_df = pd.DataFrame({
    "時間": hourly_times,
    "氣溫 (°C)": hourly_temps,
    "降雨機率 (%)": hourly_rain
}).set_index("時間")

st.line_chart(chart_df)

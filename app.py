import streamlit as st
import requests
import folium
from streamlit_folium import st_folium
import pandas as pd
from streamlit_js_eval import get_geolocation
import math

st.set_page_config(
    page_title="即時精準天氣與生活指南",
    page_icon="🌤️",
    layout="wide"
)

# -------------------------------------------------------------
# 1. 狀態管理 (儲存使用者的新增地點清單)
# -------------------------------------------------------------
DEFAULT_LOCATIONS = {
    "臺北市信義區": {"lat": 25.0330, "lon": 121.5654},
    "臺中市西區": {"lat": 24.1477, "lon": 120.6736},
    "高雄市苓雅區": {"lat": 22.6273, "lon": 120.3014},
    "花蓮縣花蓮市": {"lat": 23.9872, "lon": 121.6016}
}

if "custom_locations" not in st.session_state:
    st.session_state.custom_locations = DEFAULT_LOCATIONS.copy()

# -------------------------------------------------------------
# 2. GPS 經緯度反查地名 (Reverse Geocoding)
# -------------------------------------------------------------
@st.cache_data(ttl=86400)
def reverse_geocode(lat, lon):
    """傳入精準經緯度，反查中文鄉鎮市區名稱"""
    url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lon}&zoom=14&addressdetails=1"
    headers = {"User-Agent": "StreamlitWeatherApp/1.0"}
    try:
        res = requests.get(url, headers=headers, timeout=5).json()
        address = res.get("address", {})
        city = address.get("city") or address.get("county") or address.get("town") or ""
        suburb = address.get("suburb") or address.get("district") or address.get("town") or ""
        road = address.get("road") or ""
        
        display_name = f"{city}{suburb}".strip()
        if not display_name:
            display_name = f"目前精確位置 ({lat:.2f}, {lon:.2f})"
        return display_name
    except Exception:
        return f"我的所在位置 ({lat:.2f}, {lon:.2f})"

# -------------------------------------------------------------
# 3. 搜尋地點並轉換為經緯度 (Forward Geocoding)
# -------------------------------------------------------------
def search_location_coords(query):
    """使用者輸入地名（如「逢甲夜市」或「板橋車站」），自動找出經緯度"""
    url = f"https://nominatim.openstreetmap.org/search?format=json&q={query}&countrycodes=tw&limit=1"
    headers = {"User-Agent": "StreamlitWeatherApp/1.0"}
    try:
        res = requests.get(url, headers=headers, timeout=5).json()
        if res:
            return float(res[0]["lat"]), float(res[0]["lon"]), res[0]["display_name"].split(",")[0]
    except Exception:
        pass
    return None, None, None

# -------------------------------------------------------------
# 4. 氣象與天氣圖示資料
# -------------------------------------------------------------
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
    63: ("🌧️", "持續性降雨"),
    65: ("🌧️", "大雨來襲"),
    80: ("🌦️", "短暫陣雨"),
    81: ("🌧️", "強陣雨"),
    82: ("⛈️", "狂暴豪雨"),
    95: ("⛈️", "雷陣雨"),
    96: ("⛈️", "雷雨伴隨冰雹")
}

def get_weather_desc(code):
    return WEATHER_ICONS.get(code, ("🌤️", "多雲時晴"))

@st.cache_data(ttl=1800)
def fetch_weather(lat, lon):
    url = (
        f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
        f"&current=temperature_2m,relative_humidity_2m,weather_code,apparent_temperature"
        f"&hourly=temperature_2m,precipitation_probability,weather_code"
        f"&forecast_days=1&timezone=Asia%2FTaipei"
    )
    try:
        return requests.get(url, timeout=8).json()
    except Exception:
        return None

# 生活建議生成
def generate_ai_advice(temp, rain_prob, humidity):
    advice = []
    if temp >= 28:
        advice.append("🩳 **穿搭指引**：氣溫較高！建議穿著透氣涼爽排汗衫，戶外活動記得遮陽防曬。")
    elif 20 <= temp < 28:
        advice.append("👔 **穿搭指引**：體感舒適宜人，短袖加件薄襯衫或薄外套即可輕鬆出門。")
    else:
        advice.append("🧥 **穿搭指引**：早晚氣溫較涼，請務必搭配長袖外套或保暖衣物。")

    if rain_prob < 30 and humidity < 75:
        advice.append("🧺 **生活行動**：降雨機率低、相對乾燥，非常適合室外曬衣、洗車或戶外活動。")
    elif rain_prob >= 50:
        advice.append("☔ **外出提醒**：未來時段降雨機率高，出門請攜帶雨具，衣物建議室內陰乾。")
    else:
        advice.append("⛅ **生活行動**：濕度稍高或有局部陣雨，戶外活動建議備一把折傘。")

    return advice

# -------------------------------------------------------------
# 5. 側邊欄：搜尋、新增與編輯地點
# -------------------------------------------------------------
st.sidebar.title("📍 地點管理中心")

# 新增自訂地點
st.sidebar.markdown("### ➕ 新增關注地點")
new_loc_input = st.sidebar.text_input("輸入地名或地標（如：日月潭、板橋車站）：")
if st.sidebar.button("搜尋並加入清單"):
    if new_loc_input:
        with st.spinner("正在搜尋地標經緯度..."):
            s_lat, s_lon, formal_name = search_location_coords(new_loc_input)
            if s_lat and s_lon:
                key_name = f"{new_loc_input} ({formal_name})"
                st.session_state.custom_locations[key_name] = {"lat": s_lat, "lon": s_lon}
                st.sidebar.success(f"已成功加入：{key_name}！")
                st.rerun()
            else:
                st.sidebar.error("找不到該地點，請嘗試更完整的地名。")

# 刪除/管理自訂地點
if len(st.session_state.custom_locations) > 0:
    st.sidebar.markdown("### ⚙️ 管理與刪除地點")
    loc_to_remove = st.sidebar.selectbox("選擇要移除的地點：", list(st.session_state.custom_locations.keys()))
    if st.sidebar.button("🗑️ 刪除此地點"):
        del st.session_state.custom_locations[loc_to_remove]
        st.sidebar.warning(f"已移除：{loc_to_remove}")
        st.rerun()

# -------------------------------------------------------------
# 6. 主畫面：精確定位判斷與地點切換
# -------------------------------------------------------------
st.title("🌈 智慧即時天氣 & 精準生活指南")

# 獲取設備 GPS
location_info = get_geolocation()
current_gps_name = None

# 若瀏覽器回傳設備 GPS，直接加入清單第一位
if location_info and "coords" in location_info:
    user_lat = location_info["coords"]["latitude"]
    user_lon = location_info["coords"]["longitude"]
    current_gps_name = f"📍 目前設備所在位置 [{reverse_geocode(user_lat, user_lon)}]"
    
    # 動態將真實 GPS 座標掛進可選字典
    all_locations = {current_gps_name: {"lat": user_lat, "lon": user_lon}}
    all_locations.update(st.session_state.custom_locations)
else:
    all_locations = st.session_state.custom_locations

# 地點選擇下拉選單（預設選定設備精準位置）
location_keys = list(all_locations.keys())
selected_key = st.selectbox(
    "🗺️ 當前查看地點：",
    options=location_keys,
    index=0,
    help="首項為瀏覽器定位出的精確所在地，亦可在左側新增你關注的景點或常去區域"
)

target_coords = all_locations[selected_key]
lat, lon = target_coords["lat"], target_coords["lon"]

# -------------------------------------------------------------
# 7. 天氣數據獲取與主視窗渲染
# -------------------------------------------------------------
weather_data = fetch_weather(lat, lon)

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
    current_rain = hourly_rains[0] if hourly_rains else 0
else:
    temp, feels_like, humidity, icon, condition, current_rain = 25.0, 26.0, 60, "🌤️", "多雲時晴", 10
    hourly_times = ["12:00", "13:00", "14:00", "15:00", "16:00", "17:00"]
    hourly_temps = [25.0] * 6
    hourly_rains = [10] * 6
    hourly_codes = [1] * 6

# 上半部：地圖 + 氣象看板
col_map, col_details = st.columns([1.1, 1.2])

with col_map:
    st.markdown(f"#### 📍 地圖精確定位：{selected_key}")
    # 精準定位縮放級別設為 13~14，可以清楚看到周邊街區
    m = folium.Map(location=[lat, lon], zoom_start=13, tiles="OpenStreetMap")
    folium.Marker(
        [lat, lon],
        popup=f"{selected_key}：{temp}°C",
        tooltip=f"{selected_key} ({temp}°C)",
        icon=folium.Icon(color="red", icon="crosshairs", prefix="fa")
    ).add_to(m)
    st_folium(m, width=540, height=360, returned_objects=[])

with col_details:
    st.markdown(f"""
    <div style="background: linear-gradient(135deg, #4A00E0 0%, #8E2DE2 100%); padding: 18px; border-radius: 12px; color: white; margin-bottom: 15px;">
        <h2 style="margin: 0; color: white;">{icon} {condition} · {temp}°C</h2>
        <p style="margin: 5px 0 0 0; opacity: 0.9;">體感溫度 {feels_like}°C ｜ 空氣濕度 {humidity}% ｜ 經緯度 ({lat:.4f}, {lon:.4f})</p>
    </div>
    """, unsafe_allow_html=True)

    m1, m2 = st.columns(2)
    m1.metric("🌡️ 目前即時氣溫", f"{temp} °C", delta=f"體感 {feels_like}°C")
    m2.metric("💧 降雨機率", f"{current_rain} %")

    st.markdown("#### 💡 AI 智慧生活建議")
    advices = generate_ai_advice(temp, current_rain, humidity)
    for tip in advices:
        st.markdown(tip)

# 下半部：近 6 小時預報小卡 + 曲線圖
st.divider()
st.markdown("#### ⏱️ 未來 6 小時微氣候變化預測")

h_cols = st.columns(6)
for i in range(6):
    h_time = hourly_times[i]
    h_t = hourly_temps[i]
    h_r = hourly_rains[i]
    h_icon, _ = get_weather_desc(hourly_codes[i])
    with h_cols[i]:
        st.markdown(f"""
        <div style="border: 1px solid #ddd; border-radius: 8px; padding: 10px; text-align: center; background-color: #fafafa;">
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
    "降雨機率 (%)": hourly_rains
}).set_index("時間")

st.line_chart(chart_df)

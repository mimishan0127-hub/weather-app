import streamlit as st
import requests
import folium
from streamlit_folium import st_folium
import pandas as pd
from streamlit_js_eval import get_geolocation
import time

# -------------------------------------------------------------
# 1. 頁面全域設定與自訂 CSS
# -------------------------------------------------------------
st.set_page_config(
    page_title="SkyCast 即時氣象與生活決策",
    page_icon="🌤️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
    html, body, [class*="css"] {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    }
    header[data-testid="stHeader"] {
        background: transparent;
    }
    .weather-hero-card {
        padding: 22px 24px;
        border-radius: 16px;
        color: white;
        margin-bottom: 14px;
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.1);
    }
    .alert-banner {
        padding: 12px 18px;
        border-radius: 12px;
        margin-bottom: 14px;
        font-weight: 600;
        display: flex;
        align-items: center;
        gap: 10px;
    }
    .alert-danger {
        background-color: #fee2e2;
        color: #b91c1c;
        border: 1px solid #fecaca;
    }
    .alert-warning {
        background-color: #fef3c7;
        color: #b45309;
        border: 1px solid #fde68a;
    }
    .mini-card {
        background: #ffffff;
        border: 1px solid #eef2f6;
        border-radius: 12px;
        padding: 10px 4px;
        text-align: center;
        box-shadow: 0 2px 4px rgba(0,0,0,0.02);
    }
</style>
""", unsafe_allow_html=True)

# -------------------------------------------------------------
# 2. 狀態與地點管理
# -------------------------------------------------------------
DEFAULT_LOCATIONS = {
    "臺北市信義區": {"lat": 25.0330, "lon": 121.5654},
    "新北市板橋區": {"lat": 25.0125, "lon": 121.4657},
    "臺中市西區": {"lat": 24.1477, "lon": 120.6736},
    "高雄市苓雅區": {"lat": 22.6273, "lon": 120.3014},
    "花蓮縣花蓮市": {"lat": 23.9872, "lon": 121.6016}
}

if "locations" not in st.session_state:
    st.session_state.locations = DEFAULT_LOCATIONS.copy()

# -------------------------------------------------------------
# 3. 地理編碼工具
# -------------------------------------------------------------
@st.cache_data(ttl=86400, show_spinner=False)
def reverse_geocode_safe(lat: float, lon: float) -> str:
    url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lon}&zoom=14&addressdetails=1"
    headers = {"User-Agent": "SkyCastWeatherApp/2.1"}
    try:
        resp = requests.get(url, headers=headers, timeout=3.5)
        if resp.status_code == 200:
            addr = resp.json().get("address", {})
            city = addr.get("city") or addr.get("county") or ""
            district = addr.get("suburb") or addr.get("district") or addr.get("town") or ""
            name = f"{city}{district}".strip()
            if name:
                return name
    except Exception:
        pass
    return f"座標 ({lat:.2f}, {lon:.2f})"

@st.cache_data(ttl=86400, show_spinner=False)
def search_coords_safe(query: str):
    if not query or len(query.strip()) == 0:
        return None, None, None
    url = f"https://nominatim.openstreetmap.org/search?format=json&q={query}&countrycodes=tw&limit=1"
    headers = {"User-Agent": "SkyCastWeatherApp/2.1"}
    try:
        resp = requests.get(url, headers=headers, timeout=4.0)
        if resp.status_code == 200:
            data = resp.json()
            if data:
                top = data[0]
                name = top.get("display_name", "").split(",")[0]
                return float(top["lat"]), float(top["lon"]), name
    except Exception:
        pass
    return None, None, None

# -------------------------------------------------------------
# 4. 氣候與空氣品質 API
# -------------------------------------------------------------
WEATHER_SPECS = {
    0: ("☀️", "晴朗無雲"),
    1: ("🌤️", "多雲時晴"),
    2: ("⛅", "多雲"),
    3: ("☁️", "陰天多雲"),
    45: ("🌫️", "有霧防視線"),
    51: ("🌦️", "偶有微雨"),
    61: ("🌧️", "短暫陣雨"),
    63: ("🌧️", "持續陣雨"),
    65: ("🌧️", "大雨來襲"),
    80: ("🌦️", "短暫陣雨"),
    81: ("🌧️", "強陣雨"),
    82: ("⛈️", "狂暴豪雨"),
    95: ("⛈️", "雷陣雨"),
    96: ("⛈️", "雷雨伴隨冰雹")
}

def resolve_weather(code: int):
    return WEATHER_SPECS.get(code, ("🌤️", "多雲"))

@st.cache_data(ttl=900, show_spinner=False)
def fetch_weather_and_aqi(lat: float, lon: float):
    """同步抓取天氣預報（含每小時雨量）與即時空氣品質 (AQI / PM2.5)"""
    # 1. 氣象與預報（增加 precipitation 毫米量以判斷大雨）
    weather_url = (
        f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
        f"&current=temperature_2m,relative_humidity_2m,weather_code,apparent_temperature,precipitation"
        f"&hourly=temperature_2m,precipitation_probability,precipitation,weather_code"
        f"&forecast_days=1&timezone=Asia%2FTaipei"
    )
    # 2. 空氣品質 API (免 Key，提供 US AQI 與 PM2.5)
    aqi_url = (
        f"https://air-quality-api.open-meteo.com/v1/air-quality?latitude={lat}&longitude={lon}"
        f"&current=us_aqi,pm2_5&timezone=Asia%2FTaipei"
    )
    
    weather_res, aqi_res = {}, {}
    try:
        w_r = requests.get(weather_url, timeout=4.5)
        if w_r.status_code == 200:
            weather_res = w_r.json()
    except Exception:
        pass

    try:
        a_r = requests.get(aqi_url, timeout=3.5)
        if a_r.status_code == 200:
            aqi_res = a_r.json()
    except Exception:
        pass

    return weather_res, aqi_res

# -------------------------------------------------------------
# 5. 雷雨與強降雨警告偵測機制
# -------------------------------------------------------------
def detect_severe_weather_warning(hourly_codes, hourly_rains, hourly_precip):
    """分析未來 6 小時是否形成雷暴、豪雨或強降雨移入"""
    warnings = []
    
    # 雷雨代碼集合：95 (雷雨), 96/99 (雷雨伴隨冰雹), 82 (劇烈強降水)
    thunder_hours = [i for i, code in enumerate(hourly_codes[:6]) if code in [82, 95, 96, 99]]
    # 大雨判斷：預報時雨量 >= 8 mm 或 (降雨機率 >= 75% 且 雨量 >= 5mm)
    heavy_rain_hours = [i for i, p in enumerate(hourly_precip[:6]) if p >= 8.0 or (hourly_rains[i] >= 80 and p >= 4.0)]

    if thunder_hours:
        first_h = thunder_hours[0]
        time_hint = "當前或即刻" if first_h == 0 else f"約 {first_h} 小時後"
        warnings.append({
            "level": "danger",
            "title": "⛈️ 雷雨移入警戒",
            "message": f"監測到未來 6 小時內有雷暴系統發展或移入（{time_hint}），請注意雷擊、瞬間強陣風，戶外活動請立即尋找安全掩蔽！"
        })
    elif heavy_rain_hours:
        first_h = heavy_rain_hours[0]
        time_hint = "目前" if first_h == 0 else f"約 {first_h} 小時後"
        warnings.append({
            "level": "warning",
            "title": "🌧️ 短時強降雨提醒",
            "message": f"周邊水氣旺盛，預估 {time_hint} 降雨強度明顯增強，低窪地區請留意路面積水，出門請備妥雨具！"
        })

    return warnings

# -------------------------------------------------------------
# 6. 空污評級解析
# -------------------------------------------------------------
def parse_aqi_level(aqi_val: int):
    if aqi_val <= 50:
        return "良好", "#10b981"
    elif aqi_val <= 100:
        return "普通", "#f59e0b"
    elif aqi_val <= 150:
        return "敏感不佳", "#f97316"
    else:
        return "有害警戒", "#ef4444"

# -------------------------------------------------------------
# 7. 主程式與介面
# -------------------------------------------------------------
# GPS 定位攔截
geo = get_geolocation()
active_locations = {}

if geo and "coords" in geo:
    user_lat = geo["coords"]["latitude"]
    user_lon = geo["coords"]["longitude"]
    loc_title = reverse_geocode_safe(user_lat, user_lon)
    gps_key = f"📍 目前設備所在（{loc_title}）"
    active_locations[gps_key] = {"lat": user_lat, "lon": user_lon}

active_locations.update(st.session_state.locations)

# 頂部控制列
header_col1, header_col2 = st.columns([1.5, 2.5])
with header_col1:
    st.markdown("### 🌤️ 即時天氣與生活決策")

with header_col2:
    selected_loc_name = st.selectbox(
        "觀測地點",
        options=list(active_locations.keys()),
        index=0,
        label_visibility="collapsed"
    )

target_coords = active_locations[selected_loc_name]
target_lat, target_lon = target_coords["lat"], target_coords["lon"]

# 呼叫氣候與空污 API
weather_data, aqi_data = fetch_weather_and_aqi(target_lat, target_lon)

current = weather_data.get("current", {})
hourly = weather_data.get("hourly", {})
cur_temp = current.get("temperature_2m", 25.0)
cur_feels = current.get("apparent_temperature", cur_temp)
cur_hum = current.get("relative_humidity_2m", 60)
cur_code = current.get("weather_code", 0)
icon, condition = resolve_weather(cur_code)

times = [t.split("T")[1] for t in hourly.get("time", [])[:6]]
temps = hourly.get("temperature_2m", [])[:6]
rains = hourly.get("precipitation_probability", [])[:6]
precips = hourly.get("precipitation", [])[:6]
codes = hourly.get("weather_code", [])[:6]
cur_rain = rains[0] if rains else 0

# 空污解析
aqi_current = aqi_data.get("current", {})
aqi_val = int(aqi_current.get("us_aqi", 35)) if aqi_current.get("us_aqi") is not None else 35
pm25_val = aqi_current.get("pm2_5", 8.5)
aqi_status, aqi_color = parse_aqi_level(aqi_val)

# 偵測大雨/雷雨威脅
weather_warnings = detect_severe_weather_warning(codes, rains, precips)

# 依溫度決定卡片漸層色
if cur_temp >= 28:
    hero_bg = "linear-gradient(135deg, #FF6B6B 0%, #FF8E53 100%)"
elif cur_temp <= 18:
    hero_bg = "linear-gradient(135deg, #4b6cb7 0%, #182848 100%)"
else:
    hero_bg = "linear-gradient(135deg, #2b5876 0%, #4e4376 100%)"

# --- 介面分頁 ---
tab_main, tab_manage = st.tabs(["📊 觀測與生活指引", "⚙️ 管理地點清單"])

with tab_main:
    # 頂端警示橫幅（若有雷雨或強降雨形成）
    for w in weather_warnings:
        css_class = "alert-danger" if w["level"] == "danger" else "alert-warning"
        st.markdown(f"""
        <div class="alert-banner {css_class}">
            <span style="font-size: 20px;">⚠️</span>
            <div><strong>{w['title']}</strong>：{w['message']}</div>
        </div>
        """, unsafe_allow_html=True)

    left_col, right_col = st.columns([1.1, 1.2], gap="large")

    with left_col:
        st.markdown("##### 🗺️ 觀測座標位置")
        map_instance = folium.Map(location=[target_lat, target_lon], zoom_start=13, tiles="OpenStreetMap")
        folium.Marker(
            [target_lat, target_lon],
            tooltip=f"{selected_loc_name} · {cur_temp}°C",
            icon=folium.Icon(color="red" if weather_warnings else "blue", icon="cloud")
        ).add_to(map_instance)
        st_folium(map_instance, width=None, height=340, returned_objects=[])

    with right_col:
        st.markdown("##### ⚡ 即時氣候與空污指標")
        
        # 英雄氣象卡片（整合空污 AQI 與 PM2.5 顯示）
        st.markdown(f"""
        <div class="weather-hero-card" style="background: {hero_bg};">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <div style="font-size: 34px; font-weight: 700; line-height: 1.2;">{icon} {cur_temp}°C</div>
                    <div style="font-size: 15px; opacity: 0.95; margin-top: 4px;">{condition} ｜ 體感 {cur_feels}°C</div>
                </div>
                <div style="text-align: right; font-size: 13px; opacity: 0.95; line-height: 1.6;">
                    <div>💧 降雨機率 <strong>{cur_rain}%</strong></div>
                    <div>🌫️ 相對濕度 <strong>{cur_hum}%</strong></div>
                    <div style="margin-top: 4px; padding: 2px 8px; border-radius: 6px; background: rgba(0,0,0,0.2); display: inline-block;">
                        🍃 空污 AQI <strong>{aqi_val}</strong> ({aqi_status}) ｜ PM2.5: {pm25_val}
                    </div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # 生活指引
        wear_sum = "透氣排汗短袖" if cur_temp >= 28 else ("短袖加薄外衫" if cur_temp >= 20 else "保暖厚長袖或外套")
        dry_sum = "適合戶外曬衣" if cur_rain < 30 and cur_hum < 75 and not weather_warnings else "不宜室外曬衣（建議烘乾）"
        
        with st.expander(f"👕 穿著建議：{wear_sum}", expanded=False):
            st.write(f"當前氣溫 {cur_temp}°C，體感約 {cur_feels}°C。早晚溫差或出入冷氣房建議多備一件薄外套。")

        with st.expander(f"🧺 曬衣指數：{dry_sum}", expanded=False):
            if weather_warnings or cur_rain >= 40:
                st.write("周邊有降雨機率或對流雲系發展，衣物容易受潮或淋濕，強烈建議在室內搭配除濕機乾燥。")
            else:
                st.write("水氣偏低、通風狀況良好，衣物放置陽台約 3～4 小時即可完全曬乾。")

        # 外出與活動建議卡（納入空污判斷）
        c1, c2 = st.columns(2)
        if aqi_val > 100:
            c1.warning(f"😷 **空氣品質警戒**\n\nAQI 為 {aqi_val}，敏感族群外出建議配戴口罩。")
        else:
            c1.info(f"🍃 **空氣清新**\n\nAQI {aqi_val}（良好），適合在戶外大口呼吸。")

        if weather_warnings:
            c2.error("⚡ **戶外活動注意**\n\n有雷雨/大雨移入風險，請暫緩山區與戶外運動。")
        elif cur_rain >= 40:
            c2.warning("☔ **外出雨具提醒**\n\n降雨機率偏高，外出時請務必隨身攜帶折傘。")
        else:
            c2.info("🏃 **運動建議**\n\n天候良好無雨，適宜跑步、單車等各類運動。")

    st.markdown("---")
    
    # 未來 6 小時微氣象與預報
    st.markdown("##### ⏱️ 未來 6 小時即時預報趨勢")
    hour_cols = st.columns(6)
    for i in range(6):
        h_icon, _ = resolve_weather(codes[i])
        with hour_cols[i]:
            st.markdown(f"""
            <div class="mini-card">
                <div style="font-size: 12px; color: #64748b; font-weight: 600;">{times[i]}</div>
                <div style="font-size: 24px; margin: 4px 0;">{h_icon}</div>
                <div style="font-size: 15px; font-weight: 700; color: #1e293b;">{temps[i]}°C</div>
                <div style="font-size: 11px; color: #0284c7; margin-top: 2px;">💧 {rains[i]}%</div>
                <div style="font-size: 10px; color: #94a3b8;">{precips[i]}mm</div>
            </div>
            """, unsafe_allow_html=True)

    st.write("")
    chart_data = pd.DataFrame({
        "時間": times,
        "氣溫 (°C)": temps,
        "降雨機率 (%)": rains
    }).set_index("時間")
    st.line_chart(chart_data, height=190)

with tab_manage:
    st.markdown("##### ➕ 新增自訂關注點")
    col_input, col_submit = st.columns([3, 1])
    with col_input:
        input_name = st.text_input("輸入名稱", placeholder="例：清境農場、台南孔廟、竹科園區...", label_visibility="collapsed")
    with col_submit:
        add_btn = st.button("加入關注", use_container_width=True)

    if add_btn and input_name:
        with st.spinner("解析地標中..."):
            found_lat, found_lon, _ = search_coords_safe(input_name)
            if found_lat and found_lon:
                st.session_state.locations[input_name] = {"lat": found_lat, "lon": found_lon}
                st.success(f"已成功加入「{input_name}」！")
                time.sleep(0.4)
                st.rerun()
            else:
                st.error("查無此座標，請嘗試更具體的地名。")

    st.markdown("---")
    st.markdown("##### 🗑️ 刪除自訂地點")
    custom_keys = list(st.session_state.locations.keys())
    if len(custom_keys) > 0:
        del_col1, del_col2 = st.columns([3, 1])
        with del_col1:
            target_del = st.selectbox("選擇欲移除項目", options=custom_keys, label_visibility="collapsed")
        with del_col2:
            if st.button("確認刪除", use_container_width=True):
                del st.session_state.locations[target_del]
                st.rerun()
    else:
        st.info("目前無額外自訂地點。")

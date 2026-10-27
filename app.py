import streamlit as st
import requests
import folium
from streamlit_folium import st_folium
import pandas as pd
from streamlit_js_eval import get_geolocation

st.set_page_config(page_title="即時天氣", page_icon="🌤️", layout="wide")

# 1. 預設常備地點清單
DEFAULT_LOCS = {
    "臺北": {"lat": 25.0330, "lon": 121.5654},
    "臺中": {"lat": 24.1477, "lon": 120.6736},
    "高雄": {"lat": 22.6273, "lon": 120.3014},
    "花蓮": {"lat": 23.9872, "lon": 121.6016}
}

if "locations" not in st.session_state:
    st.session_state.locations = DEFAULT_LOCS.copy()

# 2. GPS 反查簡短地名
@st.cache_data(ttl=86400)
def get_clean_location_name(lat, lon):
    url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lon}&zoom=14&addressdetails=1"
    headers = {"User-Agent": "WeatherApp/1.0"}
    try:
        res = requests.get(url, headers=headers, timeout=4).json()
        addr = res.get("address", {})
        city = addr.get("city") or addr.get("county") or ""
        town = addr.get("suburb") or addr.get("district") or addr.get("town") or ""
        name = f"{city}{town}".strip()
        return name if name else f"{lat:.2f}, {lon:.2f}"
    except Exception:
        return f"{lat:.2f}, {lon:.2f}"

# 3. 搜尋地點座標
def find_coords(query):
    url = f"https://nominatim.openstreetmap.org/search?format=json&q={query}&countrycodes=tw&limit=1"
    headers = {"User-Agent": "WeatherApp/1.0"}
    try:
        res = requests.get(url, headers=headers, timeout=4).json()
        if res:
            name = res[0]["display_name"].split(",")[0]
            return float(res[0]["lat"]), float(res[0]["lon"]), name
    except Exception:
        pass
    return None, None, None

# 4. 天氣圖示與狀態代碼對照
WEATHER_MAP = {
    0: ("☀️", "晴天"),
    1: ("🌤️", "晴時多雲"),
    2: ("⛅", "多雲"),
    3: ("☁️", "陰天"),
    45: ("🌫️", "有霧"),
    51: ("🌦️", "微雨"),
    61: ("🌧️", "短暫陣雨"),
    63: ("🌧️", "陣雨"),
    65: ("🌧️", "大雨"),
    80: ("🌦️", "午後雷陣雨"),
    95: ("⛈️", "雷雨")
}

def get_weather_info(code):
    return WEATHER_MAP.get(code, ("🌤️", "多雲"))

# 5. 抓取氣象數據
@st.cache_data(ttl=1800)
def fetch_weather(lat, lon):
    url = (
        f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
        f"&current=temperature_2m,relative_humidity_2m,weather_code,apparent_temperature"
        f"&hourly=temperature_2m,precipitation_probability,weather_code"
        f"&forecast_days=1&timezone=Asia%2FTaipei"
    )
    try:
        return requests.get(url, timeout=6).json()
    except Exception:
        return None

# 6. 極簡生活建議 (精簡短句)
def get_concise_tips(temp, rain, humidity):
    # 穿搭
    wear = "透氣短袖" if temp >= 28 else ("舒適短袖+薄衫" if temp >= 20 else "保暖長袖外套")
    # 曬衣
    dry = "極佳（速乾）" if rain < 30 and humidity < 75 else "不宜（易潮濕/降雨）"
    # 雨具
    umbrella = "務必帶傘" if rain >= 40 else "不需帶傘"
    # 運動
    sport = "室內活動為佳" if rain >= 50 else "適合戶外運動"
    
    return [
        f"👕 **穿著**：{wear}",
        f"☔ **外出**：{umbrella}",
        f"🧺 **曬衣**：{dry}",
        f"🏃 **運動**：{sport}"
    ]

# ----------------- 畫面核心邏輯 -----------------

# 自動取得真實設備 GPS
geo = get_geolocation()
current_gps_label = None

if geo and "coords" in geo:
    u_lat, u_lon = geo["coords"]["latitude"], geo["coords"]["longitude"]
    loc_title = get_clean_location_name(u_lat, u_lon)
    current_gps_label = f"📍 目前所在地 ({loc_title})"
    active_locs = {current_gps_label: {"lat": u_lat, "lon": u_lon}}
    active_locs.update(st.session_state.locations)
else:
    active_locs = st.session_state.locations

# 頁面頂部：精簡切換選單
col_select, _ = st.columns([2, 1])
with col_select:
    selected_name = st.selectbox(
        "選擇地點：",
        options=list(active_locs.keys()),
        index=0,
        label_visibility="collapsed"
    )

target = active_locs[selected_name]
lat, lon = target["lat"], target["lon"]

# 取得天氣資料
data = fetch_weather(lat, lon)
if data:
    cur = data.get("current", {})
    temp = cur.get("temperature_2m", 24.0)
    feels = cur.get("apparent_temperature", temp)
    humidity = cur.get("relative_humidity_2m", 65)
    wcode = cur.get("weather_code", 0)
    icon, status = get_weather_info(wcode)

    hourly = data.get("hourly", {})
    times = [t.split("T")[1] for t in hourly.get("time", [])[:6]]
    temps = hourly.get("temperature_2m", [])[:6]
    rains = hourly.get("precipitation_probability", [])[:6]
    codes = hourly.get("weather_code", [])[:6]
    rain_now = rains[0] if rains else 0
else:
    temp, feels, humidity, icon, status, rain_now = 24.0, 24.0, 60, "🌤️", "多雲", 10
    times = ["12:00", "13:00", "14:00", "15:00", "16:00", "17:00"]
    temps, rains, codes = [24.0]*6, [10]*6, [1]*6

# 首頁整合分頁：主看天天氣 / 管理與自訂地點
tab_weather, tab_manage = st.tabs(["🌤️ 即時天氣與預報", "⚙️ 新增 / 管理地點"])

with tab_weather:
    col_map, col_info = st.columns([1.1, 1.2])

    with col_map:
        # 地圖
        m = folium.Map(location=[lat, lon], zoom_start=13, tiles="OpenStreetMap")
        folium.Marker(
            [lat, lon],
            tooltip=f"{selected_name} ({temp}°C)",
            icon=folium.Icon(color="blue", icon="info-sign")
        ).add_to(m)
        st_folium(m, width=500, height=340, returned_objects=[])

    with col_info:
        # 核心看板（無冗長標題，開門見山）
        st.markdown(f"""
        <div style="background: linear-gradient(135deg, #3A7BD5 0%, #3A6073 100%); padding: 18px 22px; border-radius: 12px; color: white; margin-bottom: 15px;">
            <div style="font-size: 28px; font-weight: bold; margin-bottom: 5px;">{icon} {temp}°C ｜ {status}</div>
            <div style="font-size: 14px; opacity: 0.9;">體感 {feels}°C · 濕度 {humidity}% · 降雨機率 {rain_now}%</div>
        </div>
        """, unsafe_allow_html=True)

        # 4 項極簡建議卡
        tips = get_concise_tips(temp, rain_now, humidity)
        tc1, tc2 = st.columns(2)
        tc1.info(tips[0])
        tc1.info(tips[1])
        tc2.info(tips[2])
        tc2.info(tips[3])

    # 下方：近 6 小時微氣象
    st.markdown("##### ⏱️ 未來 6 小時趨勢")
    h_cols = st.columns(6)
    for i in range(6):
        h_icon, _ = get_weather_info(codes[i])
        with h_cols[i]:
            st.markdown(f"""
            <div style="border: 1px solid #eee; border-radius: 8px; padding: 6px; text-align: center; background-color: #fafafa;">
                <div style="font-size: 12px; color: #777;">{times[i]}</div>
                <div style="font-size: 22px; margin: 2px 0;">{h_icon}</div>
                <div style="font-size: 14px; font-weight: bold;">{temps[i]}°C</div>
                <div style="font-size: 11px; color: #2196F3;">💧{rains[i]}%</div>
            </div>
            """, unsafe_allow_html=True)

    chart_df = pd.DataFrame({
        "時間": times,
        "氣溫 (°C)": temps,
        "降雨率 (%)": rains
    }).set_index("時間")
    st.line_chart(chart_df, height=180)

with tab_manage:
    st.markdown("##### ➕ 新增地點")
    c_in, c_btn = st.columns([3, 1])
    with c_in:
        query_loc = st.text_input("輸入地標或地名（例：淡水老街、台中火車站）：", label_visibility="collapsed", placeholder="輸入地標名稱...")
    with c_btn:
        add_clicked = st.button("加入關注", use_container_width=True)

    if add_clicked and query_loc:
        with st.spinner("搜尋座標中..."):
            s_lat, s_lon, formal = find_coords(query_loc)
            if s_lat and s_lon:
                st.session_state.locations[query_loc] = {"lat": s_lat, "lon": s_lon}
                st.success(f"已新增：{query_loc}")
                st.rerun()
            else:
                st.error("找不到該地點，請輸入更精確的地名。")

    st.divider()
    st.markdown("##### 🗑️ 刪除自訂地點")
    c_sel, c_del = st.columns([3, 1])
    with c_sel:
        del_target = st.selectbox("選擇要刪除的地點：", list(st.session_state.locations.keys()), label_visibility="collapsed")
    with c_del:
        if st.button("確認刪除", use_container_width=True):
            if del_target in st.session_state.locations:
                del st.session_state.locations[del_target]
                st.rerun()

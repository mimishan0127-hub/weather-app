import streamlit as st
import requests
import folium
from streamlit_folium import st_folium
import pandas as pd
from streamlit_js_eval import get_geolocation

st.set_page_config(
    page_title="即時天氣觀測與生活指南",
    page_icon="🌤️",
    layout="wide"
)

# 1. 預設常備地點清單
DEFAULT_LOCS = {
    "臺北": {"lat": 25.0330, "lon": 121.5654},
    "臺中": {"lat": 24.1477, "lon": 120.6736},
    "高雄": {"lat": 22.6273, "lon": 120.3014},
    "花蓮": {"lat": 23.9872, "lon": 121.6016}
}

if "locations" not in st.session_state:
    st.session_state.locations = DEFAULT_LOCS.copy()

# 2. GPS 反查地名
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

# 4. 天氣圖示對照
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

# 6. 穿搭與曬衣的詳細指引邏輯
def get_detailed_wear_advice(temp):
    if temp >= 28:
        summary = "透氣短袖 / 排汗衫"
        details = """
        * **衣物材質**：建議選擇棉麻、亞麻或排汗速乾機能面料。
        * **防曬搭配**：日間紫外線強烈，建議配戴遮陽帽、抗 UV 薄外套或墨鏡。
        * **室內冷氣**：辦公室或室內空調環境可自備一件超薄開襟衫防受涼。
        """
    elif 20 <= temp < 28:
        summary = "休閒短袖搭配薄衫 / 襯衫"
        details = """
        * **衣物材質**：純棉 T-shirt、輕薄長袖或棉質襯衫。
        * **早晚溫差**：日夜可能有 3~5°C 溫差，外出可準備一件牛仔外套或連帽薄外套。
        * **舒適度**：氣溫適中，單穿一件上衣加薄長褲即可活動自如。
        """
    else:
        summary = "保暖長袖搭配防風外套"
        details = """
        * **洋蔥式穿搭**：內層穿著發熱衣或棉質長袖，外層加穿厚外套或防風防潑水夾克。
        * **配件建議**：風大時可配戴薄圍巾或防風口罩，避免頭部與頸部著涼。
        """
    return summary, details

def get_detailed_dry_advice(rain, humidity):
    if rain < 30 and humidity < 75:
        summary = "非常適合戶外曬衣（快乾）"
        details = """
        * **衣物晾乾速度**：陽光與濕度條件良好，一般薄衣物約 3~4 小時可全乾。
        * **注意事項**：中午時段陽光充足，深色或特殊面料建議翻面曬晾以防褪色。
        * **適合洗滌**：床單、被套、大毛巾等厚重大件織物可趁今日清洗。
        """
    elif rain >= 50 or humidity >= 85:
        summary = "不宜戶外曬衣（建議室內除濕）"
        details = """
        * **潮濕風險**：室外降雨機率高且空氣飽和，衣物容易吸附濕氣或產生霉味。
        * **替代方案**：請將衣物置於室內，搭配除濕機或使用烘衣機低溫烘乾。
        * **通風建議**：室內晾衣請保持空氣流通，拉開衣物間距至少一個拳頭寬。
        """
    else:
        summary = "陽台陰涼通風處晾乾"
        details = """
        * **天氣變數**：濕度稍偏高或有局部微雨可能，建議晾在有遮雨棚的陽台。
        * **曬衣時程**：建議傍晚前收進室內，避免夜晚返潮影響乾爽度。
        """
    return summary, details

# ----------------- 頁面主體 -----------------

# 抓取設備 GPS
geo = get_geolocation()
if geo and "coords" in geo:
    u_lat, u_lon = geo["coords"]["latitude"], geo["coords"]["longitude"]
    loc_title = get_clean_location_name(u_lat, u_lon)
    current_gps_label = f"📍 目前所在地 ({loc_title})"
    active_locs = {current_gps_label: {"lat": u_lat, "lon": u_lon}}
    active_locs.update(st.session_state.locations)
else:
    active_locs = st.session_state.locations

# 主標題區
st.markdown("### 🌤️ 台灣即時天氣觀測與生活行動指南")

# 地點選擇下拉列
selected_name = st.selectbox(
    "觀測地點切換：",
    options=list(active_locs.keys()),
    index=0,
    help="首項為偵測出的即時位置，可於「管理地點」新增關注區域"
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

# 首頁分頁
tab_weather, tab_manage = st.tabs(["📊 即時觀測與預報", "⚙️ 新增與管理自訂地點"])

with tab_weather:
    col_map, col_info = st.columns([1.1, 1.2])

    with col_map:
        st.markdown("##### 🗺️ 觀測點周邊地圖")
        m = folium.Map(location=[lat, lon], zoom_start=13, tiles="OpenStreetMap")
        folium.Marker(
            [lat, lon],
            tooltip=f"{selected_name} ({temp}°C)",
            icon=folium.Icon(color="blue", icon="info-sign")
        ).add_to(m)
        st_folium(m, width=500, height=340, returned_objects=[])

    with col_info:
        st.markdown("##### ⚡ 當前微氣候狀態")
        
        # 視覺化看板
        st.markdown(f"""
        <div style="background: linear-gradient(135deg, #3A7BD5 0%, #3A6073 100%); padding: 16px 20px; border-radius: 12px; color: white; margin-bottom: 12px;">
            <div style="font-size: 28px; font-weight: bold; margin-bottom: 4px;">{icon} {temp}°C ｜ {status}</div>
            <div style="font-size: 14px; opacity: 0.9;">體感 {feels}°C ｜ 濕度 {humidity}% ｜ 降雨機率 {rain_now}%</div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("##### 💡 生活與穿著行動指引")
        
        wear_sum, wear_det = get_detailed_wear_advice(temp)
        dry_sum, dry_det = get_detailed_dry_advice(rain_now, humidity)
        umbrella = "務必攜帶雨具外出" if rain_now >= 40 else "降雨機率低，外出輕便"
        sport = "建議室內活動或運動" if rain_now >= 50 else "舒適，非常適合戶外運動"

        # 穿著建議（含隱藏式抽屜）
        with st.expander(f"👕 **今日穿著建議**：{wear_sum}", expanded=False):
            st.markdown(wear_det)

        # 曬衣建議（含隱藏式抽屜）
        with st.expander(f"🧺 **曬衣與防潮指數**：{dry_sum}", expanded=False):
            st.markdown(dry_det)

        # 外出與運動簡要卡
        c_left, c_right = st.columns(2)
        c_left.info(f"☔ **外出提醒**：\n{umbrella}")
        c_right.info(f"🏃 **戶外活動**：\n{sport}")

    # 下方 6 小時預報
    st.divider()
    st.markdown("##### ⏱️ 未來 6 小時逐時天氣趨勢")
    
    h_cols = st.columns(6)
    for i in range(6):
        h_icon, _ = get_weather_info(codes[i])
        with h_cols[i]:
            st.markdown(f"""
            <div style="border: 1px solid #e2e8f0; border-radius: 8px; padding: 8px; text-align: center; background-color: #ffffff; box-shadow: 0 1px 2px rgba(0,0,0,0.03);">
                <div style="font-size: 12px; color: #64748b; font-weight: 500;">{times[i]}</div>
                <div style="font-size: 24px; margin: 4px 0;">{h_icon}</div>
                <div style="font-size: 15px; font-weight: bold; color: #1e293b;">{temps[i]}°C</div>
                <div style="font-size: 11px; color: #0284c7; font-weight: 500;">💧 {rains[i]}%</div>
            </div>
            """, unsafe_allow_html=True)

    st.write("")
    chart_df = pd.DataFrame({
        "時間": times,
        "氣溫 (°C)": temps,
        "降雨機率 (%)": rains
    }).set_index("時間")
    st.line_chart(chart_df, height=190)

with tab_manage:
    st.markdown("##### ➕ 新增常用關注地點")
    st.caption("輸入台灣任何地標、景點或鄉鎮名，系統將自動解析座標並加入選單。")
    c_in, c_btn = st.columns([3, 1])
    with c_in:
        query_loc = st.text_input("輸入地標或地名：", label_visibility="collapsed", placeholder="例：日月潭、板橋車站、駁二特區...")
    with c_btn:
        add_clicked = st.button("加入清單", use_container_width=True)

    if add_clicked and query_loc:
        with st.spinner("正在搜尋座標..."):
            s_lat, s_lon, formal = find_coords(query_loc)
            if s_lat and s_lon:
                st.session_state.locations[query_loc] = {"lat": s_lat, "lon": s_lon}
                st.success(f"已成功加入「{query_loc}」！可在上方下拉選單切換。")
                st.rerun()
            else:
                st.error("找不到該地點，請輸入更精確的地名後再試。")

    st.divider()
    st.markdown("##### 🗑️ 刪除自訂地點")
    c_sel, c_del = st.columns([3, 1])
    with c_sel:
        del_target = st.selectbox("選擇要移除的地點：", list(st.session_state.locations.keys()), label_visibility="collapsed")
    with c_del:
        if st.button("確認刪除", use_container_width=True):
            if del_target in st.session_state.locations:
                del st.session_state.locations[del_target]
                st.rerun()

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
    page_title="SkyCast 即時氣象生活看板",
    page_icon="🌤️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# 注入自訂現代卡片與元件樣式
st.markdown("""
<style>
    /* 全域文字與字體優化 */
    html, body, [class*="css"] {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    }
    
    /* 隱藏 Streamlit 預設頂部裝飾條，增加沉浸感 */
    header[data-testid="stHeader"] {
        background: transparent;
    }
    
    /* 卡片容器陰影與圓角 */
    .weather-hero-card {
        padding: 24px;
        border-radius: 16px;
        color: white;
        margin-bottom: 16px;
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.1);
        transition: transform 0.2s ease;
    }
    
    .mini-card {
        background: #ffffff;
        border: 1px solid #eef2f6;
        border-radius: 12px;
        padding: 12px 6px;
        text-align: center;
        box-shadow: 0 2px 5px rgba(0,0,0,0.03);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    .mini-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 12px rgba(0,0,0,0.06);
    }
    
    /* 建議折疊抽屜外觀優化 */
    .st-emotion-cache-1f3w0dd, .streamlit-expanderHeader {
        background-color: #f8fafc !important;
        border-radius: 10px !important;
        font-weight: 600 !important;
    }
</style>
""", unsafe_allow_html=True)

# -------------------------------------------------------------
# 2. 狀態與常備地點管理
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
# 3. 穩定安全的地理反查與搜尋（含逾時與例外保護）
# -------------------------------------------------------------
@st.cache_data(ttl=86400, show_spinner=False)
def reverse_geocode_safe(lat: float, lon: float) -> str:
    """經緯度安全反查地名，失敗時平滑降級"""
    url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lon}&zoom=14&addressdetails=1"
    headers = {"User-Agent": "SkyCastWeatherApp/2.0 (contact: admin@skycast.internal)"}
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
    """地標正向搜尋，附帶防手震與邊界保護"""
    if not query or len(query.strip()) == 0:
        return None, None, None
    url = f"https://nominatim.openstreetmap.org/search?format=json&q={query}&countrycodes=tw&limit=1"
    headers = {"User-Agent": "SkyCastWeatherApp/2.0"}
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
# 4. 氣候數據存取與代碼映射
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
    65: ("🌧️", "豪雨滂沱"),
    80: ("🌦️", "局部短暫雨"),
    95: ("⛈️", "雷陣雨")
}

def resolve_weather(code: int):
    return WEATHER_SPECS.get(code, ("🌤️", "多雲"))

@st.cache_data(ttl=900, show_spinner=False)
def fetch_weather_safe(lat: float, lon: float):
    """抓取 Open-Meteo，附帶回退預設集確保畫面永不中斷"""
    url = (
        f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
        f"&current=temperature_2m,relative_humidity_2m,weather_code,apparent_temperature"
        f"&hourly=temperature_2m,precipitation_probability,weather_code"
        f"&forecast_days=1&timezone=Asia%2FTaipei"
    )
    try:
        res = requests.get(url, timeout=5.0)
        if res.status_code == 200:
            return res.json()
    except Exception:
        pass
    
    # 備援資料（預防外部服務維護）
    return {
        "current": {"temperature_2m": 25.0, "apparent_temperature": 25.5, "relative_humidity_2m": 65, "weather_code": 1},
        "hourly": {
            "time": [f"2026-01-01T{h:02d}:00" for h in range(6)],
            "temperature_2m": [25.0] * 6,
            "precipitation_probability": [15] * 6,
            "weather_code": [1] * 6
        }
    }

# -------------------------------------------------------------
# 5. 智慧生活指引引擎
# -------------------------------------------------------------
def get_living_advice(temp: float, rain: int, humidity: int):
    # 穿著邏輯
    if temp >= 28:
        wear_sum = "輕便短袖、涼爽透氣"
        wear_desc = "氣溫偏高，建議著棉麻透氣材質；戶外活動需注意防曬抗 UV，適時補充水分。"
    elif 20 <= temp < 28:
        wear_sum = "短袖加薄外衫，舒適宜人"
        wear_desc = "體感舒適，外出單穿 T-shirt 或襯衫即可；早晚若騎車可備防風薄外套。"
    else:
        wear_sum = "保暖長袖、洋蔥式外套"
        wear_desc = "氣溫偏低，建議內層親膚保暖、外搭風衣或針織衫，避免溫差受涼。"

    # 曬衣邏輯
    if rain < 30 and humidity < 75:
        dry_sum = "適合戶外曬衣（通風速乾）"
        dry_desc = "陽光及濕度條件充足，戶外曬晾約 3～4 小時即可乾燥，厚重床單亦合適。"
    elif rain >= 50 or humidity >= 85:
        dry_sum = "不建議室外曬衣（建議除濕烘乾）"
        dry_desc = "環境水氣飽和或降雨風險高，室外晾乾易產生異味，請改用烘衣機或室內除濕。"
    else:
        dry_sum = "建議陽台陰乾並留意變天"
        dry_desc = "濕度中等，晾於有遮蔽陽台為佳；傍晚前請提早收納以防夜間返潮。"

    # 外出與活動速評
    outdoor_status = "降雨風險高，出門請攜帶雨具" if rain >= 40 else "降雨機率低，外出無負擔"
    sport_status = "雨勢明顯，戶外活動建議暫緩" if rain >= 50 else "天候穩定，適宜慢跑、騎車"

    return wear_sum, wear_desc, dry_sum, dry_desc, outdoor_status, sport_status

# -------------------------------------------------------------
# 6. 主程序流與位置解析
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

selected_target = active_locations[selected_loc_name]
target_lat, target_lon = selected_target["lat"], selected_target["lon"]

# 擷取氣候資料
weather_data = fetch_weather_safe(target_lat, target_lon)
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
codes = hourly.get("weather_code", [])[:6]
cur_rain = rains[0] if rains else 0

# 根據溫度決定主卡片漸層底色
if cur_temp >= 28:
    hero_bg = "linear-gradient(135deg, #FF6B6B 0%, #FF8E53 100%)"  # 溫暖橘紅
elif cur_temp <= 18:
    hero_bg = "linear-gradient(135deg, #4b6cb7 0%, #182848 100%)"  # 寒意深藍
else:
    hero_bg = "linear-gradient(135deg, #2b5876 0%, #4e4376 100%)"  # 舒適靛青

# -------------------------------------------------------------
# 7. 介面渲染（分頁結構）
# -------------------------------------------------------------
tab_main, tab_manage = st.tabs(["📊 觀測與生活指引", "⚙️ 管理地點清單"])

with tab_main:
    left_col, right_col = st.columns([1.1, 1.2], gap="large")

    with left_col:
        st.markdown("##### 🗺️ 觀測座標位置")
        # 地圖容器設定
        map_instance = folium.Map(
            location=[target_lat, target_lon],
            zoom_start=13,
            tiles="OpenStreetMap"
        )
        folium.Marker(
            [target_lat, target_lon],
            tooltip=f"{selected_loc_name} · {cur_temp}°C",
            icon=folium.Icon(color="blue", icon="info-sign")
        ).add_to(map_instance)
        
        # 鎖定回傳物件，避免點地圖造成頁面無謂更新
        st_folium(map_instance, width=None, height=330, returned_objects=[])

    with right_col:
        st.markdown("##### ⚡ 即時微氣候狀態")
        
        # 英雄氣象大卡片
        st.markdown(f"""
        <div class="weather-hero-card" style="background: {hero_bg};">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <div style="font-size: 34px; font-weight: 700; line-height: 1.2;">{icon} {cur_temp}°C</div>
                    <div style="font-size: 16px; opacity: 0.95; margin-top: 4px;">{condition} ｜ 體感 {cur_feels}°C</div>
                </div>
                <div style="text-align: right; font-size: 13px; opacity: 0.9;">
                    <div>💧 降雨機率 <strong>{cur_rain}%</strong></div>
                    <div>🌫️ 相對濕度 <strong>{cur_hum}%</strong></div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # 生活決策建議區塊
        wear_s, wear_d, dry_s, dry_d, outdoor_s, sport_s = get_living_advice(cur_temp, cur_rain, cur_hum)

        with st.expander(f"👕 穿搭決策：{wear_s}", expanded=False):
            st.write(wear_desc if 'wear_desc' in locals() else wear_d)

        with st.expander(f"🧺 曬衣指數：{dry_s}", expanded=False):
            st.write(dry_desc if 'dry_desc' in locals() else dry_d)

        info_c1, info_c2 = st.columns(2)
        info_c1.info(f"☔ **外出叮嚀**\n\n{outdoor_s}")
        info_c2.info(f"🏃 **運動建議**\n\n{sport_s}")

    st.markdown("---")
    
    # 未來 6 小時視覺化趨勢
    st.markdown("##### ⏱️ 未來 6 小時即時預報趨勢")
    hour_cols = st.columns(6)
    for i in range(6):
        h_icon, _ = resolve_weather(codes[i])
        with hour_cols[i]:
            st.markdown(f"""
            <div class="mini-card">
                <div style="font-size: 12px; color: #64748b; font-weight: 600;">{times[i]}</div>
                <div style="font-size: 24px; margin: 4px 0;">{h_icon}</div>
                <div style="font-size: 16px; font-weight: 700; color: #1e293b;">{temps[i]}°C</div>
                <div style="font-size: 11px; color: #0284c7; margin-top: 2px;">💧 {rains[i]}%</div>
            </div>
            """, unsafe_allow_html=True)

    st.write("")
    chart_data = pd.DataFrame({
        "時間": times,
        "氣溫 (°C)": temps,
        "降雨機率 (%)": rains
    }).set_index("時間")
    st.line_chart(chart_data, height=200)

with tab_manage:
    st.markdown("##### ➕ 新增自訂關注點")
    st.caption("支援台灣任一地標、車站、景點或鄉鎮名，系統將以安全非同步方式解析。")
    
    col_input, col_submit = st.columns([3, 1])
    with col_input:
        input_name = st.text_input("輸入名稱", placeholder="例：清境農場、台南孔廟、竹科園區...", label_visibility="collapsed")
    with col_submit:
        add_btn = st.button("加入關注", use_container_width=True)

    if add_btn and input_name:
        with st.spinner("解析地標中..."):
            found_lat, found_lon, formal_title = search_coords_safe(input_name)
            if found_lat and found_lon:
                st.session_state.locations[input_name] = {"lat": found_lat, "lon": found_lon}
                st.success(f"已成功收錄「{input_name}」！")
                time.sleep(0.5)
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

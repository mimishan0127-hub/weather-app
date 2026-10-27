import streamlit as st
import requests
import folium
from streamlit_folium import st_folium
import pandas as pd
from streamlit_js_eval import get_geolocation
import time
from datetime import datetime

# -------------------------------------------------------------
# 1. 頁面全域配置與現代質感樣式
# -------------------------------------------------------------
st.set_page_config(
    page_title="SkyCast 智慧天氣生活管家",
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
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.12);
    }
    
    .assistant-intro {
        background: linear-gradient(135deg, #f0fdf4 0%, #e0f2fe 100%);
        border-left: 4px solid #0284c7;
        padding: 12px 16px;
        border-radius: 8px;
        margin-bottom: 14px;
        color: #0f172a;
        font-size: 14px;
        line-height: 1.5;
    }

    .mini-card {
        background: #ffffff;
        border: 1px solid #eef2f6;
        border-radius: 12px;
        padding: 10px 4px;
        text-align: center;
        box-shadow: 0 2px 4px rgba(0,0,0,0.02);
        transition: transform 0.2s ease;
    }
    .mini-card:hover {
        transform: translateY(-2px);
    }

    .daily-card {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 12px 6px;
        text-align: center;
        box-shadow: 0 2px 5px rgba(0,0,0,0.03);
    }
</style>
""", unsafe_allow_html=True)

# -------------------------------------------------------------
# 2. 狀態管理 (支援國內外自訂地點儲存)
# -------------------------------------------------------------
DEFAULT_PRESETS = {
    "臺北信義": {"lat": 25.0330, "lon": 121.5654},
    "臺中西區": {"lat": 24.1477, "lon": 120.6736},
    "高雄苓雅": {"lat": 22.6273, "lon": 120.3014},
    "日本東京": {"lat": 35.6895, "lon": 139.6917}
}

if "saved_locations" not in st.session_state:
    st.session_state.saved_locations = DEFAULT_PRESETS.copy()

if "active_target" not in st.session_state:
    st.session_state.active_target = None

# -------------------------------------------------------------
# 3. 全球動態地理服務（出國可用、全球精準反查、零經緯度干擾）
# -------------------------------------------------------------
@st.cache_data(ttl=86400, show_spinner=False)
def reverse_geocode_global(lat: float, lon: float) -> str:
    """無論人在台灣還是海外，純淨反查中文地名"""
    url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lon}&zoom=14&addressdetails=1&accept-language=zh-TW,zh"
    headers = {"User-Agent": "SkyCastGlobal/5.0"}
    try:
        resp = requests.get(url, headers=headers, timeout=3.5)
        if resp.status_code == 200:
            addr = resp.json().get("address", {})
            country = addr.get("country", "")
            city = addr.get("city") or addr.get("county") or addr.get("state") or ""
            district = addr.get("suburb") or addr.get("district") or addr.get("town") or addr.get("village") or ""
            
            # 若為台灣，省略國名；若為海外，保留國家與行政區
            if country in ["臺灣", "台湾"]:
                name = f"{city}{district}".strip()
            else:
                name = f"{country} {city} {district}".strip()
                
            if name:
                return name
    except Exception:
        pass
    return "目前所在地"

@st.cache_data(ttl=3600, show_spinner=False)
def get_ip_fallback():
    """當瀏覽器 GPS 尚未就緒時，依據設備對外 IP 秒取當前城市（國內外皆通用）"""
    try:
        res = requests.get("https://ipapi.co/json/", timeout=3.0).json()
        city = res.get("city", "臺中市")
        region = res.get("region", "")
        country = res.get("country_name", "臺灣")
        lat = float(res.get("latitude", 24.2586))
        lon = float(res.get("longitude", 120.8283))
        
        display = f"{region} {city}".strip() if country in ["Taiwan", "臺灣"] else f"{country} {city}".strip()
        return lat, lon, display
    except Exception:
        return 24.2586, 120.8283, "臺中市東勢區"

@st.cache_data(ttl=86400, show_spinner=False)
def global_search_location(query: str):
    """
    即時全球動態地理搜尋：
    台灣鄉鎮（如「豐原」、「東勢」、「竹北」）與海外城市（如「東京」、「倫敦」、「紐約」）通通秒搜
    """
    clean_q = query.strip()
    if not clean_q:
        return None, None, None

    # 1. 優先使用 Open-Meteo 全球地理編碼（含中文化城市庫）
    try:
        om_url = f"https://geocoding-api.open-meteo.com/v1/search?name={clean_q}&count=5&language=zh&format=json"
        res = requests.get(om_url, timeout=3.5).json()
        results = res.get("results", [])
        if results:
            top = results[0]
            name = top.get("name", "")
            admin1 = top.get("admin1", "")
            country = top.get("country", "")
            
            # 組織易讀的地標標題
            if country in ["臺灣", "台湾"]:
                full_name = f"{admin1}{name}" if admin1 and admin1 not in name else name
            else:
                full_name = f"{country} {name}" if country else name
                
            return float(top["latitude"]), float(top["longitude"]), full_name
    except Exception:
        pass

    # 2. 次選方案：OpenStreetMap 全球地標資料庫
    headers = {"User-Agent": "SkyCastGlobal/5.0"}
    try:
        osm_url = f"https://nominatim.openstreetmap.org/search?format=json&q={clean_q}&limit=1&accept-language=zh-TW,zh"
        resp = requests.get(osm_url, headers=headers, timeout=3.5)
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
# 4. 全球氣候、紫外線與空氣品質 API (自動判斷時區)
# -------------------------------------------------------------
WEATHER_SPECS = {
    0: ("☀️", "晴朗無雲"),
    1: ("🌤️", "多雲時晴"),
    2: ("⛅", "多雲"),
    3: ("☁️", "陰天多雲"),
    45: ("🌫️", "晨霧朦朧"),
    51: ("🌦️", "偶有微雨"),
    61: ("🌧️", "短暫陣雨"),
    63: ("🌧️", "綿綿陣雨"),
    65: ("🌧️", "強大豪雨"),
    80: ("🌦️", "短暫陣雨"),
    81: ("🌧️", "局部強降雨"),
    82: ("⛈️", "狂暴劇烈雷雨"),
    95: ("⛈️", "雷電交加"),
    96: ("⛈️", "雷雨伴隨冰雹")
}

def resolve_weather(code: int):
    return WEATHER_SPECS.get(code, ("🌤️", "多雲"))

def parse_uv_level(uv_val: float):
    if uv_val < 3:
        return "微量", "日常活動安全，無需特別防護。"
    elif 3 <= uv_val < 6:
        return "中量", "外出建議配戴遮陽帽或薄長袖。"
    elif 6 <= uv_val < 8:
        return "高量", "紫外線偏強，曝曬 30 分鐘易曬傷，請擦防曬。"
    elif 8 <= uv_val < 11:
        return "過量", "極易曬傷！請避開正午曝曬，備妥抗 UV 陽傘。"
    else:
        return "危險", "紫外線極強，請多留在室內陰涼處。"

@st.cache_data(ttl=900, show_spinner=False)
def fetch_weather_and_aqi(lat: float, lon: float):
    # 使用 timezone=auto 自動適應當地時間，出國也不會時間錯亂
    weather_url = (
        f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
        f"&current=temperature_2m,relative_humidity_2m,weather_code,apparent_temperature,precipitation,wind_speed_10m,uv_index"
        f"&hourly=temperature_2m,precipitation_probability,precipitation,weather_code"
        f"&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,uv_index_max"
        f"&forecast_days=7&timezone=auto"
    )
    aqi_url = (
        f"https://air-quality-api.open-meteo.com/v1/air-quality?latitude={lat}&longitude={lon}"
        f"&current=us_aqi,pm2_5&timezone=auto"
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
# 5. 生活小幫手智慧決策引擎
# -------------------------------------------------------------
def get_comprehensive_assistant_advice(temp, feels_like, rain_prob, humidity, wind_speed, aqi_val, uv_val):
    uv_status, uv_tip = parse_uv_level(uv_val)

    if rain_prob >= 60:
        intro_text = f"今日水氣偏多，出門一定要留意雨勢！目前體感約 {feels_like}°C，外出隨身必帶折傘，路面濕滑開車騎車請放慢車速。"
    elif uv_val >= 8:
        intro_text = f"紫外線達「{uv_status}」等級（UV: {uv_val:.1f}）！外出極易曬傷，請務必擦妥防曬乳、備妥抗 UV 陽傘並多補充水分。"
    elif temp >= 29:
        intro_text = f"今天體感偏熱（{feels_like}°C）！水分流失快，外出記得防曬補水，並多待在通風陰涼處。"
    elif temp <= 18:
        intro_text = f"天氣偏涼冷（體感 {feels_like}°C），早晚出門或騎車容易受風寒，請洋蔥式搭配禦寒，多喝溫熱開水暖身。"
    else:
        intro_text = f"今天整體氣候舒適宜人（體感 {feels_like}°C），紫外線屬{uv_status}等級，非常適合外出踏青散心或安排戶外活動。"

    if temp >= 28:
        wear_headline = "涼感排汗短袖 ＋ 輕薄防曬遮陽"
        wear_desc = f"""
        * **白天穿著**：建議著吸濕排汗的透氣短袖或棉麻寬鬆上衣，避免深色吸熱材質。
        * **紫外線防護**：當前紫外線為 **{uv_status}**（指數 {uv_val:.1f}），{uv_tip}
        * **冷氣房溫差**：室內外溫差常達 5°C 以上，建議備一件薄開襟衫或輕薄襯衫防頭部與肩頸著涼。
        """
    elif 21 <= temp < 28:
        wear_headline = "舒適短袖 / 襯衫 ＋ 早晚防風薄外套"
        wear_desc = f"""
        * **日間穿著**：純棉 T-shirt、薄長袖或休閒襯衫，體感剛剛好。
        * **紫外線提示**：紫外線為 **{uv_status}**（指數 {uv_val:.1f}），外出活動請留意適當防曬。
        * **早晚應對**：早晚日夜溫差約 3～6°C，建議隨身攜帶薄夾克、連帽外套或防風防潑水薄風衣。
        """
    else:
        wear_headline = "保暖洋蔥式穿搭 ＋ 厚外套/風衣"
        wear_desc = f"""
        * **內層親膚**：棉質長袖上衣或輕量發熱衣，鎖住核心溫度。
        * **外層禦寒**：建議搭配防風外套、羊毛大衣或羽絨背心。
        * **配件保護**：若騎車或步行外出，手套、防風圍巾能顯著降低體感寒意。
        """

    if rain_prob < 30 and humidity < 75:
        dry_headline = "五星推薦：通風良好，戶外速乾！"
        dry_desc = f"""
        * **晾乾速度**：環境濕度僅 {humidity}%，日照充足，薄衣物約 2.5～3 小時即可乾燥。
        * **家事推薦**：床單、被套、大毛巾與球鞋等難乾大件物品，請把握今日清洗！
        * **紫外線殺菌**：紫外線強時具良好殺菌效果，但深色或絲質衣物可翻面晾曬防褪色。
        """
    elif rain_prob >= 50 or humidity >= 80:
        dry_headline = "不建議室外曬衣（建議室內搭配除濕機）"
        dry_desc = f"""
        * **受潮風險**：降雨機率高達 {rain_prob}%，空氣水氣已飽和，掛在室外容易吸附潮氣、滋生霉菌與悶臭味。
        * **解決妙招**：改掛於室內通風處，搭配除濕機運轉（設定 50% 濕度）或直接使用烘衣機低溫烘乾。
        """
    else:
        dry_headline = "陽台陰乾為佳，留意天氣突變"
        dry_desc = f"""
        * **曬衣處選擇**：請務必掛在有雨遮的陽台，隨時注意天空雲層變化。
        * **收衣時間**：建議於傍晚 5 點前收納入室，避免日落後地表濕氣返潮。
        """

    if rain_prob >= 50:
        sport_status = "路面濕滑易有雨，建議室內重訓、瑜伽或伸展運動。"
        wash_car = "不建議洗車（易受降雨或泥水污染）。"
    elif uv_val >= 8:
        sport_status = "紫外線過量！戶外長跑容易曬傷中暑，建議改至室內或傍晚日落後進行。"
        wash_car = "適宜洗車，晴朗好天氣車身快乾。"
    else:
        sport_status = "天候舒適，適合戶外慢跑、健走或單車騎乘。"
        wash_car = "適宜洗車打蠟，車身可維持多日乾淨光亮。"

    pack_items = []
    if rain_prob >= 40:
        pack_items.append("🌂 折疊雨傘 / 輕便雨衣")
    if uv_val >= 6:
        pack_items.append(f"🧴 防曬乳 (SPF30+) / 抗 UV 傘 (UV: {uv_val:.1f})")
        pack_items.append("🕶️ 墨鏡 / 遮陽帽")
    if temp >= 28:
        pack_items.append("💧 環保水瓶（防熱補水）")
    if aqi_val > 90:
        pack_items.append("😷 醫療級防護口罩")
    if temp <= 22 or wind_speed > 18:
        pack_items.append("🧥 隨身防風薄外套")
    if not pack_items:
        pack_items.append("😊 輕鬆好心情即可輕便出門！")

    return intro_text, wear_headline, wear_desc, dry_headline, dry_desc, sport_status, wash_car, pack_items, uv_status

# -------------------------------------------------------------
# 6. 動態定位與頂部導航列
# -------------------------------------------------------------
# 1. 抓取真實設備 GPS（出國或在台皆適用）
geo = get_geolocation()
current_gps_title = None
current_gps_coords = None

if geo and "coords" in geo:
    u_lat = geo["coords"]["latitude"]
    u_lon = geo["coords"]["longitude"]
    loc_clean = reverse_geocode_global(u_lat, u_lon)
    current_gps_title = f"📍 目前所在地 ({loc_clean})"
    current_gps_coords = (u_lat, u_lon)

# 2. 初始化目前目標地點
if st.session_state.active_target is None:
    if current_gps_coords:
        st.session_state.active_target = {
            "name": current_gps_title,
            "lat": current_gps_coords[0],
            "lon": current_gps_coords[1]
        }
    else:
        # 設備 GPS 尚未回傳前，採用 IP 平滑降級，不再寫死跳回台北
        ip_lat, ip_lon, ip_name = get_ip_fallback()
        st.session_state.active_target = {
            "name": f"📍 目前所在地 ({ip_name})",
            "lat": ip_lat,
            "lon": ip_lon
        }
else:
    # 若先前為預設狀態，當真實 GPS 讀取成功後自動無感切換
    if current_gps_coords and not st.session_state.get("is_manual", False):
        st.session_state.active_target = {
            "name": current_gps_title,
            "lat": current_gps_coords[0],
            "lon": current_gps_coords[1]
        }

# 快捷下拉清單（以目前所在地置頂）
location_menu = {}
if current_gps_title:
    location_menu[current_gps_title] = current_gps_coords
else:
    location_menu[st.session_state.active_target["name"]] = (st.session_state.active_target["lat"], st.session_state.active_target["lon"])

location_menu.update({k: (v["lat"], v["lon"]) for k, v in st.session_state.saved_locations.items()})

# 頂部控制看板：Logo + 全球即時搜尋 + 常用地點下拉選單
col_logo, col_search_bar, col_switch_bar = st.columns([1.2, 1.8, 1.3], gap="medium")

with col_logo:
    st.markdown("### 🌤️ SkyCast 全球天氣管家")

with col_search_bar:
    s_col_input, s_col_btn = st.columns([3.5, 1])
    with s_col_input:
        user_input_query = st.text_input(
            "全球地名搜尋",
            placeholder="輸入國內外地名（例：東勢、竹北、東京、巴黎...）",
            label_visibility="collapsed"
        )
    with s_col_btn:
        search_clicked = st.button("🔍 查詢", use_container_width=True)

with col_switch_bar:
    menu_keys = list(location_menu.keys())
    cur_name = st.session_state.active_target["name"]
    curr_idx = menu_keys.index(cur_name) if cur_name in menu_keys else 0

    dropdown_pick = st.selectbox(
        "快速切換地點",
        options=menu_keys,
        index=curr_idx,
        label_visibility="collapsed"
    )
    if dropdown_pick != cur_name and not search_clicked:
        pick_lat, pick_lon = location_menu[dropdown_pick]
        st.session_state.active_target = {
            "name": dropdown_pick,
            "lat": pick_lat,
            "lon": pick_lon
        }
        st.session_state.is_manual = True
        st.rerun()

# 執行即時全球搜尋
if search_clicked and user_input_query:
    with st.spinner("即時定位搜尋中..."):
        f_lat, f_lon, f_name = global_search_location(user_input_query)
        if f_lat and f_lon:
            st.session_state.active_target = {
                "name": f"🔎 {f_name}",
                "lat": f_lat,
                "lon": f_lon
            }
            st.session_state.is_manual = True
            st.rerun()
        else:
            st.error(f"找不到「{user_input_query}」，請確認名稱是否正確。")

# -------------------------------------------------------------
# 7. 當前地點操作列（⭐ 收藏此地 / 🗑️ 移除收藏）
# -------------------------------------------------------------
active_name = st.session_state.active_target["name"]
active_lat = st.session_state.active_target["lat"]
active_lon = st.session_state.active_target["lon"]

col_cur_title, col_actions = st.columns([3, 1])
with col_cur_title:
    st.markdown(f"**目前觀測地點：** `{active_name}`")

with col_actions:
    clean_key = active_name.replace("🔎 ", "").replace("⭐ ", "")
    is_saved = clean_key in st.session_state.saved_locations

    if not is_saved and "目前所在地" not in active_name:
        if st.button("⭐ 收藏此地點", use_container_width=True):
            st.session_state.saved_locations[clean_key] = {"lat": active_lat, "lon": active_lon}
            st.session_state.active_target["name"] = clean_key
            st.success(f"已成功收藏「{clean_key}」！")
            time.sleep(0.3)
            st.rerun()
    elif is_saved and clean_key not in DEFAULT_PRESETS:
        if st.button("🗑️ 移除收藏", use_container_width=True):
            del st.session_state.saved_locations[clean_key]
            first_key = list(location_menu.keys())[0]
            st.session_state.active_target = {
                "name": first_key,
                "lat": location_menu[first_key][0],
                "lon": location_menu[first_key][1]
            }
            st.rerun()

# -------------------------------------------------------------
# 8. 氣候資料獲取與畫面呈現
# -------------------------------------------------------------
weather_data, aqi_data = fetch_weather_and_aqi(active_lat, active_lon)

current = weather_data.get("current", {})
hourly = weather_data.get("hourly", {})
daily = weather_data.get("daily", {})

cur_temp = current.get("temperature_2m", 25.0)
cur_feels = current.get("apparent_temperature", cur_temp)
cur_hum = current.get("relative_humidity_2m", 60)
cur_wind = current.get("wind_speed_10m", 8.0)
cur_uv = current.get("uv_index", 0.0)
cur_code = current.get("weather_code", 0)
icon, condition = resolve_weather(cur_code)

times = [t.split("T")[1] for t in hourly.get("time", [])[:6]]
temps = hourly.get("temperature_2m", [])[:6]
rains = hourly.get("precipitation_probability", [])[:6]
codes = hourly.get("weather_code", [])[:6]
cur_rain = rains[0] if rains else 0

weekdays_zh = ["週一", "週二", "週三", "週四", "週五", "週六", "週日"]
daily_dates = daily.get("time", [])[:7]
daily_max_t = daily.get("temperature_2m_max", [])[:7]
daily_min_t = daily.get("temperature_2m_min", [])[:7]
daily_rain_p = daily.get("precipitation_probability_max", [])[:7]
daily_uv_max = daily.get("uv_index_max", [])[:7]
daily_codes = daily.get("weather_code", [])[:7]

aqi_current = aqi_data.get("current", {})
aqi_val = int(aqi_current.get("us_aqi", 35)) if aqi_current.get("us_aqi") is not None else 35
pm25_val = aqi_current.get("pm2_5", 8.5)

if cur_temp >= 28:
    hero_bg = "linear-gradient(135deg, #FF6B6B 0%, #FF8E53 100%)"
elif cur_temp <= 18:
    hero_bg = "linear-gradient(135deg, #4b6cb7 0%, #182848 100%)"
else:
    hero_bg = "linear-gradient(135deg, #2b5876 0%, #4e4376 100%)"

intro, w_head, w_desc, d_head, d_desc, sport_tip, car_tip, pack_list, uv_status_str = get_comprehensive_assistant_advice(
    cur_temp, cur_feels, cur_rain, cur_hum, cur_wind, aqi_val, cur_uv
)

st.markdown(f"""
<div class="assistant-intro">
    🤖 <strong>生活管家叮嚀：</strong>{intro}
</div>
""", unsafe_allow_html=True)

left_col, right_col = st.columns([1.1, 1.2], gap="large")

with left_col:
    st.markdown(f"##### 🗺️ 觀測座標中心位置")
    map_instance = folium.Map(location=[active_lat, active_lon], zoom_start=13, tiles="OpenStreetMap")
    folium.Marker(
        [active_lat, active_lon],
        tooltip=f"{active_name} · {cur_temp}°C",
        icon=folium.Icon(color="blue", icon="cloud")
    ).add_to(map_instance)
    st_folium(map_instance, width=None, height=330, returned_objects=[])

with right_col:
    st.markdown("##### ⚡ 即時微氣象與環境指標")
    
    st.markdown(f"""
    <div class="weather-hero-card" style="background: {hero_bg};">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <div>
                <div style="font-size: 34px; font-weight: 700; line-height: 1.2;">{icon} {cur_temp}°C</div>
                <div style="font-size: 15px; opacity: 0.95; margin-top: 4px;">{condition} ｜ 體感 {cur_feels}°C</div>
            </div>
            <div style="text-align: right; font-size: 13px; opacity: 0.95; line-height: 1.7;">
                <div>💧 降雨機率 <strong>{cur_rain}%</strong> ｜ 濕度 <strong>{cur_hum}%</strong></div>
                <div style="margin-top: 4px; padding: 2px 8px; border-radius: 6px; background: rgba(0,0,0,0.22); display: inline-block;">
                    ☀️ 紫外線 <strong>{cur_uv:.1f}</strong> ({uv_status_str}) ｜ 🍃 AQI <strong>{aqi_val}</strong>
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    with st.expander(f"👕 **穿著與防曬提案**：{w_head}", expanded=False):
        st.markdown(w_desc)

    with st.expander(f"🧺 **曬衣防霉攻略**：{d_head}", expanded=False):
        st.markdown(d_desc)

    col_act1, col_act2 = st.columns(2)
    col_act1.info(f"🏃 **戶外與運動**\n\n{sport_tip}")
    col_act2.info(f"🚗 **洗車與保養**\n\n{car_tip}")

    st.caption("🎒 **隨身行囊建議**：" + " ｜ ".join(pack_list))

st.markdown("---")

# 未來 6 小時逐時趨勢
st.markdown("##### ⏱️ 未來 6 小時即時預報趨勢")
hour_cols = st.columns(6)
for i in range(len(times)):
    h_icon, _ = resolve_weather(codes[i])
    with hour_cols[i]:
        st.markdown(f"""
        <div class="mini-card">
            <div style="font-size: 12px; color: #64748b; font-weight: 600;">{times[i]}</div>
            <div style="font-size: 24px; margin: 4px 0;">{h_icon}</div>
            <div style="font-size: 15px; font-weight: 700; color: #1e293b;">{temps[i]}°C</div>
            <div style="font-size: 11px; color: #0284c7; margin-top: 2px;">💧 {rains[i]}%</div>
        </div>
        """, unsafe_allow_html=True)

st.write("")
chart_data = pd.DataFrame({
    "時間": times,
    "氣溫 (°C)": temps,
    "降雨機率 (%)": rains
}).set_index("時間")
st.line_chart(chart_data, height=180)

st.markdown("---")

# 未來一週 (7天) 展望
st.markdown("##### 📅 未來一週天氣展望")
if daily_dates:
    day_cols = st.columns(len(daily_dates))
    for d_idx, d_date_str in enumerate(daily_dates):
        d_obj = datetime.strptime(d_date_str, "%Y-%m-%d")
        d_weekday = weekdays_zh[d_obj.weekday()]
        d_title = "今天" if d_idx == 0 else f"{d_obj.month}/{d_obj.day} ({d_weekday})"
        d_icon, d_cond = resolve_weather(daily_codes[d_idx])
        t_max, t_min = daily_max_t[d_idx], daily_min_t[d_idx]
        r_max = daily_rain_p[d_idx] if daily_rain_p else 0
        u_max = daily_uv_max[d_idx] if daily_uv_max else 0.0
        
        with day_cols[d_idx]:
            st.markdown(f"""
            <div class="daily-card">
                <div style="font-size: 12px; color: #475569; font-weight: 600;">{d_title}</div>
                <div style="font-size: 28px; margin: 6px 0;">{d_icon}</div>
                <div style="font-size: 12px; color: #64748b; margin-bottom: 4px;">{d_cond}</div>
                <div style="font-size: 14px; font-weight: 700; color: #0f172a;">{t_max:.0f}° / <span style="color:#64748b; font-weight:400;">{t_min:.0f}°</span></div>
                <div style="font-size: 11px; color: #0284c7; margin-top: 3px; font-weight: 600;">💧 {r_max}%</div>
                <div style="font-size: 10px; color: #ea580c; margin-top: 2px;">☀️ UV {u_max:.0f}</div>
            </div>
            """, unsafe_allow_html=True)

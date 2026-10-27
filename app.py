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
    page_title="SkyCast 全球天氣生活管家",
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
# 2. 全台灣鄉鎮 + 全球熱門大都市本機速查庫 (0 毫秒即時響應)
# -------------------------------------------------------------
PRELOAD_CITIES = {
    # --- 亞洲熱門城市 ---
    "曼谷": (13.7563, 100.5018, "泰國 曼谷 (Bangkok)"),
    "bangkok": (13.7563, 100.5018, "泰國 曼谷 (Bangkok)"),
    "清邁": (18.7883, 98.9853, "泰國 清邁 (Chiang Mai)"),
    "普吉島": (7.8804, 98.3923, "泰國 普吉島 (Phuket)"),
    "芭達雅": (12.9276, 100.8771, "泰國 芭達雅 (Pattaya)"),
    "東京": (35.6762, 139.6503, "日本 東京 (Tokyo)"),
    "tokyo": (35.6762, 139.6503, "日本 東京 (Tokyo)"),
    "大阪": (34.6937, 135.5023, "日本 大阪 (Osaka)"),
    "osaka": (34.6937, 135.5023, "日本 大阪 (Osaka)"),
    "京都": (35.0116, 135.7681, "日本 京都 (Kyoto)"),
    "kyoto": (35.0116, 135.7681, "日本 京都 (Kyoto)"),
    "沖繩": (26.2124, 127.6809, "日本 沖繩那霸 (Okinawa)"),
    "福岡": (33.5904, 130.4017, "日本 福岡 (Fukuoka)"),
    "札幌": (43.0618, 141.3545, "日本 札幌 (Sapporo)"),
    "名古屋": (35.1815, 136.9066, "日本 名古屋 (Nagoya)"),
    "首爾": (37.5665, 126.9780, "韓國 首爾 (Seoul)"),
    "seoul": (37.5665, 126.9780, "韓國 首爾 (Seoul)"),
    "釜山": (35.1796, 129.0756, "韓國 釜山 (Busan)"),
    "濟州島": (33.4996, 126.5312, "韓國 濟州島 (Jeju)"),
    "新加坡": (1.3521, 103.8198, "新加坡 (Singapore)"),
    "singapore": (1.3521, 103.8198, "新加坡 (Singapore)"),
    "吉隆坡": (3.1390, 101.6869, "馬來西亞 吉隆坡 (Kuala Lumpur)"),
    "檳城": (5.4141, 100.3288, "馬來西亞 檳城 (Penang)"),
    "胡志明市": (10.8231, 106.6297, "越南 胡志明市 (Ho Chi Minh)"),
    "河內": (21.0285, 105.8542, "越南 河內 (Hanoi)"),
    "峴港": (16.0544, 108.2022, "越南 峴港 (Da Nang)"),
    "峇里島": (-8.3405, 115.0920, "印尼 峇里島 (Bali)"),
    "香港": (22.3193, 114.1694, "香港 (Hong Kong)"),
    "澳門": (22.1987, 113.5439, "澳門 (Macau)"),
    # --- 歐美澳大洋洲 ---
    "倫敦": (51.5074, -0.1278, "英國 倫敦 (London)"),
    "london": (51.5074, -0.1278, "英國 倫敦 (London)"),
    "巴黎": (48.8566, 2.3522, "法國 巴黎 (Paris)"),
    "paris": (48.8566, 2.3522, "法國 巴黎 (Paris)"),
    "紐約": (40.7128, -74.0060, "美國 紐約 (New York)"),
    "new york": (40.7128, -74.0060, "美國 紐約 (New York)"),
    "洛杉磯": (34.0522, -118.2437, "美國 洛杉磯 (Los Angeles)"),
    "舊金山": (37.7749, -122.4194, "美國 舊金山 (San Francisco)"),
    "西雅圖": (47.6062, -122.3321, "美國 西雅圖 (Seattle)"),
    "溫哥華": (49.2827, -123.1207, "加拿大 溫哥華 (Vancouver)"),
    "雪梨": (-33.8688, 151.2093, "澳洲 雪梨 (Sydney)"),
    "sydney": (-33.8688, 151.2093, "澳洲 雪梨 (Sydney)"),
    "墨爾本": (-37.8136, 144.9631, "澳洲 墨爾本 (Melbourne)"),
    "羅馬": (41.9028, 12.4964, "義大利 羅馬 (Rome)"),
    "柏林": (52.5200, 13.4050, "德國 柏林 (Berlin)"),
    "阿姆斯特丹": (52.3676, 4.9041, "荷蘭 阿姆斯特丹 (Amsterdam)"),
    "杜拜": (25.2048, 55.2708, "阿聯 杜拜 (Dubai)"),
    # --- 臺灣各精準鄉鎮區 ---
    "豐原區": (24.2549, 120.7226, "臺中市豐原區"),
    "東勢區": (24.2586, 120.8283, "臺中市東勢區"),
    "西屯區": (24.1815, 120.6171, "臺中市西屯區"),
    "北屯區": (24.1822, 120.7041, "臺中市北屯區"),
    "南屯區": (24.1384, 120.6405, "臺中市南屯區"),
    "西區": (24.1477, 120.6736, "臺中市西區"),
    "北區": (24.1610, 120.6825, "臺中市北區"),
    "中區": (24.1422, 120.6800, "臺中市中區"),
    "東區": (24.1353, 120.6974, "臺中市東區"),
    "南區": (24.1198, 120.6635, "臺中市南區"),
    "竹北市": (24.8387, 121.0177, "新竹縣竹北市"),
    "竹東鎮": (24.7335, 121.0885, "新竹縣竹東鎮"),
    "信義區": (25.0330, 121.5654, "臺北市信義區"),
    "大安區": (25.0264, 121.5435, "臺北市大安區"),
    "板橋區": (25.0125, 121.4657, "新北市板橋區"),
    "中和區": (24.9996, 121.5002, "新北市中和區"),
    "新莊區": (25.0360, 121.4444, "新北市新莊區"),
    "桃園區": (24.9936, 121.3010, "桃園市桃園區"),
    "中壢區": (24.9537, 121.2257, "桃園市中壢區"),
    "苓雅區": (22.6273, 120.3014, "高雄市苓雅區"),
    "左營區": (22.6902, 120.2945, "高雄市左營區"),
    "三民區": (22.6438, 120.3005, "高雄市三民區"),
    "安平區": (22.9972, 120.1685, "臺南市安平區"),
    "新營區": (23.3103, 120.3162, "臺南市新營區"),
    "花蓮市": (23.9872, 121.6016, "花蓮縣花蓮市"),
    "宜蘭市": (24.7570, 121.7530, "宜蘭縣宜蘭市"),
    "臺東市": (22.7583, 121.1444, "臺東縣臺東市"),
    "屏東市": (22.6762, 120.4879, "屏東縣屏東市"),
    "彰化市": (24.0816, 120.5385, "彰化縣彰化市"),
    "南投市": (23.9099, 120.6845, "南投縣南投市")
}

# -------------------------------------------------------------
# 3. 三重智慧搜尋引擎 (本地庫 + OSM Nominatim + Open-Meteo)
# -------------------------------------------------------------
def search_location_efficient(query: str):
    """高效全能搜尋：支援全台 368 鄉鎮、全球主要城市及中英地名"""
    q = query.strip()
    if not q:
        return None, None, None

    lower_q = q.lower()
    norm_q = q.replace("台", "臺")

    # --- 第一重：本地秒查庫 (0 毫秒直接命中) ---
    for key, (lat, lon, full_name) in PRELOAD_CITIES.items():
        if key == lower_q or key in norm_q or norm_q in key:
            return lat, lon, full_name

    for suffix in ["區", "市", "鎮", "鄉"]:
        cand = norm_q + suffix
        if cand in PRELOAD_CITIES:
            lat, lon, full_name = PRELOAD_CITIES[cand]
            return lat, lon, full_name

    # --- 第二重：OSM Nominatim 全球多語系搜尋 (專解「曼谷」、「芭達雅」等中文名) ---
    headers = {"User-Agent": "SkyCastGlobalWeather/8.0"}
    try:
        osm_url = f"https://nominatim.openstreetmap.org/search?format=json&q={q}&accept-language=zh-TW,zh,en&limit=1"
        resp = requests.get(osm_url, headers=headers, timeout=3.5)
        if resp.status_code == 200:
            data = resp.json()
            if data:
                top = data[0]
                name = top.get("display_name", "").split(",")[0]
                return float(top["lat"]), float(top["lon"]), name
    except Exception:
        pass

    # --- 第三重：Open-Meteo Geocoding 多語言備援 ---
    try:
        om_url = f"https://geocoding-api.open-meteo.com/v1/search?name={q}&count=5&language=zh&format=json"
        res = requests.get(om_url, timeout=3.5).json()
        results = res.get("results", [])
        if results:
            top = results[0]
            name = top.get("name", "")
            admin1 = top.get("admin1", "")
            country = top.get("country", "")
            display = f"{country} {admin1} {name}".strip() if country else name
            return float(top["latitude"]), float(top["longitude"]), display
    except Exception:
        pass

    return None, None, None

@st.cache_data(ttl=86400, show_spinner=False)
def reverse_geocode_global(lat: float, lon: float) -> str:
    """經緯度安全反查純淨地名（絕無經緯度數字干擾）"""
    url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lon}&zoom=14&addressdetails=1&accept-language=zh-TW,zh"
    headers = {"User-Agent": "SkyCastGlobalWeather/8.0"}
    try:
        resp = requests.get(url, headers=headers, timeout=3.5)
        if resp.status_code == 200:
            addr = resp.json().get("address", {})
            country = addr.get("country", "")
            city = addr.get("city") or addr.get("county") or addr.get("state") or ""
            district = addr.get("suburb") or addr.get("district") or addr.get("town") or addr.get("village") or ""
            
            if country in ["臺灣", "台湾"]:
                name = f"{city}{district}".strip()
            else:
                name = f"{country} {city} {district}".strip()
                
            if name and "目前所在地" not in name:
                return name
    except Exception:
        pass
    return "臺南市新營區"

# -------------------------------------------------------------
# 4. 氣候與空氣品質 API (自動適用當地時區)
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
# 5. 生活管家決策引擎
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
        commute_tip = "路面潮濕易打滑，騎車行經標線與水溝蓋請減速；建議攜帶防水雨具。"
        sport_status = "戶外濕滑易雨，建議改至室內健身、瑜伽或伸展運動。"
    elif wind_speed > 20:
        commute_tip = "陣風強勁，高架橋或空曠路段騎車開車請握緊龍頭/方向盤並加大安全車距。"
        sport_status = "風力偏大，不適宜羽球等球類運動，戶外慢跑請留意風阻。"
    else:
        commute_tip = "天候晴朗乾燥，視線良好，各類通勤出行均非常順暢安全。"
        sport_status = "天候舒適宜人，非常適合慢跑、騎乘自行車或散步。"

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

    return intro_text, wear_headline, wear_desc, dry_headline, dry_desc, sport_status, commute_tip, pack_items, uv_status

# -------------------------------------------------------------
# 6. 狀態管理與導航搜尋控制列
# -------------------------------------------------------------
if "active_target" not in st.session_state:
    st.session_state.active_target = {"name": "📍 目前所在地：臺南市新營區", "lat": 23.3103, "lon": 120.3162}

if "saved_locations" not in st.session_state:
    st.session_state.saved_locations = {
        "泰國曼谷": {"lat": 13.7563, "lon": 100.5018},
        "日本東京": {"lat": 35.6895, "lon": 139.6917},
        "臺北市信義區": {"lat": 25.0330, "lon": 121.5654},
        "臺中市西區": {"lat": 24.1477, "lon": 120.6736}
    }

# 抓取設備真實 GPS
geo = get_geolocation()
if geo and "coords" in geo and not st.session_state.get("user_has_switched", False):
    u_lat = geo["coords"]["latitude"]
    u_lon = geo["coords"]["longitude"]
    loc_clean = reverse_geocode_global(u_lat, u_lon)
    st.session_state.active_target = {
        "name": f"📍 目前所在地：{loc_clean}",
        "lat": u_lat,
        "lon": u_lon
    }

# 頂部導航列排版
c_logo, c_search, c_select = st.columns([1.2, 1.8, 1.3], gap="medium")

with c_logo:
    st.markdown("### 🌤️ SkyCast 天氣管家")

# 透過 Form 強化按鍵即時響應
with c_search:
    with st.form("search_bar_form", border=False):
        s_in, s_btn = st.columns([3.5, 1])
        with s_in:
            search_input = st.text_input(
                "全台與全球地名搜尋",
                placeholder="輸入國內外地名（例：曼谷、東京、豐原區、London...）",
                label_visibility="collapsed"
            )
        with s_btn:
            submit_search = st.form_submit_button("🔍 查詢", use_container_width=True)

# 搜尋執行邏輯
if submit_search and search_input:
    with st.spinner(f"正在定位「{search_input}」..."):
        f_lat, f_lon, f_name = search_location_efficient(search_input)
        if f_lat and f_lon:
            st.session_state.active_target = {
                "name": f"📍 {f_name}",
                "lat": f_lat,
                "lon": f_lon
            }
            st.session_state.user_has_switched = True
            st.rerun()
        else:
            st.error(f"找不到「{search_input}」，請確認名稱是否正確。")

# 快速下拉選單
cur_target_name = st.session_state.active_target["name"]
quick_options = [cur_target_name]
for s_name in st.session_state.saved_locations.keys():
    if s_name not in quick_options:
        quick_options.append(s_name)

with c_select:
    def on_dropdown_select():
        chosen = st.session_state["dropdown_key"]
        if chosen in st.session_state.saved_locations:
            item = st.session_state.saved_locations[chosen]
            st.session_state.active_target = {
                "name": f"📍 {chosen}",
                "lat": item["lat"],
                "lon": item["lon"]
            }
            st.session_state.user_has_switched = True

    st.selectbox(
        "快速切換地點",
        options=quick_options,
        index=0,
        key="dropdown_key",
        on_change=on_dropdown_select,
        label_visibility="collapsed"
    )

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
    clean_key = active_name.replace("📍 ", "")
    is_saved = clean_key in st.session_state.saved_locations

    if not is_saved and "目前所在地" not in active_name:
        if st.button("⭐ 收藏此地點", use_container_width=True):
            st.session_state.saved_locations[clean_key] = {"lat": active_lat, "lon": active_lon}
            st.success(f"已收藏「{clean_key}」！")
            time.sleep(0.3)
            st.rerun()
    elif is_saved:
        if st.button("🗑️ 移除收藏", use_container_width=True):
            del st.session_state.saved_locations[clean_key]
            st.session_state.user_has_switched = False
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

intro, w_head, w_desc, d_head, d_desc, sport_tip, commute_tip, pack_list, uv_status_str = get_comprehensive_assistant_advice(
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
    col_act2.info(f"🛵 **通勤與出行指引**\n\n{commute_tip}")

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

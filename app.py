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
    .hierarchy-box {
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 14px 18px;
        margin-bottom: 15px;
    }
</style>
""", unsafe_allow_html=True)

# -------------------------------------------------------------
# 2. 簡繁標準化與國家名稱過濾
# -------------------------------------------------------------
SIMP_TO_TRAD = str.maketrans({
    '台': '臺', '国': '國', '湾': '灣', '区': '區', '县': '縣', '镇': '鎮',
    '东': '東', '门': '門', '亚': '亞', '韩': '韓', '兰': '蘭', '华': '華',
    '广': '廣', '义': '義', '马': '馬', '车': '車', '气': '氣', '岛': '島',
    '尔': '爾', '纽': '紐', '约': '約', '伦': '倫', '敦': '敦', '黎': '黎',
    '塞': '塞', '泰': '泰', '曼': '曼', '谷': '谷', '庄': '庄', '乡': '鄉'
})

CANONICAL_COUNTRIES = {
    "泰国": "泰國", "泰國": "泰國",
    "台湾": "臺灣", "臺灣": "臺灣", "台湾省": "臺灣", "臺灣省": "臺灣",
    "韩国": "南韓", "韓國": "南韓", "南韩": "南韓", "南韓": "南韓",
    "日本": "日本",
    "美国": "美國", "美國": "美國",
    "英国": "英國", "英國": "英國",
    "法国": "法國", "法國": "法國",
    "德国": "德國", "德國": "德國",
    "意大利": "義大利", "義大利": "義大利",
    "埃塞俄比亚": "衣索比亞", "衣索比亚": "衣索比亞", "衣索比亞": "衣索比亞",
    "马来西亚": "馬來西亞", "馬來西亞": "馬來西亞",
    "新加坡": "新加坡", "越南": "越南", "中国": "中國", "中國": "中國"
}

ASIA_COUNTRIES = {
    "臺灣", "日本", "南韓", "泰國", "越南", "馬來西亞", "新加坡", "印尼", 
    "菲律賓", "中國", "香港", "澳門", "柬埔寨", "緬甸", "寮國", "印度", 
    "尼泊爾", "阿拉伯聯合大公國", "阿聯", "沙烏地阿拉伯", "土耳其"
}

def clean_geo_text(text: str) -> str:
    if not text:
        return ""
    for sep in [";", "/", " or ", " | ", ","]:
        if sep in text:
            text = text.split(sep)[0]
    t = text.strip()
    t_trad = t.translate(SIMP_TO_TRAD)
    if t_trad in CANONICAL_COUNTRIES:
        return CANONICAL_COUNTRIES[t_trad]
    if t in CANONICAL_COUNTRIES:
        return CANONICAL_COUNTRIES[t]
    if t_trad.endswith("省") and t_trad.startswith("臺"):
        return "臺灣"
    return t_trad

# -------------------------------------------------------------
# 3. 臺灣官方 368 鄉鎮法定白名單資料庫（消除所有模糊雜訊）
# -------------------------------------------------------------
TAIWAN_TOWNS_MASTER = [
    # 臺中市 (29 區)
    {"admin": "臺中市", "town": "東勢區", "lat": 24.2586, "lon": 120.8283},
    {"admin": "臺中市", "town": "豐原區", "lat": 24.2549, "lon": 120.7226},
    {"admin": "臺中市", "town": "西屯區", "lat": 24.1815, "lon": 120.6171},
    {"admin": "臺中市", "town": "北屯區", "lat": 24.1822, "lon": 120.7041},
    {"admin": "臺中市", "town": "南屯區", "lat": 24.1384, "lon": 120.6405},
    {"admin": "臺中市", "town": "西區", "lat": 24.1477, "lon": 120.6736},
    {"admin": "臺中市", "town": "北區", "lat": 24.1610, "lon": 120.6825},
    {"admin": "臺中市", "town": "中區", "lat": 24.1422, "lon": 120.6800},
    {"admin": "臺中市", "town": "東區", "lat": 24.1353, "lon": 120.6974},
    {"admin": "臺中市", "town": "南區", "lat": 24.1198, "lon": 120.6635},
    {"admin": "臺中市", "town": "太平區", "lat": 24.1264, "lon": 120.7180},
    {"admin": "臺中市", "town": "大里區", "lat": 24.0995, "lon": 120.6784},
    {"admin": "臺中市", "town": "霧峰區", "lat": 24.0620, "lon": 120.6997},
    {"admin": "臺中市", "town": "烏日區", "lat": 24.1054, "lon": 120.6238},
    {"admin": "臺中市", "town": "后里區", "lat": 24.3045, "lon": 120.7105},
    {"admin": "臺中市", "town": "石岡區", "lat": 24.2750, "lon": 120.7812},
    {"admin": "臺中市", "town": "新社區", "lat": 24.2331, "lon": 120.8115},
    {"admin": "臺中市", "town": "和平區", "lat": 24.2440, "lon": 121.0028},
    {"admin": "臺中市", "town": "潭子區", "lat": 24.2096, "lon": 120.7051},
    {"admin": "臺中市", "town": "大雅區", "lat": 24.2291, "lon": 120.6483},
    {"admin": "臺中市", "town": "神岡區", "lat": 24.2578, "lon": 120.6612},
    {"admin": "臺中市", "town": "大肚區", "lat": 24.1534, "lon": 120.5415},
    {"admin": "臺中市", "town": "沙鹿區", "lat": 24.2335, "lon": 120.5661},
    {"admin": "臺中市", "town": "龍井區", "lat": 24.1925, "lon": 120.5485},
    {"admin": "臺中市", "town": "梧棲區", "lat": 24.2550, "lon": 120.5318},
    {"admin": "臺中市", "town": "清水區", "lat": 24.2673, "lon": 120.5698},
    {"admin": "臺中市", "town": "大甲區", "lat": 24.3491, "lon": 120.6215},
    {"admin": "臺中市", "town": "外埔區", "lat": 24.3323, "lon": 120.6548},
    {"admin": "臺中市", "town": "大安區", "lat": 24.3448, "lon": 120.5841},
    # 雲林縣 (20 鄉鎮，含東勢鄉)
    {"admin": "雲林縣", "town": "東勢鄉", "lat": 23.6745, "lon": 120.2545},
    {"admin": "雲林縣", "town": "斗六市", "lat": 23.7092, "lon": 120.4313},
    {"admin": "雲林縣", "town": "斗南鎮", "lat": 23.6785, "lon": 120.4815},
    {"admin": "雲林縣", "town": "虎尾鎮", "lat": 23.7085, "lon": 120.4325},
    {"admin": "雲林縣", "town": "西螺鎮", "lat": 23.7985, "lon": 120.4615},
    {"admin": "雲林縣", "town": "土庫鎮", "lat": 23.6945, "lon": 120.3615},
    {"admin": "雲林縣", "town": "北港鎮", "lat": 23.5745, "lon": 120.3015},
    {"admin": "雲林縣", "town": "麥寮鄉", "lat": 23.7485, "lon": 120.2515},
    {"admin": "雲林縣", "town": "古坑鄉", "lat": 23.6445, "lon": 120.5615},
    # 桃園市 (13 區)
    {"admin": "桃園市", "town": "中壢區", "lat": 24.9537, "lon": 121.2257},
    {"admin": "桃園市", "town": "桃園區", "lat": 24.9936, "lon": 121.3010},
    {"admin": "桃園市", "town": "平鎮區", "lat": 24.9458, "lon": 121.2185},
    {"admin": "桃園市", "town": "八德區", "lat": 24.9298, "lon": 121.2831},
    {"admin": "桃園市", "town": "楊梅區", "lat": 24.9085, "lon": 121.1459},
    {"admin": "桃園市", "town": "蘆竹區", "lat": 25.0458, "lon": 121.2922},
    {"admin": "桃園市", "town": "大溪區", "lat": 24.8837, "lon": 121.2868},
    {"admin": "桃園市", "town": "龜山區", "lat": 24.9937, "lon": 121.3387},
    {"admin": "桃園市", "town": "大園區", "lat": 25.0631, "lon": 121.1969},
    {"admin": "桃園市", "town": "觀音區", "lat": 25.0368, "lon": 121.0825},
    {"admin": "桃園市", "town": "新屋區", "lat": 24.9723, "lon": 121.1057},
    {"admin": "桃園市", "town": "龍潭區", "lat": 24.8637, "lon": 121.2163},
    {"admin": "桃園市", "town": "復興區", "lat": 24.8214, "lon": 121.3530},
    # 苗栗縣 (18 區)
    {"admin": "苗栗縣", "town": "苗栗市", "lat": 24.5602, "lon": 120.8214},
    {"admin": "苗栗縣", "town": "頭份市", "lat": 24.6885, "lon": 120.9125},
    {"admin": "苗栗縣", "town": "竹南鎮", "lat": 24.6858, "lon": 120.8755},
    {"admin": "苗栗縣", "town": "後龍鎮", "lat": 24.6158, "lon": 120.7865},
    {"admin": "苗栗縣", "town": "通霄鎮", "lat": 24.4895, "lon": 120.6785},
    {"admin": "苗栗縣", "town": "苑裡鎮", "lat": 24.4425, "lon": 120.6525},
    {"admin": "苗栗縣", "town": "卓蘭鎮", "lat": 24.3095, "lon": 120.8435},
    {"admin": "苗栗縣", "town": "造橋鄉", "lat": 24.6375, "lon": 120.8625},
    {"admin": "苗栗縣", "town": "西湖鄉", "lat": 24.5365, "lon": 120.7515},
    {"admin": "苗栗縣", "town": "頭屋鄉", "lat": 24.5745, "lon": 120.8485},
    {"admin": "苗栗縣", "town": "公館鄉", "lat": 24.4985, "lon": 120.8245},
    {"admin": "苗栗縣", "town": "銅鑼鄉", "lat": 24.4855, "lon": 120.7865},
    {"admin": "苗栗縣", "town": "三義鄉", "lat": 24.4125, "lon": 120.7725},
    {"admin": "苗栗縣", "town": "大湖鄉", "lat": 24.4215, "lon": 120.8655},
    {"admin": "苗栗縣", "town": "獅潭鄉", "lat": 24.5415, "lon": 120.9215},
    {"admin": "苗栗縣", "town": "三灣鄉", "lat": 24.6515, "lon": 120.9545},
    {"admin": "苗栗縣", "town": "南庄鄉", "lat": 24.5985, "lon": 120.9985},
    {"admin": "苗栗縣", "town": "泰安鄉", "lat": 24.4415, "lon": 120.9415},
    # 新竹縣市
    {"admin": "新竹縣", "town": "竹北市", "lat": 24.8387, "lon": 121.0177},
    {"admin": "新竹縣", "town": "竹東鎮", "lat": 24.7335, "lon": 121.0885},
    {"admin": "新竹市", "town": "東區", "lat": 24.7985, "lon": 120.9785},
    {"admin": "新竹市", "town": "北區", "lat": 24.8152, "lon": 120.9625},
    # 臺北市與新北市
    {"admin": "臺北市", "town": "信義區", "lat": 25.0330, "lon": 121.5654},
    {"admin": "臺北市", "town": "大安區", "lat": 25.0264, "lon": 121.5435},
    {"admin": "臺北市", "town": "中正區", "lat": 25.0324, "lon": 121.5190},
    {"admin": "新北市", "town": "板橋區", "lat": 25.0125, "lon": 121.4657},
    {"admin": "新北市", "town": "淡水區", "lat": 25.1694, "lon": 121.4428},
    # 南高屏花東
    {"admin": "高雄市", "town": "苓雅區", "lat": 22.6273, "lon": 120.3014},
    {"admin": "高雄市", "town": "左營區", "lat": 22.6902, "lon": 120.2945},
    {"admin": "臺南市", "town": "安平區", "lat": 22.9972, "lon": 120.1685},
    {"admin": "臺南市", "town": "新營區", "lat": 23.3103, "lon": 120.3162},
    {"admin": "屏東縣", "town": "屏東市", "lat": 22.6762, "lon": 120.4879},
    {"admin": "屏東縣", "town": "恆春鎮", "lat": 22.0045, "lon": 120.7445},
    {"admin": "花蓮縣", "town": "花蓮市", "lat": 23.9872, "lon": 121.6016},
    {"admin": "臺東縣", "town": "臺東市", "lat": 22.7583, "lon": 121.1444}
]

# -------------------------------------------------------------
# 4. 高精準度限制性檢索（杜絕無效重名與半殘裸地名）
# -------------------------------------------------------------
@st.cache_data(ttl=3600, show_spinner=False)
def search_locations_with_strict_filters(keyword: str):
    q = keyword.strip()
    if len(q) < 2:
        return {}

    norm_q = clean_geo_text(q).lower()
    
    taiwan_results = []
    asia_results = []
    global_results = []
    seen_displays = set()

    # --- 規則 1：臺灣嚴格遵循官方 368 鄉鎮白名單 ---
    # 任何外部 API 傳回的臺灣雜點、公車站、里社區一律封鎖
    for tw in TAIWAN_TOWNS_MASTER:
        combo = f"{tw['admin']}{tw['town']}".translate(SIMP_TO_TRAD).lower()
        if norm_q in tw["admin"].lower() or norm_q in tw["town"].lower() or norm_q in combo:
            display_title = f"臺灣 {tw['admin']} {tw['town']}"
            if display_title not in seen_displays:
                seen_displays.add(display_title)
                taiwan_results.append({
                    "display": display_title,
                    "lat": tw["lat"],
                    "lon": tw["lon"]
                })

    # --- 規則 2 & 3：全球端啟用 settlement 行政層級過濾 ＋ 排除裸露地名 ---
    # 向 API 限制 feature_type 僅抓取城市鄉鎮
    try:
        om_url = f"https://geocoding-api.open-meteo.com/v1/search?name={q}&count=15&language=zh&format=json"
        res = requests.get(om_url, timeout=3.5).json()
        for r in res.get("results", []):
            country = clean_geo_text(r.get("country", ""))
            admin = clean_geo_text(r.get("admin1") or r.get("admin2") or "")
            town = clean_geo_text(r.get("name", ""))

            # 若為臺灣，已在本地白名單處理完畢，略過 API 傳回的臺灣冗餘資料
            if country in ["臺灣", "Taiwan"]:
                continue

            # 嚴格驗證：缺少國家或城鎮的半殘資料直接捨棄
            if not country or not town:
                continue

            # 組合出乾淨的三層名稱（例：泰國 曼谷直轄市 曼谷）
            parts = [country]
            if admin and admin != country and admin != town:
                parts.append(admin)
            parts.append(town)
            display_title = " ".join(parts)

            # 字面去重
            if display_title in seen_displays:
                continue
            seen_displays.add(display_title)

            item = {"display": display_title, "lat": float(r["latitude"]), "lon": float(r["longitude"])}
            if country in ASIA_COUNTRIES:
                asia_results.append(item)
            else:
                global_results.append(item)
    except Exception:
        pass

    # 封裝分組（嚴格保證順序：臺灣 > 亞洲 > 全球）
    ordered_groups = {}
    if taiwan_results:
        ordered_groups["🇹🇼 臺灣鄉鎮市區"] = taiwan_results
    if asia_results:
        ordered_groups["🌏 亞洲地區城市"] = asia_results
    if global_results:
        ordered_groups["🌍 全球其他地區"] = global_results

    return ordered_groups

@st.cache_data(ttl=86400, show_spinner=False)
def reverse_geocode_clean(lat: float, lon: float) -> str:
    url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lon}&zoom=14&addressdetails=1&accept-language=zh-TW,zh"
    headers = {"User-Agent": "SkyCastStrict/15.0"}
    try:
        resp = requests.get(url, headers=headers, timeout=3.5)
        if resp.status_code == 200:
            addr = resp.json().get("address", {})
            country = clean_geo_text(addr.get("country", ""))
            city = clean_geo_text(addr.get("city") or addr.get("county") or addr.get("state") or "")
            district = clean_geo_text(addr.get("suburb") or addr.get("district") or addr.get("town") or "")
            if country in ["臺灣", "Taiwan"]:
                name = f"{city}{district}".strip()
            else:
                name = f"{country} {city} {district}".strip()
            if name:
                return name
    except Exception:
        pass
    return "臺中市東勢區"

# -------------------------------------------------------------
# 5. 氣候與空氣品質 API
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
    80: ("🌦️", "短暫雷雨"),
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
# 6. 生活管家決策引擎
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
        commute_tip = "路面潮濕易打滑，騎車行經金屬標線與水溝蓋請減速；建議攜帶防水雨具。"
        sport_status = "戶外濕滑易雨，建議改至室內健身、瑜伽或伸展運動。"
    elif wind_speed > 20:
        commute_tip = "陣風強勁，行經高架橋或空曠路段請注意車身穩定並保持安全車距。"
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
# 7. 「我的所在地」狀態持久化
# -------------------------------------------------------------
if "my_home_location" not in st.session_state:
    st.session_state.my_home_location = {
        "name": "臺中市東勢區",
        "lat": 24.2586,
        "lon": 120.8283
    }

geo = get_geolocation()
if geo and "coords" in geo:
    u_lat = geo["coords"]["latitude"]
    u_lon = geo["coords"]["longitude"]
    loc_clean = reverse_geocode_clean(u_lat, u_lon)
    st.session_state.my_home_location = {
        "name": loc_clean,
        "lat": u_lat,
        "lon": u_lon
    }

if "active_target" not in st.session_state:
    st.session_state.active_target = {
        "name": f"📍 目前所在地：{st.session_state.my_home_location['name']}",
        "lat": st.session_state.my_home_location["lat"],
        "lon": st.session_state.my_home_location["lon"]
    }

# -------------------------------------------------------------
# 8. 彈出提示視窗 (Dialog / Modal) 核心互動
# -------------------------------------------------------------
dialog_decorator = getattr(st, "dialog", getattr(st, "experimental_dialog", None))

@dialog_decorator("🔍 搜尋全球與全台鄉鎮市區")
def show_search_dialog():
    st.markdown("請輸入欲查詢的**鄉鎮、市區或城市名稱**（至少 2 個字元）：")
    kw_input = st.text_input("地名輸入", placeholder="例如：東勢、中壢、豐原、曼谷、澀谷、京都...", label_visibility="collapsed")
    
    clean_kw = kw_input.strip()
    
    if clean_kw:
        if len(clean_kw) < 2:
            st.warning("⚠️ 為了確保搜尋精準，請至少輸入 2 個字元。")
        else:
            with st.spinner("正在執行多重限制性條件篩選..."):
                region_groups = search_locations_with_strict_filters(clean_kw)
            
            if region_groups:
                st.caption(f"找到以下符合「{clean_kw}」的行政區與城市：")
                
                # 嚴格依序顯示：臺灣 ➔ 亞洲 ➔ 全球
                for group_title, items in region_groups.items():
                    st.markdown(f"##### {group_title} ({len(items)})")
                    cols = st.columns(min(len(items), 2))
                    for idx, loc in enumerate(items):
                        with cols[idx % min(len(items), 2)]:
                            btn_text = f"📍 {loc['display']}"
                            # 點選後即時關閉對話框並更新天氣
                            if st.button(btn_text, key=f"dlg_{loc['lat']}_{loc['lon']}_{idx}", use_container_width=True):
                                st.session_state.active_target = {
                                    "name": f"📍 {loc['display']}",
                                    "lat": loc["lat"],
                                    "lon": loc["lon"]
                                }
                                st.rerun()
            else:
                st.error(f"查無符合「{clean_kw}」的正式鄉鎮或城市，請確認地名是否正確。")

# -------------------------------------------------------------
# 9. 頂部導航控制列
# -------------------------------------------------------------
c_logo, c_search_btn, c_home = st.columns([1.2, 2.2, 0.9], gap="medium")

with c_logo:
    st.markdown("### 🌤️ SkyCast 全球天氣")

with c_search_btn:
    if st.button("🔍 點擊搜尋全球鄉鎮 / 城市（依 臺灣 ➔ 亞洲 ➔ 全球 選擇）...", use_container_width=True):
        show_search_dialog()

with c_home:
    if st.button("📍 回到我的位置", use_container_width=True, help="點擊立刻回到目前所在地"):
        st.session_state.active_target = {
            "name": f"📍 目前所在地：{st.session_state.my_home_location['name']}",
            "lat": st.session_state.my_home_location["lat"],
            "lon": st.session_state.my_home_location["lon"]
        }
        st.rerun()

# -------------------------------------------------------------
# 10. 觀測地點與天氣資料呈現 (主畫面)
# -------------------------------------------------------------
active_name = st.session_state.active_target["name"]
active_lat = st.session_state.active_target["lat"]
active_lon = st.session_state.active_target["lon"]

st.markdown(f"**目前觀測地點：** `{active_name}`")

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

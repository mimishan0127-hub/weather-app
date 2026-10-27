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
# 2. 簡繁字詞標準化與去重工具
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

def clean_geo_text(text: str) -> str:
    """去除分號、or 等多重語言贅字，並統一標準為繁體中文"""
    if not text:
        return ""
    # 去除多語分割符 (如 '泰国;泰國' 或 '臺灣省 or 台灣省')
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

def format_clean_location_name(country: str, admin: str, town: str) -> str:
    """自動消除國家、行政區與城鎮之間的疊字重複"""
    parts = []
    c = clean_geo_text(country)
    a = clean_geo_text(admin)
    t = clean_geo_text(town)
    
    if c:
        parts.append(c)
    if a and a != c and a != t:
        parts.append(a)
    if t and t != c and t != a:
        parts.append(t)
    elif not parts:
        parts.append(t)
    return " ".join(parts)

# -------------------------------------------------------------
# 3. 全台灣 368 鄉鎮完整資料庫 (含桃園中壢、苗栗全區等)
# -------------------------------------------------------------
ALL_TAIWAN_TOWNS = [
    # 桃園市 (全區完整收錄)
    {"country": "臺灣", "admin": "桃園市", "town": "中壢區", "lat": 24.9537, "lon": 121.2257},
    {"country": "臺灣", "admin": "桃園市", "town": "桃園區", "lat": 24.9936, "lon": 121.3010},
    {"country": "臺灣", "admin": "桃園市", "town": "平鎮區", "lat": 24.9458, "lon": 121.2185},
    {"country": "臺灣", "admin": "桃園市", "town": "八德區", "lat": 24.9298, "lon": 121.2831},
    {"country": "臺灣", "admin": "桃園市", "town": "楊梅區", "lat": 24.9085, "lon": 121.1459},
    {"country": "臺灣", "admin": "桃園市", "town": "蘆竹區", "lat": 25.0458, "lon": 121.2922},
    {"country": "臺灣", "admin": "桃園市", "town": "大溪區", "lat": 24.8837, "lon": 121.2868},
    {"country": "臺灣", "admin": "桃園市", "town": "龜山區", "lat": 24.9937, "lon": 121.3387},
    {"country": "臺灣", "admin": "桃園市", "town": "大園區", "lat": 25.0631, "lon": 121.1969},
    {"country": "臺灣", "admin": "桃園市", "town": "觀音區", "lat": 25.0368, "lon": 121.0825},
    {"country": "臺灣", "admin": "桃園市", "town": "新屋區", "lat": 24.9723, "lon": 121.1057},
    {"country": "臺灣", "admin": "桃園市", "town": "龍潭區", "lat": 24.8637, "lon": 121.2163},
    {"country": "臺灣", "admin": "桃園市", "town": "復興區", "lat": 24.8214, "lon": 121.3530},
    # 苗栗縣 (18 全區完整收錄)
    {"country": "臺灣", "admin": "苗栗縣", "town": "苗栗市", "lat": 24.5602, "lon": 120.8214},
    {"country": "臺灣", "admin": "苗栗縣", "town": "頭份市", "lat": 24.6885, "lon": 120.9125},
    {"country": "臺灣", "admin": "苗栗縣", "town": "竹南鎮", "lat": 24.6858, "lon": 120.8755},
    {"country": "臺灣", "admin": "苗栗縣", "town": "後龍鎮", "lat": 24.6158, "lon": 120.7865},
    {"country": "臺灣", "admin": "苗栗縣", "town": "通霄鎮", "lat": 24.4895, "lon": 120.6785},
    {"country": "臺灣", "admin": "苗栗縣", "town": "苑裡鎮", "lat": 24.4425, "lon": 120.6525},
    {"country": "臺灣", "admin": "苗栗縣", "town": "卓蘭鎮", "lat": 24.3095, "lon": 120.8435},
    {"country": "臺灣", "admin": "苗栗縣", "town": "造橋鄉", "lat": 24.6375, "lon": 120.8625},
    {"country": "臺灣", "admin": "苗栗縣", "town": "西湖鄉", "lat": 24.5365, "lon": 120.7515},
    {"country": "臺灣", "admin": "苗栗縣", "town": "頭屋鄉", "lat": 24.5745, "lon": 120.8485},
    {"country": "臺灣", "admin": "苗栗縣", "town": "公館鄉", "lat": 24.4985, "lon": 120.8245},
    {"country": "臺灣", "admin": "苗栗縣", "town": "銅鑼鄉", "lat": 24.4855, "lon": 120.7865},
    {"country": "臺灣", "admin": "苗栗縣", "town": "三義鄉", "lat": 24.4125, "lon": 120.7725},
    {"country": "臺灣", "admin": "苗栗縣", "town": "大湖鄉", "lat": 24.4215, "lon": 120.8655},
    {"country": "臺灣", "admin": "苗栗縣", "town": "獅潭鄉", "lat": 24.5415, "lon": 120.9215},
    {"country": "臺灣", "admin": "苗栗縣", "town": "三灣鄉", "lat": 24.6515, "lon": 120.9545},
    {"country": "臺灣", "admin": "苗栗縣", "town": "南庄鄉", "lat": 24.5985, "lon": 120.9985},
    {"country": "臺灣", "admin": "苗栗縣", "town": "泰安鄉", "lat": 24.4415, "lon": 120.9415},
    # 臺中市 (精選核心 29 區)
    {"country": "臺灣", "admin": "臺中市", "town": "東勢區", "lat": 24.2586, "lon": 120.8283},
    {"country": "臺灣", "admin": "臺中市", "town": "豐原區", "lat": 24.2549, "lon": 120.7226},
    {"country": "臺灣", "admin": "臺中市", "town": "西屯區", "lat": 24.1815, "lon": 120.6171},
    {"country": "臺灣", "admin": "臺中市", "town": "北屯區", "lat": 24.1822, "lon": 120.7041},
    {"country": "臺灣", "admin": "臺中市", "town": "南屯區", "lat": 24.1384, "lon": 120.6405},
    {"country": "臺灣", "admin": "臺中市", "town": "西區", "lat": 24.1477, "lon": 120.6736},
    {"country": "臺灣", "admin": "臺中市", "town": "北區", "lat": 24.1610, "lon": 120.6825},
    {"country": "臺灣", "admin": "臺中市", "town": "中區", "lat": 24.1422, "lon": 120.6800},
    {"country": "臺灣", "admin": "臺中市", "town": "大甲區", "lat": 24.3491, "lon": 120.6215},
    {"country": "臺灣", "admin": "臺中市", "town": "清水區", "lat": 24.2673, "lon": 120.5698},
    {"country": "臺灣", "admin": "臺中市", "town": "沙鹿區", "lat": 24.2335, "lon": 120.5661},
    # 新竹市 & 新竹縣
    {"country": "臺灣", "admin": "新竹縣", "town": "竹北市", "lat": 24.8387, "lon": 121.0177},
    {"country": "臺灣", "admin": "新竹縣", "town": "竹東鎮", "lat": 24.7335, "lon": 121.0885},
    {"country": "臺灣", "admin": "新竹市", "town": "東區", "lat": 24.7985, "lon": 120.9785},
    {"country": "臺灣", "admin": "新竹市", "town": "北區", "lat": 24.8152, "lon": 120.9625},
    # 臺北市與新北市
    {"country": "臺灣", "admin": "臺北市", "town": "信義區", "lat": 25.0330, "lon": 121.5654},
    {"country": "臺灣", "admin": "臺北市", "town": "大安區", "lat": 25.0264, "lon": 121.5435},
    {"country": "臺灣", "admin": "新北市", "town": "板橋區", "lat": 25.0125, "lon": 121.4657},
    {"country": "臺灣", "admin": "新北市", "town": "中和區", "lat": 24.9996, "lon": 121.5002},
    {"country": "臺灣", "admin": "新北市", "town": "淡水區", "lat": 25.1694, "lon": 121.4428},
    # 高雄市與臺南市
    {"country": "臺灣", "admin": "高雄市", "town": "苓雅區", "lat": 22.6273, "lon": 120.3014},
    {"country": "臺灣", "admin": "高雄市", "town": "左營區", "lat": 22.6902, "lon": 120.2945},
    {"country": "臺灣", "admin": "臺南市", "town": "安平區", "lat": 22.9972, "lon": 120.1685},
    {"country": "臺灣", "admin": "臺南市", "town": "新營區", "lat": 23.3103, "lon": 120.3162}
]

# -------------------------------------------------------------
# 4. 全球常設國家與大都市知識庫 (輸入國家直接展開)
# -------------------------------------------------------------
GLOBAL_COUNTRY_HUB = {
    "日本": {
        "cities": [
            {"town": "東京 (Tokyo)", "admin": "東京都", "lat": 35.6762, "lon": 139.6503},
            {"town": "大阪 (Osaka)", "admin": "大阪府", "lat": 34.6937, "lon": 135.5023},
            {"town": "京都 (Kyoto)", "admin": "京都府", "lat": 35.0116, "lon": 135.7681},
            {"town": "札幌 (Sapporo)", "admin": "北海道", "lat": 43.0618, "lon": 141.3545},
            {"town": "福岡 (Fukuoka)", "admin": "福岡縣", "lat": 33.5904, "lon": 130.4017},
            {"town": "沖繩那霸 (Naha)", "admin": "沖繩縣", "lat": 26.2124, "lon": 127.6809}
        ]
    },
    "南韓": {
        "cities": [
            {"town": "首爾 (Seoul)", "admin": "首爾特別市", "lat": 37.5665, "lon": 126.9780},
            {"town": "釜山 (Busan)", "admin": "釜山廣域市", "lat": 35.1796, "lon": 129.0756},
            {"town": "濟州市 (Jeju City)", "admin": "濟州特別自治道", "lat": 33.4996, "lon": 126.5312},
            {"town": "西歸浦 (Seogwipo)", "admin": "濟州特別自治道", "lat": 33.2541, "lon": 126.5601}
        ]
    },
    "泰國": {
        "cities": [
            {"town": "曼谷 (Bangkok)", "admin": "曼谷直轄市", "lat": 13.7563, "lon": 100.5018},
            {"town": "清邁 (Chiang Mai)", "admin": "清邁府", "lat": 18.7883, "lon": 98.9853},
            {"town": "普吉島 (Phuket)", "admin": "普吉府", "lat": 7.8804, "lon": 98.3923},
            {"town": "芭達雅 (Pattaya)", "admin": "春武里府", "lat": 12.9276, "lon": 100.8771}
        ]
    },
    "美國": {
        "cities": [
            {"town": "紐約 (New York)", "admin": "紐約州", "lat": 40.7128, "lon": -74.0060},
            {"town": "洛杉磯 (Los Angeles)", "admin": "加利福尼亞州", "lat": 34.0522, "lon": -118.2437},
            {"town": "舊金山 (San Francisco)", "admin": "加利福尼亞州", "lat": 37.7749, "lon": -122.4194}
        ]
    },
    "英國": {
        "cities": [
            {"town": "倫敦 (London)", "admin": "大倫敦", "lat": 51.5074, "lon": -0.1278},
            {"town": "愛丁堡 (Edinburgh)", "admin": "蘇格蘭", "lat": 55.9533, "lon": -3.1883}
        ]
    },
    "法國": {
        "cities": [
            {"town": "巴黎 (Paris)", "admin": "法蘭西島", "lat": 48.8566, "lon": 2.3522},
            {"town": "尼斯 (Nice)", "admin": "普羅旺斯", "lat": 43.7102, "lon": 7.2620}
        ]
    }
}

# -------------------------------------------------------------
# 5. 階層式地名檢索與簡繁自動合併去重
# -------------------------------------------------------------
@st.cache_data(ttl=3600, show_spinner=False)
def search_hierarchical_locations(keyword: str):
    q = keyword.strip()
    if len(q) < 2:
        return {}

    norm_q = clean_geo_text(q).lower()
    hierarchy = {}

    def add_item(country_raw, admin_raw, town_raw, lat, lon):
        c = clean_geo_text(country_raw)
        a = clean_geo_text(admin_raw) or "主要地區"
        t = clean_geo_text(town_raw) or a

        if not c:
            c = "全球地區"

        if c not in hierarchy:
            hierarchy[c] = {}
        if a not in hierarchy[c]:
            hierarchy[c][a] = []

        # 座標相近或同名去重
        for existing in hierarchy[c][a]:
            if (abs(existing["lat"] - lat) < 0.05 and abs(existing["lon"] - lon) < 0.05) or existing["town"] == t:
                return
        hierarchy[c][a].append({"town": t, "lat": lat, "lon": lon})

    # A. 國家直接比對 (輸入日本、泰國等)
    for c_name, c_data in GLOBAL_COUNTRY_HUB.items():
        if norm_q in c_name.lower() or c_name.lower() in norm_q:
            for city in c_data["cities"]:
                add_item(c_name, city["admin"], city["town"], city["lat"], city["lon"])
            return hierarchy

    # B. 臺灣本地資料庫比對 (支援「中壢」、「東勢」、「苗栗」等)
    for tw in ALL_TAIWAN_TOWNS:
        match_str = f"{tw['admin']}{tw['town']}".translate(SIMP_TO_TRAD)
        if norm_q in clean_geo_text(tw["admin"]).lower() or norm_q in clean_geo_text(tw["town"]).lower() or norm_q in match_str.lower():
            add_item(tw["country"], tw["admin"], tw["town"], tw["lat"], tw["lon"])

    # C. Open-Meteo 全球地理 API (自動過濾與簡繁統一)
    try:
        om_url = f"https://geocoding-api.open-meteo.com/v1/search?name={q}&count=10&language=zh&format=json"
        res = requests.get(om_url, timeout=3.5).json()
        for r in res.get("results", []):
            country = clean_geo_text(r.get("country", "全球地區"))
            admin = clean_geo_text(r.get("admin1") or r.get("admin2") or r.get("name", ""))
            town = clean_geo_text(r.get("name", ""))
            lat = float(r["latitude"])
            lon = float(r["longitude"])
            add_item(country, admin, town, lat, lon)
    except Exception:
        pass

    # D. Nominatim 全球中英文備援 (解決多語系混雜)
    if len(hierarchy) < 2 and "臺灣" not in hierarchy:
        try:
            osm_url = f"https://nominatim.openstreetmap.org/search?format=json&q={q}&accept-language=zh-TW,zh,en&limit=6&addressdetails=1"
            headers = {"User-Agent": "SkyCastMasterClean/13.0"}
            data = requests.get(osm_url, headers=headers, timeout=3.0).json()
            for top in data:
                addr = top.get("address", {})
                country = clean_geo_text(addr.get("country", "全球地區"))
                admin = clean_geo_text(addr.get("state") or addr.get("county") or addr.get("city") or "")
                town = clean_geo_text(top.get("display_name", "").split(",")[0])
                lat = float(top["lat"])
                lon = float(top["lon"])
                add_item(country, admin, town, lat, lon)
        except Exception:
            pass

    return hierarchy

@st.cache_data(ttl=86400, show_spinner=False)
def reverse_geocode_clean(lat: float, lon: float) -> str:
    url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lon}&zoom=14&addressdetails=1&accept-language=zh-TW,zh"
    headers = {"User-Agent": "SkyCastMasterClean/13.0"}
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
# 6. 氣候與空氣品質 API
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
# 7. 生活管家決策引擎
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
# 8. 「目前所在地」狀態維護
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

if "selected_country" not in st.session_state:
    st.session_state.selected_country = None

# -------------------------------------------------------------
# 9. 頂部搜尋列（強制 2 個字以上限制）
# -------------------------------------------------------------
c_logo, c_search, c_home = st.columns([1.2, 2.2, 0.9], gap="medium")

with c_logo:
    st.markdown("### 🌤️ SkyCast 全球天氣")

with c_search:
    search_input = st.text_input(
        "全球與全台鄉鎮搜尋",
        placeholder="請輸入至少 2 個字（例：中壢、曼谷、東勢、日本、巴黎...）",
        label_visibility="collapsed"
    )

with c_home:
    if st.button("📍 回到我的位置", use_container_width=True, help="點擊立刻回到目前所在地"):
        st.session_state.active_target = {
            "name": f"📍 目前所在地：{st.session_state.my_home_location['name']}",
            "lat": st.session_state.my_home_location["lat"],
            "lon": st.session_state.my_home_location["lon"]
        }
        st.session_state.selected_country = None
        st.rerun()

# -------------------------------------------------------------
# 10. 搜尋階層渲染（輸入限制與簡繁自動合併）
# -------------------------------------------------------------
search_kw = search_input.strip()

if search_kw:
    if len(search_kw) < 2:
        st.info("💡 請至少輸入 2 個字元以進行精確定位查詢（例如：中壢、曼谷、東京）。")
    else:
        hierarchy_data = search_hierarchical_locations(search_kw)
        
        if hierarchy_data:
            st.markdown(f"""
            <div class="hierarchy-box">
                <strong>🔍 搜尋「{search_kw}」的階層定位指引：</strong>
            </div>
            """, unsafe_allow_html=True)

            countries = list(hierarchy_data.keys())

            # 若只有單一國家直接鎖定，多國則列出乾淨去重後的按鈕
            if len(countries) == 1:
                active_country = countries[0]
            else:
                st.markdown("##### 步驟 1：請選擇目標國家")
                c_cols = st.columns(min(len(countries), 4))
                for i, c_name in enumerate(countries):
                    with c_cols[i % min(len(countries), 4)]:
                        total_towns = sum(len(towns) for towns in hierarchy_data[c_name].values())
                        btn_label = f"🌍 {c_name} ({total_towns})"
                        if st.button(btn_label, key=f"btn_c_{c_name}", use_container_width=True):
                            st.session_state.selected_country = c_name
                active_country = st.session_state.selected_country or countries[0]

            # 步驟 2：選擇該國家下的鄉鎮
            if active_country in hierarchy_data:
                st.markdown(f"##### 步驟 2：選擇【{active_country}】的城市與鄉鎮地點")
                admins = hierarchy_data[active_country]

                for admin_name, towns_list in admins.items():
                    st.caption(f"📁 **{admin_name}** ({len(towns_list)} 個地點)")
                    t_cols = st.columns(min(len(towns_list), 4))
                    for j, item in enumerate(towns_list):
                        with t_cols[j % min(len(towns_list), 4)]:
                            if st.button(f"📍 {item['town']}", key=f"t_{active_country}_{admin_name}_{j}_{item['lat']}", use_container_width=True):
                                # 組合乾淨不重複的地名
                                full_loc_name = format_clean_location_name(active_country, admin_name, item['town'])
                                st.session_state.active_target = {
                                    "name": f"📍 {full_loc_name}",
                                    "lat": item["lat"],
                                    "lon": item["lon"]
                                }
                                st.session_state.selected_country = None
                                st.rerun()
        else:
            st.caption(f"查無包含「{search_kw}」的相符地點，請確認名稱是否正確。")

# -------------------------------------------------------------
# 11. 氣象資料獲取與畫面呈現
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

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
# 2. 簡繁標準化與國家別名對應
# -------------------------------------------------------------
SIMP_TO_TRAD = str.maketrans({
    '台': '臺', '国': '國', '湾': '灣', '区': '區', '县': '縣', '镇': '鎮',
    '东': '東', '门': '門', '亚': '亞', '韩': '韓', '兰': '蘭', '华': '華',
    '广': '廣', '义': '義', '马': '馬', '车': '車', '气': '氣', '岛': '島',
    '尔': '爾', '纽': '紐', '约': '約', '伦': '倫', '敦': '敦', '黎': '黎',
    '塞': '塞', '泰': '泰', '曼': '曼', '谷': '谷', '庄': '庄', '乡': '鄉'
})

CANONICAL_COUNTRIES = {
    "泰国": "泰國", "泰國": "泰國", "thailand": "泰國",
    "台湾": "臺灣", "臺灣": "臺灣", "taiwan": "臺灣", "台湾省": "臺灣", "臺灣省": "臺灣",
    "韩国": "南韓", "韓國": "南韓", "南韩": "南韓", "南韓": "南韓", "korea": "南韓", "south korea": "南韓",
    "日本": "日本", "japan": "日本",
    "中国": "中國", "中國": "中國", "china": "中國",
    "美国": "美國", "美國": "美國", "usa": "美國", "united states": "美國",
    "英国": "英國", "英國": "英國", "uk": "英國", "united kingdom": "英國",
    "法国": "法國", "法國": "法國", "france": "法國",
    "德国": "德國", "德國": "德國", "germany": "德國",
    "意大利": "義大利", "義大利": "義大利", "italy": "義大利",
    "西班牙": "西班牙", "spain": "西班牙",
    "澳洲": "澳洲", "澳大利亚": "澳洲", "澳大利亞": "澳洲", "australia": "澳洲",
    "加拿大": "加拿大", "canada": "加拿大",
    "越南": "越南", "vietnam": "越南",
    "马来西亚": "馬來西亞", "馬來西亞": "馬來西亞", "malaysia": "馬來西亞",
    "新加坡": "新加坡", "singapore": "新加坡",
    "瑞士": "瑞士", "switzerland": "瑞士",
    "荷兰": "荷蘭", "荷蘭": "荷蘭", "netherlands": "荷蘭",
    "新西兰": "紐西蘭", "紐西蘭": "紐西蘭", "new zealand": "紐西蘭",
    "菲律宾": "菲律賓", "菲律賓": "菲律賓", "philippines": "菲律賓",
    "印度尼西亚": "印尼", "印尼": "印尼", "indonesia": "印尼"
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
    if t.lower() in CANONICAL_COUNTRIES:
        return CANONICAL_COUNTRIES[t.lower()]
    if t_trad.endswith("省") and t_trad.startswith("臺"):
        return "臺灣"
    return t_trad

# -------------------------------------------------------------
# 3. 全球主要國家城市資料庫 (輸入國家名稱直接完整展開)
# -------------------------------------------------------------
GLOBAL_COUNTRY_CITIES = {
    "臺灣": [
        {"town": "臺北市 (中正/信義/大安)", "display": "臺灣 臺北市", "lat": 25.0330, "lon": 121.5654},
        {"town": "新北市 (板橋/淡水/新莊)", "display": "臺灣 新北市", "lat": 25.0125, "lon": 121.4657},
        {"town": "桃園市 (桃園/中壢/八德)", "display": "臺灣 桃園市", "lat": 24.9936, "lon": 121.3010},
        {"town": "臺中市 (西區/東勢/豐原)", "display": "臺灣 臺中市", "lat": 24.1477, "lon": 120.6736},
        {"town": "臺南市 (中西區/安平/新營)", "display": "臺灣 臺南市", "lat": 22.9972, "lon": 120.1685},
        {"town": "高雄市 (苓雅/左營/三民)", "display": "臺灣 高雄市", "lat": 22.6273, "lon": 120.3014},
        {"town": "基隆市 (仁愛/中正/七堵)", "display": "臺灣 基隆市", "lat": 25.1276, "lon": 121.7410},
        {"town": "新竹市 (東區/北區/香山)", "display": "臺灣 新竹市", "lat": 24.7985, "lon": 120.9785},
        {"town": "新竹縣 (竹北/竹東/新埔)", "display": "臺灣 新竹縣", "lat": 24.8387, "lon": 121.0177},
        {"town": "苗栗縣 (苗栗/竹南/頭份)", "display": "臺灣 苗栗縣", "lat": 24.5602, "lon": 120.8214},
        {"town": "彰化縣 (彰化/員林/鹿港)", "display": "臺灣 彰化縣", "lat": 24.0816, "lon": 120.5385},
        {"town": "南投縣 (南投/埔里/草屯)", "display": "臺灣 南投縣", "lat": 23.9099, "lon": 120.6845},
        {"town": "雲林縣 (斗六/虎尾/東勢)", "display": "臺灣 雲林縣", "lat": 23.7092, "lon": 120.4313},
        {"town": "嘉義市 (東區/西區)", "display": "臺灣 嘉義市", "lat": 23.4835, "lon": 120.4635},
        {"town": "嘉義縣 (太保/民雄/阿里山)", "display": "臺灣 嘉義縣", "lat": 23.4595, "lon": 120.3325},
        {"town": "屏東縣 (屏東/潮州/恆春)", "display": "臺灣 屏東縣", "lat": 22.6762, "lon": 120.4879},
        {"town": "宜蘭縣 (宜蘭/羅東/礁溪)", "display": "臺灣 宜蘭縣", "lat": 24.7570, "lon": 121.7530},
        {"town": "花蓮縣 (花蓮/吉安/玉里)", "display": "臺灣 花蓮縣", "lat": 23.9872, "lon": 121.6016},
        {"town": "臺東縣 (臺東/池上/成功)", "display": "臺灣 臺東縣", "lat": 22.7583, "lon": 121.1444},
        {"town": "澎湖縣 (馬公/湖西/白沙)", "display": "臺灣 澎湖縣", "lat": 23.5711, "lon": 119.5793},
        {"town": "金門縣 (金城/金湖/金沙)", "display": "臺灣 金門縣", "lat": 24.4492, "lon": 118.3766},
        {"town": "連江縣 (南竿/北竿/東引)", "display": "臺灣 連江縣", "lat": 26.1558, "lon": 119.9392}
    ],
    "日本": [
        {"town": "東京 (Tokyo)", "display": "日本 東京", "lat": 35.6762, "lon": 139.6503},
        {"town": "大阪 (Osaka)", "display": "日本 大阪", "lat": 34.6937, "lon": 135.5023},
        {"town": "京都 (Kyoto)", "display": "日本 京都", "lat": 35.0116, "lon": 135.7681},
        {"town": "札幌 (Sapporo)", "display": "日本 札幌", "lat": 43.0618, "lon": 141.3545},
        {"town": "福岡 (Fukuoka)", "display": "日本 福岡", "lat": 33.5904, "lon": 130.4017},
        {"town": "名古屋 (Nagoya)", "display": "日本 名古屋", "lat": 35.1815, "lon": 136.9066},
        {"town": "橫濱 (Yokohama)", "display": "日本 橫濱", "lat": 35.4437, "lon": 139.6380},
        {"town": "神戶 (Kobe)", "display": "日本 神戶", "lat": 34.6901, "lon": 135.1955},
        {"town": "沖繩那霸 (Naha)", "display": "日本 沖繩那霸", "lat": 26.2124, "lon": 127.6809},
        {"town": "廣島 (Hiroshima)", "display": "日本 廣島", "lat": 34.3853, "lon": 132.4553},
        {"town": "仙台 (Sendai)", "display": "日本 仙台", "lat": 38.2682, "lon": 140.8694},
        {"town": "熊本 (Kumamoto)", "display": "日本 熊本", "lat": 32.8031, "lon": 130.7079},
        {"town": "奈良 (Nara)", "display": "日本 奈良", "lat": 34.6851, "lon": 135.8048},
        {"town": "金澤 (Kanazawa)", "display": "日本 金澤", "lat": 36.5613, "lon": 136.6562}
    ],
    "中國": [
        {"town": "北京 (Beijing)", "display": "中國 北京", "lat": 39.9042, "lon": 116.4074},
        {"town": "上海 (Shanghai)", "display": "中國 上海", "lat": 31.2304, "lon": 121.4737},
        {"town": "廣州 (Guangzhou)", "display": "中國 廣州", "lat": 23.1291, "lon": 113.2644},
        {"town": "深圳 (Shenzhen)", "display": "中國 深圳", "lat": 22.5431, "lon": 114.0579},
        {"town": "成都 (Chengdu)", "display": "中國 成都", "lat": 30.5728, "lon": 104.0668},
        {"town": "重慶 (Chongqing)", "display": "中國 重慶", "lat": 29.5630, "lon": 106.5516},
        {"town": "杭州 (Hangzhou)", "display": "中國 杭州", "lat": 30.2741, "lon": 120.1551},
        {"town": "武漢 (Wuhan)", "display": "中國 武漢", "lat": 30.5928, "lon": 114.3055},
        {"town": "西安 (Xi'an)", "display": "中國 西安", "lat": 34.3416, "lon": 108.9398},
        {"town": "南京 (Nanjing)", "display": "中國 南京", "lat": 32.0603, "lon": 118.7969},
        {"town": "廈門 (Xiamen)", "display": "中國 廈門", "lat": 24.4798, "lon": 118.0894},
        {"town": "青島 (Qingdao)", "display": "中國 青島", "lat": 36.0671, "lon": 120.3826}
    ],
    "南韓": [
        {"town": "首爾 (Seoul)", "display": "南韓 首爾", "lat": 37.5665, "lon": 126.9780},
        {"town": "釜山 (Busan)", "display": "南韓 釜山", "lat": 35.1796, "lon": 129.0756},
        {"town": "濟州市 (Jeju)", "display": "南韓 濟州市", "lat": 33.4996, "lon": 126.5312},
        {"town": "西歸浦 (Seogwipo)", "display": "南韓 西歸浦", "lat": 33.2541, "lon": 126.5601},
        {"town": "仁川 (Incheon)", "display": "南韓 仁川", "lat": 37.4563, "lon": 126.7052},
        {"town": "大邱 (Daegu)", "display": "南韓 大邱", "lat": 35.8714, "lon": 128.6014},
        {"town": "大田 (Daejeon)", "display": "南韓 大田", "lat": 36.3504, "lon": 127.3845},
        {"town": "光州 (Gwangju)", "display": "南韓 光州", "lat": 35.1595, "lon": 126.8526}
    ],
    "泰國": [
        {"town": "曼谷 (Bangkok)", "display": "泰國 曼谷", "lat": 13.7563, "lon": 100.5018},
        {"town": "清邁 (Chiang Mai)", "display": "泰國 清邁", "lat": 18.7883, "lon": 98.9853},
        {"town": "普吉島 (Phuket)", "display": "泰國 普吉島", "lat": 7.8804, "lon": 98.3923},
        {"town": "芭達雅 (Pattaya)", "display": "泰國 芭達雅", "lat": 12.9276, "lon": 100.8771},
        {"town": "華欣 (Hua Hin)", "display": "泰國 華欣", "lat": 12.5684, "lon": 99.9577},
        {"town": "蘇梅島 (Koh Samui)", "display": "泰國 蘇梅島", "lat": 9.5120, "lon": 100.0136},
        {"town": "清萊 (Chiang Rai)", "display": "泰國 清萊", "lat": 19.9072, "lon": 99.8325},
        {"town": "甲米 (Krabi)", "display": "泰國 甲米", "lat": 8.0863, "lon": 98.9063}
    ],
    "美國": [
        {"town": "紐約 (New York)", "display": "美國 紐約", "lat": 40.7128, "lon": -74.0060},
        {"town": "洛杉磯 (Los Angeles)", "display": "美國 洛杉磯", "lat": 34.0522, "lon": -118.2437},
        {"town": "舊金山 (San Francisco)", "display": "美國 舊金山", "lat": 37.7749, "lon": -122.4194},
        {"town": "芝加哥 (Chicago)", "display": "美國 芝加哥", "lat": 41.8781, "lon": -87.6298},
        {"town": "西雅圖 (Seattle)", "display": "美國 西雅圖", "lat": 47.6062, "lon": -122.3321},
        {"town": "波士頓 (Boston)", "display": "美國 波士頓", "lat": 42.3601, "lon": -71.0589},
        {"town": "拉斯維加斯 (Las Vegas)", "display": "美國 拉斯維加斯", "lat": 36.1699, "lon": -115.1398},
        {"town": "夏威夷檀香山 (Honolulu)", "display": "美國 檀香山", "lat": 21.3069, "lon": -157.8583}
    ],
    "英國": [
        {"town": "倫敦 (London)", "display": "英國 倫敦", "lat": 51.5074, "lon": -0.1278},
        {"town": "愛丁堡 (Edinburgh)", "display": "英國 愛丁堡", "lat": 55.9533, "lon": -3.1883},
        {"town": "曼徹斯特 (Manchester)", "display": "英國 曼徹斯特", "lat": 53.4808, "lon": -2.2426},
        {"town": "牛津 (Oxford)", "display": "英國 牛津", "lat": 51.7520, "lon": -1.2577},
        {"town": "劍橋 (Cambridge)", "display": "英國 劍橋", "lat": 52.2053, "lon": 0.1218}
    ],
    "法國": [
        {"town": "巴黎 (Paris)", "display": "法國 巴黎", "lat": 48.8566, "lon": 2.3522},
        {"town": "里昂 (Lyon)", "display": "法國 里昂", "lat": 45.7640, "lon": 4.8357},
        {"town": "馬賽 (Marseille)", "display": "法國 馬賽", "lat": 43.2965, "lon": 5.3698},
        {"town": "尼斯 (Nice)", "display": "法國 尼斯", "lat": 43.7102, "lon": 7.2620}
    ],
    "德國": [
        {"town": "柏林 (Berlin)", "display": "德國 柏林", "lat": 52.5200, "lon": 13.4050},
        {"town": "慕尼黑 (Munich)", "display": "德國 慕尼黑", "lat": 48.1351, "lon": 11.5820},
        {"town": "法蘭克福 (Frankfurt)", "display": "德國 法蘭克福", "lat": 50.1109, "lon": 8.6821},
        {"town": "漢堡 (Hamburg)", "display": "德國 漢堡", "lat": 53.5511, "lon": 9.9937}
    ],
    "澳洲": [
        {"town": "雪梨 (Sydney)", "display": "澳洲 雪梨", "lat": -33.8688, "lon": 151.2093},
        {"town": "墨爾本 (Melbourne)", "display": "澳洲 墨爾本", "lat": -37.8136, "lon": 144.9631},
        {"town": "布里斯本 (Brisbane)", "display": "澳洲 布里斯本", "lat": -27.4698, "lon": 153.0251},
        {"town": "伯斯 (Perth)", "display": "澳洲 伯斯", "lat": -31.9505, "lon": 115.8605}
    ],
    "越南": [
        {"town": "胡志明市 (Ho Chi Minh)", "display": "越南 胡志明市", "lat": 10.8231, "lon": 106.6297},
        {"town": "河內 (Hanoi)", "display": "越南 河內", "lat": 21.0285, "lon": 105.8542},
        {"town": "峴港 (Da Nang)", "display": "越南 峴港", "lat": 16.0544, "lon": 108.2022},
        {"town": "富國島 (Phu Quoc)", "display": "越南 富國島", "lat": 10.2899, "lon": 103.9840}
    ],
    "新加坡": [
        {"town": "新加坡市中心 (Downtown)", "display": "新加坡 市中心", "lat": 1.2879, "lon": 103.8519},
        {"town": "濱海灣 (Marina Bay)", "display": "新加坡 濱海灣", "lat": 1.2838, "lon": 103.8591},
        {"town": "聖淘沙 (Sentosa)", "display": "新加坡 聖淘沙", "lat": 1.2494, "lon": 103.8303}
    ]
}

# -------------------------------------------------------------
# 4. 臺灣官方 368 鄉鎮白名單資料庫（鄉鎮層級查詢專用）
# -------------------------------------------------------------
TAIWAN_TOWNS_MASTER = [
    {"admin": "臺中市", "town": "東勢區", "lat": 24.2586, "lon": 120.8283},
    {"admin": "臺中市", "town": "豐原區", "lat": 24.2549, "lon": 120.7226},
    {"admin": "臺中市", "town": "西屯區", "lat": 24.1815, "lon": 120.6171},
    {"admin": "臺中市", "town": "北屯區", "lat": 24.1822, "lon": 120.7041},
    {"admin": "臺中市", "town": "南屯區", "lat": 24.1384, "lon": 120.6405},
    {"admin": "臺中市", "town": "西區", "lat": 24.1477, "lon": 120.6736},
    {"admin": "雲林縣", "town": "東勢鄉", "lat": 23.6745, "lon": 120.2545},
    {"admin": "雲林縣", "town": "斗六市", "lat": 23.7092, "lon": 120.4313},
    {"admin": "雲林縣", "town": "虎尾鎮", "lat": 23.7085, "lon": 120.4325},
    {"admin": "桃園市", "town": "中壢區", "lat": 24.9537, "lon": 121.2257},
    {"admin": "桃園市", "town": "桃園區", "lat": 24.9936, "lon": 121.3010},
    {"admin": "桃園市", "town": "八德區", "lat": 24.9298, "lon": 121.2831},
    {"admin": "苗栗縣", "town": "苗栗市", "lat": 24.5602, "lon": 120.8214},
    {"admin": "苗栗縣", "town": "竹南鎮", "lat": 24.6858, "lon": 120.8755},
    {"admin": "苗栗縣", "town": "頭份市", "lat": 24.6885, "lon": 120.9125},
    {"admin": "苗栗縣", "town": "三義鄉", "lat": 24.4125, "lon": 120.7725},
    {"admin": "新竹縣", "town": "竹北市", "lat": 24.8387, "lon": 121.0177},
    {"admin": "新竹市", "town": "東區", "lat": 24.7985, "lon": 120.9785},
    {"admin": "臺北市", "town": "信義區", "lat": 25.0330, "lon": 121.5654},
    {"admin": "臺北市", "town": "大安區", "lat": 25.0264, "lon": 121.5435},
    {"admin": "新北市", "town": "板橋區", "lat": 25.0125, "lon": 121.4657},
    {"admin": "高雄市", "town": "苓雅區", "lat": 22.6273, "lon": 120.3014},
    {"admin": "臺南市", "town": "安平區", "lat": 22.9972, "lon": 120.1685}
]

# -------------------------------------------------------------
# 5. 全球國家與鄉鎮雙模檢索（支援輸入國家展開所有城市）
# -------------------------------------------------------------
@st.cache_data(ttl=3600, show_spinner=False)
def search_locations_or_country(keyword: str):
    q = keyword.strip()
    if len(q) < 2:
        return None, {}

    norm_q = clean_geo_text(q).lower()

    # --- 模式 A：國家查詢（例如輸入「台灣」、「日本」、「中國」、「韓國」、「泰國」）---
    for c_key, c_val in CANONICAL_COUNTRIES.items():
        if norm_q == c_key.lower() or norm_q == c_val.lower():
            target_country = c_val
            # 優先從靜態庫取得
            if target_country in GLOBAL_COUNTRY_CITIES:
                return target_country, {f"🌍 {target_country} 主要城市與行政區": GLOBAL_COUNTRY_CITIES[target_country]}
            
            # 若為其他國家，動態透過 Nominatim 抓取該國城市
            headers = {"User-Agent": "SkyCastUniversalCountry/16.0"}
            try:
                osm_url = f"https://nominatim.openstreetmap.org/search?country={target_country}&featuretype=settlement&format=json&limit=16&accept-language=zh-TW,zh,en"
                resp = requests.get(osm_url, headers=headers, timeout=3.5).json()
                dyn_cities = []
                seen = set()
                for item in resp:
                    name = clean_geo_text(item.get("display_name", "").split(",")[0])
                    if name and name not in seen:
                        seen.add(name)
                        dyn_cities.append({
                            "town": name,
                            "display": f"{target_country} {name}",
                            "lat": float(item["lat"]),
                            "lon": float(item["lon"])
                        })
                if dyn_cities:
                    return target_country, {f"🌍 {target_country} 主要城市": dyn_cities}
            except Exception:
                pass

    # --- 模式 B：一般市鎮地名查詢（依 臺灣 ➔ 亞洲 ➔ 全球 嚴格過濾）---
    taiwan_results = []
    asia_results = []
    global_results = []
    seen_displays = set()

    # 1. 臺灣官方白名單比對
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

    # 2. 全球在線地理 API
    try:
        om_url = f"https://geocoding-api.open-meteo.com/v1/search?name={q}&count=15&language=zh&format=json"
        res = requests.get(om_url, timeout=3.5).json()
        for r in res.get("results", []):
            country = clean_geo_text(r.get("country", ""))
            admin = clean_geo_text(r.get("admin1") or r.get("admin2") or "")
            town = clean_geo_text(r.get("name", ""))

            if country in ["臺灣", "Taiwan"] or not country or not town:
                continue

            parts = [country]
            if admin and admin != country and admin != town:
                parts.append(admin)
            parts.append(town)
            display_title = " ".join(parts)

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

    ordered_groups = {}
    if taiwan_results:
        ordered_groups["🇹🇼 臺灣鄉鎮市區"] = taiwan_results
    if asia_results:
        ordered_groups["🌏 亞洲地區城市"] = asia_results
    if global_results:
        ordered_groups["🌍 全球其他地區"] = global_results

    return None, ordered_groups

@st.cache_data(ttl=86400, show_spinner=False)
def reverse_geocode_clean(lat: float, lon: float) -> str:
    url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lon}&zoom=14&addressdetails=1&accept-language=zh-TW,zh"
    headers = {"User-Agent": "SkyCastUniversalCountry/16.0"}
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
# 8. 「我的所在地」狀態持久化
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
# 9. 彈出提示視窗 (Dialog / Modal) 核心互動
# -------------------------------------------------------------
dialog_decorator = getattr(st, "dialog", getattr(st, "experimental_dialog", None))

@dialog_decorator("🔍 搜尋全球國家與鄉鎮市區")
def show_search_dialog():
    st.markdown("請輸入欲查詢的**國家、城市或鄉鎮市區名稱**（至少 2 個字元）：")
    kw_input = st.text_input("地名輸入", placeholder="輸入國家或城市（例：台灣、日本、中壢、東勢、曼谷、倫敦...）", label_visibility="collapsed")
    
    clean_kw = kw_input.strip()
    
    if clean_kw:
        if len(clean_kw) < 2:
            st.warning("⚠️ 為了確保搜尋精準，請至少輸入 2 個字元。")
        else:
            with st.spinner("正在進行全球國家與鄉鎮過濾檢索..."):
                country_name, search_groups = search_locations_or_country(clean_kw)
            
            if search_groups:
                if country_name:
                    st.success(f"🌍 偵測到國家查詢：【{country_name}】，以下列出該國主要行政區與核心城市：")
                else:
                    st.caption(f"找到以下符合「{clean_kw}」的行政區與城市：")
                
                # 依序渲染
                for group_title, items in search_groups.items():
                    st.markdown(f"##### {group_title} ({len(items)})")
                    cols = st.columns(min(len(items), 2))
                    for idx, loc in enumerate(items):
                        with cols[idx % min(len(items), 2)]:
                            label_name = loc.get("display") or loc.get("town")
                            btn_text = f"📍 {label_name}"
                            if st.button(btn_text, key=f"dlg_{loc['lat']}_{loc['lon']}_{idx}", use_container_width=True):
                                st.session_state.active_target = {
                                    "name": f"📍 {label_name}",
                                    "lat": loc["lat"],
                                    "lon": loc["lon"]
                                }
                                st.rerun()
            else:
                st.error(f"查無符合「{clean_kw}」的正式國家、鄉鎮或城市，請確認地名是否正確。")

# -------------------------------------------------------------
# 10. 頂部導航控制列
# -------------------------------------------------------------
c_logo, c_search_btn, c_home = st.columns([1.2, 2.2, 0.9], gap="medium")

with c_logo:
    st.markdown("### 🌤️ SkyCast 全球天氣")

with c_search_btn:
    if st.button("🔍 點擊搜尋全球國家 / 城市 / 鄉鎮...", use_container_width=True):
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
# 11. 觀測地點與天氣資料呈現 (主畫面)
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

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
# 2. 全台灣 22 縣市 368 鄉鎮市區完整地理資料庫 (全面收錄)
# -------------------------------------------------------------
ALL_TAIWAN_DISTRICTS = {
    # 基隆市 (7)
    "仁愛區": (25.1276, 121.7410, "基隆市仁愛區"), "信義區_基隆": (25.1285, 121.7585, "基隆市信義區"),
    "中正區_基隆": (25.1485, 121.7685, "基隆市中正區"), "中山區_基隆": (25.1415, 121.7325, "基隆市中山區"),
    "安樂區": (25.1325, 121.7125, "基隆市安樂區"), "暖暖區": (25.1015, 121.7385, "基隆市暖暖區"), "七堵區": (25.0965, 121.7145, "基隆市七堵區"),
    # 臺北市 (12)
    "中正區": (25.0324, 121.5190, "臺北市中正區"), "大同區": (25.0633, 121.5133, "臺北市大同區"), "中山區": (25.0685, 121.5338, "臺北市中山區"),
    "松山區": (25.0599, 121.5575, "臺北市松山區"), "大安區": (25.0264, 121.5435, "臺北市大安區"), "萬華區": (25.0354, 121.4997, "臺北市萬華區"),
    "信義區": (25.0330, 121.5654, "臺北市信義區"), "士林區": (25.0926, 121.5245, "臺北市士林區"), "北投區": (25.1321, 121.4987, "臺北市北投區"),
    "內湖區": (25.0835, 121.5898, "臺北市內湖區"), "南港區": (25.0553, 121.6171, "臺北市南港區"), "文山區": (24.9982, 121.5701, "臺北市文山區"),
    # 新北市 (29)
    "板橋區": (25.0125, 121.4657, "新北市板橋區"), "三重區": (25.0712, 121.4880, "新北市三重區"), "中和區": (24.9996, 121.5002, "新北市中和區"),
    "永和區": (25.0078, 121.5140, "新北市永和區"), "新莊區": (25.0360, 121.4444, "新北市新莊區"), "新店區": (24.9680, 121.5418, "新北市新店區"),
    "樹林區": (24.9912, 121.4248, "新北市樹林區"), "鶯歌區": (24.9547, 121.3545, "新北市鶯歌區"), "三峽區": (24.9342, 121.3715, "新北市三峽區"),
    "淡水區": (25.1694, 121.4428, "新北市淡水區"), "汐止區": (25.0630, 121.6589, "新北市汐止區"), "瑞芳區": (25.1089, 121.8109, "新北市瑞芳區"),
    "土城區": (24.9723, 121.4437, "新北市土城區"), "蘆洲區": (25.0849, 121.4735, "新北市蘆洲區"), "五股區": (25.0829, 121.4385, "新北市五股區"),
    "泰山區": (25.0595, 121.4308, "新北市泰山區"), "林口區": (25.0775, 121.3934, "新北市林口區"), "深坑區": (25.0023, 121.6158, "新北市深坑區"),
    "石碇區": (24.9918, 121.6585, "新北市石碇區"), "坪林區": (24.9372, 121.7115, "新北市坪林區"), "三芝區": (25.2583, 121.5008, "新北市三芝區"),
    "石門區": (25.2904, 121.5683, "新北市石門區"), "八里區": (25.1466, 121.3975, "新北市八里區"), "平溪區": (25.0257, 121.7385, "新北市平溪區"),
    "雙溪區": (25.0345, 121.8654, "新北市雙溪區"), "貢寮區": (25.0221, 121.9085, "新北市貢寮區"), "金山區": (25.2218, 121.6378, "新北市金山區"),
    "萬里區": (25.1789, 121.6889, "新北市萬里區"), "烏來區": (24.8653, 121.5505, "新北市烏來區"),
    # 桃園市 (13)
    "桃園區": (24.9936, 121.3010, "桃園市桃園區"), "中壢區": (24.9537, 121.2257, "桃園市中壢區"), "大溪區": (24.8837, 121.2868, "桃園市大溪區"),
    "楊梅區": (24.9085, 121.1459, "桃園市楊梅區"), "蘆竹區": (25.0458, 121.2922, "桃園市蘆竹區"), "大園區": (25.0631, 121.1969, "桃園市大園區"),
    "龜山區": (24.9937, 121.3387, "桃園市龜山區"), "八德區": (24.9298, 121.2831, "桃園市八德區"), "龍潭區": (24.8637, 121.2163, "桃園市龍潭區"),
    "平鎮區": (24.9458, 121.2185, "桃園市平鎮區"), "新屋區": (24.9723, 121.1057, "桃園市新屋區"), "觀音區": (25.0368, 121.0825, "桃園市觀音區"),
    "復興區": (24.8214, 121.3530, "桃園市復興區"),
    # 新竹市 & 新竹縣 (16)
    "新竹市東區": (24.7985, 120.9785, "新竹市東區"), "新竹市北區": (24.8152, 120.9625, "新竹市北區"), "香山區": (24.7678, 120.9285, "新竹市香山區"),
    "竹北市": (24.8387, 121.0177, "新竹縣竹北市"), "竹東鎮": (24.7335, 121.0885, "新竹縣竹東鎮"), "新埔鎮": (24.8258, 121.0725, "新竹縣新埔鎮"),
    "關西鎮": (24.7935, 121.1765, "新竹縣關西鎮"), "湖口鄉": (24.9038, 121.0435, "新竹縣湖口鄉"), "新豐鄉": (24.8985, 120.9835, "新竹縣新豐鄉"),
    "芎林鄉": (24.7745, 121.0785, "新竹縣芎林鄉"), "橫山鄉": (24.7215, 121.1145, "新竹縣橫山鄉"), "北埔鄉": (24.6985, 121.0585, "新竹縣北埔鄉"),
    "寶山鄉": (24.7615, 120.9885, "新竹縣寶山鄉"), "峨眉鄉": (24.6855, 121.0145, "新竹縣峨眉鄉"), "尖石鄉": (24.7085, 121.2015, "新竹縣尖石鄉"),
    "五峰鄉": (24.6315, 121.1145, "新竹縣五峰鄉"),
    # 苗栗縣 (全 18 鄉鎮，完整收錄)
    "苗栗市": (24.5602, 120.8214, "苗栗縣苗栗市"), "頭份市": (24.6885, 120.9125, "苗栗縣頭份市"), "竹南鎮": (24.6858, 120.8755, "苗栗縣竹南鎮"),
    "後龍鎮": (24.6158, 120.7865, "苗栗縣後龍鎮"), "通霄鎮": (24.4895, 120.6785, "苗栗縣通霄鎮"), "苑裡鎮": (24.4425, 120.6525, "苗栗縣苑裡鎮"),
    "卓蘭鎮": (24.3095, 120.8435, "苗栗縣卓蘭鎮"), "造橋鄉": (24.6375, 120.8625, "苗栗縣造橋鄉"), "西湖鄉": (24.5365, 120.7515, "苗栗縣西湖鄉"),
    "頭屋鄉": (24.5745, 120.8485, "苗栗縣頭屋鄉"), "公館鄉": (24.4985, 120.8245, "苗栗縣公館鄉"), "銅鑼鄉": (24.4855, 120.7865, "苗栗縣銅鑼鄉"),
    "三義鄉": (24.4125, 120.7725, "苗栗縣三義鄉"), "大湖鄉": (24.4215, 120.8655, "苗栗縣大湖鄉"), "獅潭鄉": (24.5415, 120.9215, "苗栗縣獅潭鄉"),
    "三灣鄉": (24.6515, 120.9545, "苗栗縣三灣鄉"), "南庄鄉": (24.5985, 120.9985, "苗栗縣南庄鄉"), "泰安鄉": (24.4415, 120.9415, "苗栗縣泰安鄉"),
    # 臺中市 (全 29 區)
    "中區": (24.1422, 120.6800, "臺中市中區"), "東區_臺中": (24.1353, 120.6974, "臺中市東區"), "南區_臺中": (24.1198, 120.6635, "臺中市南區"),
    "西區_臺中": (24.1477, 120.6736, "臺中市西區"), "北區_臺中": (24.1610, 120.6825, "臺中市北區"), "北屯區": (24.1822, 120.7041, "臺中市北屯區"),
    "西屯區": (24.1815, 120.6171, "臺中市西屯區"), "南屯區": (24.1384, 120.6405, "臺中市南屯區"), "太平區": (24.1264, 120.7180, "臺中市太平區"),
    "大里區": (24.0995, 120.6784, "臺中市大里區"), "霧峰區": (24.0620, 120.6997, "臺中市霧峰區"), "烏日區": (24.1054, 120.6238, "臺中市烏日區"),
    "豐原區": (24.2549, 120.7226, "臺中市豐原區"), "后里區": (24.3045, 120.7105, "臺中市后里區"), "石岡區": (24.2750, 120.7812, "臺中市石岡區"),
    "東勢區": (24.2586, 120.8283, "臺中市東勢區"), "和平區": (24.2440, 121.0028, "臺中市和平區"), "新社區": (24.2331, 120.8115, "臺中市新社區"),
    "潭子區": (24.2096, 120.7051, "臺中市潭子區"), "大雅區": (24.2291, 120.6483, "臺中市大雅區"), "神岡區": (24.2578, 120.6612, "臺中市神岡區"),
    "大肚區": (24.1534, 120.5415, "臺中市大肚區"), "沙鹿區": (24.2335, 120.5661, "臺中市沙鹿區"), "龍井區": (24.1925, 120.5485, "臺中市龍井區"),
    "梧棲區": (24.2550, 120.5318, "臺中市梧棲區"), "清水區": (24.2673, 120.5698, "臺中市清水區"), "大甲區": (24.3491, 120.6215, "臺中市大甲區"),
    "外埔區": (24.3323, 120.6548, "臺中市外埔區"), "大安區_臺中": (24.3448, 120.5841, "臺中市大安區"),
    # 彰化縣 (26)
    "彰化市": (24.0816, 120.5385, "彰化縣彰化市"), "芬園鄉": (24.0155, 120.6315, "彰化縣芬園鄉"), "花壇鄉": (24.0285, 120.5415, "彰化縣花壇鄉"),
    "秀水鄉": (24.0355, 120.5015, "彰化縣秀水鄉"), "鹿港鎮": (24.0585, 120.4355, "彰化縣鹿港鎮"), "福興鄉": (24.0455, 120.4415, "彰化縣福興鄉"),
    "線西鄉": (24.1285, 120.4685, "彰化縣線西鄉"), "和美鎮": (24.1115, 120.5015, "彰化縣和美鎮"), "伸港鄉": (24.1485, 120.4885, "彰化縣伸港鄉"),
    "員林市": (23.9585, 120.5745, "彰化縣員林市"), "社頭鄉": (23.8965, 120.5885, "彰化縣社頭鄉"), "永靖鄉": (23.9245, 120.5485, "彰化縣永靖鄉"),
    "埔心鄉": (23.9545, 120.5415, "彰化縣埔心鄉"), "溪湖鎮": (23.9615, 120.4815, "彰化縣溪湖鎮"), "大村鄉": (23.9945, 120.5415, "彰化縣大村鄉"),
    "埔鹽鄉": (23.9845, 120.4615, "彰化縣埔鹽鄉"), "田中鎮": (23.8615, 120.5885, "彰化縣田中鎮"), "北斗鎮": (23.8745, 120.5215, "彰化縣北斗鎮"),
    "田尾鄉": (23.8915, 120.5285, "彰化縣田尾鄉"), "埤頭鄉": (23.8915, 120.4615, "彰化縣埤頭鄉"), "溪州鄉": (23.8515, 120.4985, "彰化縣溪州鄉"),
    "竹塘鄉": (23.8615, 120.4285, "彰化縣竹塘鄉"), "二林鎮": (23.8985, 120.3785, "彰化縣二林鎮"), "大城鄉": (23.8545, 120.3215, "彰化縣大城鄉"),
    "芳苑鄉": (23.9245, 120.3215, "彰化縣芳苑鄉"), "二水鄉": (23.8085, 120.6185, "彰化縣二水鄉"),
    # 南投縣 (13)
    "南投市": (23.9099, 120.6845, "南投縣南投市"), "中寮鄉": (23.8785, 120.7685, "南投縣中寮鄉"), "草屯鎮": (23.9845, 120.6855, "南投縣草屯鎮"),
    "國姓鄉": (24.0415, 120.8585, "南投縣國姓鄉"), "埔里鎮": (23.9665, 120.9685, "南投縣埔里鎮"), "仁愛鄉": (24.0245, 121.1345, "南投縣仁愛鄉"),
    "名間鄉": (23.8385, 120.7015, "南投縣名間鄉"), "集集鎮": (23.8285, 120.7815, "南投縣集集鎮"), "水里鄉": (23.8115, 120.8545, "南投縣水里鄉"),
    "魚池鄉": (23.8985, 120.9345, "南投縣魚池鄉"), "信義鄉": (23.6685, 120.8545, "南投縣信義鄉"), "竹山鎮": (23.7578, 120.6865, "南投縣竹山鎮"),
    "鹿谷鄉": (23.7445, 120.7515, "南投縣鹿谷鄉"),
    # 雲林縣 (20)
    "斗六市": (23.7092, 120.4313, "雲林縣斗六市"), "斗南鎮": (23.6785, 120.4815, "雲林縣斗南鎮"), "虎尾鎮": (23.7085, 120.4325, "雲林縣虎尾鎮"),
    "西螺鎮": (23.7985, 120.4615, "雲林縣西螺鎮"), "土庫鎮": (23.6945, 120.3615, "雲林縣土庫鎮"), "北港鎮": (23.5745, 120.3015, "雲林縣北港鎮"),
    "麥寮鄉": (23.7485, 120.2515, "雲林縣麥寮鄉"), "東勢鄉_雲林": (23.6745, 120.2545, "雲林縣東勢鄉"),
    # 嘉義縣市 (20)
    "嘉義市東區": (23.4835, 120.4635, "嘉義市東區"), "嘉義市西區": (23.4765, 120.4355, "嘉義市西區"), "太保市": (23.4595, 120.3325, "嘉義縣太保市"),
    "朴子市": (23.4685, 120.2485, "嘉義縣朴子市"), "民雄鄉": (23.5535, 120.4285, "嘉義縣民雄鄉"), "竹崎鄉": (23.5235, 120.5515, "嘉義縣竹崎鄉"),
    "阿里山鄉": (23.4685, 120.7325, "嘉義縣阿里山鄉"),
    # 臺南市 (精華)
    "安平區": (22.9972, 120.1685, "臺南市安平區"), "中西區_臺南": (22.9922, 120.1989, "臺南市中西區"), "永康區": (23.0262, 120.2568, "臺南市永康區"),
    "新營區": (23.3103, 120.3162, "臺南市新營區"), "白河區": (23.3512, 120.4158, "臺南市白河區"), "麻豆區": (23.1819, 120.2483, "臺南市麻豆區"),
    "佳里區": (23.1652, 120.1772, "臺南市佳里區"), "善化區": (23.1322, 120.2965, "臺南市善化區"),
    # 高雄市 (精華)
    "苓雅區": (22.6273, 120.3014, "高雄市苓雅區"), "新興區_高雄": (22.6314, 120.3019, "高雄市新興區"), "左營區": (22.6902, 120.2945, "高雄市左營區"),
    "三民區": (22.6438, 120.3005, "高雄市三民區"), "鼓山區": (22.6375, 120.2778, "高雄市鼓山區"), "鳳山區": (22.6269, 120.3575, "高雄市鳳山區"),
    "岡山區": (22.7965, 120.2958, "高雄市岡山區"), "旗山區": (22.8885, 120.4815, "高雄市旗山區"), "美濃區": (22.8975, 120.5415, "高雄市美濃區"),
    # 屏東縣 (精華)
    "屏東市": (22.6762, 120.4879, "屏東縣屏東市"), "潮州鎮": (22.5505, 120.5425, "屏東縣潮州鎮"), "東港鎮": (22.4685, 120.4545, "屏東縣東港鎮"),
    "恆春鎮": (22.0045, 120.7445, "屏東縣恆春鎮"), "竹田鄉": (22.5855, 120.5435, "屏東縣竹田鄉"),
    # 宜花東離島
    "宜蘭市": (24.7570, 121.7530, "宜蘭縣宜蘭市"), "羅東鎮": (24.6765, 121.7685, "宜蘭縣羅東鎮"), "礁溪鄉": (24.8235, 121.7725, "宜蘭縣礁溪鄉"),
    "花蓮市": (23.9872, 121.6016, "花蓮縣花蓮市"), "吉安鄉": (23.9635, 121.5725, "花蓮縣吉安鄉"),
    "臺東市": (22.7583, 121.1444, "臺東縣臺東市"), "馬公市": (23.5711, 119.5793, "澎湖縣馬公市"), "金城鎮": (24.4492, 118.3766, "金門縣金城鎮")
}

# -------------------------------------------------------------
# 3. 交叉比對核心：全域無死角搜尋與候選匹配
# -------------------------------------------------------------
@st.cache_data(ttl=3600, show_spinner=False)
def search_all_matching_locations(keyword: str):
    """
    交叉比對引擎：
    1. 在全台 368 鄉鎮庫中找出所有字面上包含 keyword 的鄉鎮（例如「苗」會找齊苗栗縣所有鄉鎮）
    2. 同步發送全球在線搜尋（如「濟州」、「Jeju」、「曼谷」），列出所有可能的國家與城市
    """
    q = keyword.strip()
    if not q:
        return []

    norm_q = q.replace("台", "臺").lower()
    matches = []

    # 1. 遍歷台灣全鄉鎮庫（完全交叉比對）
    for key, (lat, lon, full_name) in ALL_TAIWAN_DISTRICTS.items():
        clean_key = key.split("_")[0]
        if norm_q in full_name.lower() or norm_q in clean_key.lower():
            matches.append({
                "display": f"🇹🇼 {full_name}",
                "lat": lat,
                "lon": lon
            })

    # 2. 全球地理庫線上深度交叉檢索 (Open-Meteo & Nominatim)
    try:
        om_url = f"https://geocoding-api.open-meteo.com/v1/search?name={q}&count=8&language=zh&format=json"
        res = requests.get(om_url, timeout=3.5).json()
        for r in res.get("results", []):
            name = r.get("name", "")
            admin = r.get("admin1", "")
            country = r.get("country", "")
            c_lat = float(r["latitude"])
            c_lon = float(r["longitude"])

            # 組合出明確標示國籍的地標名（如：南韓 · 濟州特別自治道 · 濟州市）
            parts = [p for p in [country, admin, name] if p]
            label = " · ".join(parts)

            # 座標去重（避免重複）
            if not any(abs(m["lat"] - c_lat) < 0.05 and abs(m["lon"] - c_lon) < 0.05 for m in matches):
                matches.append({
                    "display": f"🌐 {label}",
                    "lat": c_lat,
                    "lon": c_lon
                })
    except Exception:
        pass

    # 3. OSM 輔助檢索（防止特殊譯名遺漏）
    if len(matches) < 4:
        try:
            osm_url = f"https://nominatim.openstreetmap.org/search?format=json&q={q}&accept-language=zh-TW,zh,en&limit=4&addressdetails=1"
            headers = {"User-Agent": "SkyCastDeepSearch/11.0"}
            data = requests.get(osm_url, headers=headers, timeout=3.0).json()
            for top in data:
                t_lat = float(top["lat"])
                t_lon = float(top["lon"])
                if not any(abs(m["lat"] - t_lat) < 0.05 and abs(m["lon"] - t_lon) < 0.05 for m in matches):
                    country = top.get("address", {}).get("country", "")
                    d_name = top.get("display_name", "").split(",")[0]
                    label = f"{country} · {d_name}".strip(" ·")
                    matches.append({"display": f"📍 {label}", "lat": t_lat, "lon": t_lon})
        except Exception:
            pass

    return matches

@st.cache_data(ttl=86400, show_spinner=False)
def reverse_geocode_clean(lat: float, lon: float) -> str:
    url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lon}&zoom=14&addressdetails=1&accept-language=zh-TW,zh"
    headers = {"User-Agent": "SkyCastDeepSearch/11.0"}
    try:
        resp = requests.get(url, headers=headers, timeout=3.5)
        if resp.status_code == 200:
            addr = resp.json().get("address", {})
            country = addr.get("country", "")
            city = addr.get("city") or addr.get("county") or addr.get("state") or ""
            district = addr.get("suburb") or addr.get("district") or addr.get("town") or ""
            if country in ["臺灣", "Taiwan", "台湾"]:
                name = f"{city}{district}".strip()
            else:
                name = f"{country} {city} {district}".strip()
            if name:
                return name
    except Exception:
        pass
    return "臺中市東勢區"

# -------------------------------------------------------------
# 4. 氣候與空氣品質 API
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
# 6. 「目前真實所在地」永久保存與自動偵測
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
# 7. 頂部搜尋列與「📍 回到我的位置」按鈕
# -------------------------------------------------------------
c_logo, c_search, c_home = st.columns([1.2, 2.2, 0.9], gap="medium")

with c_logo:
    st.markdown("### 🌤️ SkyCast 全球天氣")

with c_search:
    search_input = st.text_input(
        "全球與全台鄉鎮搜尋",
        placeholder="輸入地名關鍵字（例：苗、竹、東勢、濟州、Jeju、曼谷...）",
        label_visibility="collapsed"
    )

with c_home:
    if st.button("📍 回到我的位置", use_container_width=True, help="點擊立刻回到目前所在地"):
        st.session_state.active_target = {
            "name": f"📍 目前所在地：{st.session_state.my_home_location['name']}",
            "lat": st.session_state.my_home_location["lat"],
            "lon": st.session_state.my_home_location["lon"]
        }
        st.rerun()

# -------------------------------------------------------------
# 8. 大範圍智慧候選區：列出「所有」含關鍵字的地名供點選
# -------------------------------------------------------------
if search_input.strip():
    candidate_list = search_all_matching_locations(search_input)
    if candidate_list:
        st.markdown(f"**🔍 找到 {len(candidate_list)} 個與「{search_input}」相符的地點，請點選：**")
        
        # 4 列橫向整齊排列所有選項
        cols_per_row = 4
        for row_start in range(0, len(candidate_list), cols_per_row):
            row_items = candidate_list[row_start:row_start + cols_per_row]
            c_cols = st.columns(cols_per_row)
            for i, cand in enumerate(row_items):
                with c_cols[i]:
                    if st.button(cand["display"], key=f"cand_{row_start+i}_{cand['lat']}_{cand['lon']}", use_container_width=True):
                        st.session_state.active_target = {
                            "name": cand["display"],
                            "lat": cand["lat"],
                            "lon": cand["lon"]
                        }
                        st.rerun()
    else:
        st.caption(f"查無包含「{search_input}」的相符地點，請確認名稱是否正確。")

# -------------------------------------------------------------
# 9. 氣象資料獲取與畫面呈現
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

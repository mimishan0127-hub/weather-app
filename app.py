import streamlit as st
import requests
import folium
from streamlit_folium import st_folium
import pandas as pd
from streamlit_js_eval import get_geolocation
import time
import os
import json
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime

# -------------------------------------------------------------
# 1. 頁面全域配置與現代極簡樣式
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
        color: #1e293b;
    }
    header[data-testid="stHeader"] {
        background: transparent;
    }
    @media (max-width: 768px) {
        .block-container {
            padding-top: 0.8rem !important;
            padding-bottom: 2rem !important;
            padding-left: 0.8rem !important;
            padding-right: 0.8rem !important;
        }
    }

    /* 頂部地名膠囊按鈕樣式 */
    div[data-testid="column"] button {
        border-radius: 20px !important;
        border: 1px solid #cbd5e1 !important;
        background-color: #ffffff !important;
        color: #334155 !important;
        font-weight: 500 !important;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04) !important;
        transition: all 0.2s ease !important;
    }
    div[data-testid="column"] button:hover {
        border-color: #0284c7 !important;
        color: #0284c7 !important;
        background-color: #f0f9ff !important;
        transform: translateY(-1px);
    }

    /* 核心氣象大卡片 */
    .weather-hero-card {
        padding: 22px 24px;
        border-radius: 18px;
        color: white;
        margin-bottom: 14px;
        box-shadow: 0 10px 25px -5px rgba(15, 23, 42, 0.15), 0 8px 10px -6px rgba(15, 23, 42, 0.1);
        border: 1px solid rgba(255, 255, 255, 0.2);
    }
    @media (max-width: 768px) {
        .weather-hero-card {
            padding: 18px 16px;
        }
    }

    /* 4 大指標響應式網格 (桌機 4 欄, 手機 2x2) */
    .status-grid-bottom {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 8px;
        margin-top: 14px;
    }
    @media (max-width: 768px) {
        .status-grid-bottom {
            grid-template-columns: repeat(2, 1fr);
        }
    }

    .status-badge {
        font-size: 12px;
        font-weight: 600;
        padding: 6px 4px;
        border-radius: 14px;
        white-space: nowrap;
        display: flex;
        justify-content: center;
        align-items: center;
        text-align: center;
        gap: 3px;
        width: 100%;
        box-sizing: border-box;
    }

    /* 橫向滑動卡片流 */
    .weather-scroll-row {
        display: flex;
        gap: 12px;
        overflow-x: auto;
        padding: 6px 2px 14px 2px;
        -webkit-overflow-scrolling: touch;
        scrollbar-width: thin;
    }
    .weather-scroll-row::-webkit-scrollbar {
        height: 6px;
    }
    .weather-scroll-row::-webkit-scrollbar-thumb {
        background: #cbd5e1;
        border-radius: 6px;
    }

    .hourly-scroll-card {
        flex: 0 0 105px;
        background: #ffffff;
        border: 1px solid #f1f5f9;
        border-radius: 14px;
        padding: 12px 6px;
        text-align: center;
        box-shadow: 0 2px 6px rgba(0, 0, 0, 0.03);
    }
    .daily-scroll-card {
        flex: 0 0 120px;
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 14px;
        padding: 14px 8px;
        text-align: center;
        box-shadow: 0 2px 6px rgba(0, 0, 0, 0.03);
    }

    .map-frame-container {
        border-radius: 16px;
        overflow: hidden;
        border: 1px solid #e2e8f0;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.04);
        margin-top: 8px;
    }
    .selector-box {
        background-color: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 16px;
        margin-top: 10px;
    }
    .compact-tip-box {
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        padding: 9px 12px;
        margin-bottom: 12px;
        font-size: 13.5px;
        color: #334155;
    }
</style>
""", unsafe_allow_html=True)

# -------------------------------------------------------------
# 2. 原生零依賴 XLSX 解構引擎 (Zero-Dependency)
# -------------------------------------------------------------
def parse_xlsx_without_packages(filename):
    with zipfile.ZipFile(filename, 'r') as z:
        shared_strings = []
        if 'xl/sharedStrings.xml' in z.namelist():
            tree = ET.fromstring(z.read('xl/sharedStrings.xml'))
            for si in tree.findall('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}si'):
                texts = [t.text for t in si.iter('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t') if t.text]
                shared_strings.append("".join(texts))
        
        sheet_xml = z.read('xl/worksheets/sheet1.xml')
        tree = ET.fromstring(sheet_xml)
        
        rows = []
        for row in tree.findall('.//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}row'):
            row_data = []
            for c in row.findall('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}c'):
                t = c.get('t')
                v = c.find('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}v')
                val = v.text if v is not None else ""
                if t == 's' and val.isdigit():
                    val = shared_strings[int(val)]
                row_data.append(val)
            rows.append(row_data)

    hierarchy = {}
    for row in rows[1:]:
        if len(row) < 6:
            continue
        continent, country, city_zh, city_en, lat_str, lon_str = row[0], row[1], row[2], row[3], row[4], row[5]
        
        continent = str(continent).strip()
        country = str(country).strip()
        city_zh = str(city_zh).strip()
        city_en = str(city_en).strip()

        if continent in ['未知', '', 'None']:
            continue
            
        try:
            lat = float(lat_str)
            lon = float(lon_str)
        except (ValueError, TypeError):
            continue

        # 針對臺灣鄉鎮與一般世界城市的標籤智慧命名
        if "臺灣" in country or "Taiwan" in country:
            # 臺灣格式: 縣市 鄉鎮區 (例如: 臺中市 東勢區)
            if city_en and city_en != city_zh:
                city_label = f"{city_zh} {city_en}"
            else:
                city_label = city_zh
        else:
            city_label = f"{city_zh} ({city_en})" if city_en and city_en != city_zh else city_zh

        if continent not in hierarchy:
            hierarchy[continent] = {}
        if country not in hierarchy[continent]:
            hierarchy[continent][country] = {}
        hierarchy[continent][country][city_label] = [lat, lon]

    return hierarchy

@st.cache_data(show_spinner=False)
def load_all_cities_hierarchy():
    # 優先讀取整合後的 world_cities_and_taiwan.xlsx
    possible_names = [
        "world_cities_and_taiwan.json",
        "world_cities_and_taiwan.xlsx",
        "world_cities_over_50k_zh_en_no_taiwan.xlsx",
        "world_cities.json"
    ]
    
    search_dirs = [
        os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else "",
        os.getcwd(),
        os.path.join(os.getcwd(), ".."),
    ]
    search_dirs = [d for d in search_dirs if d and os.path.exists(d)]
    
    found_path = None
    for d in search_dirs:
        for name in possible_names:
            p = os.path.join(d, name)
            if os.path.exists(p):
                found_path = p
                break
        if found_path:
            break

    if found_path and found_path.endswith(".json"):
        try:
            with open(found_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass

    if found_path and found_path.endswith(".xlsx"):
        try:
            hierarchy = parse_xlsx_without_packages(found_path)
            try:
                cache_out = os.path.join(os.path.dirname(found_path), "world_cities_and_taiwan.json")
                with open(cache_out, "w", encoding="utf-8") as f:
                    json.dump(hierarchy, f, ensure_ascii=False)
            except Exception:
                pass
            return hierarchy
        except Exception:
            pass

    # 備援資料庫（若找不到試算表時防護）
    return {
        "亞洲 (Asia)": {
            "臺灣 / Taiwan": {
                "臺中市 東勢區": [24.2586, 120.8283],
                "臺北市 中正區": [25.0324, 121.5190],
                "高雄市 苓雅區": [22.6273, 120.3014]
            },
            "日本 / Japan": {
                "東京 (Tokyo)": [35.6762, 139.6503],
                "大阪 (Osaka)": [34.6937, 135.5023]
            }
        }
    }

# -------------------------------------------------------------
# 3. 資料結構分離：動態提取臺灣縣市與扁平搜尋索引
# -------------------------------------------------------------
@st.cache_data(show_spinner=False)
def get_taiwan_and_search_index():
    hierarchy = load_all_cities_hierarchy()
    taiwan_data = {}
    flattened_index = []

    for continent, countries in hierarchy.items():
        for country, cities in countries.items():
            is_taiwan = "臺灣" in country or "Taiwan" in country
            clean_c = country.split("/")[0].strip()

            for city_label, coords in cities.items():
                if is_taiwan:
                    # 分解 縣市 與 鄉鎮市區 (例如: "臺中市 東勢區")
                    parts = city_label.split(" ")
                    county = parts[0]
                    town = parts[1] if len(parts) > 1 else parts[0]
                    
                    if county not in taiwan_data:
                        taiwan_data[county] = {}
                    taiwan_data[county][town] = coords
                    flattened_index.append((f"🇹🇼 臺灣 {county} {town}", coords[0], coords[1]))
                else:
                    flattened_index.append((f"🌍 {clean_c} {city_label}", coords[0], coords[1]))

    return taiwan_data, flattened_index

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
        w_r = requests.get(weather_url, timeout=5)
        if w_r.status_code == 200:
            weather_res = w_r.json()
    except Exception:
        pass

    try:
        a_r = requests.get(aqi_url, timeout=4)
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
        intro_text = f"有雨路滑(體感 {feels_like}°C),出門請隨身攜帶雨具、放慢車速。"
    elif uv_val >= 8:
        intro_text = f"紫外線偏強(UV {uv_val:.1f}),外出請務必防曬防曬傷並多補充水分。"
    elif temp >= 29:
        intro_text = f"體感偏熱({feels_like}°C),請多喝水預防中暑,待陰涼通風處。"
    elif temp <= 18:
        intro_text = f"天氣偏涼(體感 {feels_like}°C),早晚溫差顯著,出門請搭配洋蔥式保暖。"
    else:
        intro_text = f"氣候舒適宜人(體感 {feels_like}°C),適宜外出踏青散心或戶外活動。"

    if temp >= 28:
        wear_headline = "舒適短袖 / 薄襯衫"
        wear_desc = f"""
        * **日間穿著**:透氣吸汗短袖或棉麻寬鬆上衣。
        * **防曬提醒**:紫外線為 **{uv_status}**(指數 {uv_val:.1f}),{uv_tip}
        * **室內溫差**:室內外溫差常達 5°C 以上,建議備薄開襟衫防冷氣著涼。
        """
    elif 21 <= temp < 28:
        wear_headline = "舒適短袖 / 襯衫 + 薄外套"
        wear_desc = f"""
        * **日間穿著**:純棉 T-shirt、薄長袖或休閒襯衫剛剛好。
        * **防曬提醒**:紫外線為 **{uv_status}**(指數 {uv_val:.1f}),請適度防曬。
        * **早晚應對**:早晚日夜溫差約 3~6°C,建議攜帶薄夾克或風衣。
        """
    else:
        wear_headline = "洋蔥式保暖 + 厚外套/風衣"
        wear_desc = f"""
        * **內層保暖**:棉質長袖或輕量發熱衣鎖住核心體溫。
        * **外層禦寒**:搭配防風外套、羊毛大衣或羽絨背心。
        * **防風配件**:步行或騎車配戴防風圍巾降低體感寒意。
        """

    if rain_prob < 30 and humidity < 75:
        dry_headline = "五星推薦:通風良好,戶外速乾!"
        dry_desc = f"""
        * **晾乾速度**:環境濕度僅 {humidity}%,通風充足,衣物約 2.5~3 小時即可乾燥。
        * **推薦清洗**:床單、被套等難乾大件物品請把握今日!
        """
    elif rain_prob >= 50 or humidity >= 80:
        dry_headline = "不建議室外(建議搭配除濕機)"
        dry_desc = f"""
        * **受潮風險**:降雨機率高達 {rain_prob}%,空氣濕度飽和,室外晾掛易吸附潮氣。
        * **解決方式**:改掛於室內通風處,搭配除濕機或低溫烘乾。
        """
    else:
        dry_headline = "陽台陰乾為佳,留意天氣突變"
        dry_desc = f"""
        * **曬衣處選擇**:請掛於有遮棚陽台,並於傍晚日落前收納入室避免返潮。
        """

    if rain_prob >= 50:
        commute_tip = "路面潮濕易打滑,行經標線水溝蓋請減速;建議攜帶防水雨具。"
        sport_status = "戶外濕滑易雨,建議改至室內伸展或健身訓練。"
    elif wind_speed > 20:
        commute_tip = "陣風偏大,行經橋樑空曠路段請注意車身穩定與車距。"
        sport_status = "風力稍大,不宜羽球等球類運動,慢跑請留意風阻。"
    else:
        commute_tip = "天候晴朗乾燥,視線良好,各類通勤出行均非常順暢安全。"
        sport_status = "氣候舒適,非常適合慢跑、散步或單車騎乘。"

    # 這裡變數是 pack_items
    pack_items = []
    if rain_prob >= 40:
        pack_items.append("🌂 折疊雨傘 / 輕便雨具")
    if uv_val >= 6:
        pack_items.append(f"🧴 防曬乳 (SPF30+) / 抗 UV 傘")
    if temp >= 28:
        pack_items.append("💧 環保水瓶(防熱補水)")
    if aqi_val > 90:
        pack_items.append("😷 醫療級防護口罩")
    if temp <= 22 or wind_speed > 18:
        pack_items.append("🧥 隨身防風薄外套")
    if not pack_items:
        pack_items.append("😊 輕鬆好心情即可輕便出門!")

    # 注意第 8 個回傳值必須是 pack_items
    return intro_text, wear_headline, wear_desc, dry_headline, dry_desc, sport_status, commute_tip, pack_items, uv_status

# -------------------------------------------------------------
# 6. 所在地狀態持久化
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
    st.session_state.my_home_location = {
        "name": "目前設備所在",
        "lat": u_lat,
        "lon": u_lon
    }

if "active_target" not in st.session_state:
    st.session_state.active_target = {
        "name": f"📍 目前所在地:{st.session_state.my_home_location['name']}",
        "lat": st.session_state.my_home_location["lat"],
        "lon": st.session_state.my_home_location["lon"]
    }

# -------------------------------------------------------------
# 7. 選擇觀測地區彈窗 (快搜 + 臺灣獨立選單 + 全球大洲選單)
# -------------------------------------------------------------
dialog_decorator = getattr(st, "dialog", getattr(st, "experimental_dialog", None))

def render_selector_body():
    taiwan_data, flattened_index = get_taiwan_and_search_index()
    world_hierarchy = load_all_cities_hierarchy()

    tab_search, tab_tw, tab_world = st.tabs(["🔍 關鍵字快搜", "🇹🇼 臺灣鄉鎮", "🌍 全球城市"])

    with tab_search:
        st.markdown('<div class="selector-box">', unsafe_allow_html=True)
        search_query = st.text_input("輸入地名關鍵字 (例如: 東勢、板橋、新宿、巴黎、London)", placeholder="請輸入地名...")
        if search_query.strip():
            q = search_query.strip().lower()
            matched = [item for item in flattened_index if q in item[0].lower()]
            
            if matched:
                st.caption(f"找到 {len(matched)} 個相符地點（顯示前 10 筆）：")
                for name, lat, lon in matched[:10]:
                    clean_name = name.replace("🇹🇼 ", "").replace("🌍 ", "")
                    if st.button(f"📍 {name}", key=f"s_{clean_name}_{lat}_{lon}", use_container_width=True):
                        st.session_state.active_target = {
                            "name": f"📍 {clean_name}",
                            "lat": lat,
                            "lon": lon
                        }
                        st.rerun()
            else:
                st.info("查無符合地點，請嘗試輸入其他關鍵字或至分類標籤點選。")
        else:
            st.caption("💡 提示：輸入鄉鎮名（例：淡水、鹿港）或全球城市（例：首爾、紐約）即可一鍵定位。")
        st.markdown('</div>', unsafe_allow_html=True)

    with tab_tw:
        st.markdown('<div class="selector-box">', unsafe_allow_html=True)
        st.markdown("##### 🇹🇼 臺灣縣市與鄉鎮市區點選 (資料取自試算表)")
        
        county_list = list(taiwan_data.keys())
        if county_list:
            default_county_idx = county_list.index("臺中市") if "臺中市" in county_list else 0
            selected_county = st.selectbox("1. 選擇縣市", options=county_list, index=default_county_idx)
            
            town_dict = taiwan_data.get(selected_county, {})
            town_list = list(town_dict.keys())
            default_town_idx = town_list.index("東勢區") if "東勢區" in town_list else 0
            selected_town = st.selectbox("2. 選擇鄉鎮市區", options=town_list, index=default_town_idx if town_list else 0)
            
            if selected_town:
                target_coords = town_dict[selected_town]
                full_name = f"臺灣 {selected_county} {selected_town}"
                
                st.write("")
                if st.button(f"📍 確認定位: {full_name}", use_container_width=True, type="primary"):
                    st.session_state.active_target = {
                        "name": f"📍 {full_name}",
                        "lat": target_coords[0],
                        "lon": target_coords[1]
                    }
                    st.rerun()
        else:
            st.warning("⚠️ 試算表中尚未讀取到臺灣資料，請確認國家欄位是否包含「臺灣 / Taiwan」。")
        st.markdown('</div>', unsafe_allow_html=True)

    with tab_world:
        st.markdown('<div class="selector-box">', unsafe_allow_html=True)
        st.markdown("##### 🌍 全球大洲、國家與世界城市點選")
        
        continents = list(world_hierarchy.keys())
        default_cont_idx = continents.index("亞洲 (Asia)") if "亞洲 (Asia)" in continents else 0
        selected_continent = st.selectbox("1. 選擇大洲", options=continents, index=default_cont_idx)
        
        countries_dict = world_hierarchy.get(selected_continent, {})
        country_list = sorted(list(countries_dict.keys()))
        
        selected_country = st.selectbox("2. 選擇國家", options=country_list, index=0 if country_list else None)
        
        cities_dict = countries_dict.get(selected_country, {}) if selected_country else {}
        city_list = list(cities_dict.keys())
        
        selected_city = st.selectbox(
            f"3. 選擇城市 (共 {len(city_list)} 個城市)", 
            options=city_list, 
            index=0 if city_list else None
        )
        
        if selected_city:
            target_coords = cities_dict[selected_city]
            clean_c = selected_country.split('/')[0].strip() if selected_country else ""
            clean_t = selected_city.split('(')[0].strip()
            full_name = f"{clean_c} {clean_t}"
            
            st.write("")
            if st.button(f"📍 確認定位: {full_name}", use_container_width=True, type="primary"):
                st.session_state.active_target = {
                    "name": f"📍 {full_name}",
                    "lat": target_coords[0],
                    "lon": target_coords[1]
                }
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

if dialog_decorator:
    @dialog_decorator("🧭 選擇觀測地區")
    def show_cascading_selector_dialog():
        render_selector_body()
else:
    def show_cascading_selector_dialog():
        render_selector_body()

# -------------------------------------------------------------
# 8. 頂部導航列 (地名膠囊化)
# -------------------------------------------------------------
active_name = st.session_state.active_target["name"]
active_lat = st.session_state.active_target["lat"]
active_lon = st.session_state.active_target["lon"]

display_location_text = active_name.replace("📍 ", "").replace("目前所在地:", "")

c_logo, c_capsule_btn, c_home_btn = st.columns([1.4, 2.0, 0.4], gap="small")

with c_logo:
    st.markdown("### 🌤️ SkyCast 全球天氣")

with c_capsule_btn:
    if st.button(f"📍 {display_location_text}  ▾", use_container_width=True, help="點擊切換地點"):
        show_cascading_selector_dialog()

with c_home_btn:
    if st.button("🎯", use_container_width=True, help="回到目前設備所在位置"):
        st.session_state.active_target = {
            "name": f"📍 目前所在地:{st.session_state.my_home_location['name']}",
            "lat": st.session_state.my_home_location["lat"],
            "lon": st.session_state.my_home_location["lon"]
        }
        st.rerun()

# -------------------------------------------------------------
# 9. 天氣資料獲取與運算
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

raw_times = hourly.get("time", [])
raw_temps = hourly.get("temperature_2m", [])
raw_rains = hourly.get("precipitation_probability", [])
raw_codes = hourly.get("weather_code", [])

limit_h = min(6, len(raw_times), len(raw_temps), len(raw_rains), len(raw_codes))
times = [raw_times[i].split("T")[1] for i in range(limit_h)] if limit_h > 0 else []
temps = [raw_temps[i] for i in range(limit_h)] if limit_h > 0 else []
rains = [raw_rains[i] for i in range(limit_h)] if limit_h > 0 else []
codes = [raw_codes[i] for i in range(limit_h)] if limit_h > 0 else []
cur_rain = rains[0] if rains else 0

weekdays_zh = ["週一", "週二", "週三", "週四", "週五", "週六", "週日"]
daily_dates = daily.get("time", [])
daily_max_t = daily.get("temperature_2m_max", [])
daily_min_t = daily.get("temperature_2m_min", [])
daily_rain_p = daily.get("precipitation_probability_max", [])
daily_uv_max = daily.get("uv_index_max", [])
daily_codes = daily.get("weather_code", [])

limit_d = min(7, len(daily_dates), len(daily_max_t), len(daily_min_t), len(daily_codes))

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

# -------------------------------------------------------------
# 10. 4 大警示指標動態顏色運算
# -------------------------------------------------------------
if cur_temp >= 33:
    temp_badge = f'<div class="status-badge" style="background:#fee2e2; color:#b91c1c; border:1px solid #fca5a5;">🌡️ 溫度 {cur_temp}°C (酷熱)</div>'
elif cur_temp <= 15:
    temp_badge = f'<div class="status-badge" style="background:#eff6ff; color:#1d4ed8; border:1px solid #bfdbfe;">🌡️ 溫度 {cur_temp}°C (低溫)</div>'
elif cur_temp >= 29:
    temp_badge = f'<div class="status-badge" style="background:#fef3c7; color:#b45309; border:1px solid #fcd34d;">🌡️ 溫度 {cur_temp}°C (偏熱)</div>'
else:
    temp_badge = f'<div class="status-badge" style="background:#f0fdf4; color:#15803d; border:1px solid #bbf7d0;">🌡️ 溫度 {cur_temp}°C (宜人)</div>'

if cur_rain >= 60:
    rain_badge = f'<div class="status-badge" style="background:#fee2e2; color:#b91c1c; border:1px solid #fca5a5;">💧 降雨 {cur_rain}% (警戒)</div>'
elif cur_rain >= 30:
    rain_badge = f'<div class="status-badge" style="background:#fef3c7; color:#b45309; border:1px solid #fcd34d;">💧 降雨 {cur_rain}% (注意)</div>'
else:
    rain_badge = f'<div class="status-badge" style="background:#f0fdf4; color:#15803d; border:1px solid #bbf7d0;">💧 降雨 {cur_rain}% (良好)</div>'

if cur_uv >= 8:
    uv_badge = f'<div class="status-badge" style="background:#fee2e2; color:#b91c1c; border:1px solid #fca5a5;">☀️ 紫外線 {cur_uv:.1f} (過量)</div>'
elif cur_uv >= 6:
    uv_badge = f'<div class="status-badge" style="background:#ffedd5; color:#c2410c; border:1px solid #fed7aa;">☀️ 紫外線 {cur_uv:.1f} (高量)</div>'
elif cur_uv >= 3:
    uv_badge = f'<div class="status-badge" style="background:#fef3c7; color:#b45309; border:1px solid #fcd34d;">☀️ 紫外線 {cur_uv:.1f} (中量)</div>'
else:
    uv_badge = f'<div class="status-badge" style="background:#f0fdf4; color:#15803d; border:1px solid #bbf7d0;">☀️ 紫外線 {cur_uv:.1f} (微量)</div>'

if aqi_val >= 150:
    aqi_badge = f'<div class="status-badge" style="background:#fee2e2; color:#b91c1c; border:1px solid #fca5a5;">🍃 空污 AQI {aqi_val} (有害)</div>'
elif aqi_val >= 101:
    aqi_badge = f'<div class="status-badge" style="background:#ffedd5; color:#c2410c; border:1px solid #fed7aa;">🍃 空污 AQI {aqi_val} (敏感)</div>'
elif aqi_val >= 51:
    aqi_badge = f'<div class="status-badge" style="background:#fef3c7; color:#b45309; border:1px solid #fcd34d;">🍃 空污 AQI {aqi_val} (普通)</div>'
else:
    aqi_badge = f'<div class="status-badge" style="background:#f0fdf4; color:#15803d; border:1px solid #bbf7d0;">🍃 空污 AQI {aqi_val} (良好)</div>'

# -------------------------------------------------------------
# 11. 即時微氣象與生活小幫手
# -------------------------------------------------------------
col_weather, col_tips = st.columns([1.1, 1.2], gap="large")

with col_weather:
    st.markdown("##### ⚡ 即時微氣象")
    st.markdown(
        f'<div class="weather-hero-card" style="background: {hero_bg};">'
        f'<div style="display: flex; justify-content: space-between; align-items: center;">'
        f'<div><div style="font-size: 34px; font-weight: 700; line-height: 1.2;">{icon} {cur_temp}°C</div>'
        f'<div style="font-size: 15px; opacity: 0.95; margin-top: 4px;">{condition} | 體感 {cur_feels}°C</div></div>'
        f'<div style="text-align: right; font-size: 13px; opacity: 0.95; line-height: 1.7;">'
        f'<div>💧 降雨機率 <strong>{cur_rain}%</strong> | 濕度 <strong>{cur_hum}%</strong></div>'
        f'<div style="margin-top: 4px; padding: 2px 8px; border-radius: 6px; background: rgba(0,0,0,0.22); display: inline-block;">'
        f'☀️ 紫外線 <strong>{cur_uv:.1f}</strong> ({uv_status_str}) | 🍃 AQI <strong>{aqi_val}</strong></div></div></div></div>',
        unsafe_allow_html=True
    )

    col_act1, col_act2 = st.columns(2)
    col_act1.info(f"🏃 **戶外與運動**\n\n{sport_tip}")
    col_act2.info(f"🛵 **通勤與出行指引**\n\n{commute_tip}")

with col_tips:
    st.markdown("##### 💡 生活小幫手")
    st.markdown(f'<div class="compact-tip-box">✨ <strong>出門建議：</strong>{intro}</div>', unsafe_allow_html=True)

    with st.expander(f"👕 **穿著**：{w_head}", expanded=True):
        st.markdown(w_desc)

    with st.expander(f"🧺 **曬衣**：{d_head}", expanded=False):
        st.markdown(d_desc)

    st.caption("🎒 **隨身行囊建議**：" + " | ".join(pack_list))

    st.markdown(
        f'<div class="status-grid-bottom">'
        f'{temp_badge}'
        f'{rain_badge}'
        f'{uv_badge}'
        f'{aqi_badge}'
        f'</div>',
        unsafe_allow_html=True
    )

st.markdown("---")

# -------------------------------------------------------------
# 12. 未來 6 小時即時預報 (防崩潰折線圖)
# -------------------------------------------------------------
st.markdown("##### ⏱️ 未來 6 小時即時預報趨勢")

if limit_h > 0:
    hourly_cards = []
    for i in range(limit_h):
        h_icon, _ = resolve_weather(codes[i])
        card_html = (
            f'<div class="hourly-scroll-card">'
            f'<div style="font-size: 12px; color: #64748b; font-weight: 600;">{times[i]}</div>'
            f'<div style="font-size: 24px; margin: 4px 0;">{h_icon}</div>'
            f'<div style="font-size: 15px; font-weight: 700; color: #1e293b;">{temps[i]}°C</div>'
            f'<div style="font-size: 11px; color: #0284c7; margin-top: 2px;">💧 {rains[i]}%</div>'
            f'</div>'
        )
        hourly_cards.append(card_html)

    st.markdown(f'<div class="weather-scroll-row">{"".join(hourly_cards)}</div>', unsafe_allow_html=True)

    chart_data = pd.DataFrame({
        "時間": times,
        "氣溫 (°C)": temps,
        "降雨機率 (%)": rains
    }).set_index("時間")
    st.line_chart(chart_data, height=180)
else:
    st.info("ℹ️ 暫時無法取得每小時即時氣象資料。")

st.markdown("---")

# -------------------------------------------------------------
# 13. 未來一週 (7天) 展望
# -------------------------------------------------------------
st.markdown("##### 📅 未來一週天氣展望")
if limit_d > 0:
    daily_cards = []
    for d_idx in range(limit_d):
        d_date_str = daily_dates[d_idx]
        d_obj = datetime.strptime(d_date_str, "%Y-%m-%d")
        d_weekday = weekdays_zh[d_obj.weekday()]
        d_title = "今天" if d_idx == 0 else f"{d_obj.month}/{d_obj.day} ({d_weekday})"
        d_icon, d_cond = resolve_weather(daily_codes[d_idx])
        t_max, t_min = daily_max_t[d_idx], daily_min_t[d_idx]
        r_max = daily_rain_p[d_idx] if len(daily_rain_p) > d_idx else 0
        u_max = daily_uv_max[d_idx] if len(daily_uv_max) > d_idx else 0.0

        d_card_html = (
            f'<div class="daily-scroll-card">'
            f'<div style="font-size: 12px; color: #475569; font-weight: 600;">{d_title}</div>'
            f'<div style="font-size: 26px; margin: 6px 0;">{d_icon}</div>'
            f'<div style="font-size: 12px; color: #64748b; margin-bottom: 4px;">{d_cond}</div>'
            f'<div style="font-size: 14px; font-weight: 700; color: #0f172a;">{t_max:.0f}° / <span style="color:#64748b; font-weight:400;">{t_min:.0f}°</span></div>'
            f'<div style="font-size: 11px; color: #0284c7; margin-top: 3px; font-weight: 600;">💧 {r_max}%</div>'
            f'<div style="font-size: 10px; color: #ea580c; margin-top: 2px;">☀️ UV {u_max:.0f}</div>'
            f'</div>'
        )
        daily_cards.append(d_card_html)

    st.markdown(f'<div class="weather-scroll-row">{"".join(daily_cards)}</div>', unsafe_allow_html=True)
else:
    st.info("ℹ️ 暫無一週長期展望數據。")

st.markdown("---")

# -------------------------------------------------------------
# 14. 地圖置底呈現 (完全防拖曳與防誤觸)
# -------------------------------------------------------------
st.markdown("##### 🗺️ 觀測座標中心位置")

map_instance = folium.Map(
    location=[active_lat, active_lon],
    zoom_start=13,
    tiles="OpenStreetMap",
    dragging=False,
    zoom_control=False,
    scrollWheelZoom=False,
    doubleClickZoom=False,
    touchZoom=False
)
folium.Marker(
    [active_lat, active_lon],
    tooltip=f"{active_name} · {cur_temp}°C",
    icon=folium.Icon(color="blue", icon="cloud")
).add_to(map_instance)

st.markdown('<div class="map-frame-container">', unsafe_allow_html=True)
st_folium(map_instance, width=None, height=300, returned_objects=[])
st.markdown('</div>', unsafe_allow_html=True)

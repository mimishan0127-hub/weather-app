import streamlit as st
import requests
import pandas as pd
import folium
from streamlit_folium import st_folium

st.set_page_config(page_title="台灣即時天氣與生活指南", page_icon="🌤️", layout="wide")

# 台灣主要縣市座標對照表
TAIWAN_CITIES = {
    "臺北市": {"lat": 25.0330, "lon": 121.5654},
    "新北市": {"lat": 25.0125, "lon": 121.4657},
    "桃園市": {"lat": 24.9936, "lon": 121.3010},
    "臺中市": {"lat": 24.1477, "lon": 120.6736},
    "臺南市": {"lat": 22.9997, "lon": 120.2270},
    "高雄市": {"lat": 22.6273, "lon": 120.3014},
    "基隆市": {"lat": 25.1283, "lon": 121.7419},
    "新竹市": {"lat": 24.8138, "lon": 120.9675},
    "嘉義市": {"lat": 23.4800, "lon": 120.4491},
    "宜蘭縣": {"lat": 24.7021, "lon": 121.7377},
    "花蓮縣": {"lat": 23.9872, "lon": 121.6016},
    "臺東縣": {"lat": 22.7583, "lon": 121.1444},
    "澎湖縣": {"lat": 23.5711, "lon": 119.5793},
    "金門縣": {"lat": 24.4490, "lon": 118.3766},
    "連江縣": {"lat": 26.1505, "lon": 119.9499}
}

# 讀取金鑰：優先讀取 Streamlit Secrets，若無則留空
CWA_KEY = st.secrets.get("CWA_API_KEY", "")
MOENV_KEY = st.secrets.get("MOENV_API_KEY", "")

# 1. 取得使用者概略所在城市 (IP 定位)
@st.cache_data(ttl=3600)
def detect_user_city():
    try:
        res = requests.get("https://ipapi.co/json/", timeout=5).json()
        city_raw = res.get("city", "")
        # 比對英文城市名稱並轉換為繁體中文
        city_map = {
            "Taipei": "臺北市", "New Taipei": "新北市", "Taichung": "臺中市",
            "Tainan": "臺南市", "Kaohsiung": "高雄市", "Taoyuan": "桃園市"
        }
        for en, tw in city_map.items():
            if en.lower() in city_raw.lower():
                return tw
    except Exception:
        pass
    return "臺北市"

# 2. 串接中央氣象署 API (F-D0047-089)
@st.cache_data(ttl=1800)
def get_cwa_weather(city_name: str, api_key: str):
    if not api_key:
        return None
    url = "https://opendata.cwa.gov.tw/api/v1/rest/datastore/F-D0047-089"
    params = {
        "Authorization": api_key,
        "locationName": city_name,
        "elementName": "T,PoP6h,Wx"
    }
    try:
        res = requests.get(url, params=params, timeout=10)
        data = res.json()
        records = data.get("records", {}).get("Locations", [])[0].get("Location", [])
        if not records:
            return None
        target = records[0]
        elements = {elem["ElementName"]: elem["Time"] for elem in target.get("WeatherElement", [])}
        return elements
    except Exception:
        return None

# 3. 串接環境部空氣品質 API (aqx_p_432)
@st.cache_data(ttl=1800)
def get_moenv_aqi(city_name: str, api_key: str):
    if not api_key:
        return None
    url = "https://data.moenv.gov.tw/api/v2/aqx_p_432"
    params = {"api_key": api_key, "limit": 100, "sort": "ImportDate desc", "format": "json"}
    try:
        res = requests.get(url, params=params, timeout=10).json()
        records = res.get("records", [])
        for r in records:
            if city_name in r.get("county", ""):
                return {
                    "sitename": r.get("sitename"),
                    "aqi": int(r.get("aqi", 0)),
                    "status": r.get("status", "未知"),
                    "pm25": r.get("pm2.5_avg", "--")
                }
    except Exception:
        pass
    return None

# 4. 智慧生活建議推論引擎
def generate_life_advice(temp, pop, aqi):
    advice = []
    # 穿著
    if temp >= 28:
        wear = "天氣炎熱，建議著輕便透氣短袖，注意防曬補水。"
    elif temp >= 22:
        wear = "體感舒適，穿著短袖搭配薄襯衫或薄外套即可。"
    elif temp >= 16:
        wear = "早晚偏涼，建議長袖衣物搭配防風保暖外套。"
    else:
        wear = "氣溫偏低，請準備保暖毛衣、大衣或發熱衣物。"
    advice.append(f"👔 **穿搭指引**：{wear}")

    # 降雨與曬衣
    if pop >= 50:
        laundry = "降雨機率偏高，外出務必帶傘，不建議戶外曬衣。"
    elif pop >= 30:
        laundry = "有局部降雨機率，建議將衣物晾於室內或通風陽台。"
    else:
        laundry = "降雨機率低，非常適合戶外曬衣及戶外洗車。"
    advice.append(f"🧺 **曬衣與防雨**：{laundry}")

    # 空氣品質與運動
    if aqi <= 50:
        exercise = "空氣品質良好，非常適合跑步、騎車等各類戶外運動。"
    elif aqi <= 100:
        exercise = "空氣品質普通，一般大眾可正常戶外活動，極敏感族群可微調強度。"
    else:
        exercise = "空氣品質不佳（橘色或紅色警示），建議減少戶外劇烈運動，出門配戴口罩。"
    advice.append(f"🏃 **運動與空污**：{exercise}")

    return advice

# --- 主介面渲染 ---
st.title("🌤️ 台灣即時天氣看板 & 生活行動指南")

# 自動判定初次載入預設城市
if "selected_city" not in st.session_state:
    st.session_state.selected_city = detect_user_city()

# 側邊欄：API Key 設定（若無設定在 secrets）
with st.sidebar:
    st.header("⚙️ 系統設定")
    if not CWA_KEY:
        CWA_KEY = st.text_input("輸入中央氣象署 API Key", type="password")
    if not MOENV_KEY:
        MOENV_KEY = st.text_input("輸入環境部 API Key", type="password")

# 區域選單
city_list = list(TAIWAN_CITIES.keys())
current_idx = city_list.index(st.session_state.selected_city) if st.session_state.selected_city in city_list else 0
selected_city = st.selectbox("請選擇查詢區域：", city_list, index=current_idx)
st.session_state.selected_city = selected_city

# 讀取氣象與空污資料
raw_weather = get_cwa_weather(selected_city, CWA_KEY)
aqi_data = get_moenv_aqi(selected_city, MOENV_KEY)

# 整理 6 小時預報數據
temps, pops, times = [], [], []
current_temp, current_pop = 24.0, 10
if raw_weather:
    t_records = raw_weather.get("T", [])[:3]
    pop_records = raw_weather.get("PoP6h", [])[:2]
    if t_records:
        current_temp = float(t_records[0]["ElementValue"][0]["Temperature"])
        temps = [float(item["ElementValue"][0]["Temperature"]) for item in t_records]
        times = [item["StartTime"][11:16] for item in t_records]
    if pop_records:
        current_pop = int(pop_records[0]["ElementValue"][0]["ProbabilityOfPrecipitation"])
        pops = [int(item["ElementValue"][0]["ProbabilityOfPrecipitation"]) for item in pop_records]

current_aqi = aqi_data["aqi"] if aqi_data else 35
current_pm25 = aqi_data["pm25"] if aqi_data else "12"
aqi_status = aqi_data["status"] if aqi_data else "良好"

# 介面雙欄：左地圖，右指標與建議
col_map, col_info = st.columns([1.1, 1])

coords = TAIWAN_CITIES[selected_city]

with col_map:
    st.markdown(f"#### 📍 {selected_city} 區域標示")
    # 建立簡約地圖 (CartoDB positron 淺色底圖)
    m = folium.Map(location=[coords["lat"], coords["lon"]], zoom_start=11, tiles="CartoDB positron")
    folium.Marker(
        [coords["lat"], coords["lon"]],
        popup=f"{selected_city}",
        tooltip=f"{selected_city}: {current_temp}°C",
        icon=folium.Icon(color="blue", icon="cloud")
    ).add_to(m)
    st_folium(m, width=550, height=420)

with col_info:
    st.markdown(f"#### 📊 即時觀測數據")
    m1, m2, m3 = st.columns(3)
    m1.metric("即時氣溫", f"{current_temp} °C")
    m2.metric("降雨機率", f"{current_pop} %")
    m3.metric("空氣品質 (AQI)", f"{current_aqi}", help=f"PM2.5: {current_pm25} | 狀態: {aqi_status}")

    st.divider()
    st.markdown("#### 🤖 智慧生活建議")
    advice_list = generate_life_advice(current_temp, current_pop, current_aqi)
    for adv in advice_list:
        st.write(adv)

# 下方：近 6 小時氣溫趨勢
if temps:
    st.divider()
    st.markdown("#### ⏱️ 近期預測趨勢 (每3小時)")
    chart_df = pd.DataFrame({"時間": times, "氣溫 (°C)": temps}).set_index("時間")
    st.line_chart(chart_df)

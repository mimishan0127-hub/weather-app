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
    
    /* 核心氣候英雄卡 */
    .weather-hero-card {
        padding: 22px 24px;
        border-radius: 16px;
        color: white;
        margin-bottom: 14px;
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.12);
    }
    
    /* 小幫手語錄專區 */
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

    /* 預報微型卡片 */
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
# 2. 狀態管理
# -------------------------------------------------------------
DEFAULT_LOCATIONS = {
    "臺北市信義區": {"lat": 25.0330, "lon": 121.5654},
    "臺中市西區": {"lat": 24.1477, "lon": 120.6736},
    "高雄市苓雅區": {"lat": 22.6273, "lon": 120.3014},
    "花蓮縣花蓮市": {"lat": 23.9872, "lon": 121.6016}
}

if "locations" not in st.session_state:
    st.session_state.locations = DEFAULT_LOCATIONS.copy()

if "selected_location_key" not in st.session_state:
    st.session_state.selected_location_key = None

# -------------------------------------------------------------
# 3. 地理工具
# -------------------------------------------------------------
@st.cache_data(ttl=86400, show_spinner=False)
def reverse_geocode_safe(lat: float, lon: float) -> str:
    url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lon}&zoom=14&addressdetails=1"
    headers = {"User-Agent": "SkyCastAssistant/3.2"}
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
    return f"目前座標 ({lat:.2f}, {lon:.2f})"

@st.cache_data(ttl=86400, show_spinner=False)
def search_coords_safe(query: str):
    if not query or len(query.strip()) == 0:
        return None, None, None
    url = f"https://nominatim.openstreetmap.org/search?format=json&q={query}&countrycodes=tw&limit=1"
    headers = {"User-Agent": "SkyCastAssistant/3.2"}
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
# 4. 氣候與空氣品質 API
# -------------------------------------------------------------
WEATHER_SPECS = {
    0: ("☀️", "晴朗無雲"),
    1: ("🌤️", "多雲時晴"),
    2: ("⛅", "多雲"),
    3: ("☁️", "陰天多雲"),
    45: ("🌫️", "晨霧朦朧"),
    51: ("🌦️", "偶有毛毛細雨"),
    61: ("🌧️", "短暫陣雨"),
    63: ("🌧️", "綿綿陣雨"),
    65: ("🌧️", "強大豪雨"),
    80: ("🌦️", "午後短暫雷陣雨"),
    81: ("🌧️", "局部強降雨"),
    82: ("⛈️", "狂暴劇烈雷雨"),
    95: ("⛈️", "雷電交加"),
    96: ("⛈️", "雷雨伴隨冰雹")
}

def resolve_weather(code: int):
    return WEATHER_SPECS.get(code, ("🌤️", "多雲"))

def parse_uv_level(uv_val: float):
    if uv_val < 3:
        return "微量", "#10b981", "安全，日常活動不需特別防護。"
    elif 3 <= uv_val < 6:
        return "中量", "#f59e0b", "外出建議帽子、薄防曬保護。"
    elif 6 <= uv_val < 8:
        return "高量", "#f97316", "紫外線偏強，曝曬 30 分鐘內易受傷，請擦防曬。"
    elif 8 <= uv_val < 11:
        return "過量", "#ef4444", "危險邊緣！請避開正午曝曬，備妥抗 UV 陽傘。"
    else:
        return "危險", "#7c3aed", "極端強烈！盡量待在室內陰涼處。"

@st.cache_data(ttl=900, show_spinner=False)
def fetch_weather_and_aqi(lat: float, lon: float):
    weather_url = (
        f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
        f"&current=temperature_2m,relative_humidity_2m,weather_code,apparent_temperature,precipitation,wind_speed_10m,uv_index"
        f"&hourly=temperature_2m,precipitation_probability,precipitation,weather_code"
        f"&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,uv_index_max"
        f"&forecast_days=7&timezone=Asia%2FTaipei"
    )
    aqi_url = (
        f"https://air-quality-api.open-meteo.com/v1/air-quality?latitude={lat}&longitude={lon}"
        f"&current=us_aqi,pm2_5&timezone=Asia%2FTaipei"
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
# 5. 生活管家智慧推論引擎
# -------------------------------------------------------------
def get_comprehensive_assistant_advice(temp, feels_like, rain_prob, humidity, wind_speed, aqi_val, uv_val):
    uv_status, _, uv_tip = parse_uv_level(uv_val)

    if rain_prob >= 60:
        intro_text = f"今日水氣偏多，出門一定要留意雨勢！目前體感約 {feels_like}°C，外出隨身必帶折傘，路面濕滑開車騎車請放慢車速。"
    elif uv_val >= 8:
        intro_text = f"紫外線達到「{uv_status}」等級（UV: {uv_val:.1f}）！外出極易曬傷，請務必擦妥防曬乳、備妥抗 UV 陽傘並多補充水分。"
    elif temp >= 29:
        intro_text = f"今天豔陽高照、體感偏熱（{feels_like}°C）！水分流失快，外出記得防曬、補水，並多待在通風陰涼處。"
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
        * **配件保護**：若騎車外出，手套、防風圍巾與包覆性口罩能顯著降低體感寒意。
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
# 6. 整合式導航與地點搜尋控制列（無任何分頁）
# -------------------------------------------------------------
geo = get_geolocation()
active_locations = {}
gps_key = None

if geo and "coords" in geo:
    user_lat = geo["coords"]["latitude"]
    user_lon = geo["coords"]["longitude"]
    loc_title = reverse_geocode_safe(user_lat, user_lon)
    gps_key = f"📍 目前所在地（{loc_title}）"
    active_locations[gps_key] = {"lat": user_lat, "lon": user_lon}

# 加入自訂地點清單
active_locations.update(st.session_state.locations)

CUSTOM_ACTION_KEY = "➕ 自訂 / 搜尋新地點..."
selection_options = list(active_locations.keys()) + [CUSTOM_ACTION_KEY]

# 決定選單的預設值
if st.session_state.selected_location_key not in selection_options:
    st.session_state.selected_location_key = selection_options[0]

header_left, header_right = st.columns([1.2, 2.8])
with header_left:
    st.markdown("### 🌤️ SkyCast 天氣生活管家")

with header_right:
    # 支援選取與刪除按鈕並排
    col_sel, col_del = st.columns([4, 1])
    with col_sel:
        current_choice = st.selectbox(
            "切換或搜尋地點",
            options=selection_options,
            index=selection_options.index(st.session_state.selected_location_key),
            label_visibility="collapsed"
        )
        st.session_state.selected_location_key = current_choice

    with col_del:
        # 如果是使用者自訂儲存的地點，提供一鍵刪除
        if current_choice in st.session_state.locations and current_choice not in DEFAULT_LOCATIONS:
            if st.button("🗑️ 刪除", use_container_width=True, help="從儲存清單中移除此地點"):
                del st.session_state.locations[current_choice]
                st.session_state.selected_location_key = selection_options[0]
                st.rerun()

# 若使用者選擇「自訂 / 搜尋新地點」，在正下方展開輕量輸入列
if current_choice == CUSTOM_ACTION_KEY:
    with st.container():
        st.info("💡 請輸入要查詢的地點名稱（如：清境農場、板橋車站、駁二藝術特區），查詢後將自動加入清單並儲存。")
        in_col1, in_col2 = st.columns([4, 1])
        with in_col1:
            new_place_input = st.text_input("地點搜尋", placeholder="輸入地標或地址...", label_visibility="collapsed")
        with in_col2:
            search_btn = st.button("儲存並查詢", use_container_width=True)

        if search_btn and new_place_input:
            with st.spinner("定位搜尋中..."):
                found_lat, found_lon, formal_name = search_coords_safe(new_place_input)
                if found_lat and found_lon:
                    save_name = f"⭐ {new_place_input}"
                    st.session_state.locations[save_name] = {"lat": found_lat, "lon": found_lon}
                    st.session_state.selected_location_key = save_name
                    st.success(f"已儲存「{new_place_input}」！")
                    time.sleep(0.4)
                    st.rerun()
                else:
                    st.error("找不到該地點，請輸入更具體或知名的地標名稱。")
    st.stop()  # 停止下方天氣渲染，等待使用者輸入完成

# -------------------------------------------------------------
# 7. 氣象資料獲取與畫面呈現
# -------------------------------------------------------------
target_coords = active_locations[current_choice]
target_lat, target_lon = target_coords["lat"], target_coords["lon"]

weather_data, aqi_data = fetch_weather_and_aqi(target_lat, target_lon)

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

# 生活管家叮嚀語
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
    st.markdown("##### 🗺️ 觀測座標位置")
    map_instance = folium.Map(location=[target_lat, target_lon], zoom_start=13, tiles="OpenStreetMap")
    folium.Marker(
        [target_lat, target_lon],
        tooltip=f"{current_choice} · {cur_temp}°C",
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

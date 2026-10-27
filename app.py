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
        padding: 24px;
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

    /* 警示橫幅 */
    .alert-banner {
        padding: 12px 18px;
        border-radius: 12px;
        margin-bottom: 14px;
        font-weight: 600;
        display: flex;
        align-items: center;
        gap: 10px;
    }
    .alert-danger { background-color: #fee2e2; color: #b91c1c; border: 1px solid #fecaca; }
    .alert-warning { background-color: #fef3c7; color: #b45309; border: 1px solid #fde68a; }

    /* 地點管理卡片 */
    .location-item-box {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        padding: 12px 16px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 8px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.02);
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

# -------------------------------------------------------------
# 3. 地理工具
# -------------------------------------------------------------
@st.cache_data(ttl=86400, show_spinner=False)
def reverse_geocode_safe(lat: float, lon: float) -> str:
    url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lon}&zoom=14&addressdetails=1"
    headers = {"User-Agent": "SkyCastAssistant/3.0"}
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
    headers = {"User-Agent": "SkyCastAssistant/3.0"}
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

@st.cache_data(ttl=900, show_spinner=False)
def fetch_weather_and_aqi(lat: float, lon: float):
    weather_url = (
        f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
        f"&current=temperature_2m,relative_humidity_2m,weather_code,apparent_temperature,precipitation,wind_speed_10m"
        f"&hourly=temperature_2m,precipitation_probability,precipitation,weather_code"
        f"&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max"
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
def get_comprehensive_assistant_advice(temp, feels_like, rain_prob, humidity, wind_speed, aqi_val):
    # 1. 小幫手今日總評
    if rain_prob >= 60:
        intro_text = f"今日水氣偏多，出門一定要留意雨勢！目前體感約 {feels_like}°C，出門隨身必帶折傘，路面濕滑開車騎車請放慢車速。"
    elif temp >= 29:
        intro_text = f"今天豔陽高照、體感偏熱（{feels_like}°C）！紫外線與水分流失較快，外出記得防曬、補水，並多待在通風陰涼處。"
    elif temp <= 18:
        intro_text = f"天氣偏涼冷（體感 {feels_like}°C），早晚出門或騎車容易受風寒，請洋蔥式搭配禦寒，多喝溫熱開水暖身。"
    else:
        intro_text = f"今天整體氣候舒適宜人（體感 {feels_like}°C），晴朗中帶有些許微風，非常適合外出踏青散心或安排戶外活動。"

    # 2. 細緻穿搭指南
    if temp >= 28:
        wear_headline = "涼感排汗短袖 ＋ 輕薄防曬遮陽"
        wear_desc = f"""
        * **白天建議**：穿著吸濕排汗的透氣短袖或棉麻寬鬆上衣，避免深色吸熱材質。
        * **冷氣房溫差**：室內外溫差常達 5°C 以上，建議備一件薄開襟衫或輕薄襯衫防頭部與肩頸著涼。
        * **通勤防護**：日間日照強烈，機車族與步調通勤者建議配戴遮陽帽、抗 UV 涼感袖套或墨鏡。
        """
    elif 21 <= temp < 28:
        wear_headline = "舒適短袖 / 襯衫 ＋ 早晚防風薄外套"
        wear_desc = f"""
        * **日間穿著**：純棉 T-shirt、薄長袖或休閒襯衫，體感剛剛好。
        * **早晚應對**：早晚日夜溫差約 3～6°C，建議隨身攜帶薄夾克、連帽外套或防風防潑水薄風衣。
        * **鞋履選擇**：降雨機率 {rain_prob}%，若超過 30% 建議選擇防滑或輕度防水鞋款。
        """
    else:
        wear_headline = "保暖洋蔥式穿搭 ＋ 厚外套/風衣"
        wear_desc = f"""
        * **內層親膚**：棉質長袖上衣或輕量發熱衣，鎖住核心溫度。
        * **外層禦寒**：建議搭配防風外套、羊毛大衣或羽絨背心。
        * **配件保護**：若騎車外出，手套、防風圍巾與包覆性口罩能顯著降低體感寒意。
        """

    # 3. 曬衣防霉攻略
    if rain_prob < 30 and humidity < 75:
        dry_headline = "五星推薦：通風良好，戶外速乾！"
        dry_desc = f"""
        * **晾乾速度**：環境濕度僅 {humidity}%，日照充足，薄衣物約 2.5～3 小時即可乾燥。
        * **家事推薦**：床單、被套、大毛巾與球鞋等難乾大件物品，請把握今日清洗！
        * **貼心叮嚀**：中午陽光充足，深色或絲質衣物可翻面晾曬，避免布料日曬褪色。
        """
    elif rain_prob >= 50 or humidity >= 80:
        dry_headline = "不建議室外曬衣（建議室內搭配除濕機）"
        dry_desc = f"""
        * **受潮風險**：降雨機率高達 {rain_prob}%，空氣水氣已飽和，掛在室外容易吸附潮氣、滋生霉菌與悶臭味。
        * **解決妙招**：改掛於室內通風處，搭配除濕機運轉（設定 50% 濕度）或直接使用烘衣機低溫烘乾。
        * **防潮間距**：室內晾衣請拉開衣物間距至少 10 公分，底下放置電風扇加強對流。
        """
    else:
        dry_headline = "陽台陰乾為佳，留意天氣突變"
        dry_desc = f"""
        * **曬衣處選擇**：請務必掛在有雨遮的陽台，隨時注意天空雲層變化。
        * **收衣時間**：建議於傍晚 5 點前收納入室，避免日落後地表濕氣返潮。
        """

    # 4. 運動、洗車與生活評估
    if rain_prob >= 50:
        sport_status = "建議室內健身、瑜伽或居家伸展；戶外路滑請避免路跑。"
        wash_car = "不建議洗車（易受降雨或泥水污染）。"
    else:
        sport_status = "適合戶外慢跑、健走或單車騎乘，活動前請先熱身。"
        wash_car = "適宜洗車打蠟，車身可維持多日乾淨光亮。"

    # 5. 隨身出門清單必備推薦
    pack_items = []
    if rain_prob >= 40:
        pack_items.append("🌂 折疊雨傘 / 輕便雨衣")
    if temp >= 28:
        pack_items.append("🕶️ 防曬乳 / 墨鏡")
        pack_items.append("💧 環保水瓶（及時補水）")
    if aqi_val > 90:
        pack_items.append("😷 醫療級防護口罩")
    if temp <= 22 or wind_speed > 18:
        pack_items.append("🧥 隨身防風薄外套")
    if not pack_items:
        pack_items.append("😊 輕鬆好心情即可輕便出門！")

    return intro_text, wear_headline, wear_desc, dry_headline, dry_desc, sport_status, wash_car, pack_items

# -------------------------------------------------------------
# 6. 主程式資料獲取
# -------------------------------------------------------------
geo = get_geolocation()
active_locations = {}

if geo and "coords" in geo:
    user_lat = geo["coords"]["latitude"]
    user_lon = geo["coords"]["longitude"]
    loc_title = reverse_geocode_safe(user_lat, user_lon)
    gps_key = f"📍 目前所在地（{loc_title}）"
    active_locations[gps_key] = {"lat": user_lat, "lon": user_lon}

active_locations.update(st.session_state.locations)

# 頂部導航
header_col1, header_col2 = st.columns([1.5, 2.5])
with header_col1:
    st.markdown("### 🌤️ 即時天氣與生活管家")

with header_col2:
    selected_loc_name = st.selectbox(
        "切換地點",
        options=list(active_locations.keys()),
        index=0,
        label_visibility="collapsed"
    )

target_coords = active_locations[selected_loc_name]
target_lat, target_lon = target_coords["lat"], target_coords["lon"]

# 呼叫 API
weather_data, aqi_data = fetch_weather_and_aqi(target_lat, target_lon)

current = weather_data.get("current", {})
hourly = weather_data.get("hourly", {})
daily = weather_data.get("daily", {})

cur_temp = current.get("temperature_2m", 25.0)
cur_feels = current.get("apparent_temperature", cur_temp)
cur_hum = current.get("relative_humidity_2m", 60)
cur_wind = current.get("wind_speed_10m", 8.0)
cur_code = current.get("weather_code", 0)
icon, condition = resolve_weather(cur_code)

times = [t.split("T")[1] for t in hourly.get("time", [])[:6]]
temps = hourly.get("temperature_2m", [])[:6]
rains = hourly.get("precipitation_probability", [])[:6]
precips = hourly.get("precipitation", [])[:6]
codes = hourly.get("weather_code", [])[:6]
cur_rain = rains[0] if rains else 0

weekdays_zh = ["週一", "週二", "週三", "週四", "週五", "週六", "週日"]
daily_dates = daily.get("time", [])[:7]
daily_max_t = daily.get("temperature_2m_max", [])[:7]
daily_min_t = daily.get("temperature_2m_min", [])[:7]
daily_rain_p = daily.get("precipitation_probability_max", [])[:7]
daily_codes = daily.get("weather_code", [])[:7]

aqi_current = aqi_data.get("current", {})
aqi_val = int(aqi_current.get("us_aqi", 35)) if aqi_current.get("us_aqi") is not None else 35
pm25_val = aqi_current.get("pm2_5", 8.5)

# 背景情境色
if cur_temp >= 28:
    hero_bg = "linear-gradient(135deg, #FF6B6B 0%, #FF8E53 100%)"
elif cur_temp <= 18:
    hero_bg = "linear-gradient(135deg, #4b6cb7 0%, #182848 100%)"
else:
    hero_bg = "linear-gradient(135deg, #2b5876 0%, #4e4376 100%)"

# -------------------------------------------------------------
# 7. 畫面渲染
# -------------------------------------------------------------
tab_main, tab_manage = st.tabs(["📊 天氣看板與生活指引", "📍 關注地點管理"])

with tab_main:
    # 生活管家前導問候
    intro, w_head, w_desc, d_head, d_desc, sport_tip, car_tip, pack_list = get_comprehensive_assistant_advice(
        cur_temp, cur_feels, cur_rain, cur_hum, cur_wind, aqi_val
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
            tooltip=f"{selected_loc_name} · {cur_temp}°C",
            icon=folium.Icon(color="blue", icon="cloud")
        ).add_to(map_instance)
        st_folium(map_instance, width=None, height=330, returned_objects=[])

    with right_col:
        st.markdown("##### ⚡ 即時微氣象與空污指標")
        
        st.markdown(f"""
        <div class="weather-hero-card" style="background: {hero_bg};">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <div style="font-size: 34px; font-weight: 700; line-height: 1.2;">{icon} {cur_temp}°C</div>
                    <div style="font-size: 15px; opacity: 0.95; margin-top: 4px;">{condition} ｜ 體感 {cur_feels}°C</div>
                </div>
                <div style="text-align: right; font-size: 13px; opacity: 0.95; line-height: 1.6;">
                    <div>💧 降雨機率 <strong>{cur_rain}%</strong></div>
                    <div>🌫️ 空氣濕度 <strong>{cur_hum}%</strong></div>
                    <div style="margin-top: 4px; padding: 2px 8px; border-radius: 6px; background: rgba(0,0,0,0.2); display: inline-block;">
                        🍃 空氣 AQI <strong>{aqi_val}</strong> ｜ PM2.5: {pm25_val}
                    </div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # 展開式詳細生活指南
        with st.expander(f"👕 **穿著提案**：{w_head}", expanded=False):
            st.markdown(w_desc)

        with st.expander(f"🧺 **曬衣防霉攻略**：{d_head}", expanded=False):
            st.markdown(d_desc)

        # 運動與洗車生活卡片
        col_act1, col_act2 = st.columns(2)
        col_act1.info(f"🏃 **戶外與運動**\n\n{sport_tip}")
        col_act2.info(f"🚗 **洗車與保養**\n\n{car_tip}")

        # 出門包包清單
        st.caption("🎒 **隨身行囊建議**：" + " ｜ ".join(pack_list))

    st.markdown("---")
    
    # 逐時預報
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

    # 一週預報
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
            
            with day_cols[d_idx]:
                st.markdown(f"""
                <div class="daily-card">
                    <div style="font-size: 12px; color: #475569; font-weight: 600;">{d_title}</div>
                    <div style="font-size: 28px; margin: 6px 0;">{d_icon}</div>
                    <div style="font-size: 12px; color: #64748b; margin-bottom: 4px;">{d_cond}</div>
                    <div style="font-size: 14px; font-weight: 700; color: #0f172a;">{t_max:.0f}° / <span style="color:#64748b; font-weight:400;">{t_min:.0f}°</span></div>
                    <div style="font-size: 11px; color: #0284c7; margin-top: 4px; font-weight: 600;">💧 {r_max}%</div>
                </div>
                """, unsafe_allow_html=True)

# -------------------------------------------------------------
# 8. 直覺式地點管理（卡片化與快捷鍵）
# -------------------------------------------------------------
with tab_manage:
    st.markdown("#### 📍 自訂關注地點管理")
    st.caption("新增常去的城市、工作地或露營旅遊景點，隨時切換掌握當地微氣候。")

    # 快捷一鍵加入
    st.markdown("##### ⚡ 常用熱門捷徑（點擊直接新增）")
    preset_shortcuts = {
        "🏕️ 清境農場": [24.0475, 121.1558],
        "🌊 淡水漁人碼頭": [25.1822, 121.4116],
        "🚄 左營高鐵站": [22.6872, 120.3075],
        "⛰️ 阿里山風景區": [23.5113, 120.8037],
        "🏮 九份老街": [25.1098, 121.8452]
    }
    
    sc_cols = st.columns(len(preset_shortcuts))
    for idx, (p_name, p_coords) in enumerate(preset_shortcuts.items()):
        with sc_cols[idx]:
            if st.button(p_name, use_container_width=True):
                st.session_state.locations[p_name] = {"lat": p_coords[0], "lon": p_coords[1]}
                st.success(f"已收錄：{p_name}")
                time.sleep(0.3)
                st.rerun()

    st.markdown("---")

    # 搜尋新增區塊
    st.markdown("##### 🔍 搜尋台灣地標或鄉鎮")
    col_search, col_add_btn = st.columns([3.5, 1])
    with col_search:
        search_query = st.text_input(
            "輸入想新增的地標名稱",
            placeholder="例如：板橋火車站、駁二藝術特區、竹科管理局、羅東夜市...",
            label_visibility="collapsed"
        )
    with col_add_btn:
        do_search = st.button("➕ 新增至清單", use_container_width=True)

    if do_search and search_query:
        with st.spinner("搜尋地理資訊中..."):
            s_lat, s_lon, formal_name = search_coords_safe(search_query)
            if s_lat and s_lon:
                st.session_state.locations[search_query] = {"lat": s_lat, "lon": s_lon}
                st.success(f"✅ 成功加入「{search_query}」！")
                time.sleep(0.4)
                st.rerun()
            else:
                st.error("找不到該地點，請輸入更具體或知名的地標名稱。")

    st.markdown("---")

    # 直覺卡片式已存清單（帶有獨立單鍵刪除）
    st.markdown("##### 📋 目前已關注的地點清單")
    if not st.session_state.locations:
        st.info("目前清單為空，請從上方搜尋或點擊熱門捷徑新增。")
    else:
        for loc_key, loc_val in list(st.session_state.locations.items()):
            c_box1, c_box2 = st.columns([4, 1])
            with c_box1:
                st.markdown(f"""
                <div class="location-item-box">
                    <div>
                        <strong style="font-size: 15px; color: #1e293b;">📍 {loc_key}</strong>
                        <div style="font-size: 12px; color: #64748b; margin-top: 2px;">座標：{loc_val['lat']:.3f}, {loc_val['lon']:.3f}</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
            with c_box2:
                # 獨立刪除按鈕
                if st.button("🗑️ 移除", key=f"del_{loc_key}", use_container_width=True):
                    del st.session_state.locations[loc_key]
                    st.rerun()

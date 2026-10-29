import streamlit as st
import streamlit.components.v1 as components
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
# 1. 頁面全域配置 (側邊欄預設收折)
# -------------------------------------------------------------
st.set_page_config(
    page_title="SkyCast 全球天氣生活管家",
    page_icon="🌤️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
    /* 1. 僅隱藏右上角分享、星星、GitHub 等無關按鈕，嚴格保留左上角側邊欄按鈕 */
    [data-testid="stToolbar"],
    .stAppDeployButton,
    #MainMenu,
    footer,
    [data-testid="stStatusWidget"],
    [data-testid="manage-app-button"],
    #manage-app-button,
    div[class*="viewerBadge"],
    div[class*="StatusWidget"],
    div[class*="Profile"] {
        display: none !important;
        visibility: hidden !important;
        height: 0px !important;
        width: 0px !important;
        opacity: 0 !important;
        pointer-events: none !important;
        margin: 0 !important;
        padding: 0 !important;
    }

    /* 頂部 Header 保持透明但維持高度以容納按鈕 */
    header[data-testid="stHeader"] {
        background: transparent !important;
        height: 3.2rem !important;
        z-index: 9999 !important;
    }

    /* 2. 【核心修復】強化左上角側邊欄展開按鈕的可見度與觸控範圍 */
    [data-testid="collapsedControl"],
    button[kind="header"] {
        display: flex !important;
        visibility: visible !important;
        opacity: 1 !important;
        top: 0.6rem !important;
        left: 0.6rem !important;
        z-index: 999999 !important;
        background-color: #ffffff !important;
        color: #0284c7 !important;
        border-radius: 12px !important;
        box-shadow: 0 2px 10px rgba(15, 23, 42, 0.12) !important;
        border: 1px solid #cbd5e1 !important;
        width: 38px !important;
        height: 38px !important;
        align-items: center !important;
        justify-content: center !important;
    }
    [data-testid="collapsedControl"]:hover {
        background-color: #f0f9ff !important;
        border-color: #0284c7 !important;
    }

    /* 3. 鎖定全域寬度防橫向破版 */
    html, body, [data-testid="stAppViewContainer"], .main, .block-container {
        max-width: 100vw !important;
        width: 100% !important;
        overflow-x: hidden !important;
        box-sizing: border-box !important;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
        color: #0f172a;
        background-color: #f8fafc;
    }

    /* 4. 邊距極致適配 */
    .block-container {
        padding-top: 0.6rem !important;
        padding-bottom: 2rem !important;
        padding-left: 1rem !important;
        padding-right: 1rem !important;
    }
    @media (max-width: 768px) {
        .block-container {
            padding-top: 0.4rem !important;
            padding-bottom: 1.5rem !important;
            padding-left: 0.65rem !important;
            padding-right: 0.65rem !important;
        }
    }

    /* 5. 頂部 App 品牌標題欄 */
    .app-brand-bar {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 8px;
        margin-top: 2px;
    }
    .app-brand-title {
        font-size: 20px;
        font-weight: 800;
        color: #0f172a;
        letter-spacing: -0.3px;
        display: flex;
        align-items: center;
        gap: 6px;
    }

    /* 6. 天氣自適應動態質感深藍大卡片 */
    .weather-hero-card {
        padding: 22px 24px;
        border-radius: 20px;
        color: white;
        margin-top: 4px;
        margin-bottom: 12px;
        border: 1px solid rgba(255, 255, 255, 0.25);
        box-sizing: border-box;
        transition: all 0.4s ease;
    }
    @media (max-width: 768px) {
        .weather-hero-card {
            padding: 18px 16px;
            border-radius: 16px;
        }
    }

    /* 大卡內部的 4 大指標毛玻璃微光膠囊 */
    .hero-metrics-grid {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 8px;
        margin-top: 14px;
        padding-top: 12px;
        border-top: 1px solid rgba(255, 255, 255, 0.18);
    }
    @media (max-width: 768px) {
        .hero-metrics-grid {
            grid-template-columns: repeat(2, 1fr);
            gap: 6px;
            margin-top: 12px;
            padding-top: 10px;
        }
    }
    .hero-metric-pill {
        background: rgba(255, 255, 255, 0.12);
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        border: 1px solid rgba(255, 255, 255, 0.2);
        border-radius: 10px;
        padding: 7px 10px;
        font-size: 12.5px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
    }

    /* 橫向滑動預報卡片流 */
    .weather-scroll-row {
        display: flex;
        gap: 10px;
        overflow-x: auto;
        padding: 6px 2px 14px 2px;
        -webkit-overflow-scrolling: touch;
        scrollbar-width: thin;
        max-width: 100% !important;
        box-sizing: border-box !important;
    }
    .weather-scroll-row::-webkit-scrollbar {
        height: 6px;
    }
    .weather-scroll-row::-webkit-scrollbar-thumb {
        background: #cbd5e1;
        border-radius: 6px;
    }

    .hourly-scroll-card {
        flex: 0 0 98px;
        background: #ffffff;
        border: 1px solid #f1f5f9;
        border-radius: 14px;
        padding: 12px 6px;
        text-align: center;
        box-shadow: 0 2px 6px rgba(0, 0, 0, 0.03);
    }
    .daily-scroll-card {
        flex: 0 0 114px;
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 14px;
        padding: 14px 8px;
        text-align: center;
        box-shadow: 0 2px 6px rgba(0, 0, 0, 0.03);
    }

    /* AI 12小時變化洞察卡片樣式 */
    .ai-summary-card {
        background: #ffffff;
        border: 1px solid #e0f2fe;
        border-radius: 16px;
        padding: 15px 18px;
        box-shadow: 0 4px 14px rgba(2, 132, 199, 0.06);
        box-sizing: border-box;
        margin-bottom: 10px;
    }
    .ai-summary-header {
        display: flex;
        align-items: center;
        gap: 6px;
        padding-bottom: 8px;
        margin-bottom: 10px;
        border-bottom: 1px dashed #bae6fd;
    }
    .ai-summary-body {
        display: flex;
        flex-direction: column;
        gap: 9px;
        font-size: 13.5px;
        line-height: 1.6;
        color: #334155;
    }
    .ai-summary-item {
        display: flex;
        align-items: flex-start;
        gap: 8px;
    }
    .ai-item-icon {
        font-size: 15px;
        flex-shrink: 0;
        margin-top: 2px;
    }

    .map-frame-container {
        border-radius: 16px;
        overflow: hidden;
        border: 1px solid #e2e8f0;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.04);
        margin-top: 8px;
        width: 100% !important;
        max-width: 100% !important;
    }
    .map-frame-container iframe, iframe {
        max-width: 100% !important;
        width: 100% !important;
    }

    .compact-tip-box {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 11px 15px;
        margin-bottom: 10px;
        font-size: 13.5px;
        color: #334155;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.02);
    }
</style>
""", unsafe_allow_html=True)

# -------------------------------------------------------------
# 2. 臺灣全境 22 縣市 368 鄉鎮市區法定基底庫
# -------------------------------------------------------------
BUILTIN_TAIWAN_DATA = {
    "臺北市": {
        "中正區": (25.0324, 121.5190), "大同區": (25.0633, 121.5133), "中山區": (25.0685, 121.5338),
        "松山區": (25.0599, 121.5575), "大安區": (25.0264, 121.5435), "萬華區": (25.0354, 121.4997),
        "信義區": (25.0330, 121.5654), "士林區": (25.0926, 121.5245), "北投區": (25.1321, 121.4987),
        "內湖區": (25.0835, 121.5898), "南港區": (25.0553, 121.6171), "文山區": (24.9982, 121.5701)
    },
    "新北市": {
        "板橋區": (25.0125, 121.4657), "三重區": (25.0712, 121.4880), "中和區": (24.9996, 121.5002),
        "永和區": (25.0078, 121.5140), "新莊區": (25.0360, 121.4444), "新店區": (24.9680, 121.5418),
        "樹林區": (24.9912, 121.4248), "鶯歌區": (24.9547, 121.3545), "三峽區": (24.9342, 121.3715),
        "淡水區": (25.1694, 121.4428), "汐止區": (25.0630, 121.6589), "瑞芳區": (25.1089, 121.8109),
        "土城區": (24.9723, 121.4437), "蘆洲區": (25.0849, 121.4735), "五股區": (25.0829, 121.4385),
        "泰山區": (25.0595, 121.4308), "林口區": (25.0775, 121.3934), "深坑區": (25.0023, 121.6158),
        "石碇區": (24.9918, 121.6585), "坪林區": (24.9372, 121.7115), "三芝區": (25.2583, 121.5008),
        "石門區": (25.2904, 121.5683), "八里區": (25.1466, 121.3975), "平溪區": (25.0257, 121.7385),
        "雙溪區": (25.0345, 121.8654), "貢寮區": (25.0221, 121.9085), "金山區": (25.2218, 121.6378),
        "萬里區": (25.1789, 121.6889), "烏來區": (24.8653, 121.5505)
    },
    "基隆市": {
        "仁愛區": (25.1276, 121.7410), "信義區": (25.1285, 121.7585), "中正區": (25.1485, 121.7685),
        "中山區": (25.1415, 121.7325), "安樂區": (25.1325, 121.7125), "暖暖區": (25.1015, 121.7385), "七堵區": (25.0965, 121.7145)
    },
    "桃園市": {
        "桃園區": (24.9936, 121.3010), "中壢區": (24.9537, 121.2257), "平鎮區": (24.9458, 121.2185),
        "八德區": (24.9298, 121.2831), "楊梅區": (24.9085, 121.1459), "蘆竹區": (25.0458, 121.2922),
        "大溪區": (24.8837, 121.2868), "龜山區": (24.9937, 121.3387), "大園區": (25.0631, 121.1969),
        "觀音區": (25.0368, 121.0825), "新屋區": (24.9723, 121.1057), "龍潭區": (24.8637, 121.2163), "復興區": (24.8214, 121.3530)
    },
    "新竹市": {
        "東區": (24.7985, 120.9785), "北區": (24.8152, 120.9625), "香山區": (24.7678, 120.9285)
    },
    "新竹縣": {
        "竹北市": (24.8387, 121.0177), "竹東鎮": (24.7335, 121.0885), "新埔鎮": (24.8258, 121.0725),
        "關西鎮": (24.7935, 121.1765), "湖口鄉": (24.9038, 121.0435), "新豐鄉": (24.8985, 120.9835),
        "芎林鄉": (24.7745, 121.0785), "橫山鄉": (24.7215, 121.1145), "北埔鄉": (24.6985, 121.0585),
        "寶山鄉": (24.7615, 120.9885), "峨眉鄉": (24.6855, 121.0145), "尖石鄉": (24.7085, 121.2015), "五峰鄉": (24.6315, 121.1145)
    },
    "苗栗縣": {
        "苗栗市": (24.5602, 120.8214), "頭份市": (24.6885, 120.9125), "竹南鎮": (24.6858, 120.8755),
        "後龍鎮": (24.6158, 120.7865), "通霄鎮": (24.4895, 120.6785), "苑裡鎮": (24.4425, 120.6525),
        "卓蘭鎮": (24.3095, 120.8435), "造橋鄉": (24.6375, 120.8625), "西湖鄉": (24.5365, 120.7515),
        "頭屋鄉": (24.5745, 120.8485), "公館鄉": (24.4985, 120.8245), "銅鑼鄉": (24.4855, 120.7865),
        "三義鄉": (24.4125, 120.7725), "大湖鄉": (24.4215, 120.8655), "獅潭鄉": (24.5415, 120.9215),
        "三灣鄉": (24.6515, 120.9545), "南庄鄉": (24.5985, 120.9985), "泰安鄉": (24.4415, 120.9415)
    },
    "臺中市": {
        "中區": (24.1422, 120.6800), "東區": (24.1353, 120.6974), "南區": (24.1198, 120.6635),
        "西區": (24.1477, 120.6736), "北區": (24.1610, 120.6825), "北屯區": (24.1822, 120.7041),
        "西屯區": (24.1815, 120.6171), "南屯區": (24.1384, 120.6405), "太平區": (24.1264, 120.7180),
        "大里區": (24.0995, 120.6784), "霧峰區": (24.0620, 120.6997), "烏日區": (24.1054, 120.6238),
        "豐原區": (24.2549, 120.7226), "后里區": (24.3045, 120.7105), "石岡區": (24.2750, 120.7812),
        "東勢區": (24.2586, 120.8283), "和平區": (24.2440, 121.0028), "新社區": (24.2331, 120.8115),
        "潭子區": (24.2096, 120.7051), "大雅區": (24.2291, 120.6483), "神岡區": (24.2578, 120.6612),
        "大肚區": (24.1534, 120.5415), "沙鹿區": (24.2335, 120.5661), "龍井區": (24.1925, 120.5485),
        "梧棲區": (24.2550, 120.5318), "清水區": (24.2673, 120.5698), "大甲區": (24.3491, 120.6215),
        "外埔區": (24.3323, 120.6548), "大安區": (24.3448, 120.5841)
    },
    "彰化縣": {
        "彰化市": (24.0816, 120.5385), "鹿港鎮": (24.0585, 120.4355), "和美鎮": (24.1115, 120.5015),
        "線西鄉": (24.1285, 120.4685), "伸港鄉": (24.1485, 120.4885), "福興鄉": (24.0455, 120.4415),
        "秀水鄉": (24.0355, 120.5015), "花壇鄉": (24.0285, 120.5415), "芬園鄉": (24.0155, 120.6315),
        "員林市": (23.9585, 120.5745), "溪湖鎮": (23.9615, 120.4815), "田中鎮": (23.8615, 120.5885),
        "大村鄉": (23.9945, 120.5415), "埔鹽鄉": (23.9845, 120.4615), "埔心鄉": (23.9545, 120.5415),
        "永靖鄉": (23.9245, 120.5485), "社頭鄉": (23.8965, 120.5885), "二水鄉": (23.8085, 120.6185),
        "田尾鄉": (23.8915, 120.5285), "埤頭鄉": (23.8915, 120.4615), "芳苑鄉": (23.9245, 120.3215),
        "大城鄉": (23.8545, 120.3215), "竹塘鄉": (23.8615, 120.4285), "二林鎮": (23.8985, 120.3785),
        "北斗鎮": (23.8745, 120.5215), "溪州鄉": (23.8515, 120.4985)
    },
    "南投縣": {
        "南投市": (23.9099, 120.6845), "埔里鎮": (23.9665, 120.9685), "草屯鎮": (23.9845, 120.6855),
        "竹山鎮": (23.7578, 120.6865), "集集鎮": (23.8285, 120.7815), "名間鄉": (23.8385, 120.7015),
        "鹿谷鄉": (23.7445, 120.7515), "中寮鄉": (23.8785, 120.7685), "魚池鄉": (23.8985, 120.9345),
        "國姓鄉": (24.0415, 120.8585), "水里鄉": (23.8115, 120.8545), "信義鄉": (23.6685, 120.8545), "仁愛鄉": (24.0245, 121.1345)
    },
    "雲林縣": {
        "斗六市": (23.7092, 120.4313), "斗南鎮": (23.6785, 120.4815), "虎尾鎮": (23.7085, 120.4325),
        "西螺鎮": (23.7985, 120.4615), "土庫鎮": (23.6945, 120.3615), "北港鎮": (23.5745, 120.3015),
        "古坑鄉": (23.6445, 120.5615), "大埤鄉": (23.6445, 120.4315), "莿桐鄉": (23.7745, 120.5315),
        "林內鄉": (23.7585, 120.6145), "二崙鄉": (23.7715, 120.4145), "崙背鄉": (23.7615, 120.3545),
        "麥寮鄉": (23.7485, 120.2515), "東勢鄉": (23.6745, 120.2545), "褒忠鄉": (23.6945, 120.3115),
        "臺西鄉": (23.7015, 120.1985), "元長鄉": (23.6485, 120.3145), "四湖鄉": (23.6385, 120.2245),
        "口湖鄉": (23.5815, 120.1885), "水林鄉": (23.5715, 120.2455)
    },
    "嘉義市": {
        "東區": (23.4835, 120.4635), "西區": (23.4765, 120.4355)
    },
    "嘉義縣": {
        "太保市": (23.4595, 120.3325), "朴子市": (23.4685, 120.2485), "布袋鎮": (23.3785, 120.1615),
        "大林鎮": (23.6045, 120.4715), "民雄鄉": (23.5535, 120.4285), "溪口鄉": (23.6045, 120.3945),
        "新港鄉": (23.5545, 120.3485), "六腳鄉": (23.5045, 120.2545), "東石鄉": (23.4545, 120.1545),
        "義竹鄉": (23.3385, 120.2415), "鹿草鄉": (23.4115, 120.3115), "水上鄉": (23.4285, 120.3985),
        "中埔鄉": (23.4245, 120.5245), "竹崎鄉": (23.5235, 120.5515), "梅山鄉": (23.5845, 120.5585),
        "番路鄉": (23.4645, 120.5545), "大埔鄉": (23.2985, 120.5945), "阿里山鄉": (23.4685, 120.7325)
    },
    "臺南市": {
        "新營區": (23.3103, 120.3162), "鹽水區": (23.3185, 120.2645), "白河區": (23.3512, 120.4158),
        "柳營區": (23.2785, 120.3115), "後壁區": (23.3645, 120.3585), "東山區": (23.3245, 120.4045),
        "麻豆區": (23.1819, 120.2483), "下營區": (23.2345, 120.2645), "六甲區": (23.2315, 120.3485),
        "官田區": (23.1945, 120.3145), "大內區": (23.1185, 120.3515), "佳里區": (23.1652, 120.1772),
        "學甲區": (23.2315, 120.1815), "西港區": (23.1215, 120.2015), "七股區": (23.1415, 120.1345),
        "將軍區": (23.1985, 120.1585), "北門區": (23.2685, 120.1245), "新化區": (23.0384, 120.3105),
        "善化區": (23.1322, 120.2965), "新市區": (23.0785, 120.2945), "安定區": (23.1085, 120.2345),
        "山上區": (23.1045, 120.3545), "玉井區": (23.1245, 120.4615), "楠西區": (23.1745, 120.4885),
        "南化區": (23.0445, 120.4785), "左鎮區": (23.0585, 120.4145), "仁德區": (22.9715, 120.2515),
        "歸仁區": (22.9672, 120.2934), "關廟區": (22.9615, 120.3285), "龍崎區": (22.9645, 120.3615),
        "永康區": (23.0262, 120.2568), "東區": (22.9815, 120.2241), "南區": (22.9610, 120.1956),
        "北區": (23.0071, 120.2078), "安南區": (23.0478, 120.1852), "安平區": (22.9972, 120.1685),
        "中西區": (22.9922, 120.1989)
    },
    "高雄市": {
        "鹽埕區": (22.6247, 120.2842), "鼓山區": (22.6375, 120.2778), "左營區": (22.6902, 120.2945),
        "楠梓區": (22.7285, 120.3262), "三民區": (22.6438, 120.3005), "新興區": (22.6314, 120.3019),
        "前金區": (22.6272, 120.2952), "苓雅區": (22.6273, 120.3014), "前鎮區": (22.5864, 120.3162),
        "旗津區": (22.5715, 120.2945), "小港區": (22.5654, 120.3562), "鳳山區": (22.6269, 120.3575),
        "林園區": (22.5045, 120.3945), "大寮區": (22.6045, 120.3985), "大樹區": (22.6945, 120.4315),
        "大社區": (22.7315, 120.3485), "仁武區": (22.7015, 120.3485), "鳥松區": (22.6585, 120.3645),
        "岡山區": (22.7965, 120.2958), "橋頭區": (22.7585, 120.3045), "燕巢區": (22.7945, 120.3615),
        "田寮區": (22.8745, 120.3615), "阿蓮區": (22.8845, 120.3285), "路竹區": (22.8585, 120.2615),
        "湖內區": (22.9045, 120.2145), "茄萣區": (22.9085, 120.1815), "永安區": (22.8185, 120.2285),
        "彌陀區": (22.7815, 120.2415), "梓官區": (22.7615, 120.2645), "旗山區": (22.8885, 120.4815),
        "美濃區": (22.8975, 120.5415), "六龜區": (22.9985, 120.6345), "甲仙區": (23.0845, 120.5915),
        "杉林區": (22.9715, 120.5385), "內門區": (22.9445, 120.4615), "茂林區": (22.8845, 120.6645),
        "桃源區": (23.1585, 120.7615), "那瑪夏區": (23.2385, 120.6945)
    },
    "屏東縣": {
        "屏東市": (22.6762, 120.4879), "潮州鎮": (22.5505, 120.5425), "東港鎮": (22.4685, 120.4545),
        "恆春鎮": (22.0045, 120.7445), "萬丹鄉": (22.5885, 120.4845), "長治鄉": (22.6785, 120.5285),
        "麟洛鄉": (22.6515, 120.5285), "九如鄉": (22.7385, 120.4885), "里港鄉": (22.7785, 120.4945),
        "高樹鄉": (22.8245, 120.5985), "萬巒鄉": (22.5715, 120.5685), "內埔鄉": (22.6145, 120.5645),
        "竹田鄉": (22.5855, 120.5435), "新埤鄉": (22.4685, 120.5485), "枋寮鄉": (22.3685, 120.5945),
        "車城鄉": (22.0745, 120.7115), "滿州鄉": (22.0245, 120.8385), "琉球鄉": (22.3415, 120.3685)
    },
    "宜蘭縣": {
        "宜蘭市": (24.7570, 121.7530), "羅東鎮": (24.6765, 121.7685), "蘇澳鎮": (24.5945, 121.8485),
        "頭城鎮": (24.8585, 121.8215), "礁溪鄉": (24.8235, 121.7725), "壯圍鄉": (24.7445, 121.8145),
        "員山鄉": (24.7445, 121.7215), "冬山鄉": (24.6345, 121.7945), "五結鄉": (24.6945, 121.7985),
        "三星鄉": (24.6645, 121.6515), "大同鄉": (24.6745, 121.6085), "南澳鄉": (24.4645, 121.7985)
    },
    "花蓮縣": {
        "花蓮市": (23.9872, 121.6016), "鳳林鎮": (23.7445, 121.4515), "玉里鎮": (23.3345, 121.3145),
        "新城鄉": (24.0315, 121.6085), "吉安鄉": (23.9635, 121.5725), "壽豐鄉": (23.8715, 121.5085),
        "光復鄉": (23.6685, 121.4185), "豐濱鄉": (23.5985, 121.5185), "瑞穗鄉": (23.4985, 121.3785),
        "富里鄉": (23.1785, 121.2515), "秀林鄉": (24.1545, 121.6215)
    },
    "臺東縣": {
        "臺東市": (22.7583, 121.1444), "成功鎮": (23.1045, 121.3785), "關山鎮": (23.0485, 121.1615),
        "卑南鄉": (22.7845, 121.0845), "鹿野鄉": (22.9145, 121.1345), "池上鄉": (23.1245, 121.2185),
        "東河鄉": (22.9715, 121.3015), "太麻里鄉": (22.6145, 120.9985), "綠島鄉": (22.6645, 121.4915), "蘭嶼鄉": (22.0485, 121.5515)
    },
    "澎湖縣": {
        "馬公市": (23.5711, 119.5793), "湖西鄉": (23.5845, 119.6585), "白沙鄉": (23.6645, 119.5985),
        "西嶼鄉": (23.6015, 119.5085), "望安鄉": (23.3685, 119.5015), "七美鄉": (23.2045, 119.4285)
    },
    "金門縣": {
        "金城鎮": (24.4492, 118.3766), "金沙鎮": (24.4845, 118.4185), "金湖鎮": (24.4385, 118.4185),
        "金寧鄉": (24.4585, 118.3345), "烈嶼鄉": (24.4285, 118.2415)
    },
    "連江縣": {
        "南竿鄉": (26.1558, 119.9392), "北竿鄉": (26.2215, 119.9885), "莒光鄉": (25.9715, 119.9345), "東引鄉": (26.3685, 120.4945)
    }
}

# -------------------------------------------------------------
# 3. 原生零依賴 XLSX 解構引擎 (Zero-Dependency)
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

        is_tw = any(k in country for k in ["臺灣", "台灣", "Taiwan"])
        if is_tw:
            city_label = f"{city_zh} {city_en}" if city_en and city_en != city_zh else city_zh
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

    return {
        "亞洲 (Asia)": {
            "日本 / Japan": {
                "東京 (Tokyo)": [35.6762, 139.6503],
                "大阪 (Osaka)": [34.6937, 135.5023]
            },
            "南韓 / South Korea": {
                "首爾 (Seoul)": [37.5665, 126.9780]
            }
        },
        "歐洲 (Europe)": {
            "法國 / France": {
                "巴黎 (Paris)": [48.8566, 2.3522]
            },
            "英國 / United Kingdom": {
                "倫敦 (London)": [51.5074, -0.1278]
            }
        },
        "北美洲 (North America)": {
            "美國 / United States": {
                "紐約 (New York)": [40.7128, -74.0060],
                "洛杉磯 (Los Angeles)": [34.0522, -118.2437]
            }
        }
    }

load_world_cities_hierarchy = load_all_cities_hierarchy

# -------------------------------------------------------------
# 4. 資料庫整合
# -------------------------------------------------------------
@st.cache_data(show_spinner=False)
def get_taiwan_and_search_index():
    hierarchy = load_all_cities_hierarchy()
    taiwan_data = {c: dict(t) for c, t in BUILTIN_TAIWAN_DATA.items()}

    for continent, countries in hierarchy.items():
        for country, cities in countries.items():
            is_taiwan = any(k in country for k in ["臺灣", "台灣", "Taiwan"])

            for city_label, coords in cities.items():
                try:
                    lat_f, lon_f = float(coords[0]), float(coords[1])
                except (ValueError, TypeError, IndexError):
                    continue

                if is_taiwan:
                    parts = city_label.split(" ")
                    county = parts[0]
                    town = parts[1] if len(parts) > 1 else parts[0]
                    if county in taiwan_data:
                        taiwan_data[county][town] = (lat_f, lon_f)

    return taiwan_data, hierarchy

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

def get_weather_hero_style(code: int, temp: float):
    if code in [0, 1]:
        return (
            "background: radial-gradient(ellipse at 85% 15%, rgba(253, 224, 71, 0.35) 0%, rgba(56, 189, 248, 0.18) 45%, transparent 70%), "
            "linear-gradient(135deg, #1d4ed8 0%, #0284c7 55%, #0369a1 100%); "
            "box-shadow: 0 14px 30px -6px rgba(2, 132, 199, 0.4), inset 0 1px 1px rgba(255, 255, 255, 0.35);"
        )
    elif code == 2:
        return (
            "background: radial-gradient(ellipse at 85% 15%, rgba(224, 242, 254, 0.28) 0%, rgba(96, 165, 250, 0.15) 45%, transparent 65%), "
            "linear-gradient(135deg, #1e3a8a 0%, #1e40af 50%, #172554 100%); "
            "box-shadow: 0 14px 30px -6px rgba(30, 58, 138, 0.38), inset 0 1px 1px rgba(255, 255, 255, 0.28);"
        )
    elif code in [3, 45, 48]:
        return (
            "background: radial-gradient(ellipse at 85% 15%, rgba(203, 213, 225, 0.24) 0%, transparent 60%), "
            "linear-gradient(135deg, #334155 0%, #1e293b 55%, #0f172a 100%); "
            "box-shadow: 0 14px 30px -6px rgba(15, 23, 42, 0.45), inset 0 1px 1px rgba(255, 255, 255, 0.2);"
        )
    elif code in [51, 61, 63, 65, 80, 81]:
        return (
            "background: radial-gradient(ellipse at 85% 15%, rgba(56, 189, 248, 0.32) 0%, rgba(14, 116, 144, 0.2) 45%, transparent 70%), "
            "linear-gradient(135deg, #0c2340 0%, #133e68 55%, #081d33 100%); "
            "box-shadow: 0 14px 30px -6px rgba(12, 35, 64, 0.5), inset 0 1px 1px rgba(56, 189, 248, 0.28);"
        )
    elif code in [82, 95, 96]:
        return (
            "background: radial-gradient(ellipse at 85% 15%, rgba(168, 85, 247, 0.35) 0%, rgba(99, 102, 241, 0.2) 45%, transparent 65%), "
            "linear-gradient(135deg, #0f172a 0%, #1e1b4b 50%, #172554 100%); "
            "box-shadow: 0 14px 30px -6px rgba(30, 27, 75, 0.55), inset 0 1px 1px rgba(192, 132, 252, 0.3);"
        )
    else:
        return (
            "background: radial-gradient(ellipse at 85% 15%, rgba(255, 255, 255, 0.2) 0%, transparent 55%), "
            "linear-gradient(135deg, #1e3c72 0%, #2a5298 55%, #1e293b 100%); "
            "box-shadow: 0 14px 30px -6px rgba(30, 58, 138, 0.38), inset 0 1px 1px rgba(255, 255, 255, 0.25);"
        )

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
# 6. 生活管家決策引擎
# -------------------------------------------------------------
def get_comprehensive_assistant_advice(temp, feels_like, rain_prob, humidity, wind_speed, aqi_val, uv_val):
    uv_status, uv_tip = parse_uv_level(uv_val)

    diff = round(feels_like - temp, 1)
    if abs(diff) >= 3.0:
        if diff > 0:
            diff_note = f"（濕度偏高，體感比氣溫高出 {abs(diff)}°C）"
        else:
            diff_note = f"（風速影響，體感比氣溫低 {abs(diff)}°C）"
    else:
        diff_note = ""

    if rain_prob >= 60:
        intro_text = f"路面潮濕易滑（體感 {feels_like:.1f}°C{diff_note}），出門請隨身攜帶雨具並放慢車速。"
    elif uv_val >= 8:
        intro_text = f"紫外線偏強（UV {uv_val:.1f}），外出請加強防曬並適時補充水分。"
    elif temp >= 29:
        intro_text = f"體感偏熱（體感 {feels_like:.1f}°C{diff_note}），外出活動請防曬、多喝水預防中暑。"
    elif temp <= 18:
        intro_text = f"天氣偏涼（體感 {feels_like:.1f}°C{diff_note}），早晚溫差大，出門建議洋蔥式穿搭。"
    else:
        intro_text = f"氣候舒適宜人（體感 {feels_like:.1f}°C{diff_note}），非常適宜外出踏青或戶外活動。"

    ref_temp = feels_like
    if ref_temp >= 28:
        wear_headline = "舒適短袖 / 透氣薄襯衫"
        wear_desc = f"""
        * **日間穿著**：透氣吸汗短袖或棉麻寬鬆上衣。
        * **防曬提醒**：紫外線為 **{uv_status}**（指數 {uv_val:.1f}），{uv_tip}
        * **室內溫差**：室內外溫差常達 5°C 以上，建議備薄開襟衫防冷氣著涼。
        """
    elif 21 <= ref_temp < 28:
        wear_headline = "舒適短袖 / 襯衫 + 薄外套備用"
        wear_desc = f"""
        * **日間穿著**：純棉 T-shirt、薄長袖或休閒襯衫剛剛好。
        * **防曬提醒**：紫外線為 **{uv_status}**（指數 {uv_val:.1f}），請適度防曬。
        * **早晚應對**：早晚日夜溫差約 3~6°C，建議隨身攜帶薄夾克或風衣。
        """
    else:
        wear_headline = "洋蔥式保暖 + 厚外套/風衣"
        wear_desc = f"""
        * **內層保暖**：棉質長袖或輕量發熱衣鎖住核心體溫。
        * **外層禦寒**：搭配防風外套、羊毛大衣或羽絨背心。
        * **防風配件**：步行或騎車配戴防風圍巾降低體感寒意。
        """

    if rain_prob < 30 and humidity < 75:
        dry_headline = "五星推薦（通風良好，戶外速乾）"
        dry_desc = f"""
        * **晾乾速度**：環境濕度僅 {humidity}%，通風充足，衣物約 2.5~3 小時即可乾燥。
        * **推薦清洗**：床單、被套等難乾大件物品請把握今日！
        """
    elif rain_prob >= 50 or humidity >= 80:
        dry_headline = "不建議室外（建議室內搭配除濕機）"
        dry_desc = f"""
        * **受潮風險**：降雨機率高達 {rain_prob}%，空氣濕度飽和，室外晾掛易吸附潮氣。
        * **解決方式**：改掛於室內通風處，搭配除濕機或低溫烘乾。
        """
    else:
        dry_headline = "陽台陰乾為佳（留意午後天氣突變）"
        dry_desc = f"""
        * **曬衣處選擇**：請掛於有遮棚陽台，並於傍晚日落前收納入室避免返潮。
        """

    if rain_prob >= 50:
        commute_tip = "路面潮濕易打滑，行經標線水溝蓋請減速；建議攜帶防水雨具。"
        sport_status = "戶外濕滑易雨，建議改至室內伸展或健身訓練。"
    elif wind_speed > 20:
        commute_tip = "陣風偏大，行經橋樑空曠路段請注意車身穩定與車距。"
        sport_status = "風力稍大，不宜羽球等球類運動，慢跑請留意風阻。"
    else:
        commute_tip = "天候晴朗乾燥，視線良好，各類通勤出行均非常順暢安全。"
        sport_status = "氣候舒適宜人，非常適合慢跑、散步或單車騎乘。"

    pack_items = []
    if rain_prob >= 40:
        pack_items.append("🌂 折疊雨傘 / 輕便雨具")
    if uv_val >= 6:
        pack_items.append("🧴 防曬乳 (SPF30+) / 抗 UV 傘")
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
# 7. AI 12小時氣象洞察分析引擎
# -------------------------------------------------------------
def generate_12h_ai_summary(times, temps, rains, codes):
    if not times or not temps or len(temps) == 0:
        return """
        <div class="ai-summary-card">
            <div class="ai-summary-header">
                <span style="font-size: 17px;">🤖</span>
                <span style="font-weight: 700; font-size: 14.5px; color: #0284c7;">AI 氣象管家 · 12H 變化洞察</span>
            </div>
            <div class="ai-summary-body">
                <div>資料同步中，請稍候刷新即可取得即時洞察。</div>
            </div>
        </div>
        """

    try:
        max_t = max(temps)
        min_t = min(temps)
        max_t_idx = temps.index(max_t)
        min_t_idx = temps.index(min_t)
        max_t_time = times[max_t_idx] if max_t_idx < len(times) else "稍後"
        min_t_time = times[min_t_idx] if min_t_idx < len(times) else "稍後"
        temp_range = round(max_t - min_t, 1)

        safe_rains = rains if rains else [0] * len(temps)
        max_r = max(safe_rains)
        max_r_idx = safe_rains.index(max_r)
        max_r_time = times[max_r_idx] if max_r_idx < len(times) else "期間"

        start_t = temps[0]
        end_t = temps[-1]
        if end_t - start_t >= 2.5:
            t_trend_desc = f"氣溫呈現明顯回升趨勢（溫差攀升約 {round(end_t - start_t, 1)}°C）"
        elif start_t - end_t >= 2.5:
            t_trend_desc = f"氣溫將逐漸下滑轉涼（預估降幅達 {round(start_t - end_t, 1)}°C）"
        else:
            t_trend_desc = "氣溫起伏相對平緩穩健"

        rainy_hours = [times[i] for i, r in enumerate(safe_rains) if r >= 40 and i < len(times)]
        if rainy_hours:
            rain_desc = f"預計在 <strong>{', '.join(rainy_hours[:3])}</strong> 等時段降雨機率偏高（最高達 <strong>{max_r}%</strong> 出現在 {max_r_time}），出門請隨身攜帶雨具。"
        elif max_r >= 25:
            rain_desc = f"降雨機率最高約 <strong>{max_r}%</strong>（約 {max_r_time}），雲量偏多偶有微雨，天色稍陰但總體影響不大。"
        else:
            rain_desc = f"未來 12 小時天候乾爽穩定，最高降雨機率僅 <strong>{max_r}%</strong>，外出無需擔心降雨打擾。"

        advice_list = []
        if temp_range >= 5:
            advice_list.append(f"早晚/日夜溫差達 {temp_range}°C，建議採洋蔥式穿搭並攜帶薄外套")
        if max_r >= 40:
            advice_list.append("路面潮濕易打滑，行經標線或水溝蓋請減速慢行")
        if max_t >= 30:
            advice_list.append(f"最高溫達 {max_t:.1f}°C，戶外請加強防曬並適時補充水分")
        elif min_t <= 18:
            advice_list.append(f"最低溫觸及 {min_t:.1f}°C，出門請加強防風保暖")

        if not advice_list:
            advice_list.append("氣候舒適平穩，非常適宜各項戶外休閒散步或出行")

        return f"""
        <div class="ai-summary-card">
            <div class="ai-summary-header">
                <span style="font-size: 17px;">🤖</span>
                <span style="font-weight: 700; font-size: 14.5px; color: #0284c7;">AI 氣象管家 · 12H 變化洞察</span>
            </div>
            <div class="ai-summary-body">
                <div class="ai-summary-item">
                    <span class="ai-item-icon">🌡️</span>
                    <div><strong>氣溫起伏：</strong>預估在 <strong>{min_t:.1f}°C ~ {max_t:.1f}°C</strong> 之間波動，高溫落在 {max_t_time}，低溫在 {min_t_time}，{t_trend_desc}。</div>
                </div>
                <div class="ai-summary-item">
                    <span class="ai-item-icon">💧</span>
                    <div><strong>降雨走向：</strong>{rain_desc}</div>
                </div>
                <div class="ai-summary-item">
                    <span class="ai-item-icon">💡</span>
                    <div><strong>即時建議：</strong>{'；'.join(advice_list)}。</div>
                </div>
            </div>
        </div>
        """
    except Exception:
        return "<div class='ai-summary-card'>AI 氣象管家正連線中...</div>"

# -------------------------------------------------------------
# 8. 所在地狀態持久化
# -------------------------------------------------------------
if "my_home_location" not in st.session_state:
    st.session_state.my_home_location = {
        "name": "臺中市東勢區",
        "lat": 24.2586,
        "lon": 120.8283
    }

geo = get_geolocation()
if geo and isinstance(geo, dict) and "coords" in geo and geo["coords"]:
    try:
        u_lat = float(geo["coords"].get("latitude", 24.2586))
        u_lon = float(geo["coords"].get("longitude", 120.8283))
        if (abs(u_lat - st.session_state.my_home_location["lat"]) > 0.005 or
            abs(u_lon - st.session_state.my_home_location["lon"]) > 0.005):
            st.session_state.my_home_location = {
                "name": "目前設備所在",
                "lat": u_lat,
                "lon": u_lon
            }
    except (ValueError, TypeError):
        pass

if "active_target" not in st.session_state:
    st.session_state.active_target = {
        "name": f"📍 目前所在地:{st.session_state.my_home_location['name']}",
        "lat": float(st.session_state.my_home_location["lat"]),
        "lon": float(st.session_state.my_home_location["lon"])
    }

taiwan_data, world_hierarchy = get_taiwan_and_search_index()

# -------------------------------------------------------------
# 9. 階層式選擇視窗
# -------------------------------------------------------------
dialog_decorator = getattr(st, "dialog", getattr(st, "experimental_dialog", None))

def render_location_dialog_content():
    st.markdown("#### 🧭 請選擇查詢地區")

    region_type = st.radio(
        "區域選擇",
        options=["🇹🇼 臺灣鄉鎮", "🌍 全球城市"],
        horizontal=True,
        label_visibility="collapsed"
    )

    st.write("")

    if "臺灣" in region_type:
        county_list = list(taiwan_data.keys())
        if county_list:
            default_c_idx = county_list.index("臺中市") if "臺中市" in county_list else 0
            sel_county = st.selectbox("1. 選擇縣市", options=county_list, index=default_c_idx, key="diag_tw_county")

            town_dict = taiwan_data.get(sel_county, {})
            town_list = list(town_dict.keys())
            default_t_idx = town_list.index("東勢區") if "東勢區" in town_list else 0
            sel_town = st.selectbox("2. 選擇鄉鎮市區", options=town_list, index=default_t_idx if town_list else 0, key="diag_tw_town")

            st.write("")
            if st.button(f"📍 確認觀測：臺灣 {sel_county} {sel_town}", use_container_width=True, type="primary"):
                coords = town_dict[sel_town]
                st.session_state.active_target = {
                    "name": f"📍 臺灣 {sel_county} {sel_town}",
                    "lat": float(coords[0]),
                    "lon": float(coords[1])
                }
                st.rerun()
    else:
        continents = list(world_hierarchy.keys())
        default_cont_idx = continents.index("亞洲 (Asia)") if "亞洲 (Asia)" in continents else 0
        sel_cont = st.selectbox("1. 篩選大洲", options=continents, index=default_cont_idx, key="diag_world_cont")

        countries_dict = world_hierarchy.get(sel_cont, {})
        country_list = sorted(list(countries_dict.keys()))
        sel_country = st.selectbox("2. 挑選國家", options=country_list, index=0 if country_list else None, key="diag_world_country")

        cities_dict = countries_dict.get(sel_country, {}) if sel_country else {}
        city_list = list(cities_dict.keys())
        sel_city = st.selectbox("3. 挑選城市", options=city_list, index=0 if city_list else None, key="diag_world_city")

        if sel_city and sel_country:
            clean_c = sel_country.split('/')[0].strip()
            clean_t = sel_city.split('(')[0].strip()
            st.write("")
            if st.button(f"📍 確認觀測：{clean_c} {clean_t}", use_container_width=True, type="primary"):
                coords = cities_dict[sel_city]
                st.session_state.active_target = {
                    "name": f"📍 {clean_c} {clean_t}",
                    "lat": float(coords[0]),
                    "lon": float(coords[1])
                }
                st.rerun()

if dialog_decorator:
    @dialog_decorator("🧭 選擇觀測地區")
    def open_location_dialog():
        render_location_dialog_content()
else:
    def open_location_dialog():
        render_location_dialog_content()

# -------------------------------------------------------------
# 10. 側邊欄地點選單配置
# -------------------------------------------------------------
is_at_home = (
    abs(st.session_state.active_target["lat"] - st.session_state.my_home_location["lat"]) < 0.001 and 
    abs(st.session_state.active_target["lon"] - st.session_state.my_home_location["lon"]) < 0.001
)

active_name = st.session_state.active_target["name"]
active_lat = float(st.session_state.active_target["lat"])
active_lon = float(st.session_state.active_target["lon"])

display_location_text = (
    active_name.replace("📍 ", "")
    .replace("目前所在地:", "")
    .replace("臺灣 ", "")
)

with st.sidebar:
    st.markdown("### 🧭 觀測地區選單")
    st.caption(f"目前觀測視角：**{display_location_text}**")
    st.markdown("---")

    btn_type_home = "primary" if is_at_home else "secondary"
    if st.button("📍 目前設備位置", use_container_width=True, type=btn_type_home, key="sidebar_btn_home"):
        st.session_state.active_target = {
            "name": f"📍 目前所在地:{st.session_state.my_home_location['name']}",
            "lat": float(st.session_state.my_home_location["lat"]),
            "lon": float(st.session_state.my_home_location["lon"])
        }
        st.rerun()

    st.write("")
    
    btn_type_other = "secondary" if is_at_home else "primary"
    if st.button("🌍 挑選其他地區", use_container_width=True, type=btn_type_other, key="sidebar_btn_other"):
        open_location_dialog()

    st.markdown("---")
    st.markdown("##### ⚡ 側邊欄快速選取")

    with st.expander("🇹🇼 臺灣鄉鎮直接切換", expanded=False):
        county_list = list(taiwan_data.keys())
        if county_list:
            def_c = county_list.index("臺中市") if "臺中市" in county_list else 0
            sb_c = st.selectbox("縣市", county_list, index=def_c, key="sb_tw_c")
            t_dict = taiwan_data.get(sb_c, {})
            t_list = list(t_dict.keys())
            def_t = t_list.index("東勢區") if "東勢區" in t_list else 0
            sb_t = st.selectbox("鄉鎮市區", t_list, index=def_t, key="sb_tw_t")
            if st.button(f"切換至 {sb_c} {sb_t}", use_container_width=True, type="primary", key="sb_confirm_tw"):
                coords = t_dict[sb_t]
                st.session_state.active_target = {
                    "name": f"📍 臺灣 {sb_c} {sb_t}",
                    "lat": float(coords[0]),
                    "lon": float(coords[1])
                }
                st.rerun()

    with st.expander("🌍 全球城市直接切換", expanded=False):
        cont_list = list(world_hierarchy.keys())
        def_cont = cont_list.index("亞洲 (Asia)") if "亞洲 (Asia)" in continents if 'continents' in locals() else 0
        sb_cont = st.selectbox("大洲", cont_list, index=0, key="sb_world_cont")
        c_dict = world_hierarchy.get(sb_cont, {})
        c_list = sorted(list(c_dict.keys()))
        sb_country = st.selectbox("國家", c_list, index=0 if c_list else None, key="sb_world_country")
        city_dict = c_dict.get(sb_country, {}) if sb_country else {}
        city_list = list(city_dict.keys())
        sb_city = st.selectbox("城市", city_list, index=0 if city_list else None, key="sb_world_city")
        if sb_city and sb_country:
            clean_c = sb_country.split('/')[0].strip()
            clean_t = sb_city.split('(')[0].strip()
            if st.button(f"切換至 {clean_t}", use_container_width=True, type="primary", key="sb_confirm_world"):
                coords = city_dict[sb_city]
                st.session_state.active_target = {
                    "name": f"📍 {clean_c} {clean_t}",
                    "lat": float(coords[0]),
                    "lon": float(coords[1])
                }
                st.rerun()

# -------------------------------------------------------------
# 11. 頂部雙重呼叫欄 (有標題 + 直覺呼叫地點按鈕)
# -------------------------------------------------------------
c_head_title, c_head_btn = st.columns([3.5, 1.2])
with c_head_title:
    st.markdown('<div class="app-brand-title">🌤️ SkyCast 全球天氣生活管家</div>', unsafe_allow_html=True)
with c_head_btn:
    # 雙重防呆：點擊此處也能直接彈出地點選單，免去找側邊欄箭頭的困擾！
    if st.button("🧭 切換地區", use_container_width=True, key="main_open_location"):
        open_location_dialog()

# -------------------------------------------------------------
# 12. 天氣資料獲取與運算 (12 小時預報)
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

limit_h = min(12, len(raw_times), len(raw_temps), len(raw_rains), len(raw_codes))
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

hero_card_style = get_weather_hero_style(cur_code, cur_temp)

intro, w_head, w_desc, d_head, d_desc, sport_tip, commute_tip, pack_items, uv_status_str = get_comprehensive_assistant_advice(
    cur_temp, cur_feels, cur_rain, cur_hum, cur_wind, aqi_val, cur_uv
)

# -------------------------------------------------------------
# 13. 【核心焦點】自適應高質感動態深藍氣象大卡片
# -------------------------------------------------------------
st.markdown(
    f"""
    <div class="weather-hero-card" style="{hero_card_style}">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
            <div style="font-size: 17.5px; font-weight: 700; opacity: 0.95; display: flex; align-items: center; gap: 4px;">
                📍 {display_location_text}
            </div>
            <div style="font-size: 12.5px; opacity: 0.9; background: rgba(0,0,0,0.22); padding: 2px 8px; border-radius: 6px;">
                {condition}
            </div>
        </div>
        <div style="display: flex; justify-content: space-between; align-items: flex-start;">
            <div>
                <div style="font-size: 38px; font-weight: 800; line-height: 1.15; letter-spacing: -0.5px;">
                    {icon} {cur_temp:.1f}°C
                </div>
                <div style="font-size: 14.5px; opacity: 0.95; margin-top: 4px; font-weight: 500;">
                    體感約 {cur_feels:.1f}°C
                </div>
            </div>
            <div style="text-align: right; font-size: 13.5px; opacity: 0.95; line-height: 1.65;">
                <div>💨 風速 <strong>{cur_wind} km/h</strong></div>
                <div>💧 濕度 <strong>{cur_hum}%</strong></div>
            </div>
        </div>
        <div class="hero-metrics-grid">
            <div class="hero-metric-pill">
                <span>💧 降雨機率</span>
                <strong>{cur_rain}%</strong>
            </div>
            <div class="hero-metric-pill">
                <span>☀️ 紫外線</span>
                <strong>{cur_uv:.1f} ({uv_status_str})</strong>
            </div>
            <div class="hero-metric-pill">
                <span>🍃 空氣 AQI</span>
                <strong>{aqi_val}</strong>
            </div>
            <div class="hero-metric-pill">
                <span>🌫️ PM2.5</span>
                <strong>{pm25_val:.1f}</strong>
            </div>
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

# -------------------------------------------------------------
# 14. 【生活小幫手】(預設收折，整齊俐落)
# -------------------------------------------------------------
st.markdown("##### 💡 生活小幫手")
st.markdown(f'<div class="compact-tip-box">✨ <strong>出門指引：</strong>{intro}</div>', unsafe_allow_html=True)

with st.expander(f"👕 **穿著建議**：{w_head}", expanded=False):
    st.markdown(w_desc)

with st.expander(f"🧺 **曬衣指引**：{d_head}", expanded=False):
    st.markdown(d_desc)

with st.expander(f"🏃 **運動與出行指引**", expanded=False):
    st.markdown(f"**🏃 戶外活動與運動**\n\n{sport_tip}")
    st.markdown(f"**🛵 通勤出行建議**\n\n{commute_tip}")

with st.expander(f"🎒 **隨身行囊建議**", expanded=False):
    st.markdown(" · ".join(pack_items))

st.markdown("---")

# -------------------------------------------------------------
# 15. 未來 12 小時即時預報 (標題簡潔)
# -------------------------------------------------------------
st.markdown("##### ⏱️ 未來 12 小時即時預報")

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

    col_chart, col_ai = st.columns([1.1, 1.0], gap="medium")

    with col_chart:
        chart_data = pd.DataFrame({
            "時間": times,
            "氣溫 (°C)": temps,
            "降雨機率 (%)": rains
        }).set_index("時間")
        st.line_chart(chart_data, height=195)

    with col_ai:
        ai_summary_html = generate_12h_ai_summary(times, temps, rains, codes)
        st.markdown(ai_summary_html, unsafe_allow_html=True)
else:
    st.info("ℹ️ 暫時無法取得每小時即時氣象資料。")

st.markdown("---")

# -------------------------------------------------------------
# 16. 未來一週 (7天) 展望
# -------------------------------------------------------------
st.markdown("##### 📅 未來一週天氣展望")
if limit_d > 0:
    daily_cards = []
    for d_idx in range(limit_d):
        d_date_str = daily_dates[d_idx]
        try:
            d_obj = datetime.strptime(d_date_str, "%Y-%m-%d")
            d_weekday = weekdays_zh[d_obj.weekday()]
            d_title = "今天" if d_idx == 0 else f"{d_obj.month}/{d_obj.day} ({d_weekday})"
        except Exception:
            d_title = f"第 {d_idx+1} 天"

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
# 17. 地圖置底呈現 (動態 Key 確保瞬移置中)
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
    tooltip=f"{active_name} · {cur_temp:.1f}°C",
    icon=folium.Icon(color="blue", icon="cloud")
).add_to(map_instance)

st.markdown('<div class="map-frame-container">', unsafe_allow_html=True)
try:
    st_folium(
        map_instance,
        key=f"map_{active_lat:.4f}_{active_lon:.4f}",
        use_container_width=True,
        height=260,
        returned_objects=[]
    )
except TypeError:
    st_folium(
        map_instance,
        key=f"map_{active_lat:.4f}_{active_lon:.4f}",
        width=None,
        height=260,
        returned_objects=[]
    )
st.markdown('</div>', unsafe_allow_html=True)

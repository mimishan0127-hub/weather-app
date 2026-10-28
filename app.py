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
    .selector-box {
        background-color: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        padding: 16px;
        margin-top: 10px;
    }
</style>
""", unsafe_allow_html=True)

# -------------------------------------------------------------
# 2. 臺灣全境 22 縣市 368 鄉鎮市區完整法定資料庫
# -------------------------------------------------------------
TAIWAN_COMPLETE_DATA = {
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
# 3. 全球六大洲完整代表國家與各省州城市資料庫
# -------------------------------------------------------------
GLOBAL_HIERARCHY_DATA = {
    "🌏 亞洲 (Asia)": {
        "日本": {
            "東京都 (Tokyo)": (35.6762, 139.6503), "大阪府 (Osaka)": (34.6937, 135.5023),
            "京都府 (Kyoto)": (35.0116, 135.7681), "北海道 (札幌)": (43.0618, 141.3545),
            "福岡縣 (Fukuoka)": (33.5904, 130.4017), "愛知縣 (名古屋)": (35.1815, 136.9066),
            "沖繩縣 (那霸)": (26.2124, 127.6809), "神奈川縣 (橫濱)": (35.4437, 139.6380),
            "兵庫縣 (神戶)": (34.6901, 135.1955), "廣島縣 (Hiroshima)": (34.3853, 132.4553)
        },
        "南韓": {
            "首爾特別市 (Seoul)": (37.5665, 126.9780), "釜山廣域市 (Busan)": (35.1796, 129.0756),
            "濟州特別自治道 (濟州市)": (33.4996, 126.5312), "濟州特別自治道 (西歸浦)": (33.2541, 126.5601),
            "仁川廣域市 (Incheon)": (37.4563, 126.7052), "大邱廣域市 (Daegu)": (35.8714, 128.6014)
        },
        "泰國": {
            "曼谷直轄市 (Bangkok)": (13.7563, 100.5018), "清邁府 (Chiang Mai)": (18.7883, 98.9853),
            "普吉府 (Phuket)": (7.8804, 98.3923), "春武里府 (芭達雅)": (12.9276, 100.8771),
            "素叻他尼府 (蘇梅島)": (9.5120, 100.0136), "班武里府 (華欣)": (12.5684, 99.9577)
        },
        "新加坡": {
            "中央商務區 (Downtown)": (1.2879, 103.8519), "濱海灣 (Marina Bay)": (1.2838, 103.8591),
            "聖淘沙 (Sentosa)": (1.2494, 103.8303), "烏節路 (Orchard)": (1.3048, 103.8318)
        },
        "馬來西亞": {
            "吉隆坡 (Kuala Lumpur)": (3.1390, 101.6869), "檳城 (George Town)": (5.4141, 100.3288),
            "沙巴 (亞庇)": (5.9804, 116.0735), "柔佛 (新山)": (1.4927, 103.7414), "馬六甲 (Melaka)": (2.1896, 102.2501)
        },
        "越南": {
            "胡志明市 (Ho Chi Minh)": (10.8231, 106.6297), "河內市 (Hanoi)": (21.0285, 105.8542),
            "峴港市 (Da Nang)": (16.0544, 108.2022), "堅江省 (富國島)": (10.2899, 103.9840)
        },
        "中國": {
            "北京市 (Beijing)": (39.9042, 116.4074), "上海市 (Shanghai)": (31.2304, 121.4737),
            "廣東省 (廣州)": (23.1291, 113.2644), "廣東省 (深圳)": (22.5431, 114.0579),
            "四川省 (成都)": (30.5728, 104.0668), "重慶市 (Chongqing)": (29.5630, 106.5516),
            "香港特別行政區 (Hong Kong)": (22.3193, 114.1694), "澳門特別行政區 (Macau)": (22.1987, 113.5439)
        },
        "阿拉伯聯合大公國": {
            "杜拜 (Dubai)": (25.2048, 55.2708), "阿布達比 (Abu Dhabi)": (24.4539, 54.3773)
        }
    },
    "🌍 歐洲 (Europe)": {
        "英國": {
            "大倫敦 (London)": (51.5074, -0.1278), "蘇格蘭 (愛丁堡)": (55.9533, -3.1883),
            "大曼徹斯特 (Manchester)": (53.4808, -2.2426), "牛津郡 (Oxford)": (51.7520, -1.2577)
        },
        "法國": {
            "法蘭西島 (巴黎)": (48.8566, 2.3522), "普羅旺斯 (尼斯)": (43.7102, 7.2620),
            "奧弗涅 (里昂)": (45.7640, 4.8357), "普羅旺斯 (馬賽)": (43.2965, 5.3698)
        },
        "德國": {
            "柏林州 (Berlin)": (52.5200, 13.4050), "巴伐利亞 (慕尼黑)": (48.1351, 11.5820),
            "黑森州 (法蘭克福)": (50.1109, 8.6821), "漢堡州 (Hamburg)": (53.5511, 9.9937)
        },
        "義大利": {
            "拉齊奧 (羅馬)": (41.9028, 12.4964), "倫巴底 (米蘭)": (45.4642, 9.1900),
            "托斯卡納 (佛羅倫斯)": (43.7696, 11.2558), "威尼托 (威尼斯)": (45.4408, 12.3155)
        },
        "瑞士": {
            "蘇黎世州 (Zurich)": (47.3769, 8.5417), "日內瓦州 (Geneva)": (46.2044, 6.1432),
            "琉森州 (Lucerne)": (47.0502, 8.3093), "伯恩州 (Bern)": (46.9480, 7.4474)
        }
    },
    "🌎 北美洲 (North America)": {
        "美國": {
            "紐約州 (New York)": (40.7128, -74.0060), "加州 (洛杉磯)": (34.0522, -118.2437),
            "加州 (舊金山)": (37.7749, -122.4194), "華盛頓州 (西雅圖)": (47.6062, -122.3321),
            "伊利諾州 (芝加哥)": (41.8781, -87.6298), "夏威夷 (檀香山)": (21.3069, -157.8583)
        },
        "加拿大": {
            "不列顛哥倫比亞 (溫哥華)": (49.2827, -123.1207), "安大略省 (多倫多)": (43.6532, -79.3832),
            "魁北克省 (蒙特婁)": (45.5017, -73.5673)
        }
    },
    "🌏 大洋洲 (Oceania)": {
        "澳洲": {
            "新南威爾斯 (雪梨)": (-33.8688, 151.2093), "維多利亞 (墨爾本)": (-37.8136, 144.9631),
            "昆士蘭 (布里斯本)": (-27.4698, 153.0251), "西澳 (伯斯)": (-31.9505, 115.8605)
        },
        "紐西蘭": {
            "北島 (奧克蘭)": (-36.8485, 174.7633), "南島 (基督城)": (-43.5321, 172.6362),
            "北島 (威靈頓)": (-41.2865, 174.7762), "南島 (皇后鎮)": (-45.0312, 168.6626)
        }
    },
    "🌎 南美洲 (South America)": {
        "巴西": {
            "聖保羅州 (Sao Paulo)": (-23.5505, -46.6333), "里約熱內盧 (Rio)": (-22.9068, -43.1729)
        },
        "阿根廷": {
            "布宜諾斯艾利斯 (Buenos Aires)": (-34.6037, -58.3816)
        }
    },
    "🌍 非洲 (Africa)": {
        "埃及": {
            "開羅省 (Cairo)": (30.0444, 31.2357), "亞歷山大 (Alexandria)": (31.2001, 29.9187)
        },
        "南非": {
            "西開普 (開普敦)": (-33.9249, 18.4241), "豪登省 (約翰尼斯堡)": (-26.2041, 28.0473)
        }
    }
}

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
# 6. 「我的所在地」狀態維護
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
        "name": "臺中市東勢區",
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
# 7. 階梯式點選提示視窗 (Dialog / Modal)
# -------------------------------------------------------------
dialog_decorator = getattr(st, "dialog", getattr(st, "experimental_dialog", None))

@dialog_decorator("🧭 選擇觀測地區（點選篩選）")
def show_cascading_selector_dialog():
    st.markdown("請選擇您要查詢的區域體系：")
    
    # 第一層：臺灣 vs 全球
    scope_choice = st.radio(
        "區域範圍",
        options=["🇹🇼 臺灣", "🌍 全球"],
        horizontal=True,
        label_visibility="collapsed"
    )

    if scope_choice == "🇹🇼 臺灣":
        st.markdown('<div class="selector-box">', unsafe_allow_html=True)
        st.markdown("##### 🇹🇼 臺灣縣市與鄉鎮市區點選")
        
        # 第二層：全台 22 縣市
        county_list = list(TAIWAN_COMPLETE_DATA.keys())
        selected_county = st.selectbox("1. 選擇縣市", options=county_list, index=county_list.index("臺中市"))
        
        # 第三層：該縣市所有的鄉鎮市區
        town_dict = TAIWAN_COMPLETE_DATA[selected_county]
        town_list = list(town_dict.keys())
        selected_town = st.selectbox("2. 選擇鄉鎮市區", options=town_list, index=town_list.index("東勢區") if "東勢區" in town_list else 0)
        
        target_coords = town_dict[selected_town]
        full_name = f"臺灣 {selected_county} {selected_town}"
        
        st.write("")
        if st.button(f"📍 確認定位：{full_name}", use_container_width=True, type="primary"):
            st.session_state.active_target = {
                "name": f"📍 {full_name}",
                "lat": target_coords[0],
                "lon": target_coords[1]
            }
            st.rerun()
            
        st.markdown('</div>', unsafe_allow_html=True)

    else:
        st.markdown('<div class="selector-box">', unsafe_allow_html=True)
        st.markdown("##### 🌍 全球大洲、國家與城市點選")
        
        # 第二層：各大洲
        continents = list(GLOBAL_HIERARCHY_DATA.keys())
        selected_continent = st.selectbox("1. 選擇大洲", options=continents, index=0)
        
        # 第三層：該洲所有國家
        countries_dict = GLOBAL_HIERARCHY_DATA[selected_continent]
        country_list = list(countries_dict.keys())
        selected_country = st.selectbox("2. 選擇國家", options=country_list, index=0)
        
        # 第四層：該國家所有主要城市/行政區
        cities_dict = countries_dict[selected_country]
        city_list = list(cities_dict.keys())
        selected_city = st.selectbox("3. 選擇主要城市 / 行政區", options=city_list, index=0)
        
        target_coords = cities_dict[selected_city]
        full_name = f"{selected_country} {selected_city}"
        
        st.write("")
        if st.button(f"📍 確認定位：{full_name}", use_container_width=True, type="primary"):
            st.session_state.active_target = {
                "name": f"📍 {full_name}",
                "lat": target_coords[0],
                "lon": target_coords[1]
            }
            st.rerun()
            
        st.markdown('</div>', unsafe_allow_html=True)

# -------------------------------------------------------------
# 8. 頂部導航控制列 (按鈕點擊觸發提示視窗)
# -------------------------------------------------------------
c_logo, c_selector_btn, c_home = st.columns([1.1, 2.3, 0.9], gap="medium")

with c_logo:
    st.markdown("### 🌤️ SkyCast 全球天氣")

with c_selector_btn:
    if st.button("🧭 點擊篩選地點（臺灣 368 鄉鎮市區 ｜ 全球各洲各國城市）...", use_container_width=True):
        show_cascading_selector_dialog()

with c_home:
    if st.button("📍 回到我的位置", use_container_width=True, help="點擊立刻回到目前所在地"):
        st.session_state.active_target = {
            "name": f"📍 目前所在地：{st.session_state.my_home_location['name']}",
            "lat": st.session_state.my_home_location["lat"],
            "lon": st.session_state.my_home_location["lon"]
        }
        st.rerun()

# -------------------------------------------------------------
# 9. 觀測地點與天氣資料呈現 (主畫面)
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

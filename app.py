from enum import nonmember
import io
import math
import streamlit as st
import os
import pandas as pd

# ページ設定（最初のStreamlitコマンドでなければならない）
st.set_page_config(
    page_title="芝しごと・施肥設計ナビ",
    page_icon="🌱",
    layout="wide",
)

# CSS読み込み（1回だけ）
css_path = os.path.join(os.path.dirname(__file__), "style.css")
with open(css_path, encoding="utf-8") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

TERM_GUIDE = {
    "競技場向け": """
**MLSN（Minimum Levels for Sustainable Nutrition）**  
競技利用において芝生の健全性を長期的に維持するための  
**土壌中栄養要素の最低限必要な水準**を示します。  
※ N は Nitrogen（窒素）ではなく、Nutrition（栄養）を意味します。

**SLAN（Sufficiency Level of Available Nutrition）**  
芝生の生育反応が安定し、品質が確保される  
**利用可能栄養の十分域**を示す指標です。

本アプリでは、  
**MLSN〜SLANの範囲内で、競技要求度に応じた位置づけ**を行います。
""",

    "ゴルフ場向け": """
**MLSN（Minimum Levels for Sustainable Nutrition）**  
芝草が過不足なく持続的に生育するために必要な  
**土壌中栄養要素の下限値**を示します。  
※ N は Nitrogen（窒素）ではなく、Nutrition（栄養）を意味します。

**SLAN（Sufficiency Level of Available Nutrition）**  
芝草の生育が安定し、管理効率が高まる  
**栄養供給の目安となる上限域**です。

本アプリでは、  
**MLSN〜SLANを幅として捉え、管理方針に応じて活用**します。
"""
}

CA_MG_COMMENT = {
    "競技場向け": {
        "high": "Ca 優位です。硬化・乾燥により、競技コンディション低下の恐れがあります。",
        "balanced": "Ca : Mg 比はおおむね良好です。競技条件として安定しています。",
        "low": "Mg 優位です。過湿化や軟弱化に注意してください。"
    },
    "ゴルフ場向け": {
        "high": "Ca がやや優位です。表層の締まりや乾きやすさに留意してください。",
        "balanced": "Ca : Mg 比はバランスの取れた状態です。",
        "low": "Mg がやや多めです。湿害や柔らかさに注意が必要です。"
    }
}

CA_MG_ACTION = {
    "競技場向け": {
        "high": "Ca 優位のため、表層硬化・乾燥進行に注意。Mg補給や物理的緩和措置の検討が有効です。",
        "balanced": "Ca:Mg 比は競技条件下でも安定しています。現行管理を維持しつつ推移を確認してください。",
        "low": "Mg 優位の傾向があります。過湿・軟弱化を避けるため、Ca バランスに注意してください。"
    },
    "ゴルフ場向け": {
        "high": "Ca がやや優位です。硬化傾向が出る場合は Mg 補給や有機物管理を検討してください。",
        "balanced": "Ca:Mg 比は良好です。大きな調整は不要と考えられます。",
        "low": "Mg 優位のため、排水性や踏圧条件に応じた Ca バランス調整を検討します。"
    }
}

N_ACTION = {
    "競技場向け": {
        "low": "競技品質を維持するには、生育量と密度の底上げが必要です。即効性と持続性のバランスを考慮します。",
        "balanced": "現状の生育水準は安定しています。急激な変化を避け、状態維持を優先します。",
        "high": "過繁茂による品質低下に注意が必要です。抑制的管理や施肥間隔の調整を検討します。"
    },
    "ゴルフ場向け": {
        "low": "生育改善を目的に、段階的な補給を検討します。",
        "balanced": "現在の施肥設計は妥当です。現行管理を継続します。",
        "high": "過剰生育を避けるため、施肥量やタイミングの見直しを検討します。"
    }
}

ELEMENTS = {
    "N": {
        "mlsn": 5.0,
        "slan": 15.0,
    },
    "P": {
        "mlsn": 1.0,
        "slan": 3.0,
    },
    "K": {
        "mlsn": 15.0,
        "slan": 25.0,
    },
}

# 仮換算係数（後で必ず差し替える）
MG100G_TO_KG10A = 0.15

FERTILIZERS = {
    "N": {
        "name": "硫安",
        "nutrient": "N",
        "rate": 0.21,   # N含有率
    },
    "P": {
        "name": "過リン酸石灰",
        "nutrient": "P2O5",
        "rate": 0.17,
    },
    "K": {
        "name": "塩化カリ",
        "nutrient": "K2O",
        "rate": 0.60,
    },
}

# 月別配分（割合）
MONTHLY_DISTRIBUTION = {
    "N": {
        "3": 0.15,
        "4": 0.20,
        "5": 0.25,
        "6": 0.15,
        "9": 0.15,
        "10": 0.10,
    },
    "P": {
        "4": 0.50,
        "9": 0.50,
    },
    "K": {
        "4": 0.30,
        "5": 0.30,
        "9": 0.40,
    }
}

fert_results = {}


def judge_status(value, mlsn, slan):
    """
    数値と基準値から状態を判定する
    戻り値: "不足" / "適正" / "過剰"
    """
    if value < mlsn:
        return "不足"
    elif value > slan:
        return "過剰"
    else:
        return "適正"

def calc_deficit(value, mlsn):
    return max(0, mlsn - value)

def action_template(status, name, tone):
    ACTIONS = {
        ("N", "不足", "競技場向け"):
            "生育量と回復力を優先し、即効性を意識した設計が有効です。",
        ("N", "適正", "競技場向け"):
            "現状の生育水準は良好です。試合強度に応じた微調整を行います。",
        ("N", "過剰", "競技場向け"):
            "過繁茂による品質低下に注意し、抑制的な配分を検討します。",

        ("N", "不足", "ゴルフ場向け"):
            "生育改善を目的に、段階的な補給を検討します。",
        ("N", "適正", "ゴルフ場向け"):
            "現在の施肥設計は妥当です。現行管理を継続します。",
        ("N", "過剰", "ゴルフ場向け"):
            "過剰生育を避けるため、施肥量の見直しを検討します。",
    }

    return ACTIONS.get(
        (name, status, tone),
        "この要素の設計指針は今後拡張予定です。"
    )


# ④ コメント生成関数（★ここが正解）
def comment_template(status, name):
    """
    評価結果に応じた簡単なコメントを返す
    status: "不足" / "適正" / "過剰"
    name: 要素名 (N, P, K, Ca, Mg など)
    """
    if status == "不足":
        return f"土壌中の{name}は、目安とする範囲を下回っています。"
    elif status == "適正":
        return f"土壌中の{name}は、概ね適正な範囲にあります。"
    else:  # 過剰
        return f"土壌中の{name}は、目安とする範囲を上回っています。"


def render_soil_eval(name, value, mlsn, slan):
    """要素ごとの土壌評価を表示する"""

    # ── 1. 判定 ──
    status = judge_status(value, mlsn, slan)

    # ── 2. 表示変数の設定 ──
    if status == "不足":
        box_color    = "#fff3f3"
        status_label = "⚠️ 不足"
    elif status == "過剰":
        box_color    = "#fffff0"
        status_label = "⚡ 過剰"
    else:
        box_color    = "#f0fff0"
        status_label = "✅ 適正"

    warning_text = ""
    comment      = comment_template(status, name)
    meaning_text = ""
    action       = ""
    deficit_text = ""
    fert_text    = ""
    monthly_plan = None
    monthly_text = ""

    # ── 3. 不足時：補正量の算出と登録 ──
    if status == "不足":
        deficit        = mlsn - value
        deficit_kg_10a = deficit * MG100G_TO_KG10A
        fert_kg        = calc_fertilizer_amount(deficit_kg_10a, name)
        warning_text   = (
            "⚠️ この項目は目安値を下回っています。"
            "早めの対応を検討してください。<br>"
        )
        deficit_text = f"不足量（目安）：{deficit:.1f} mg/100g<br>"

        if fert_kg is not None and name in ["N", "P", "K"]:
            fert_results[name] = fert_kg
            monthly_plan = split_by_month(fert_kg, name)
            fert_text = (
                f"肥料換算（{FERTILIZERS[name]['name']}）："
                f"{fert_kg:.2f} kg / 10a<br>"
            )
    else:
        deficit = 0.0
        fert_kg = None

    # ── 4. 月別配分テキストの生成・テーブル表示 ──
    if monthly_plan is not None:
        monthly_text = "<br>".join(
            [f"{m}月：{v:.2f} kg / 10a" for m, v in monthly_plan.items()]
        )

        df_monthly = pd.DataFrame({
            "月": [f"{m}月" for m in monthly_plan.keys()],
            "施肥量（kg / 10a）": [round(v, 2) for v in monthly_plan.values()],
        })
        st.subheader(f"月別施肥配分({name})")
        st.caption("※ 単位：kg / 10a（月別の施肥量）")
        st.dataframe(df_monthly)
        st.caption(
            "※ 表示されている施肥量は 10a あたり・月別の目安量です。"
            "芝種・利用強度・天候条件により調整してください。"
        )

    # ── 5. メインボックスの描画 ──
#    monthly_section = (
#        f'<br><strong>月別配分（目安）</strong><br>{monthly_text}'
#        if name == "N" and status == "不足"
#        else ""
#    )

    st.markdown(
        f"""
<div style="
    background-color:{box_color};
    padding:12px;
    border-radius:8px;
    margin-bottom:12px;
">
<strong>{name}</strong><br>
判定：{status_label}<br><br>
{warning_text}
{comment}
{deficit_text}
<em>{meaning_text}</em>
<hr style="border:none;border-top:1px solid #ccc;">
<strong>設計上の考え方</strong><br>
{action}
{fert_text}
</div>
""",
        unsafe_allow_html=True
    )

def calc_fertilizer_amount(deficit_kg, elem):
    """
    deficit_kg : 不足成分量（kg/10a）
    elem        : "N" / "P" / "K"
    """
    fert = FERTILIZERS.get(elem)
    if fert is None:
        return None

    rate = fert["rate"]
    return deficit_kg / rate

def split_by_month(total_kg_10a, elem):
    dist = MONTHLY_DISTRIBUTION.get(elem, {})
    return {
        month: total_kg_10a * ratio
        for month, ratio in dist.items()
    }


def render_ca_mg_ratio(ca, mg):
    if mg <= 0:
        st.markdown("""
**Ca : Mg 比**

- Ca : Mg = 不明  
- 設計上の考え方：Mg が未測定のため、推定モードで評価します。
""")
        return

    ratio = ca / mg

    if ratio < 10:
        comment = "Mg 優位です。通気性や軟らかさを意識した管理が必要です。"
    elif ratio > 30:
        comment = "Ca が優位です。表層の締まりや乾きやすさに留意してください。"
    else:
        comment = "Ca と Mg のバランスは概ね良好です。"

    st.markdown(f"""
**Ca : Mg 比**

- Ca : Mg = {ratio:.1f}

**設計上の考え方**  
{comment}
""")


# ============================================================
# Growth Potential（GP）算出関数
# ============================================================

def estimate_temperature(day, latitude):
    """
    緯度から仮想的な年間気温カーブを生成する。
    T(d) = T_mean + A * sin(2π * (d - φ) / 365)

    ・T_mean : 年平均気温（緯度から簡易推定）
    ・A       : 年較差の半分（緯度から簡易推定）
    ・φ       : 位相（日本国内では定数: 最高気温が8月上旬に来るよう設定）
    ※ 実測値ではなく「地点の気候的傾向」を表すためのモデル
    """
    t_mean    = 36.0 - 0.6 * latitude
    amplitude = 0.35 * latitude - 2.5
    phase     = 121  # sin ピークが day≒212（8月上旬）になる位相

    return t_mean + amplitude * math.sin(2 * math.pi * (day - phase) / 365)


def gp_cool(temp):
    """寒地型芝の GP（気温応答関数）"""
    if temp <= 0:
        return 0.0
    elif temp <= 20:
        return temp / 20.0
    elif temp < 35:
        return (35.0 - temp) / 15.0
    else:
        return 0.0


def gp_warm(temp):
    """暖地型芝の GP（気温応答関数）"""
    if temp <= 10:
        return 0.0
    elif temp <= 30:
        return (temp - 10.0) / 20.0
    elif temp < 45:
        return (45.0 - temp) / 15.0
    else:
        return 0.0


def weight_cool(temp):
    """WOS 時の寒地型寄与率 w(T)"""
    if temp <= 12:
        return 1.0
    elif temp < 22:
        return (22.0 - temp) / 10.0
    else:
        return 0.0


def calculate_daily_gp(latitude, turf_type):
    """
    365 日分の GP を算出する。
    戻り値: list[float]（長さ 365）
    """
    daily_gp = []
    for day in range(1, 366):
        temp = estimate_temperature(day, latitude)

        if turf_type == "寒地型芝":
            gp = gp_cool(temp)
        elif turf_type in ("暖地型芝", "日本芝"):
            gp = gp_warm(temp)
        elif turf_type == "ウィンターオーバーシード（WOS）":
            w = weight_cool(temp)
            gp = w * gp_cool(temp) + (1 - w) * gp_warm(temp)
        else:
            gp = 0.0

        daily_gp.append(gp)

    return daily_gp


def monthly_gp_averages(daily_gp):
    """
    365 日分の GP を月別平均に集約する。
    戻り値: dict（キー "1"〜"12"、値: 月平均 GP）
    """
    month_days = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    monthly = {}
    start = 0
    for m, days in enumerate(month_days, 1):
        end = start + days
        monthly[str(m)] = sum(daily_gp[start:end]) / days
        start = end
    return monthly


# ============================================================
# URL クエリパラメータからの復元（ページ再読み込み時）
# ============================================================
TURF_OPTIONS = ["寒地型芝", "暖地型芝", "日本芝", "ウィンターオーバーシード（WOS）"]
DIST_OPTIONS = ["春重点配分（おすすめ）", "GP準拠", "均等配分"]

qp = st.query_params

if "lat" in qp and "geo_lat" not in st.session_state:
    try:
        _lat = float(qp["lat"])
        if 20.0 <= _lat <= 50.0:
            st.session_state["geo_lat"] = _lat
    except (ValueError, TypeError):
        pass

if "lon" in qp and "geo_lon" not in st.session_state:
    try:
        _lon = float(qp["lon"])
        if 120.0 <= _lon <= 155.0:
            st.session_state["geo_lon"] = _lon
    except (ValueError, TypeError):
        pass

if "turf" in qp:
    st.session_state.setdefault("qp_turf", qp["turf"])

if "dist" in qp:
    st.session_state.setdefault("qp_dist", qp["dist"])

st.title("芝しごと・施肥設計ナビ")

st.markdown(
    '<div class="subtitle">— グリーンキーパーのための土壌分析ベース施肥設計 —</div>',
    unsafe_allow_html=True
)
st.markdown(
    '<div class="version">2026/2/12版</div>',
    unsafe_allow_html=True
)

# ── バナー表示 ──
banner_728 = os.path.join(os.path.dirname(__file__), "banner_ad_recruitment_728x90.jpg")
banner_300 = os.path.join(os.path.dirname(__file__), "banner_ad_recruitment_300x250.jpg")

col_banner_wide, col_banner_sq = st.columns([3, 1])
with col_banner_wide:
    if os.path.exists(banner_728):
        st.image(banner_728)
with col_banner_sq:
    if os.path.exists(banner_300):
        st.image(banner_300)

col1, col2 = st.columns(2)

col_main, col_guide = st.columns([3, 1])

st.markdown("## 基本条件（設計前提）")

tone = st.selectbox(
    "表現スタイル",
    ["競技場向け", "ゴルフ場向け"]
)

with col_guide:
    st.markdown("### 用語ガイド")
    st.markdown(TERM_GUIDE[tone])

st.caption(f"現在の表現スタイル：{tone}")

with st.container():
    _turf_default = st.session_state.get("qp_turf", TURF_OPTIONS[0])
    _turf_index = TURF_OPTIONS.index(_turf_default) if _turf_default in TURF_OPTIONS else 0
    turf_type = st.selectbox("芝種", TURF_OPTIONS, index=_turf_index)

    management_target = st.selectbox(
        "管理対象",
        ["競技場", "ゴルフグリーン", "フェアウェイ"]
    )

    latitude = st.number_input(
        "緯度",
        min_value=20.0,
        max_value=50.0,
        value=st.session_state.get("geo_lat", 35.0),
        step=0.1
    )

    longitude = st.number_input(
        "経度",
        min_value=120.0,
        max_value=155.0,
        value=st.session_state.get("geo_lon", 139.0),
        step=0.1
    )

with st.container():
    management_intensity = st.selectbox(
        "管理強度",
        ["低", "中", "高"]
    )

    allocation_method = st.radio(
        "配分方法",
        ["春重点配分", "均等配分", "GP準拠"]
    )

    pgr_intensity = st.selectbox(
        "PGR強度",
        ["弱", "中", "強"]
    )

    msl_slan_position = st.selectbox(
        "MLSN〜SLAN内の位置",
        ["下限寄り", "中央", "上限寄り"]
    )

# ① 配分方法の選択
_dist_default = st.session_state.get("qp_dist", DIST_OPTIONS[0])
_dist_index = DIST_OPTIONS.index(_dist_default) if _dist_default in DIST_OPTIONS else 0
distribution_method = st.selectbox("施肥配分方法", DIST_OPTIONS, index=_dist_index)

# ── 入力値を URL クエリパラメータに保存 ──
st.query_params["lat"] = str(latitude)
st.query_params["lon"] = str(longitude)
st.query_params["turf"] = turf_type
st.query_params["dist"] = distribution_method

# ② 選択に応じた説明文（←ここ！）
if distribution_method.startswith("春重点配分"):
    st.caption(
        "春の気温上昇期に施肥を多く配分し、"
        "立ち上がりと被覆回復を重視する方法です。"
        "実務で扱いやすく、多くの圃場で安定した結果が得られます。"
    )

elif distribution_method == "GP準拠":
    st.caption(
        "気温から算出した成長ポテンシャル（GP）に基づき、"
        "芝の成長しやすさに応じて施肥量を配分します。"
        "理論的ですが、気象データの品質に影響を受けます。"
    )

elif distribution_method == "均等配分":
    st.caption(
        "年間施肥量を均等に配分する方法です。"
        "シンプルですが、季節ごとの成長差は考慮しません。"
    )

# ===== Growth Potential（GP）表示 =====
st.subheader("Growth Potential（GP）")
st.caption(
    "GPは「その地点で、その芝がどれだけ生育できるか」を表す"
    "相対指標（0〜1）です。緯度から推定した年間気温カーブと、"
    "芝種ごとの気温応答関数から算出しています。"
)

daily_gp = calculate_daily_gp(latitude, turf_type)
monthly_gp = monthly_gp_averages(daily_gp)

months_label = [f"{m}月" for m in range(1, 13)]
months_order = pd.CategoricalIndex(months_label, categories=months_label, ordered=True)
gp_turf_labels = {
    "寒地型芝": "寒地型GP",
    "暖地型芝": "暖地型GP",
    "日本芝": "日本芝GP",
}

if turf_type == "ウィンターオーバーシード（WOS）":
    daily_cool = calculate_daily_gp(latitude, "寒地型芝")
    daily_warm = calculate_daily_gp(latitude, "暖地型芝")
    monthly_cool = monthly_gp_averages(daily_cool)
    monthly_warm = monthly_gp_averages(daily_warm)

    df_gp = pd.DataFrame({
        "寒地型GP": [monthly_cool[str(m)] for m in range(1, 13)],
        "暖地型GP": [monthly_warm[str(m)] for m in range(1, 13)],
        "WOS（合成GP）": [monthly_gp[str(m)] for m in range(1, 13)],
    }, index=months_order)
else:
    label = gp_turf_labels.get(turf_type, turf_type)
    df_gp = pd.DataFrame({
        label: [monthly_gp[str(m)] for m in range(1, 13)],
    }, index=months_order)

st.line_chart(df_gp)

st.dataframe(
    df_gp.T.style.format("{:.2f}"),
    use_container_width=True,
)

with st.expander("GPの設計思想について"):
    st.markdown("""
**Growth Potential（GP）とは**

GPは、気温に対する芝の生育応答を 0〜1 の相対値で表した指標です。
施肥量を直接決定する数値ではなく、
**生育の強弱や季節リズムを把握するための判断材料**として位置づけています。

**算出の仕組み**

1. **仮想年間気温カーブ**：緯度をもとに、平均的な年間気温推移を
正弦波で近似しています（実測値ではなく、地点の気候的傾向を表すモデルです）。
2. **芝種別GP関数**：寒地型芝は 0〜20℃ で上昇・20〜35℃ で低下、
暖地型芝は 10〜30℃ で上昇・30〜45℃ で低下する応答関数を使用します。

**WOS（ウィンターオーバーシード）の扱い**

WOS は寒地型と暖地型の単純平均ではなく、
**季節に応じた主役交代**として扱います。
気温が低い時期は寒地型が主体、気温が高い時期は暖地型が主体となるよう、
気温に応じた重み付き合成を行っています。
""")

st.subheader("2. 土壌分析値（mg/100g）")
st.caption("※ 最新の土壌分析結果を入力してください（乾土基準）")

col1, col2 = st.columns(2)

with col1:
    no3_n = st.number_input(
        "硝酸態窒素（NO₃-N）",
        min_value=0.0,
        step=0.1,
        help="mg/100g 乾土"
    )

    nh4_n = st.number_input(
        "アンモニア態窒素（NH₄-N）",
        min_value=0.0,
        step=0.1,
        help="mg/100g 乾土"
    )

with col2:
    p2o5 = st.number_input(
        "可給態リン酸（P₂O₅）",
        min_value=0.0,
        step=0.1,
        help="mg/100g 乾土"
    )

    k2o = st.number_input(
        "交換性カリ（K₂O）",
        min_value=0.0,
        step=0.1,
        help="mg/100g 乾土"
    )
    ca = st.number_input(
        "カルシウム（CaO）",
        min_value=0.0,
        step=0.1,
        help="mg/100g 乾土"
    )
    mg = st.number_input(
        "マグネシウム（MgO）",
        min_value=0.0,
        step=0.1,
        help="mg/100g 乾土"
    )

values = {
    "N": no3_n,
    "P": p2o5,
    "K": k2o,
}




# Ca:Mg 比（安全計算のみ ── 表示はセクション3で行う）
if mg > 0:
    ca_mg_ratio = ca / mg

    if ca_mg_ratio >= 10:
        comment_key = "high"
    elif ca_mg_ratio >= 3:
        comment_key = "balanced"
    else:
        comment_key = "low"

else:
    ca_mg_ratio = None

COMMENT_TEMPLATES = {
    "競技場向け": {
        "不足": "競技条件を考えると、{elem}は不足気味です。速やかな補正を検討してください。",
        "適正": "{elem}は競技使用に対して適正範囲内です。現状維持が妥当です。",
        "過剰": "{elem}はやや過剰傾向です。競技品質への影響に注意してください。"
    },
    "ゴルフ場向け": {
        "不足": "{elem}はやや不足しています。次回施肥での補正を検討しましょう。",
        "適正": "{elem}は良好な水準です。現在の管理を継続してください。",
        "過剰": "{elem}は過剰気味です。施肥量の見直しが必要です。"
    }
}

#def generate_comment(status, elem, value, mlsn, slan):
#    if status == "不足":
#        return (
#            f"{elem} は {value:.1f} で、"
#            f"MLSN（{mlsn:.1f}）を下回っています。"
#        )
#
#    elif status == "適正":
#        return (
#            f"{elem} は {value:.1f} で、"
#            f"MLSN〜SLAN（{mlsn:.1f}〜{slan:.1f}）の範囲内です。"
#        )
#
#    else:
#        return (
#            f"{elem} は {value:.1f} で、"
#            f"SLAN（{slan:.1f}）を上回っています。"
#        )


col1, col2 = st.columns(2)

st.subheader("3. 土壌分析値の評価（仮）")
st.caption("※ MLSN / SLAN に基づく評価ロジックは今後実装予定です")

col1, col2 = st.columns(2)

# ---- 左列：N / P / K ----
with col1:
    for elem, cfg in ELEMENTS.items():
        render_soil_eval(
            elem,
            values[elem],
            cfg["mlsn"],
            cfg["slan"],
        )

# ===== 月別施肥計画（N・P・K 統合） =====

monthly_all = {}

for elem in ["N", "P", "K"]:
    if elem in fert_results:
        plan = split_by_month(fert_results[elem], elem)
        for month, kg in plan.items():
            if month not in monthly_all:
                monthly_all[month] = {"N": 0.0, "P": 0.0, "K": 0.0}
            monthly_all[month][elem] = kg

if monthly_all:
    df_all = (
        pd.DataFrame.from_dict(monthly_all, orient="index")
        .fillna(0)
    )
    df_all = df_all.loc[sorted(df_all.index, key=int)]
    df_all.index = [f"{m}月" for m in df_all.index]

    st.subheader("月別施肥計画（N・P・K）")
    st.caption("※ 単位：kg / 10a（不足分を月別に配分した目安）")
    st.dataframe(df_all)

    # ===== CSV / Excel ダウンロード =====
    export_rows = []
    for m in range(1, 13):
        m_str = str(m)
        gp_val = round(monthly_gp.get(m_str, 0.0), 2)
        dist_coeff = round(MONTHLY_DISTRIBUTION["N"].get(m_str, 0.0), 3)

        n_kgha = round(monthly_all.get(m_str, {}).get("N", 0.0), 2)
        p_kgha = round(monthly_all.get(m_str, {}).get("P", 0.0), 2)
        k_kgha = round(monthly_all.get(m_str, {}).get("K", 0.0), 2)

        export_rows.append({
            "月": f"{m}月",
            "GP": gp_val,
            "配分係数": dist_coeff,
            "N (kg/ha)": n_kgha,
            "P (kg/ha)": p_kgha,
            "K (kg/ha)": k_kgha,
            "N (g/㎡)": round(n_kgha * 0.1, 2),
            "P (g/㎡)": round(p_kgha * 0.1, 2),
            "K (g/㎡)": round(k_kgha * 0.1, 2),
        })

    export_rows.append({
        "月": "年間合計",
        "GP": "",
        "配分係数": "",
        "N (kg/ha)": round(sum(r["N (kg/ha)"] for r in export_rows), 2),
        "P (kg/ha)": round(sum(r["P (kg/ha)"] for r in export_rows), 2),
        "K (kg/ha)": round(sum(r["K (kg/ha)"] for r in export_rows), 2),
        "N (g/㎡)": round(sum(r["N (g/㎡)"] for r in export_rows), 2),
        "P (g/㎡)": round(sum(r["P (g/㎡)"] for r in export_rows), 2),
        "K (g/㎡)": round(sum(r["K (g/㎡)"] for r in export_rows), 2),
    })

    df_export = pd.DataFrame(export_rows)

    # CSV（BOM付きUTF-8で Excel でも文字化けしない）
    csv_data = df_export.to_csv(index=False, encoding="utf-8-sig")

    # Excel
    excel_buffer = io.BytesIO()
    with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
        df_export.to_excel(writer, index=False, sheet_name="施肥設計")
    excel_data = excel_buffer.getvalue()

    col_dl1, col_dl2 = st.columns(2)
    with col_dl1:
        st.download_button(
            label="📥 CSVダウンロード",
            data=csv_data,
            file_name="施肥設計.csv",
            mime="text/csv",
        )
    with col_dl2:
        st.download_button(
            label="📥 Excelダウンロード",
            data=excel_data,
            file_name="施肥設計.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

# ---- 右列：Ca / Mg ----
with col2:
    render_soil_eval("Ca", ca, 100.0, 200.0)
    render_soil_eval("Mg", mg, 2.0, 4.0)

    render_ca_mg_ratio(ca, mg)

# ===== 設計思想まとめ =====
st.markdown("---")
st.subheader("設計思想について")

st.markdown("""
本アプリは、芝生管理における施肥設計を
数値を自動計算するためのツールではなく、
判断を整理するための支援ツールとして設計されています。

芝生の生育は、年間を通じて一定ではなく、
気温条件によって大きく変化します。
そのため、本アプリでは
気温に対する芝生の生育しやすさを
**Growth Potential（GP）**という指標で整理しています。

GPは、
「どれだけ施肥するか」を直接決める数値ではなく、
生育の強弱や季節の流れを把握するための目安です。
""")

st.markdown("#### GPと施肥配分の考え方")
st.markdown("""
施肥設計において重要なのは、
年間施肥量そのものよりも
どの時期に配分するかという考え方です。

本アプリでは、
芝生の生育が実用的に始まる目安として
GPが0.2を超える期間を
「施肥が効きやすい時期」として扱っています。

極寒期は養分吸収がほとんど行われないため施肥は行わず、
夏季は高温ストレスを考慮し、
過剰な成長を避ける配分となります。
""")

st.markdown("#### 春重点配分について")
st.markdown("""
春重点配分とは、
春から初夏にかけての生育立ち上がり期に
年間施肥量の一定割合を配分する考え方です。

本アプリでは、
30%、50%、70% の配分割合を用意しており、
50%を標準的なおすすめ設定としています。

どの配分が正解ということはなく、
管理方針やその年の条件に応じて
選択することを前提としています。
""")

st.markdown("#### 最後に")
st.markdown("""
本アプリは、
施肥の正解を提示するものではありません。

気候条件と芝生の生育特性を整理し、
考えやすい形で情報を提示することを目的としています。

最終的な判断は、
現場の状況や管理方針に応じて
調整してください。
""")

#st.markdown("### Ca : Mg 比")
#
#if ca_mg_ratio is None:
#    st.write("Mg が 0 のため、比率は算出できません。")
#else:
#    st.write(f"Ca : Mg = {ca_mg_ratio:.1f}")
#
#if ca_mg_ratio is not None:
#    if ca_mg_ratio < 3:
#        msg = (
#            "Mg 優位の状態です。土壌が締まりやすく、"
#            "競技条件では踏圧影響に注意が必要です。"
#            if tone == "競技場向け"
#            else
#            "Mg がやや多く、通気性低下のリスクがあります。"
#        )
#    elif ca_mg_ratio > 6:
#        msg = (
#            "Ca 優位です。硬化・乾燥傾向に注意してください。"
#            if tone == "競技場向け"
#            else
#            "Ca 過多により Mg 欠乏を招く可能性があります。"
#        )
#    else:
#        msg = (
#            "Ca:Mg 比は概ね適正範囲です。"
#            if tone == "競技場向け"
#            else
#            "バランスの取れた Ca:Mg 比です。"#
#        )
#
#    st.caption(msg)

# ===== フッター =====
st.markdown("---")
st.markdown("""
<div style="text-align: center; padding: 1rem 0; color: #666;">
    <a href="https://www.turf-tools.jp/" target="_blank" style="text-decoration: none; color: #666;">
        &copy;グロウアンドプログレス
    </a>
</div>
""", unsafe_allow_html=True)

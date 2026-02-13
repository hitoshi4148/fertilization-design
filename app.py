import io
import math
import base64
import streamlit as st
import os
import pandas as pd
import altair as alt

from logic.monthly_distribution import (
    calculate_monthly_distribution_ratios,
    get_season_factors,
)

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

fert_results = {}

# ── 月順ラベル（暦年 1月〜12月 固定） ──
MONTHS_LABEL = ["1月", "2月", "3月", "4月", "5月", "6月",
                "7月", "8月", "9月", "10月", "11月", "12月"]


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
        deficit        = max(0.0, mlsn - value)
        deficit_kg_10a = max(0.0, deficit * MG100G_TO_KG10A)
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
        # 月順を 1〜12 で明示的に固定
        ordered_months = [str(m) for m in range(1, 13)]
        monthly_text = "<br>".join(
            [f"{m}月：{monthly_plan.get(m, 0.0):.2f} kg / 10a" for m in ordered_months]
        )

        df_monthly = pd.DataFrame({
            "月": MONTHS_LABEL,
            "施肥量（kg / 10a）": [round(monthly_plan.get(str(m), 0.0), 2) for m in range(1, 13)],
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

def split_by_month(total_kg_10a, _elem=None):
    """年間施肥量をGP配分比率で12ヶ月に配分する。
    monthly_dist_ratios はGP計算後に設定されるグローバル変数。
    """
    return {str(m + 1): total_kg_10a * monthly_dist_ratios[m] for m in range(12)}


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
DIST_OPTIONS = ["春重点70", "春重点50", "春重点30", "GP準拠"]
DIST_LABELS = {
    "春重点70": "春重点70%",
    "春重点50": "春重点50%（おすすめ）",
    "春重点30": "春重点30%",
    "GP準拠": "GP準拠",
}

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

# ── バナー表示（mailto リンク付き） ──
_BANNER_MAILTO = "mailto:growthandprogress4148@gmail.com?subject=%E3%83%90%E3%83%8A%E3%83%BC%E5%BA%83%E5%91%8A%E3%81%AB%E3%81%A4%E3%81%84%E3%81%A6"
banner_728 = os.path.join(os.path.dirname(__file__), "banner_ad_recruitment_728x90.jpg")
banner_300 = os.path.join(os.path.dirname(__file__), "banner_ad_recruitment_300x250.jpg")

def _img_to_base64(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()

col_banner_wide, col_banner_sq = st.columns([3, 1])
with col_banner_wide:
    if os.path.exists(banner_728):
        b64 = _img_to_base64(banner_728)
        st.markdown(
            f'<a href="{_BANNER_MAILTO}">'
            f'<img src="data:image/jpeg;base64,{b64}" style="width:100%;" />'
            f'</a>',
            unsafe_allow_html=True,
        )
with col_banner_sq:
    if os.path.exists(banner_300):
        b64 = _img_to_base64(banner_300)
        st.markdown(
            f'<a href="{_BANNER_MAILTO}">'
            f'<img src="data:image/jpeg;base64,{b64}" style="width:100%;" />'
            f'</a>',
            unsafe_allow_html=True,
        )

st.markdown("## 基本条件（設計前提）")

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
    _dist_default = st.session_state.get("qp_dist", "春重点50")
    if _dist_default not in DIST_OPTIONS:
        _dist_default = "春重点50"
    _dist_index = DIST_OPTIONS.index(_dist_default)
    allocation_method = st.radio(
        "🌱 配分方法（GP基準）",
        DIST_OPTIONS,
        index=_dist_index,
        format_func=lambda x: DIST_LABELS.get(x, x),
    )

    _mlsn_options = ["下限寄り", "中央", "上限寄り"]
    _mlsn_labels = {
        "下限寄り": "下限寄り（MLSN重視）",
        "中央": "中央",
        "上限寄り": "上限寄り（SLAN重視）",
    }
    msl_slan_position = st.selectbox(
        "🎯 土壌目標水準の選択",
        _mlsn_options,
        format_func=lambda x: _mlsn_labels.get(x, x),
    )
    st.caption("土壌診断値から不足量を算出する際の目標水準を選択します。")

# ── 入力値を URL クエリパラメータに保存 ──
st.query_params["lat"] = str(latitude)
st.query_params["lon"] = str(longitude)
st.query_params["turf"] = turf_type
st.query_params["dist"] = allocation_method

# 配分方法の説明文
if allocation_method.startswith("春重点"):
    _pct = allocation_method.replace("春重点", "")
    st.caption(
        f"春の気温上昇期に年間施肥量の約{_pct}%を配分し、"
        "立ち上がりと被覆回復を重視する方法です。"
        "GPに基づく季節補正を加えて月別に配分します。"
    )
elif allocation_method == "GP準拠":
    st.caption(
        "気温から算出した成長ポテンシャル（GP）に基づき、"
        "芝の成長しやすさに応じて施肥量を配分します。"
        "理論的ですが、気象データの品質に影響を受けます。"
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

# ── GP値のリスト化・配分比率の計算 ──
gp_values_list = [monthly_gp[str(m)] for m in range(1, 13)]
_gp_sum = sum(gp_values_list)
gp_ratios_list = (
    [v / _gp_sum for v in gp_values_list] if _gp_sum > 0 else [1.0 / 12] * 12
)

# 管理対象 → 利用形態に変換
if "ゴルフ" in management_target or "フェアウェイ" in management_target:
    _usage_type = "ゴルフ場"
else:
    _usage_type = "競技場"

# 季節補正係数を取得（春重点70/50/30 → "春重点" で季節係数をルックアップ）
_base_stance = "春重点" if allocation_method.startswith("春重点") else allocation_method
_season_factors = get_season_factors(
    turf_type, _usage_type, _base_stance,
    use_heavy=True,
)

# 月別配分比率を計算（全要素共通、allocation_method が反映される）
monthly_dist_ratios = calculate_monthly_distribution_ratios(
    gp_ratios_list, _season_factors, allocation_method, gp_values_list
)

# ── 防御的正規化：負値クリップ＋合計 1.0 保証 ──
monthly_dist_ratios = [max(0.0, r) for r in monthly_dist_ratios]
_ratio_total = sum(monthly_dist_ratios)
if _ratio_total > 0:
    monthly_dist_ratios = [r / _ratio_total for r in monthly_dist_ratios]
else:
    monthly_dist_ratios = [1.0 / 12] * 12

# ── GPチャート用 DataFrame ──
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
    }, index=MONTHS_LABEL)
else:
    label = gp_turf_labels.get(turf_type, turf_type)
    df_gp = pd.DataFrame({
        label: [monthly_gp[str(m)] for m in range(1, 13)],
    }, index=MONTHS_LABEL)

# ── 月順を明示的に 1月〜12月 で固定 ──
df_gp = df_gp.reindex(MONTHS_LABEL)

# ── 安全チェック：NaN / 全ゼロ / 空 ──
if df_gp.empty:
    st.error("⚠️ df_gp が空です。GP計算に問題がある可能性があります。")
elif df_gp.isnull().any().any():
    st.warning("⚠️ GP値に NaN が含まれています。緯度・芝種の設定を確認してください。")
elif (df_gp == 0).all().any():
    st.warning("⚠️ GP値がすべて 0 の列があります。緯度・芝種の設定を確認してください。")

# ── Altair で GP グラフを描画（月順を明示的にカテゴリ制御） ──
df_plot = df_gp.reset_index()
df_plot.columns = ["月"] + list(df_gp.columns)

# wide → long 形式に変換（複数系列に対応）
df_long = df_plot.melt(id_vars="月", var_name="系列", value_name="GP")

gp_chart = (
    alt.Chart(df_long)
    .mark_line(point=True)
    .encode(
        x=alt.X("月:N", sort=MONTHS_LABEL, title="月"),
        y=alt.Y("GP:Q", scale=alt.Scale(domain=[0, 1]), title="Growth Potential"),
        color=alt.Color("系列:N", title=""),
    )
    .properties(height=350)
)
st.altair_chart(gp_chart, use_container_width=True)

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

st.subheader("3. 土壌分析値の評価")

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
    # 全12ヶ月分を明示的に 1〜12 順で構築
    all_months_str = [str(m) for m in range(1, 13)]
    rows = []
    for m_str in all_months_str:
        row = monthly_all.get(m_str, {"N": 0.0, "P": 0.0, "K": 0.0})
        rows.append(row)
    df_all = pd.DataFrame(rows, index=MONTHS_LABEL).fillna(0)

    st.subheader("月別施肥計画（N・P・K）")
    st.caption("※ 単位：kg / 10a（不足分を月別に配分した目安）")
    st.dataframe(df_all)

    # ===== CSV / Excel ダウンロード =====
    export_rows = []
    for m in range(1, 13):
        m_str = str(m)
        gp_val = round(monthly_gp.get(m_str, 0.0), 2)
        dist_coeff = round(monthly_dist_ratios[m - 1], 3)

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

# ===== 用語ガイド =====
st.markdown("---")
st.markdown("""
### 📘 用語ガイド

**MLSN（Minimum Level for Sustainable Nutrition）**  
持続可能な芝生管理における最低養分基準。  
過剰施肥を避けながら健全な生育を維持する考え方。

**SLAN（Sufficiency Level of Available Nutrients）**  
芝生が十分に生育可能とされる養分水準。

本アプリでは、選択した目標基準に基づき不足量を算出し、
年間施肥計画を月別に配分しています。
""")

# ===== フッター =====
st.markdown("---")
st.caption("Soil-Based Fertilization Planner | 2026/2/13版")
st.markdown("""
<div style="text-align: center; padding: 1rem 0; color: #666;">
    <a href="https://www.turf-tools.jp/" target="_blank" style="text-decoration: none; color: #666;">
        &copy;グロウアンドプログレス
    </a>
</div>
""", unsafe_allow_html=True)

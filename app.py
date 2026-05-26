import io
import base64
import os

import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import altair as alt

from logic.design_service import (
    DesignInputs,
    NasaPowerError,
    compute_gp_distribution_from_nasa,
    last_calendar_year,
    run_design_with_gp,
)
from logic.gp_daily import MONTHS_LABEL
from logic.pdf_import import extract_soil_from_pdf
from logic.soil_evaluation import ElementEvaluation
from ui.prefs import (
    apply_geolocation_from_query,
    create_cookie_manager,
    load_prefs_from_cookies,
    render_geolocation_trigger,
    save_prefs_to_cookies,
)

_GA_MEASUREMENT_ID = os.environ.get("GA_MEASUREMENT_ID", "").strip()

TURF_OPTIONS = ["寒地型芝", "暖地型芝", "日本芝", "ウィンターオーバーシード（WOS）"]
DIST_OPTIONS = ["春重点70", "春重点50", "春重点30", "GP準拠"]
DIST_LABELS = {
    "春重点70": "春重点70%",
    "春重点50": "春重点50%（おすすめ）",
    "春重点30": "春重点30%",
    "GP準拠": "GP準拠",
}


def _inject_google_analytics() -> None:
    if not _GA_MEASUREMENT_ID:
        return
    if st.session_state.get("_ga_parent_head_injection"):
        return
    st.session_state["_ga_parent_head_injection"] = True
    ga_id = _GA_MEASUREMENT_ID
    components.html(
        f"""
<script>
try {{
  var w = window.parent;
  if (!w || w === window) throw new Error("no parent");
  var d = w.document;
  if (d.getElementById("st-ga-gtag")) {{}}
  else {{
    var ext = d.createElement("script");
    ext.id = "st-ga-gtag-ext";
    ext.async = true;
    ext.src = "https://www.googletagmanager.com/gtag/js?id={ga_id}";
    d.head.appendChild(ext);
    var inl = d.createElement("script");
    inl.id = "st-ga-gtag";
    inl.text = "\\n  window.dataLayer = window.dataLayer || [];\\n  function gtag(){{dataLayer.push(arguments);}}\\n  gtag('js', new Date());\\n  gtag('config', '{ga_id}');\\n";
    d.head.appendChild(inl);
  }}
}} catch (e) {{}}
</script>
""",
        height=0,
    )


def _clear_gp_and_design() -> None:
    st.session_state["gp_result"] = None
    st.session_state["gp_snapshot"] = None
    st.session_state["design_result"] = None
    st.session_state["nasa_error"] = None


def _snapshot_matches(lat: float, lon: float, turf: str) -> bool:
    snap = st.session_state.get("gp_snapshot")
    if not snap:
        return False
    return (
        abs(lat - snap["lat"]) < 1e-6
        and abs(lon - snap["lon"]) < 1e-6
        and turf == snap["turf"]
    )


def render_soil_eval(ev: ElementEvaluation) -> None:
    if ev.status == "不足":
        box_color, status_label = "#fff3f3", "⚠️ 不足"
    elif ev.status == "過剰":
        box_color, status_label = "#fffff0", "⚡ 過剰"
    else:
        box_color, status_label = "#f0fff0", "✅ 適正"

    warning_text, deficit_text, fert_text = "", "", ""
    if ev.status == "不足":
        warning_text = (
            "⚠️ この項目は目安値を下回っています。"
            "早めの対応を検討してください。<br>"
        )
        deficit_text = f"不足量（目安）：{ev.deficit_mg:.1f} mg/100g<br>"
        if ev.fert_kg_10a is not None and ev.fertilizer_name:
            # 1 kg / 10a = 1 g / ㎡
            fert_text = (
                f"肥料換算（{ev.fertilizer_name}）："
                f"{ev.fert_kg_10a:.2f} g / ㎡<br>"
            )

    if ev.monthly_plan is not None:
        df_monthly = pd.DataFrame({
            "月": MONTHS_LABEL,
            "施肥量（g / ㎡）": [
                round(ev.monthly_plan.get(str(m), 0.0), 2) for m in range(1, 13)
            ],
        })
        st.subheader(f"月別施肥配分({ev.name})")
        st.caption("※ 単位：g / ㎡（月別の施肥量）")
        st.dataframe(df_monthly)

    st.markdown(
        f"""
<div style="background-color:{box_color};padding:12px;border-radius:8px;margin-bottom:12px;">
<strong>{ev.name}</strong><br>判定：{status_label}<br><br>
{warning_text}{ev.comment}{deficit_text}
<hr style="border:none;border-top:1px solid #ccc;">
<strong>設計上の考え方</strong><br>{fert_text}
</div>
""",
        unsafe_allow_html=True,
    )


def render_pdf_soil_importer() -> None:
    # ファイル選択後に操作ボタンが隠れないよう、既定で展開しておく
    with st.expander("📄 土壌分析PDFを読み込む（フェーズ1）", expanded=True):
        st.caption(
            "対応形式: 形式A（mg/100g計量表）, 形式B（PPM→mg/100g）, 形式C（JA診断処方箋）。"
            "未対応PDFは手入力での対応をお願いします。"
        )
        up = st.file_uploader("PDFファイル", type=["pdf"], accept_multiple_files=False)
        if not up:
            return
        if st.button("🔍 PDFから候補値を抽出する", type="primary"):
            try:
                st.session_state["pdf_extract"] = extract_soil_from_pdf(up.getvalue())
                st.session_state["pdf_extract_error"] = None
            except Exception as exc:
                st.session_state["pdf_extract"] = None
                st.session_state["pdf_extract_error"] = str(exc)

        err = st.session_state.get("pdf_extract_error")
        if err:
            st.error(f"PDFの解析に失敗しました: {err}")
            return

        ex = st.session_state.get("pdf_extract")
        if not ex:
            return

        st.write(f"判定: **{ex.template_label}**")
        for note in ex.notes:
            st.caption(note)

        if not ex.fields:
            st.warning("読み取れる項目が見つかりませんでした。")
            return

        df = pd.DataFrame(ex.as_rows())
        st.dataframe(df, use_container_width=True)

        if st.button("✅ 候補値を土壌入力欄へ反映する"):
            soil = ex.as_soil_inputs()
            if "N" in soil:
                st.session_state["soil_no3"] = float(soil["N"])
            if "NH4" in soil:
                st.session_state["soil_nh4"] = float(soil["NH4"])
            if "P" in soil:
                st.session_state["soil_p2o5"] = float(soil["P"])
            if "K" in soil:
                st.session_state["soil_k2o"] = float(soil["K"])
            if "Ca" in soil:
                st.session_state["soil_ca"] = float(soil["Ca"])
            if "Mg" in soil:
                st.session_state["soil_mg"] = float(soil["Mg"])
            st.success("土壌入力欄に反映しました。数値を確認してから次へ進んでください。")


def render_design_philosophy_guide() -> None:
    """月別施肥計画の下に表示する設計思想・用語の説明（旧版 UI の復元）。"""
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

    st.markdown("---")
    st.markdown("""
### 📘 用語ガイド

**MLSN（Minimum Level for Sustainable Nutrition）**  
持続可能な芝生管理における最低養分基準。  
過剰施肥を避けながら健全な生育を維持する考え方。

**SLAN（Sufficiency Level of Available Nutrients）**  
芝生が十分に生育可能とされる養分水準。

本アプリでは、土壌目標水準（MSLN〜SLAN）で年間設計量を決め、
**GP と配分方法（春重点など）** で月別に配分しています。
土壌が不足の要素は不足分を、適正の要素は年間設計量を月別表に示します。
""")


def render_ca_mg_ratio(ratio: float | None, comment: str) -> None:
    if ratio is None:
        st.markdown("""
**Ca : Mg 比**
- Ca : Mg = 不明
- 設計上の考え方：Mg が未測定のため、推定モードで評価します。
""")
        return
    st.markdown(f"""
**Ca : Mg 比**
- Ca : Mg = {ratio:.1f}
**設計上の考え方**
{comment}
""")


def _run_gp_calculation(
    cookies,
    turf_type: str,
    management_target: str,
    latitude: float,
    longitude: float,
    allocation_method: str,
) -> None:
    with st.spinner(
        "NASA POWER から昨年の月別気温を取得し、GP を計算しています。"
        " **5〜15 秒かかることがあります。**"
    ):
        try:
            gp = compute_gp_distribution_from_nasa(
                turf_type,
                management_target,
                latitude,
                longitude,
                allocation_method,
            )
            st.session_state["gp_result"] = gp
            st.session_state["gp_snapshot"] = {
                "lat": latitude,
                "lon": longitude,
                "turf": turf_type,
            }
            st.session_state["nasa_error"] = None
            st.session_state["design_result"] = None
            save_prefs_to_cookies(cookies, latitude, longitude, turf_type)
            st.rerun()
        except NasaPowerError as exc:
            st.session_state["nasa_error"] = str(exc)
            st.session_state["gp_result"] = None
            st.session_state["gp_snapshot"] = None


st.set_page_config(
    page_title="芝しごと・施肥設計ナビ",
    page_icon="🌱",
    layout="wide",
    initial_sidebar_state="expanded",
)

_inject_google_analytics()

# 旧実装で session_state に保持していた CookieManager は削除
st.session_state.pop("_fert_cookie_manager", None)

cookies = create_cookie_manager()
if not cookies.ready():
    st.info("設定を読み込んでいます…")
    st.stop()

css_path = os.path.join(os.path.dirname(__file__), "style.css")
with open(css_path, encoding="utf-8") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

for key, default in (
    ("gp_result", None),
    ("gp_snapshot", None),
    ("design_result", None),
    ("nasa_error", None),
):
    st.session_state.setdefault(key, default)

for key, default in (
    ("soil_no3", 0.0),
    ("soil_nh4", 0.0),
    ("soil_p2o5", 0.0),
    ("soil_k2o", 0.0),
    ("soil_ca", 0.0),
    ("soil_mg", 0.0),
    ("pdf_extract", None),
    ("pdf_extract_error", None),
):
    st.session_state.setdefault(key, default)

if "prefs_initialized" not in st.session_state:
    lat, lon, tidx = load_prefs_from_cookies(cookies, TURF_OPTIONS)
    st.session_state["input_lat"] = lat
    st.session_state["input_lon"] = lon
    st.session_state["turf_index"] = tidx
    st.session_state["prefs_initialized"] = True

apply_geolocation_from_query()

st.title("芝しごと・施肥設計ナビ")
st.markdown(
    '<div class="subtitle">— グリーンキーパーのための土壌分析ベース施肥設計 —</div>',
    unsafe_allow_html=True,
)
st.caption("操作の流れ・進行状況は **左のサイドバー** に常時表示されます。")

def _compute_step(show_gp: bool, gp_calculated: bool) -> int:
    """
    進行ステップ（1〜5）
    1: 基本条件 → 2: GP計算 → 3: 土壌入力 → 4: 施肥設計 → 5: 出力
    """
    if st.session_state.get("design_result"):
        return 5
    if show_gp:
        return 3
    if gp_calculated:
        return 2
    return 1


def render_workflow_steps(step: int) -> None:
    """左サイドバー用。メインをスクロールしても常に見える。"""
    steps = [
        "① 基本条件",
        "② GP計算",
        "③ 土壌入力",
        "④ 施肥設計",
        "⑤ 出力",
    ]
    for i, label in enumerate(steps, start=1):
        if i < step:
            st.markdown(f'<p class="workflow-step-done">✅ {label}</p>', unsafe_allow_html=True)
        elif i == step:
            st.markdown(
                f'<p class="workflow-step-current">▶ {label}（いまここ）</p>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(f'<p class="workflow-step-todo">⚪ {label}</p>', unsafe_allow_html=True)

_BANNER_PR_URL = "https://www.turf-tools.jp/services-4"
banner_pr = os.path.join(os.path.dirname(__file__), "banner_pr_size1.png")


def _img_to_base64(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def _linked_png_banner_markup(path: str, url: str, img_alt: str, w: int, h: int) -> str:
    if not os.path.exists(path):
        return ""
    b64 = _img_to_base64(path)
    return (
        f'<a href="{url}" target="_blank" rel="noopener noreferrer">'
        f'<img src="data:image/png;base64,{b64}" alt="{img_alt}" '
        f'width="{w}" height="{h}" style="width:{w}px;height:{h}px;display:block;" /></a>'
    )


if os.path.exists(banner_pr):
    b64 = _img_to_base64(banner_pr)
    st.markdown(
        f'<a href="{_BANNER_PR_URL}" target="_blank">'
        f'<img src="data:image/png;base64,{b64}" alt="PR" '
        f'style="max-width:100%;display:block;" /></a>',
        unsafe_allow_html=True,
    )

_blog_banner_parts: list[str] = []
for url, path, img_alt in (
    ("https://www.turf-tools.jp/blog", "bloglink.png", "ブログ"),
    (
        "https://www.youtube.com/channel/UCSRU0zk4Fj1ETWqMRlJDPJQ",
        "youtubelink.png",
        "YouTube",
    ),
):
    p = os.path.join(os.path.dirname(__file__), path)
    html = _linked_png_banner_markup(p, url, img_alt, 300, 100)
    if html:
        _blog_banner_parts.append(html)
if _blog_banner_parts:
    st.markdown(
        '<div style="display:flex;flex-direction:row;flex-wrap:nowrap;'
        'gap:4px;align-items:flex-start;width:fit-content;">'
        + "".join(_blog_banner_parts)
        + "</div>",
        unsafe_allow_html=True,
    )

st.markdown("## 基本条件（設計前提）")

with st.container():
    if "input_turf" not in st.session_state:
        st.session_state["input_turf"] = TURF_OPTIONS[
            st.session_state.get("turf_index", 0)
        ]
    turf_type = st.selectbox("芝種", TURF_OPTIONS, key="input_turf")
    management_target = st.selectbox(
        "管理対象",
        ["競技場", "ゴルフグリーン", "フェアウェイ"],
    )
    _geo_success = st.session_state.pop("geolocation_success_msg", None)
    if _geo_success:
        st.success(_geo_success)

    col_geo1, col_geo2, col_geo3 = st.columns([1, 1, 0.9])
    # 位置情報の反映は緯度・経度ウィジェットより先に実行する（同一ラン内の session_state 更新制約）
    with col_geo3:
        st.markdown("<div style='height:1.75rem'></div>", unsafe_allow_html=True)
        render_geolocation_trigger()
    with col_geo1:
        latitude = st.number_input(
            "緯度",
            min_value=20.0,
            max_value=50.0,
            step=0.1,
            key="input_lat",
        )
    with col_geo2:
        longitude = st.number_input(
            "経度",
            min_value=120.0,
            max_value=155.0,
            step=0.1,
            key="input_lon",
        )

with st.container():
    allocation_method = st.radio(
        "🌱 配分方法（GP基準）",
        DIST_OPTIONS,
        index=DIST_OPTIONS.index("春重点50"),
        format_func=lambda x: DIST_LABELS.get(x, x),
    )
    msl_slan_position = st.selectbox(
        "🎯 土壌目標水準の選択",
        ["下限寄り", "中央", "上限寄り"],
        index=1,
        format_func=lambda x: {
            "下限寄り": "下限寄り（MLSN重視）",
            "中央": "中央",
            "上限寄り": "上限寄り（SLAN重視）",
        }.get(x, x),
    )
    st.caption(
        "土壌が適正なときの **年間施肥量（MSLN/SLAN）** の位置、"
        "不足時の補正目標にも用います。"
    )

if st.session_state.get("gp_result") and not _snapshot_matches(
    latitude, longitude, turf_type
):
    _clear_gp_and_design()

col_gp1, col_gp2 = st.columns([1, 1])
with col_gp1:
    gp_clicked = st.button(
        "📈 GP を計算する",
        type="primary",
        help="NASA POWER の昨年の月別気温から GP を算出します。",
    )
with col_gp2:
    retry_clicked = bool(
        st.session_state.get("nasa_error")
        and st.button("🔄 再試行")
    )

if gp_clicked or retry_clicked:
    _run_gp_calculation(
        cookies,
        turf_type,
        management_target,
        latitude,
        longitude,
        allocation_method,
    )

if st.session_state.get("nasa_error"):
    st.error(f"GP の計算に失敗しました: {st.session_state['nasa_error']}")

gp_result = st.session_state.get("gp_result")
show_gp = gp_result is not None and _snapshot_matches(latitude, longitude, turf_type)

if show_gp:
    year = gp_result.temperature_year or last_calendar_year()
    st.subheader("Growth Potential（GP）")
    st.caption(
        f"NASA POWER の **{year}年（1〜12月）** の月平均気温（T2M）と、"
        "芝種別の気温応答関数から GP を算出しています（0〜1）。"
    )

    df_gp = pd.DataFrame(gp_result.gp_chart_series, index=MONTHS_LABEL).reindex(
        MONTHS_LABEL
    )
    df_plot = df_gp.reset_index()
    df_plot.columns = ["月"] + list(df_gp.columns)
    df_long = df_plot.melt(id_vars="月", var_name="系列", value_name="GP")

    gp_chart = (
        alt.Chart(df_long)
        .mark_line(point=True, interpolate="natural")
        .encode(
            x=alt.X("月:N", sort=MONTHS_LABEL, title="月"),
            y=alt.Y("GP:Q", scale=alt.Scale(domain=[0, 1]), title="Growth Potential"),
            color=alt.Color("系列:N", title=""),
        )
        .properties(height=350)
    )
    st.altair_chart(gp_chart, use_container_width=True)
    st.dataframe(df_gp.T.style.format("{:.2f}"), use_container_width=True)

    if gp_result.monthly_temperatures_c:
        st.caption(
            "参考: 月平均気温（℃） "
            + " / ".join(
                f"{m}月 {t:.1f}"
                for m, t in zip(range(1, 13), gp_result.monthly_temperatures_c)
            )
        )

    with st.expander("GPの設計思想について"):
        st.markdown("""
**Growth Potential（GP）** は気温に対する生育応答を 0〜1 で表した指標です。
本画面では NASA POWER の月平均気温に芝種別応答関数を適用しています。
**WOS** は寒地型・暖地型の季節的な主役交代（重み付き合成）で算出します。
""")

    st.subheader("2. 土壌分析値（mg/100g）")
    st.caption("※ 最新の土壌分析結果を入力してください（乾土基準）")

    render_pdf_soil_importer()

    col1, col2 = st.columns(2)
    with col1:
        no3_n = st.number_input(
            "硝酸態窒素（NO₃-N）",
            min_value=0.0,
            step=0.1,
            key="soil_no3",
        )
        nh4_n = st.number_input(
            "アンモニア態窒素（NH₄-N）",
            min_value=0.0,
            step=0.1,
            key="soil_nh4",
        )
    with col2:
        p2o5 = st.number_input(
            "可給態リン酸（P₂O₅）",
            min_value=0.0,
            step=0.1,
            key="soil_p2o5",
        )
        k2o = st.number_input(
            "交換性カリ（K₂O）",
            min_value=0.0,
            step=0.1,
            key="soil_k2o",
        )
        ca = st.number_input(
            "カルシウム（CaO）",
            min_value=0.0,
            step=0.1,
            key="soil_ca",
        )
        mg = st.number_input(
            "マグネシウム（MgO）",
            min_value=0.0,
            step=0.1,
            key="soil_mg",
        )

    _ = nh4_n
    soil_values = {"N": no3_n, "P": p2o5, "K": k2o, "Ca": ca, "Mg": mg}

    st.caption("次の操作: 土壌値を入力し、下の **「🌱 施肥設計を実行する」** を押してください。")

    if st.button(
        "🌱 施肥設計を実行する",
        type="primary",
        help="土壌評価と N・P・K の月別配分を計算します。",
    ):
        inputs = DesignInputs(
            turf_type=turf_type,
            management_target=management_target,
            latitude=latitude,
            longitude=longitude,
            allocation_method=allocation_method,
            soil_target_position=msl_slan_position,
            soil=soil_values,
        )
        st.session_state["design_result"] = run_design_with_gp(inputs, gp_result)
        st.rerun()

    design = st.session_state.get("design_result")
    if design:
        st.subheader("3. 土壌分析値の評価")
        col1, col2 = st.columns(2)
        with col1:
            for elem in ("N", "P", "K"):
                render_soil_eval(design.soil_evaluations[elem])

        monthly_all = design.monthly_fertilizer_plan
        st.subheader("月別施肥計画（N・P・K）")
        annual = design.annual_nutrients
        if design.plan_mode == "mixed":
            st.info(
                "**適正** の要素（N・P・K）は MSLN/SLAN の年間設計量を GP 配分で月別表示、"
                "**不足** の要素は土壌不足分（要素量）を GP 配分で月別表示しています。"
            )
            st.caption("※ 単位：g / ㎡（要素量）")
        elif design.plan_mode == "annual_gp" and annual:
            n_ann = annual["N"]["annual_value"]
            st.info(
                "N・P・K は土壌目安範囲内（適正）のため、"
                f"**MSLN/SLAN 年間設計量（N {n_ann*0.1:.1f} g/㎡ など）** を "
                "画面上部の **GP 配分係数** で月別に配分しています。"
            )
            st.caption("※ 単位：g / ㎡（要素量。年間設計量 × 月別配分係数）")

        rows = [
            monthly_all.get(str(m), {"N": 0.0, "P": 0.0, "K": 0.0})
            for m in range(1, 13)
        ]
        df_all = pd.DataFrame(rows, index=MONTHS_LABEL).fillna(0)
        st.dataframe(df_all)

        if design.export_rows:
            df_export = pd.DataFrame(design.export_rows)
            csv_data = df_export.to_csv(index=False, encoding="utf-8-sig")
            excel_buffer = io.BytesIO()
            with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
                df_export.to_excel(writer, index=False, sheet_name="施肥設計")
            c1, c2 = st.columns(2)
            with c1:
                st.download_button(
                    "📥 CSVダウンロード", csv_data, "施肥設計.csv", "text/csv"
                )
            with c2:
                st.download_button(
                    "📥 Excelダウンロード",
                    excel_buffer.getvalue(),
                    "施肥設計.xlsx",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )

        with col2:
            render_soil_eval(design.soil_evaluations["Ca"])
            render_soil_eval(design.soil_evaluations["Mg"])
            if design.ca_mg:
                render_ca_mg_ratio(design.ca_mg.ratio, design.ca_mg.comment)

        render_design_philosophy_guide()
    else:
        st.info("次の操作: 土壌値を入力し、**「🌱 施肥設計を実行する」** を押してください。")

else:
    st.info(
        "次の操作: 上の **「📈 GP を計算する」** を押してください。"
        "（GP を計算すると、土壌分析値の入力欄が表示されます）"
    )

# 手順・進行状況（サイドバー＝スクロールしても常時表示）
_gp_for_bar = st.session_state.get("gp_result")
_gp_calculated = _gp_for_bar is not None
_show_gp_for_bar = _gp_calculated and _snapshot_matches(
    latitude, longitude, turf_type
)
with st.sidebar:
    st.markdown("### 操作の流れ")
    render_workflow_steps(_compute_step(_show_gp_for_bar, _gp_calculated))

st.markdown("---")
st.caption("Soil-Based Fertilization Planner | v.2.0.0")
st.markdown("""
<div style="text-align:center;padding:1rem 0;color:#666;">
<a href="https://www.turf-tools.jp/" target="_blank" style="color:#666;text-decoration:none;">
&copy;グロウアンドプログレス</a></div>
""", unsafe_allow_html=True)

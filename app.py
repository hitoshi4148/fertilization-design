"""
芝しごと・施肥設計ナビ
Streamlit UI
"""

import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime
import tempfile
import os
import json

from streamlit_cookies_manager import CookieManager
from logic import (
    GrassType,
    UsageType,
    ManagementIntensity,
    PGRIntensity,
    FertilizerStance,
    calculate_growth_potential,
    calculate_growth_potentials,
    calculate_fertilizer_requirements,
)
from logic.gp import get_monthly_n_distribution
# PDF機能を一時的に無効化（Streamlit Community Cloud対応）
try:
    from pdf import generate_pdf
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False
    generate_pdf = None


# ページ設定
st.set_page_config(
    page_title="芝しごと・施肥設計ナビ",
    page_icon="🌱",
    layout="wide",
)

# サイドバーの行間を詰めるCSS（強力な上書き）
st.markdown("""
<style>
    /* サイドバー全体のリセット - すべてのマージンとパディングを0に */
    section[data-testid="stSidebar"] > div {
        padding-top: 0.2rem !important;
        padding-bottom: 0.2rem !important;
    }
    
    /* すべての要素コンテナのマージンとパディングを最小化 */
    section[data-testid="stSidebar"] div[class*="element-container"],
    section[data-testid="stSidebar"] div[class*="stWidget"],
    section[data-testid="stSidebar"] div[class*="row-widget"] {
        margin-top: 0 !important;
        margin-bottom: 0.1rem !important;
        padding-top: 0 !important;
        padding-bottom: 0.1rem !important;
    }
    
    /* ヘッダー（h1, h2, h3）のマージンを完全に削除 */
    section[data-testid="stSidebar"] h1,
    section[data-testid="stSidebar"] h2,
    section[data-testid="stSidebar"] h3 {
        margin: 0 !important;
        padding: 0 !important;
        margin-bottom: 0.2rem !important;
        line-height: 1.1 !important;
        font-size: 1.1rem !important;
    }
    
    /* パラグラフ（markdown）のマージンを削除 */
    section[data-testid="stSidebar"] p {
        margin: 0 !important;
        padding: 0 !important;
        margin-bottom: 0.1rem !important;
        line-height: 1.2 !important;
    }
    section[data-testid="stSidebar"] p strong {
        display: block;
        margin-bottom: 0.3rem !important;
        margin-top: 0.3rem !important;
        line-height: 1.2 !important;
        font-size: 0.95rem !important;
        font-weight: 600 !important;
    }
    /* セクション区切り線（hr）のスタイル */
    section[data-testid="stSidebar"] hr {
        margin: 0.5rem 0 !important;
        border: none !important;
        border-top: 1px solid #e0e0e0 !important;
        padding: 0 !important;
    }
    /* キャプション（説明文）のスタイル */
    section[data-testid="stSidebar"] .stCaption {
        margin: 0 !important;
        padding: 0 !important;
        margin-bottom: 0.2rem !important;
        font-size: 0.8rem !important;
        color: #666 !important;
        line-height: 1.2 !important;
    }
    
    /* ラベルのマージンとパディングを削除 */
    section[data-testid="stSidebar"] label,
    section[data-testid="stSidebar"] label > div {
        margin: 0 !important;
        padding: 0 !important;
        margin-bottom: 0.3rem !important;
        line-height: 1.1 !important;
        font-size: 0.9rem !important;
    }
    
    /* 入力フィールド（number_input, selectbox）のコンテナ */
    section[data-testid="stSidebar"] div[data-baseweb="input"],
    section[data-testid="stSidebar"] div[data-baseweb="select"],
    section[data-testid="stSidebar"] div[data-baseweb="radio"],
    section[data-testid="stSidebar"] .stNumberInput > div,
    section[data-testid="stSidebar"] .stSelectbox > div,
    section[data-testid="stSidebar"] .stRadio > div {
        margin: 0 !important;
        padding: 0 !important;
        margin-top: 0.05rem !important;
        margin-bottom: 0.05rem !important;
    }
    
    /* 入力フィールド自体の高さを統一（number_inputとselectboxを同じ高さに） */
    section[data-testid="stSidebar"] input,
    section[data-testid="stSidebar"] select,
    section[data-testid="stSidebar"] input[type="number"],
    section[data-testid="stSidebar"] [data-baseweb="input"] input,
    section[data-testid="stSidebar"] [data-baseweb="select"] select {
        min-height: 28px !important;
        height: 28px !important;
        padding: 0.2rem 0.5rem !important;
        font-size: 0.9rem !important;
        line-height: 1.2 !important;
    }
    /* BaseWebコンポーネントのコンテナも同じ高さに */
    section[data-testid="stSidebar"] [data-baseweb="input"],
    section[data-testid="stSidebar"] [data-baseweb="select"] {
        min-height: 28px !important;
        height: 28px !important;
    }
    
    /* ボタンのマージンとパディングを削減 */
    section[data-testid="stSidebar"] button,
    section[data-testid="stSidebar"] .stButton > button {
        margin: 0 !important;
        padding: 0.3rem 0.5rem !important;
        margin-top: 0.1rem !important;
        margin-bottom: 0.1rem !important;
        min-height: 32px !important;
        height: 32px !important;
        font-size: 0.9rem !important;
        line-height: 1.2 !important;
    }
    
    /* ボタンコンテナのマージンを削減 */
    section[data-testid="stSidebar"] .stButton {
        margin: 0 !important;
        padding: 0 !important;
        margin-top: 0.1rem !important;
        margin-bottom: 0.1rem !important;
    }
    
    /* カラムのマージンを削減 */
    section[data-testid="stSidebar"] div[data-testid="column"],
    section[data-testid="stSidebar"] [class*="column"] {
        margin: 0 !important;
        padding: 0 !important;
        margin-bottom: 0.05rem !important;
    }
    
    /* カラム内の要素のマージンも削減 */
    section[data-testid="stSidebar"] div[data-testid="column"] > div {
        margin: 0 !important;
        padding: 0 !important;
    }
    
    /* 成功/エラーメッセージのマージンを削減 */
    section[data-testid="stSidebar"] .stSuccess,
    section[data-testid="stSidebar"] .stError,
    section[data-testid="stSidebar"] .stInfo {
        margin: 0 !important;
        padding: 0.3rem !important;
        margin-top: 0.1rem !important;
        margin-bottom: 0.1rem !important;
        font-size: 0.85rem !important;
    }
    
    /* Streamlitの内部スペーサーを削除 */
    section[data-testid="stSidebar"] [class*="block-container"],
    section[data-testid="stSidebar"] [class*="main"] {
        padding: 0 !important;
        margin: 0 !important;
    }
    
    /* スピナーボタン（-/+）のサイズを小さく */
    section[data-testid="stSidebar"] input[type="number"]::-webkit-inner-spin-button,
    section[data-testid="stSidebar"] input[type="number"]::-webkit-outer-spin-button {
        width: 12px !important;
        height: 12px !important;
        opacity: 0.6 !important;
    }
    /* BaseWebコンポーネント内のスピナーボタンも小さく */
    section[data-testid="stSidebar"] [data-baseweb="input"] input[type="number"]::-webkit-inner-spin-button,
    section[data-testid="stSidebar"] [data-baseweb="input"] input[type="number"]::-webkit-outer-spin-button {
        width: 12px !important;
        height: 12px !important;
        opacity: 0.6 !important;
    }
    
    /* 右側ガイドカラム（「この画面で何を決めているか」）の文字サイズを1ポイント小さく */
    /* タイトル（h3）を1ポイント小さく */
    div[data-testid="column"]:nth-child(2) h3,
    div[data-testid="column"]:nth-child(2) .stMarkdown h3 {
        font-size: 0.85em !important;
    }
    /* タイトル以外（pなど）を1ポイント小さく */
    div[data-testid="column"]:nth-child(2) p,
    div[data-testid="column"]:nth-child(2) .stMarkdown p {
        font-size: 0.85em !important;
    }
    div[data-testid="column"]:nth-child(2) .stInfo {
        font-size: 0.8em !important;
    }
</style>
""", unsafe_allow_html=True)

# Cookie管理の初期化（キャッシュなしで直接初期化）
cookies = CookieManager()

# タイトルとバナー画像を横並びに配置
title_col, banner_col = st.columns([3, 1])
with title_col:
    st.title("芝しごと・施肥設計ナビ")
    st.markdown("""
    <div style="line-height: 1.2; margin-top: -0.5rem;">
        <strong>土壌分析値に基づく芝生施肥設計支援</strong><br>
        <span style="font-size: 0.9em; color: #666;">（2026.1.27版）</span>
    </div>
    """, unsafe_allow_html=True)
    # サブタイトル下のバナー画像
    banner_728_path = "pdf/banner_ad_recruitment_728x90.jpg"
    if os.path.exists(banner_728_path):
        st.image(banner_728_path)
    else:
        st.caption("バナー画像が見つかりません")
with banner_col:
    # バナー画像を表示
    banner_path = "pdf/banner_ad_recruitment_300x250.jpg"
    if os.path.exists(banner_path):
        st.image(banner_path)
    else:
        # 画像ファイルが存在しない場合のフォールバック
        st.markdown("")
        st.caption("バナー画像が見つかりません")

st.markdown("---")

# Cookieから保存されたデータを読み込む
def load_from_cookies():
    """Cookieから入力データを読み込む"""
    try:
        # CookieManagerがreadyになるまで待つ
        if not cookies.ready():
            return None
        
        saved_data = cookies.get("fertilization_input_data")
        if saved_data:
            if isinstance(saved_data, str):
                return json.loads(saved_data)
            return saved_data
    except Exception as e:
        # エラーは表示せず、Noneを返す（初回起動時など）
        pass
    return None

def save_to_cookies(data):
    """入力データをCookieに保存"""
    try:
        # CookieManagerは辞書形式で操作し、save()を呼び出す
        cookies["fertilization_input_data"] = json.dumps(data)
        cookies.save()
    except Exception as e:
        st.error(f"Cookie保存エラー: {e}")

# Cookieからデータを読み込む
saved_data = load_from_cookies()

# サイドバー：入力フォーム
with st.sidebar:
    st.header("📋 入力条件")
    
    # 1. 基本条件
    st.markdown("**1. 基本条件**")
    # 芝種
    grass_type = st.selectbox("芝種", options=[gt.value for gt in GrassType], index=[gt.value for gt in GrassType].index(saved_data["grass_type"]) if saved_data and "grass_type" in saved_data and saved_data["grass_type"] in [gt.value for gt in GrassType] else 0)
    # 管理対象
    usage_type = st.selectbox("管理対象", options=[ut.value for ut in UsageType], index=[ut.value for ut in UsageType].index(saved_data["usage_type"]) if saved_data and "usage_type" in saved_data and saved_data["usage_type"] in [ut.value for ut in UsageType] else 0)
    # 施設の場所（緯度経度）
    col1, col2 = st.columns(2)
    with col1:
        latitude = st.number_input("緯度", min_value=-90.0, max_value=90.0, value=saved_data.get("latitude", 35.6812) if saved_data else 35.6812, step=0.0001, format="%.4f", key="latitude_input")
    with col2:
        longitude = st.number_input("経度", min_value=-180.0, max_value=180.0, value=saved_data.get("longitude", 139.7671) if saved_data else 139.7671, step=0.0001, format="%.4f", key="longitude_input")
    
    st.markdown("---")
    
    # 2. 土壌分析値
    st.markdown("**2. 土壌分析値（mg/100g）**")
    st.caption("Nは土壌診断値から算出されます")
    soil_p = st.number_input("P（リン酸）", min_value=0.0, value=saved_data.get("soil_p", 20.0) if saved_data else 20.0, step=0.1)
    soil_k = st.number_input("K（カリウム）", min_value=0.0, value=saved_data.get("soil_k", 20.0) if saved_data else 20.0, step=0.1)
    soil_ca = st.number_input("Ca（カルシウム）", min_value=0.0, value=saved_data.get("soil_ca", 300.0) if saved_data else 300.0, step=1.0)
    soil_mg = st.number_input("Mg（マグネシウム）", min_value=0.0, value=saved_data.get("soil_mg", 30.0) if saved_data else 30.0, step=0.1)
    
    st.markdown("---")
    
    # 3. 管理条件
    st.markdown("**3. 管理条件**")
    management_intensity = st.selectbox("管理強度", options=[mi.value for mi in ManagementIntensity], index=[mi.value for mi in ManagementIntensity].index(saved_data["management_intensity"]) if saved_data and "management_intensity" in saved_data and saved_data["management_intensity"] in [mi.value for mi in ManagementIntensity] else 1)
    
    # 管理強度の説明文
    management_intensity_descriptions = {
        "低": "利用頻度を優先し、過度な生育刺激を避ける管理です。\n施肥量は最小限とし、安定した被覆維持を目的とします。",
        "中": "競技性と維持管理のバランスを重視した標準的な管理です。\n季節に応じた生育を促し、年間を通じた品質維持を目指します。",
        "高": "競技品質を最優先し、生育ピークを明確に作る管理です。\n春の立ち上げを重視し、刈込み頻度や調整剤使用を前提とします。"
    }
    if management_intensity in management_intensity_descriptions:
        st.caption(management_intensity_descriptions[management_intensity])
    
    distribution_stance = st.radio("配分方法", options=["春重点", "平準", "GP準拠"], index=0, help="春重点：春先に重点的に施肥（デフォルト）\n平準：年間を通じて均等に配分\nGP準拠：Growth Potentialのみに基づく配分")
    
    # 春重点配分の説明文
    if distribution_stance == "春重点":
        st.caption("春の立ち上げ期に施肥を重点配分する設計です。\n初期生育を安定させ、その後の管理負荷低減を目的とします。")
    else:  # 平準 または GP準拠
        st.caption("成長能（GP）に応じて、年間を通じて均等に配分する設計です。\n特定の季節に偏らない施肥を行いたい場合に選択します。")
    
    pgr_intensity = st.selectbox("PGR強度", options=[pgr.value for pgr in PGRIntensity], index=[pgr.value for pgr in PGRIntensity].index(saved_data["pgr_intensity"]) if saved_data and "pgr_intensity" in saved_data and saved_data["pgr_intensity"] in [pgr.value for pgr in PGRIntensity] else 0)
    
    # PGR強度の説明文
    pgr_intensity_descriptions = {
        "なし": "植物成長調整剤を使用しない管理です。\n芝の自然な生育に合わせて施肥を行います。",
        "弱": "生育ピーク時に限定して使用する管理です。\n刈込み負荷を軽減しつつ、生育の流れを大きく変えません。",
        "中": "生育期を通じて計画的に使用する管理です。\n刈粕量の抑制を前提に、施肥量を調整します。",
        "強": "競技品質を最優先し、継続的に使用する管理です。\n生育速度を強く抑制し、施肥量も抑えた設計となります。"
    }
    if pgr_intensity in pgr_intensity_descriptions:
        st.caption(pgr_intensity_descriptions[pgr_intensity])
    
    st.markdown("---")
    
    # 施肥スタンス（管理条件の後に配置）
    fertilizer_stance = st.selectbox("MSLN〜SLAN内の位置", options=[fs.value for fs in FertilizerStance], index=[fs.value for fs in FertilizerStance].index(saved_data["fertilizer_stance"]) if saved_data and "fertilizer_stance" in saved_data and saved_data["fertilizer_stance"] in [fs.value for fs in FertilizerStance] else 1)
    
    st.markdown("---")
    
    # Cookie保存ボタン
    col1, col2 = st.columns(2)
    with col1:
        if st.button("💾 保存", use_container_width=True):
            input_data = {
                "latitude": latitude, "longitude": longitude, "grass_type": grass_type, "usage_type": usage_type,
                "management_intensity": management_intensity, "pgr_intensity": pgr_intensity,
                "soil_p": soil_p, "soil_k": soil_k, "soil_ca": soil_ca, "soil_mg": soil_mg, "fertilizer_stance": fertilizer_stance,
            }
            save_to_cookies(input_data)
            st.success("✅ 保存しました")
    with col2:
        if st.button("🗑️ クリア", use_container_width=True):
            try:
                if "fertilization_input_data" in cookies:
                    del cookies["fertilization_input_data"]
                    cookies.save()
                st.success("✅ クリアしました")
                st.rerun()
            except Exception as e:
                st.error(f"❌ エラー: {e}")
    
    # 計算ボタン
    calculate_button = st.button("🔄 計算実行", type="primary", use_container_width=True)

# メインエリア
# 計算結果が表示されていない場合のみ、2カラムレイアウトでガイドを表示
has_results = calculate_button or "results" in st.session_state

if not has_results:
    # 計算前：2カラムレイアウト（左：メイン、右：ガイド）
    main_col, guide_col = st.columns([2, 1])
    
    with guide_col:
        st.markdown("---")
        st.markdown("### 📖 この画面で何を決めているか")
        st.markdown(
            "この設定は、年間を通じた芝の管理強度の山とタイミングを決めます。"
            "ゴルフ場でもグラウンドでも使える考え方です。"
        )
        
        st.markdown("**各設定項目の意味**")
        st.markdown(
            "**・管理強度（高・中・低）**\n"
            "年間を通した基本的な管理レベルを決めます。"
            "更新頻度・刈込み・施肥量の目安に影響します。\n\n"
            "**・PGR強度**\n"
            "生育抑制剤（PGR）の効かせ方の強さを示します。"
            "GP（生育ポテンシャル）と連動して効き方が変わります。\n\n"
            "**・春重点配分（ON / OFF）**\n"
            "春の生育ピークにどれだけ管理リソースを集中させるかを決めます。"
            "グリーン重視か、年間均し重視かの考え方です。"
        )
    
        st.markdown("**MSLN / SLANについて**")
        st.markdown(
            "**MSLN**は「Minimum Sustainable Level of Nitrogen」（持続可能な最低窒素水準）で、"
            "芝が健全に維持できる最低限の窒素供給レベルです。\n\n"
            "**SLAN**は「Sufficiency Level of Available Nitrogen」（十分量の可給態窒素水準）で、"
            "生育を十分に支えるための適正な窒素レベルです。\n\n"
            "本アプリでは、管理強度やPGR設定を考える際の"
            "“考え方の基準”として用いています。"
        )
        
        st.info("💡 **迷った場合は、まず『管理強度：中』『春重点：ON』から試してください**")
    
    with main_col:
        # 初期表示（計算結果が表示されていない場合）
        st.info("👈 左側のサイドバーから入力条件を設定し、「計算実行」ボタンをクリックしてください。")
        
        st.markdown("""
        ### 📖 使い方
        
        この画面では、芝の種類・場所・管理方針を入力することで、年間を通じた施肥設計を自動計算します。
        
        **入力の流れ**
        
        1. **基本条件**
           - 芝種、管理対象、緯度・経度を設定します
           - 芝の種類と施設の場所から、気候条件を自動判定します
        
        2. **土壌分析値**
           - 土壌診断で得られたP、K、Ca、Mgの値を入力します（mg/100g）
           - これらの値から、適切な施肥量を計算します
        
        3. **管理条件**
           - 管理強度、配分方法、PGR強度、MSLN〜SLAN内の位置を選択します
           - どのような管理方針で施肥設計するかを決めます
        
        4. **計算実行**
           - 「計算実行」ボタンをクリックすると、年間施肥設計が表示されます
           - 計算結果は画面で確認できます
        """)
else:
    # 計算後：単一カラムレイアウト（全幅表示）
    # st.columnsを呼ばずに、直接全幅で計算結果を表示
    # 入力値をEnumに変換
    grass_type_enum = GrassType(grass_type)
    usage_type_enum = UsageType(usage_type)
    management_intensity_enum = ManagementIntensity(management_intensity)
    pgr_intensity_enum = PGRIntensity(pgr_intensity)
    fertilizer_stance_enum = FertilizerStance(fertilizer_stance)
    
    # 土壌診断値
    soil_values = {
        "P": soil_p,
        "K": soil_k,
        "Ca": soil_ca,
        "Mg": soil_mg,
    }
    
    # 計算実行
    with st.spinner("計算中..."):
        # 施肥量計算（GP × 季節補正配分）
        results = calculate_fertilizer_requirements(
            grass_type=grass_type_enum,
            usage_type=usage_type_enum,
            management_intensity=management_intensity_enum,
            pgr_intensity=pgr_intensity_enum,
            soil_values=soil_values,
            fertilizer_stance=fertilizer_stance_enum,
            latitude=latitude,
            longitude=longitude,
            distribution_stance=distribution_stance,
        )
        
        # GP値を取得（結果に含まれている）
        monthly_gp = results["N"]["gp_values"]
        
        # 月別配分量を取得
        monthly_n = results["N"]["monthly"]
        monthly_p = results["P"]["monthly"]
        monthly_k = results["K"]["monthly"]
        monthly_ca = results["Ca"]["monthly"]
        monthly_mg = results["Mg"]["monthly"]
        
        # 後方互換性のため、gp_dictも作成（既存のグラフ表示用）
        from logic.gp import calculate_growth_potentials
        gp_dict = calculate_growth_potentials(grass_type)
        gp_values = monthly_gp  # 気温ベースのGPを使用
        
        # セッションに保存
        st.session_state["results"] = results
        st.session_state["monthly_gp"] = monthly_gp  # 気温ベースのGP
        st.session_state["gp_values"] = monthly_gp
        st.session_state["gp_dict"] = gp_dict  # 後方互換性のため
        st.session_state["monthly_n"] = monthly_n
        st.session_state["monthly_p"] = monthly_p
        st.session_state["monthly_k"] = monthly_k
        st.session_state["monthly_ca"] = monthly_ca
        st.session_state["monthly_mg"] = monthly_mg
        st.session_state["distribution_stance"] = distribution_stance
        
        # 管理強度の説明文を取得
        management_intensity_descriptions = {
            "低": "利用頻度を優先し、過度な生育刺激を避ける管理です。\n施肥量は最小限とし、安定した被覆維持を目的とします。",
            "中": "競技性と維持管理のバランスを重視した標準的な管理です。\n季節に応じた生育を促し、年間を通じた品質維持を目指します。",
            "高": "競技品質を最優先し、生育ピークを明確に作る管理です。\n春の立ち上げを重視し、刈込み頻度や調整剤使用を前提とします。"
        }
        management_intensity_description = management_intensity_descriptions.get(management_intensity, "")
        
        # PGR強度の説明文を取得
        pgr_intensity_descriptions = {
            "なし": "植物成長調整剤を使用しない管理です。\n芝の自然な生育に合わせて施肥を行います。",
            "弱": "生育ピーク時に限定して使用する管理です。\n刈込み負荷を軽減しつつ、生育の流れを大きく変えません。",
            "中": "生育期を通じて計画的に使用する管理です。\n刈粕量の抑制を前提に、施肥量を調整します。",
            "強": "競技品質を最優先し、継続的に使用する管理です。\n生育速度を強く抑制し、施肥量も抑えた設計となります。"
        }
        pgr_intensity_description = pgr_intensity_descriptions.get(pgr_intensity, "")
        
        # 配分方法（春重点配分）の説明文を取得
        if distribution_stance == "春重点":
            distribution_stance_description = "春の立ち上げ期に施肥を重点配分する設計です。\n初期生育を安定させ、その後の管理負荷低減を目的とします。"
        else:  # 平準 または GP準拠
            distribution_stance_description = "成長能（GP）に応じて、年間を通じて均等に配分する設計です。\n特定の季節に偏らない施肥を行いたい場合に選択します。"
        
        st.session_state["input_data"] = {
            "grass_type": grass_type,
            "usage_type": usage_type,
            "management_intensity": management_intensity,
            "management_intensity_description": management_intensity_description,
            "pgr_intensity": pgr_intensity,
            "pgr_intensity_description": pgr_intensity_description,
            "fertilizer_stance": fertilizer_stance,
            "soil_values": soil_values,
            "latitude": latitude,
            "longitude": longitude,
            "distribution_stance": distribution_stance,
            "distribution_stance_description": distribution_stance_description,
        }
        
        # 計算実行時に自動保存
        input_data_for_cookie = {
            "latitude": latitude,
            "longitude": longitude,
            "grass_type": grass_type,
            "usage_type": usage_type,
            "management_intensity": management_intensity,
            "pgr_intensity": pgr_intensity,
            "soil_p": soil_p,
            "soil_k": soil_k,
            "soil_ca": soil_ca,
            "soil_mg": soil_mg,
            "fertilizer_stance": fertilizer_stance,
        }
        save_to_cookies(input_data_for_cookie)
        
        st.success("✅ 計算が完了しました")
        st.markdown("---")
        
        # 結果表示
        st.header("📊 年間施肥設計結果")
        
        # 数値表
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("年間施肥量（MSLN/SLAN理論）")
            result_data = {
                "成分": ["N（窒素）", "P（リン酸）", "K（カリウム）", "Ca（カルシウム）", "Mg（マグネシウム）"],
                "年間量（g/m²）": [
                    results["N"]["annual_value"] / 10,
                    results["P"]["annual_value"] / 10,
                    results["K"]["annual_value"] / 10,
                    results["Ca"]["annual_value"] / 10,
                    results["Mg"]["annual_value"] / 10,
                ],
                "MSLN（g/m²）": [
                    results["N"]["msln"] / 10,
                    results["P"]["msln"] / 10,
                    results["K"]["msln"] / 10,
                    results["Ca"]["msln"] / 10,
                    results["Mg"]["msln"] / 10,
                ],
                "SLAN（g/m²）": [
                    results["N"]["slan"] / 10,
                    results["P"]["slan"] / 10,
                    results["K"]["slan"] / 10,
                    results["Ca"]["slan"] / 10,
                    results["Mg"]["slan"] / 10,
                ],
            }
            st.dataframe(result_data, use_container_width=True, hide_index=True)
        
        with col2:
            st.subheader("MSLN/SLAN内の位置")
            position_data = {
            "成分": ["N", "P", "K", "Ca", "Mg"],
            "位置": [
                results["N"]["position"],
                results["P"]["position"],
                results["K"]["position"],
                results["Ca"]["position"],
                results["Mg"]["position"],
            ],
        }
            st.dataframe(position_data, use_container_width=True, hide_index=True)
        
        # 説明文
        st.subheader("💡 各成分の説明")
        for nutrient in ["N", "P", "K", "Ca", "Mg"]:
            with st.expander(f"{nutrient}（{'窒素' if nutrient == 'N' else 'リン酸' if nutrient == 'P' else 'カリウム' if nutrient == 'K' else 'カルシウム' if nutrient == 'Ca' else 'マグネシウム'}）"):
                st.info(results[nutrient]["explanation"])
        
        st.markdown("---")
        
        # 配分スタンスの説明
        st.info(
        "💡 **月別配分の考え方**\n\n"
        "本アプリでは、芝の生理的成長能（Growth Potential）を基準としつつ、"
        "ゴルフ場管理で一般的な「春先重点・夏期抑制」の施肥戦略を反映するため、"
        "季節ごとの補正係数を用いて月別施肥量を算出しています。"
        "特にゴルフグリーンでは、年間施肥量の約6〜7割を梅雨入り前までに配分する考え方を反映しています。\n\n"
        "管理強度が高いほど、春先に生育基盤を作るため施肥配分のピークが強調されます。"
        "管理強度が低い場合は、生育変動を抑えるため配分を平準化します。\n\n"
        "GP（Growth Potential）は芝が実際に養分を利用できる能力を示します。"
        "本設計では、GPが低い時期は施肥を抑え、"
        "GPが過剰に高い時期は生育暴走を防ぐため制御を行っています。\n\n"
        "植物成長調整剤（PGR）を使用すると、芝の生育速度と刈粕量が低下します。"
        "本設計では、PGR使用強度に応じて、"
        "芝が実際に吸収可能な養分量へ施肥量を調整しています。"
        )
        
        # グラフ表示
        st.header("📈 年間Growth Potential × 施肥配分")
        
        months = ["1月", "2月", "3月", "4月", "5月", "6月", 
              "7月", "8月", "9月", "10月", "11月", "12月"]
        
        # GPデータを取得（気温ベース）
        monthly_gp = st.session_state.get("monthly_gp", [0.5] * 12)
        gp_dict = st.session_state.get("gp_dict", {})
        
        # サブプロット作成
        fig = make_subplots(
            rows=2, cols=1,
            subplot_titles=("Growth Potential", "月別施肥配分（N, P, K, Ca, Mg）"),
            vertical_spacing=0.15,
            row_heights=[0.4, 0.6],
        )
        
        # GPグラフ（気温ベースのGPを優先）
        # monthly_gpが存在する場合、それを使用（WOSの場合を除く）
        # WOSの場合のみ、gp_dictからcoolとwarmの両方を表示
        
        gp_dict = st.session_state.get("gp_dict", {})
        
        if monthly_gp is not None:
            # 気温ベースのGPが存在する場合
            # WOSの場合のみ、coolとwarmの両方を追加表示
            if "cool" in gp_dict and "warm" in gp_dict:
                # WOS：気温ベースのGP（メイン）と、cool/warmの両方を表示
                fig.add_trace(
                go.Scatter(
                    x=months,
                    y=monthly_gp,
                    mode="lines+markers",
                    name="Growth Potential（気温ベース）",
                    line=dict(color="#2c5f2d", width=2),
                    marker=dict(size=8),
                ),
                row=1, col=1,
                )
                fig.add_trace(
                    go.Scatter(
                        x=months,
                        y=gp_dict["cool"],
                        mode="lines+markers",
                        name="寒地型GP",
                        line=dict(color="#2c5f2d", width=2, dash="solid"),
                        marker=dict(size=8),
                    ),
                    row=1, col=1,
                )
                fig.add_trace(
                    go.Scatter(
                        x=months,
                        y=gp_dict["warm"],
                        mode="lines+markers",
                        name="暖地型GP",
                        line=dict(color="#ff6b6b", width=2, dash="dash"),
                        marker=dict(size=8),
                    ),
                    row=1, col=1,
                )
            else:
                # 暖地型・寒地型・日本芝など：気温ベースのGPのみを表示
                # ラベルは芝種に応じて適切な名前に変更
                if "warm" in gp_dict:
                    # 暖地型の場合
                    label = "Growth Potential（暖地型・気温ベース）"
                elif "cool" in gp_dict:
                    # 寒地型の場合
                    label = "Growth Potential（寒地型・気温ベース）"
                else:
                    # その他（日本芝など）
                    label = "Growth Potential（気温ベース）"
                
                fig.add_trace(
                go.Scatter(
                    x=months,
                    y=monthly_gp,
                    mode="lines+markers",
                    name=label,
                    line=dict(color="#2c5f2d", width=2),
                    marker=dict(size=8),
                ),
                row=1, col=1,
                )
        elif "cool" in gp_dict and "warm" in gp_dict:
            # WOS（monthly_gpが存在しない場合のフォールバック）
            fig.add_trace(
            go.Scatter(
                x=months,
                y=gp_dict["cool"],
                mode="lines+markers",
                name="寒地型GP",
                line=dict(color="#2c5f2d", width=2, dash="solid"),
                marker=dict(size=8),
            ),
            row=1, col=1,
            )
            fig.add_trace(
                go.Scatter(
                    x=months,
                    y=gp_dict["warm"],
                    mode="lines+markers",
                    name="暖地型GP",
                    line=dict(color="#ff6b6b", width=2, dash="dash"),
                    marker=dict(size=8),
                ),
                row=1, col=1,
            )
        elif "cool" in gp_dict:
            # 寒地型のみ（monthly_gpが存在しない場合のフォールバック）
            fig.add_trace(
            go.Scatter(
                x=months,
                y=gp_dict["cool"],
                mode="lines+markers",
                name="寒地型GP",
                line=dict(color="#2c5f2d", width=2),
                marker=dict(size=8),
            ),
            row=1, col=1,
            )
        elif "warm" in gp_dict:
            # 暖地型のみ（monthly_gpが存在しない場合のフォールバック）
            fig.add_trace(
            go.Scatter(
                x=months,
                y=gp_dict["warm"],
                mode="lines+markers",
                name="暖地型GP",
                line=dict(color="#ff6b6b", width=2),
                marker=dict(size=8),
            ),
            row=1, col=1,
            )
        else:
            # その他（日本芝など、monthly_gpが存在しない場合のフォールバック）
            fig.add_trace(
            go.Scatter(
                x=months,
                y=gp_values,
                mode="lines+markers",
                name="Growth Potential",
                line=dict(color="#2c5f2d", width=2),
                marker=dict(size=8),
            ),
            row=1, col=1,
        )
        
        fig.update_yaxes(title_text="GP", range=[0, 1], row=1, col=1)
        
        fig.update_yaxes(title_text="GP", range=[0, 1], row=1, col=1)
        
        # 施肥配分グラフ（積み上げバー）
        # kg/haをg/m²に変換（1 ha = 10,000 m², 1 kg = 1,000 g）
        # kg/ha → g/m² = (kg/ha) × 1,000 / 10,000 = (kg/ha) / 10
        monthly_p = st.session_state.get("monthly_p", [0] * 12)
        monthly_k = st.session_state.get("monthly_k", [0] * 12)
        monthly_ca = st.session_state.get("monthly_ca", [0] * 12)
        monthly_mg = st.session_state.get("monthly_mg", [0] * 12)
        
        # kg/haをg/m²に変換
        monthly_n_m2 = [n / 10 for n in monthly_n]
        monthly_p_m2 = [p / 10 for p in monthly_p]
        monthly_k_m2 = [k / 10 for k in monthly_k]
        monthly_ca_m2 = [ca / 10 for ca in monthly_ca]
        monthly_mg_m2 = [mg / 10 for mg in monthly_mg]
        
        fig.add_trace(
            go.Bar(
                x=months,
                y=monthly_n_m2,
                name="N（窒素）",
                marker_color="#4a90e2",
            ),
            row=2, col=1,
        )
        fig.add_trace(
            go.Bar(
                x=months,
                y=monthly_p_m2,
                name="P（リン酸）",
                marker_color="#ff6b6b",
            ),
            row=2, col=1,
        )
        fig.add_trace(
            go.Bar(
                x=months,
                y=monthly_k_m2,
                name="K（カリウム）",
                marker_color="#51cf66",
            ),
            row=2, col=1,
        )
        fig.add_trace(
            go.Bar(
                x=months,
                y=monthly_ca_m2,
                name="Ca（カルシウム）",
                marker_color="#ffd93d",
            ),
            row=2, col=1,
        )
        fig.add_trace(
            go.Bar(
                x=months,
                y=monthly_mg_m2,
                name="Mg（マグネシウム）",
                marker_color="#a29bfe",
            ),
            row=2, col=1,
        )
        
        fig.update_yaxes(title_text="施肥量（g/m²）", row=2, col=1)
        fig.update_xaxes(title_text="月", row=2, col=1)
        fig.update_layout(
            height=700,
            showlegend=True,
            barmode="group",  # グループ化バー
            title_text="年間Growth Potential × 施肥配分",
            title_x=0.5,
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # 月別施肥配分の表
        st.subheader("📋 月別施肥配分量（g/m²）")
        
        # 表データを準備
        monthly_data = {
            "月": months,
            "N（窒素）": [round(n / 10, 3) for n in monthly_n],
            "P（リン酸）": [round(p / 10, 3) for p in monthly_p],
            "K（カリウム）": [round(k / 10, 3) for k in monthly_k],
            "Ca（カルシウム）": [round(ca / 10, 3) for ca in monthly_ca],
            "Mg（マグネシウム）": [round(mg / 10, 3) for mg in monthly_mg],
        }
        st.dataframe(monthly_data, use_container_width=True, hide_index=True)
        
        st.markdown("---")
        
        # PDF出力（一時的に無効化：Streamlit Community Cloud対応）
        # st.header("📄 PDF出力")
        # 
        # if PDF_AVAILABLE and generate_pdf:
        #     if st.button("📥 施肥設計PDFを生成", type="primary", use_container_width=True):
        #         with st.spinner("PDFを生成中..."):
        #             try:
        #                 # セッションからデータを取得
        #                 pdf_results = st.session_state.get("results", results)
        #                 pdf_gp_values = st.session_state.get("gp_values", gp_values)
        #                 pdf_gp_dict = st.session_state.get("gp_dict", {"main": gp_values})
        #                 pdf_monthly_n = st.session_state.get("monthly_n", monthly_n)
        #                 
        #                 # 一時ファイルにPDFを生成
        #                 pdf_path = generate_pdf(
        #                     input_data=st.session_state["input_data"],
        #                     calculation_results=pdf_results,
        #                     gp_values=pdf_gp_values,
        #                     gp_dict=pdf_gp_dict,
        #                     monthly_n=pdf_monthly_n,
        #                 )
        #                 
        #                 # PDFファイルを読み込み
        #                 with open(pdf_path, "rb") as pdf_file:
        #                     pdf_bytes = pdf_file.read()
        #                 
        #                 # ダウンロードボタン
        #                 st.download_button(
        #                     label="📥 PDFをダウンロード",
        #                     data=pdf_bytes,
        #                     file_name=f"施肥設計_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
        #                     mime="application/pdf",
        #                     use_container_width=True,
        #                 )
        #                 
        #                 # 一時ファイルを削除
        #                 os.unlink(pdf_path)
        #                 
        #                 st.success("✅ PDFが生成されました")
        #                 
        #                 # kaleidoがインストールされていない場合の警告
        #                 try:
        #                     import kaleido
        #                 except ImportError:
        #                     st.warning("⚠️ グラフ画像を含めるには、kaleidoパッケージが必要です。以下のコマンドでインストールしてください：\n```bash\npip install -U kaleido\n```")
        #                     
        #             except Exception as e:
        #                 st.error(f"❌ PDF生成エラー: {str(e)}")
        #                 if "kaleido" in str(e).lower():
        #                     st.info("💡 **解決方法**: 以下のコマンドでkaleidoをインストールしてください：\n```bash\npip install -U kaleido\n```")
        #                 st.exception(e)
        # else:
        #     st.info("ℹ️ PDF出力機能は現在利用できません（Streamlit Community Cloud対応のため一時的に無効化されています）")

# フッター
st.markdown("---")
st.markdown("""
<div style="text-align: center; padding: 1rem 0; color: #666;">
    <a href="https://www.turf-tools.jp/" target="_blank" style="text-decoration: none; color: #666;">
        ©グロウアンドプログレス
    </a>
</div>
""", unsafe_allow_html=True)

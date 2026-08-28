"""
ブラウザ Cookie（緯度・経度・芝種）と位置情報取得。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Tuple

import streamlit as st

# Streamlit 1.62+ で st.cache が削除。streamlit-cookies-manager が未更新のため互換。
if not hasattr(st, "cache"):
    st.cache = st.cache_data

if TYPE_CHECKING:
    from streamlit_cookies_manager import CookieManager

COOKIE_LAT = "saved_lat"
COOKIE_LON = "saved_lon"
COOKIE_TURF = "saved_turf"


def create_cookie_manager() -> "CookieManager":
    """
    CookieManager を生成する（実行のたびに1回だけ呼ぶこと）。

    初回はブラウザから Cookie が届くまで ready() が False。
    その場合は st.stop() し、次のランで ready になる（session_state に保持しない）。
    """
    from streamlit_cookies_manager import CookieManager

    return CookieManager(prefix="fert_design/")


def load_prefs_from_cookies(
    cookies: "CookieManager", turf_options: list[str]
) -> Tuple[float, float, int]:
    """Cookie から緯度・経度・芝種インデックスを復元。"""
    lat = 35.0
    lon = 139.0
    turf_index = 0

    try:
        if cookies.get(COOKIE_LAT) is not None:
            lat = float(cookies[COOKIE_LAT])
        if cookies.get(COOKIE_LON) is not None:
            lon = float(cookies[COOKIE_LON])
    except (TypeError, ValueError):
        pass

    lat = max(20.0, min(50.0, lat))
    lon = max(120.0, min(155.0, lon))

    saved_turf = cookies.get(COOKIE_TURF)
    if saved_turf in turf_options:
        turf_index = turf_options.index(saved_turf)

    return lat, lon, turf_index


def save_prefs_to_cookies(
    cookies: "CookieManager",
    latitude: float,
    longitude: float,
    turf_type: str,
) -> None:
    """GP 計算成功時に緯度・経度・芝種を Cookie へ保存。"""
    cookies[COOKIE_LAT] = str(round(latitude, 4))
    cookies[COOKIE_LON] = str(round(longitude, 4))
    cookies[COOKIE_TURF] = turf_type
    cookies.save()


def apply_geolocation_from_query() -> bool:
    """位置取得後のクエリ ?_geo_lat / _geo_lon を1回だけ反映（レガシー）。"""
    qp = st.query_params
    if "_geo_lat" not in qp or "_geo_lon" not in qp:
        return False

    try:
        lat = float(qp["_geo_lat"])
        lon = float(qp["_geo_lon"])
    except (TypeError, ValueError):
        return False

    if not (20.0 <= lat <= 50.0 and 120.0 <= lon <= 155.0):
        st.warning("取得した位置が日本国内の想定範囲外です。手動で修正してください。")

    st.session_state["input_lat"] = round(lat, 4)
    st.session_state["input_lon"] = round(lon, 4)

    for key in ("_geo_lat", "_geo_lon"):
        if key in st.query_params:
            del st.query_params[key]

    return True


def _apply_coords_to_session(lat: float, lon: float) -> bool:
    """緯度経度を session_state に書き込み、変更があれば True。"""
    lat_r = round(lat, 4)
    lon_r = round(lon, 4)
    prev = st.session_state.get("_last_applied_geo")
    current = (lat_r, lon_r)
    if prev == current:
        return False

    st.session_state["input_lat"] = lat_r
    st.session_state["input_lon"] = lon_r
    st.session_state["_last_applied_geo"] = current
    return True


def _parse_geolocation_result(loc: Any) -> Tuple[float, float] | None:
    """streamlit_js_eval の戻り値から緯度経度を取り出す。"""
    if not isinstance(loc, dict):
        return None

    if loc.get("error"):
        err = loc["error"]
        msg = err.get("message", str(err)) if isinstance(err, dict) else str(err)
        st.error(f"位置情報を取得できませんでした: {msg}")
        st.caption(
            "ブラウザのアドレスバー付近で、このサイトの「位置情報」を **許可** にしてください。"
            "（Chrome: 鍵アイコン → サイトの設定 → 位置情報）"
        )
        return None

    coords = loc.get("coords")
    if not isinstance(coords, dict):
        return None

    try:
        return float(coords["latitude"]), float(coords["longitude"])
    except (KeyError, TypeError, ValueError):
        return None


def render_geolocation_trigger() -> None:
    """
    現在地取得（Streamlit 標準ボタン + streamlit-js-eval）。

    streamlit-geolocation は新しい Streamlit でボタンが反応しないことがあるため不採用。
    """
    try:
        from streamlit_js_eval import get_geolocation
    except ImportError:
        st.error("位置情報には streamlit-js-eval が必要です。pip install -r requirements.txt")
        return

    if st.button(
        "📍 現在地を取得",
        help="ブラウザの位置情報を使って緯度・経度欄を埋めます。",
        key="btn_geolocation",
    ):
        st.session_state["geolocation_requested"] = True

    if not st.session_state.get("geolocation_requested"):
        return

    with st.spinner("位置情報を取得しています…"):
        loc = get_geolocation(component_key="fert_geolocation")

    if loc is None:
        st.caption(
            "取得結果を待っています。表示が変わらない場合は、"
            "もう一度「📍 現在地を取得」を押してください。"
        )
        return

    st.session_state["geolocation_requested"] = False

    parsed = _parse_geolocation_result(loc)
    if parsed is None:
        if not (isinstance(loc, dict) and loc.get("error")):
            st.warning("位置情報の形式が想定外です。手動で緯度・経度を入力してください。")
        return

    lat, lon = parsed

    if not (20.0 <= lat <= 50.0 and 120.0 <= lon <= 155.0):
        st.warning(
            f"取得座標（{lat:.4f}, {lon:.4f}）は日本国内の想定範囲外です。"
            "緯度・経度欄で手動修正できます。"
        )

    if _apply_coords_to_session(lat, lon):
        st.session_state["geolocation_success_msg"] = (
            f"位置を反映しました（緯度 {lat:.4f}、経度 {lon:.4f}）"
        )
        st.rerun()

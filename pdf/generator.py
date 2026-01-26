"""
PDF生成ロジック
"""

import os
import tempfile
import base64
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional
from jinja2 import Template
# PDF機能を一時的に無効化（Streamlit Community Cloud対応）
# from xhtml2pdf import pisa
# from reportlab.pdfbase import pdfmetrics
# from reportlab.pdfbase.ttfonts import TTFont
# from reportlab.pdfbase.cidfonts import UnicodeCIDFont
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import platform


def _create_graph_image(
    gp_values: list,
    gp_dict: dict,
    monthly_n: list, 
    monthly_p: list,
    monthly_k: list,
    monthly_ca: list,
    monthly_mg: list,
    months: list,
    monthly_gp: Optional[list] = None,  # 気温ベースのGP
) -> Optional[str]:
    """
    GPと施肥配分のグラフを画像として生成（base64エンコード）
    
    Returns:
        base64エンコードされた画像データ（data URI形式）、またはNone（kaleidoが利用できない場合）
    """
    try:
        fig = make_subplots(
            rows=2, cols=1,
            subplot_titles=("Growth Potential", "月別施肥配分（N, P, K, Ca, Mg）"),
            vertical_spacing=0.15,
            row_heights=[0.4, 0.6],
        )
        
        # GPグラフ（気温ベースのGPを優先）
        # monthly_gpが存在する場合、それを使用（WOSの場合を除く）
        # WOSの場合のみ、gp_dictからcoolとwarmの両方を表示
        
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
        
        # 施肥配分グラフ
        # kg/haをg/m²に変換（1 ha = 10,000 m², 1 kg = 1,000 g）
        # kg/ha → g/m² = (kg/ha) × 1,000 / 10,000 = (kg/ha) / 10
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
            barmode="group",
            title_text="年間Growth Potential × 施肥配分",
            title_x=0.5,
        )
        
        # 画像としてエクスポート（base64）
        img_bytes = fig.to_image(format="png", width=800, height=600)
        img_base64 = base64.b64encode(img_bytes).decode("utf-8")
        return f"data:image/png;base64,{img_base64}"
    except (ValueError, ImportError) as e:
        # kaleidoが利用できない場合はNoneを返す
        if "kaleido" in str(e).lower():
            return None
        raise


# PDF機能を一時的に無効化（Streamlit Community Cloud対応）
def _register_japanese_fonts():
    """
    Windows環境で日本語フォントを登録
    登録されたフォント名を返す
    """
    # PDF機能が無効化されているため、ダミー値を返す
    return None
    # registered_font_name = None
    # 
    # if platform.system() != "Windows":
    #     # Windows以外の場合はCIDフォントを試す
    #     try:
    #         pdfmetrics.registerFont(UnicodeCIDFont("HeiseiKakuGo-W5"))
    #         registered_font_name = "HeiseiKakuGo-W5"
    #     except Exception:
    #         pass
    #     return registered_font_name
    # 
    # # Windowsの標準日本語フォントパス（複数の候補を試す）
    # font_paths = [
    #     (r"C:\Windows\Fonts\msgothic.ttc", "JapaneseFont", 0),
    #     (r"C:\Windows\Fonts\msmincho.ttc", "JapaneseFont", 0),
    #     (r"C:\Windows\Fonts\meiryo.ttc", "JapaneseFont", 0),
    #     (r"C:\Windows\Fonts\yugothic.ttf", "JapaneseFont", None),
    #     (r"C:\Windows\Fonts\msgothic.ttc", "msgothic", 0),
    #     (r"C:\Windows\Fonts\msmincho.ttc", "msmincho", 0),
    #     (r"C:\Windows\Fonts\meiryo.ttc", "meiryo", 0),
    # ]
    # 
    # # 利用可能なフォントを登録
    # for font_path, font_name, subfont_index in font_paths:
    #     if os.path.exists(font_path):
    #         try:
    #             if font_path.endswith(".ttc") and subfont_index is not None:
    #                 pdfmetrics.registerFont(TTFont(font_name, font_path, subfontIndex=subfont_index))
    #             else:
    #                 pdfmetrics.registerFont(TTFont(font_name, font_path))
    #             registered_font_name = font_name
    #             break  # 最初に登録できたフォントを使用
    #         except Exception as e:
    #             continue
    # 
    # # フォントが登録できなかった場合は、ReportLabのデフォルトCIDフォントを使用
    # if not registered_font_name:
    #     try:
    #         pdfmetrics.registerFont(UnicodeCIDFont("HeiseiKakuGo-W5"))
    #         registered_font_name = "HeiseiKakuGo-W5"
    #     except Exception:
    #         try:
    #             pdfmetrics.registerFont(UnicodeCIDFont("HeiseiMin-W3"))
    #             registered_font_name = "HeiseiMin-W3"
    #         except Exception:
    #             pass
    # 
    # return registered_font_name


def generate_pdf(
    input_data: Dict[str, Any],
    calculation_results: Dict[str, Dict],
    gp_values: list,
    gp_dict: dict,
    monthly_n: list,
    output_path: Optional[str] = None
) -> str:
    """
    PDFを生成
    
    Args:
        input_data: 入力データ（芝種区分、利用形態など）
        calculation_results: 計算結果
        gp_values: 12ヶ月分のGP値（メイン）
        gp_dict: GP値の辞書（cool, warmを含む可能性）
        monthly_n: 12ヶ月分のN配分量
        output_path: 出力パス（Noneの場合は一時ファイル）
    
    Returns:
        生成されたPDFファイルのパス
    """
    # 日本語フォントを登録（最初に実行）
    registered_font_name = _register_japanese_fonts()
    
    # HTMLテンプレートを読み込み
    template_path = Path(__file__).parent / "template.html"
    with open(template_path, "r", encoding="utf-8") as f:
        template_content = f.read()
    
    template = Template(template_content)
    
    # データを準備
    months = ["1月", "2月", "3月", "4月", "5月", "6月", 
              "7月", "8月", "9月", "10月", "11月", "12月"]
    
    # GPとN配分のデータを準備（グラフ用）
    gp_n_data = [
        {"month": months[i], "gp": gp_values[i], "n": monthly_n[i]}
        for i in range(12)
    ]
    
    # 月別配分データを取得
    monthly_p = [calculation_results["P"]["monthly"][i] if "monthly" in calculation_results["P"] else 0 for i in range(12)]
    monthly_k = [calculation_results["K"]["monthly"][i] if "monthly" in calculation_results["K"] else 0 for i in range(12)]
    monthly_ca = [calculation_results["Ca"]["monthly"][i] if "monthly" in calculation_results["Ca"] else 0 for i in range(12)]
    monthly_mg = [calculation_results["Mg"]["monthly"][i] if "monthly" in calculation_results["Mg"] else 0 for i in range(12)]
    
    # 月別施肥配分の表データを準備（g/m²単位）
    monthly_fertilizer_data = [
        {
            "month": months[i],
            "n": round(monthly_n[i] / 10, 3),
            "p": round(monthly_p[i] / 10, 3),
            "k": round(monthly_k[i] / 10, 3),
            "ca": round(monthly_ca[i] / 10, 3),
            "mg": round(monthly_mg[i] / 10, 3),
        }
        for i in range(12)
    ]
    
    # グラフ画像を生成（kaleidoが利用できない場合はNone）
    # 気温ベースのGPを取得（結果に含まれている場合）
    monthly_gp = None
    if calculation_results and "N" in calculation_results:
        monthly_gp = calculation_results["N"].get("gp_values")
    
    graph_image = _create_graph_image(
        gp_values, gp_dict, monthly_n, monthly_p, monthly_k, monthly_ca, monthly_mg, months, monthly_gp
    )
    
    # グラフ画像を一時ファイルとして保存（xhtml2pdfはdata URIをサポートしていない可能性があるため）
    graph_file_path = None
    if graph_image:
        try:
            # base64データから画像ファイルを作成
            img_data = base64.b64decode(graph_image.split(",")[1])
            graph_file_path = tempfile.mktemp(suffix=".png")
            with open(graph_file_path, "wb") as img_file:
                img_file.write(img_data)
        except Exception:
            # base64デコードに失敗した場合はgraph_imageをそのまま使用
            graph_file_path = None
    
    # フォント名をテンプレートに渡す
    font_family = registered_font_name if registered_font_name else "HeiseiKakuGo-W5"
    
    html_content = template.render(
        title="芝しごと・施肥設計ナビ",
        creation_date=datetime.now().strftime("%Y年%m月%d日"),
        input_data=input_data,
        calculation_results=calculation_results,
        gp_n_data=gp_n_data,
        monthly_fertilizer_data=monthly_fertilizer_data,
        months=months,
        graph_image=graph_file_path if graph_file_path else (graph_image if graph_image else None),
        has_graph=graph_image is not None,
        font_family=font_family,
    )
    
    # PDF機能を一時的に無効化（Streamlit Community Cloud対応）
    # PDFを生成
    # if output_path is None:
    #     output_path = tempfile.mktemp(suffix=".pdf")
    # 
    #     # xhtml2pdfでPDFを生成
    #     with open(output_path, "wb") as pdf_file:
    #         # CSSでフォントを明示的に指定（PDF出力用の追加設定）
    #         # xhtml2pdfではmm単位が確実に機能する
    #         # 左余白を確保しつつ、日本語の折り返しを確実にする
    #         css_content = f"""
    #         @page {{
    #             size: A4;
    #             margin: 20mm 25mm;
    #         }}
    #         * {{
    #             font-family: "{font_family}", "HeiseiKakuGo-W5", "HeiseiMin-W3", sans-serif !important;
    #             box-sizing: border-box;
    #         }}
    #         html {{
    #             width: 100%;
    #             margin: 0;
    #             padding: 0;
    #             overflow-x: hidden;
    #         }}
    #         body {{
    #             font-family: "{font_family}", "HeiseiKakuGo-W5", "HeiseiMin-W3", sans-serif !important;
    #             width: 100%;
    #             max-width: 100%;
    #             margin: 0;
    #             padding: 0;
    #             overflow: hidden;
    #         }}
    #         div, section, article {{
    #             max-width: 100%;
    #             overflow: hidden;
    #         }}
    #         p, li, span, td, th {{
    #             word-break: break-all;
    #             word-wrap: break-word;
    #             white-space: normal;
    #             overflow: hidden;
    #             max-width: 100%;
    #         }}
    #         table {{
    #             width: 100%;
    #             max-width: 100%;
    #             table-layout: fixed;
    #             overflow: hidden;
    #         }}
    #         """
    #         pisa_status = pisa.CreatePDF(
    #             html_content,
    #             dest=pdf_file,
    #             encoding="utf-8",
    #             default_css=css_content
    #         )
    # 
    # # 一時画像ファイルを削除
    # if graph_file_path and os.path.exists(graph_file_path):
    #     try:
    #         os.unlink(graph_file_path)
    #     except Exception:
    #         pass  # 削除に失敗しても続行
    # 
    # # エラーチェック
    # if pisa_status.err:
    #     raise Exception(f"PDF生成エラー: {pisa_status.err}")
    # 
    # return output_path
    
    # PDF機能が無効化されているため、エラーを発生させる
    raise NotImplementedError("PDF機能は一時的に無効化されています（Streamlit Community Cloud対応のため）")

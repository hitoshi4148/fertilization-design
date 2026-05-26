from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import re
import io

import pdfplumber


@dataclass
class SoilPdfField:
    key: str  # "N","NH4","P","K","Ca","Mg"
    label: str
    raw_value: float
    raw_unit: str  # "mg/100g" or "ppm"
    value_mg100g: float
    confidence: str  # "high" | "medium" | "low"
    source: str  # e.g. "p2 text match", "p4 table match"


@dataclass
class SoilPdfExtract:
    template_id: str  # internal id: "format_a" / "format_b" / "format_c" / "unknown"
    template_label: str  # UI label (no company names)
    fields: List[SoilPdfField]
    notes: List[str]

    def as_rows(self) -> List[Dict[str, Any]]:
        return [
            {
                "項目": f.label,
                "抽出値": f.raw_value,
                "抽出単位": f.raw_unit,
                "換算(mg/100g)": round(f.value_mg100g, 3),
                "信頼度": f.confidence,
                "出典": f.source,
            }
            for f in self.fields
        ]

    def as_soil_inputs(self) -> Dict[str, float]:
        out: Dict[str, float] = {}
        for f in self.fields:
            # UIの入力欄に合わせたキー
            if f.key == "N":
                out["N"] = f.value_mg100g
            elif f.key == "NH4":
                out["NH4"] = f.value_mg100g
            elif f.key == "P":
                out["P"] = f.value_mg100g
            elif f.key == "K":
                out["K"] = f.value_mg100g
            elif f.key == "Ca":
                out["Ca"] = f.value_mg100g
            elif f.key == "Mg":
                out["Mg"] = f.value_mg100g
        return out


def _safe_float(s: str) -> Optional[float]:
    try:
        return float(s.replace(",", "").strip())
    except Exception:
        return None


def _leading_number(raw: Any) -> Optional[float]:
    """'30.0 ▲高い' など分析値セルから先頭の数値だけ取り出す。"""
    if raw is None:
        return None
    m = re.match(r"([\d.,]+)", str(raw).strip())
    if not m:
        return None
    return _safe_float(m.group(1))


def _ppm_to_mg100g(ppm: float) -> float:
    """
    ユーザー仕様:
    1 ppm = 0.001 mg/g
    よって mg/100g = ppm/10
    """
    return ppm / 10.0


def _extract_text_pages(pdf_bytes: bytes) -> List[str]:
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        return [(p.extract_text() or "") for p in pdf.pages]


def detect_template(pages_text: List[str]) -> Tuple[str, str]:
    """
    テンプレート方式: PDFの「形式」を判定し、専用の抽出ルールを適用する。
    UI文言では企業名を出さない。
    """
    all_text = "\n".join(pages_text)
    # 形式A: 「計量項目」「硝酸態窒素」「有効態リン酸」等が出る
    if ("硝酸態窒素" in all_text and "有効態リン酸" in all_text) or ("計量項目" in all_text and "計量結果" in all_text):
        return "format_a", "形式A（mg/100gの計量表）"
    # 形式B: 「分析結果4」「栄養素測定値」「合計PPM」等が出る
    if ("栄養素測定値" in all_text and "合計PPM" in all_text) or ("分析結果4" in all_text and "合計PPM" in all_text):
        return "format_b", "形式B（PPM→mg/100g換算）"
    # 形式C: JA系「診断処方箋」（可給態リン酸・交換性加里等、mg/100g）
    compact = all_text.replace(" ", "").replace("\u3000", "")
    if (
        "診断処方箋" in compact
        or (
            "可給態リン酸" in all_text
            and "交換性加里" in all_text
            and "交換性石灰" in all_text
        )
    ):
        return "format_c", "形式C（JA診断処方箋・mg/100g）"
    return "unknown", "未対応"


def _parse_format_a(pages_text: List[str]) -> SoilPdfExtract:
    all_text = "\n".join(pages_text)
    # 代表的な行をテキストから抜く（表抽出より頑健なことが多い）
    patterns = [
        ("NH4", "アンモニア態窒素", r"アンモニア態窒素\s+([\d.]+)"),
        ("N", "硝酸態窒素", r"硝酸態窒素\s+([\d.]+)"),
        ("P", "有効態リン酸", r"有効態リン酸\s+([\d.]+)"),
        ("K", "加里", r"加里\s+([\d.]+)"),
        ("Ca", "石灰", r"石灰\s+([\d.]+)"),
        ("Mg", "苦土", r"苦土\s+([\d.]+)"),
    ]
    fields: List[SoilPdfField] = []
    for key, label, pat in patterns:
        m = re.search(pat, all_text)
        if not m:
            continue
        v = _safe_float(m.group(1))
        if v is None:
            continue
        fields.append(
            SoilPdfField(
                key=key,
                label=label,
                raw_value=v,
                raw_unit="mg/100g",
                value_mg100g=v,
                confidence="high",
                source="text match",
            )
        )

    notes = [
        "この形式は mg/100g（乾土）表記の項目を直接読み取ります。",
        "数値は候補として表示し、反映前に必ず確認してください。",
    ]
    return SoilPdfExtract(
        template_id="format_a",
        template_label="形式A（mg/100gの計量表）",
        fields=fields,
        notes=notes,
    )


def _parse_format_b(pages_text: List[str]) -> SoilPdfExtract:
    # 「栄養素測定値」ページを優先
    target_text = ""
    for t in pages_text:
        if "栄養素測定値" in t or "分析結果4" in t:
            target_text = t
            break
    if not target_text:
        target_text = "\n".join(pages_text)

    # 形式Bでは「合計PPM」を採用し、mg/100gへ換算する（ppm/10）
    # 例: カルシウム(Ca) 合計PPM 680 680 839 → 最初の 680 を採用
    line_specs = [
        ("Ca", "カルシウム(Ca) 合計", r"カルシウム\(Ca\)\s+合計PPM\s+([\d.,]+)"),
        ("Mg", "マグネシウム(Mg) 合計", r"マグネシウム\(Mg\)\s+合計PPM\s+([\d.,]+)"),
        ("K", "カリウム(K) 合計", r"カリウム\(K\)\s+合計PPM\s+([\d.,]+)"),
        ("P", "リン(P) 合計", r"リン\(P\)\s+合計PPM\s+([\d.,]+)"),
        ("N", "硝酸態(NO3) 可給態", r"硝酸態\(NO\s*3\s*\)\s+可給態PPM\s+([\d.,]+)"),
        ("NH4", "アンモニア態(NH4) 可給態", r"アンモニア態\(NH\s*4\s*\)\s+可給態PPM\s+([\d.,]+)"),
    ]

    fields: List[SoilPdfField] = []
    for key, label, pat in line_specs:
        m = re.search(pat, target_text)
        if not m:
            continue
        v_ppm = _safe_float(m.group(1))
        if v_ppm is None:
            continue
        fields.append(
            SoilPdfField(
                key=key,
                label=label,
                raw_value=v_ppm,
                raw_unit="ppm",
                value_mg100g=_ppm_to_mg100g(v_ppm),
                confidence="medium" if key in ("N", "NH4") else "high",
                source="text match (totalPPM or availablePPM)",
            )
        )

    notes = [
        "この形式は PPM 表記を読み取り、mg/100gへ自動換算します（mg/100g = ppm / 10）。",
        "本アプリでは計算上、形式BのP/K/Ca/Mgは「合計PPM」を換算した値を候補として表示します。",
        "硝酸態・アンモニア態はレポート上で可給態PPMとして記載される場合があり、信頼度を下げています。",
    ]
    return SoilPdfExtract(
        template_id="format_b",
        template_label="形式B（PPM→mg/100g換算）",
        fields=fields,
        notes=notes,
    )


_FORMAT_C_ROW_MAP: Dict[str, Tuple[str, str]] = {
    "硝酸態窒素": ("N", "硝酸態窒素"),
    "可給態硝酸態窒素": ("N", "可給態硝酸態窒素"),
    "アンモニア態窒素": ("NH4", "アンモニア態窒素"),
    "可給態リン酸": ("P", "可給態リン酸"),
    "交換性加里": ("K", "交換性加里"),
    "交換性石灰": ("Ca", "交換性石灰"),
    "交換性苦土": ("Mg", "交換性苦土"),
}


def _parse_format_c_tables(pdf_bytes: bytes) -> List[SoilPdfField]:
    fields: List[SoilPdfField] = []
    seen_keys: set[str] = set()
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            for tbl in page.extract_tables() or []:
                if not tbl or len(tbl) < 2:
                    continue
                header = [str(c or "").strip() for c in tbl[0]]
                if "分析項目" not in header or "分析値" not in header:
                    continue
                try:
                    item_i = header.index("分析項目")
                    unit_i = header.index("単位")
                    val_i = header.index("分析値")
                except ValueError:
                    continue
                for row in tbl[1:]:
                    if not row or item_i >= len(row):
                        continue
                    item = str(row[item_i] or "").strip()
                    spec = _FORMAT_C_ROW_MAP.get(item)
                    if not spec:
                        continue
                    key, label = spec
                    if key in seen_keys:
                        continue
                    unit = str(row[unit_i] or "").strip() if unit_i < len(row) else ""
                    if unit and unit != "mg/100g":
                        continue
                    v = _leading_number(row[val_i] if val_i < len(row) else None)
                    if v is None:
                        continue
                    seen_keys.add(key)
                    fields.append(
                        SoilPdfField(
                            key=key,
                            label=label,
                            raw_value=v,
                            raw_unit="mg/100g",
                            value_mg100g=v,
                            confidence="high",
                            source="analysis table",
                        )
                    )
    return fields


def _parse_format_c_text(pages_text: List[str]) -> List[SoilPdfField]:
    all_text = "\n".join(pages_text)
    patterns = [
        ("N", "硝酸態窒素", r"硝酸態窒素\s+mg/100g\s+([\d.,]+)"),
        ("N", "可給態硝酸態窒素", r"可給態硝酸態窒素\s+mg/100g\s+([\d.,]+)"),
        ("NH4", "アンモニア態窒素", r"アンモニア態窒素\s+mg/100g\s+([\d.,]+)"),
        ("P", "可給態リン酸", r"可給態リン酸\s+mg/100g\s+([\d.,]+)"),
        ("K", "交換性加里", r"交換性加里\s+mg/100g\s+([\d.,]+)"),
        ("Ca", "交換性石灰", r"交換性石灰\s+mg/100g\s+([\d.,]+)"),
        ("Mg", "交換性苦土", r"交換性苦土\s+mg/100g\s+([\d.,]+)"),
    ]
    fields: List[SoilPdfField] = []
    seen_keys: set[str] = set()
    for key, label, pat in patterns:
        if key in seen_keys:
            continue
        m = re.search(pat, all_text)
        if not m:
            continue
        v = _safe_float(m.group(1))
        if v is None:
            continue
        seen_keys.add(key)
        fields.append(
            SoilPdfField(
                key=key,
                label=label,
                raw_value=v,
                raw_unit="mg/100g",
                value_mg100g=v,
                confidence="high",
                source="text match",
            )
        )
    return fields


def _parse_format_c(pdf_bytes: bytes, pages_text: List[str]) -> SoilPdfExtract:
    fields = _parse_format_c_tables(pdf_bytes)
    if not fields:
        fields = _parse_format_c_text(pages_text)
    else:
        # 表に無い項目だけテキストで補完
        have = {f.key for f in fields}
        for f in _parse_format_c_text(pages_text):
            if f.key not in have:
                fields.append(f)

    notes = [
        "この形式は JA 系の診断処方箋から mg/100g（乾土）の分析値を読み取ります。",
        "リン・加里・石灰・苦土を中心に抽出します（レポートに記載がある窒素項目も読み取ります）。",
        "数値は候補として表示し、反映前に必ず確認してください。",
    ]
    return SoilPdfExtract(
        template_id="format_c",
        template_label="形式C（JA診断処方箋・mg/100g）",
        fields=fields,
        notes=notes,
    )


def extract_soil_from_pdf(pdf_bytes: bytes) -> SoilPdfExtract:
    pages_text = _extract_text_pages(pdf_bytes)
    template_id, template_label = detect_template(pages_text)
    if template_id == "format_a":
        return _parse_format_a(pages_text)
    if template_id == "format_b":
        return _parse_format_b(pages_text)
    if template_id == "format_c":
        return _parse_format_c(pdf_bytes, pages_text)

    return SoilPdfExtract(
        template_id="unknown",
        template_label=template_label,
        fields=[],
        notes=[
            "このPDF形式は現在のフェーズ1では未対応です（スキャン画像のみ等）。",
            "手入力での対応をお願いします。",
        ],
    )


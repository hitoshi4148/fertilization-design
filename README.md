# 芝しごと・施肥設計ナビ

芝生管理（ターフマネジメント）分野の業務支援 Web アプリケーション（**v2.0.2**）。

土壌診断値と管理方針をもとに、**NASA POWER** の気温データから算出した **Growth Potential（GP）** と、**MSLN/SLAN** に基づく年間施肥設計・月別配分の目安を表示し、CSV / Excel でエクスポートできます。

## v2.0.2 の主な変更点

- **フッター**: ターフプールへのリンクを `https://www.turf-tools.jp/portal/turfpool/` に更新（Cloudflare Pages / 芝しごとポータル配下の本番 URL）

## v2.0.1 の主な変更点

- **フッター**: 芝しごとシリーズ各アプリへのリンクをロゴ上に追加
- **ブランディング**: グロウアンドプログレスのロゴをフッターに表示し、バージョン表記をリンク下へ移動
- **ファビコン**: ブラウザタブアイコンをグロウアンドプログレスのロゴに変更
- **バナー**: PR・ブログ・YouTube を高さ約 76px・最大幅 720px の **1行3列** に統一（ポータルと同系レイアウト）

## v2.0.0 の主な変更点

### 施肥設計ロジック

- **MSLN/SLAN** 理論に基づく年間設計量（芝種・利用形態・管理強度・土壌目標水準から決定）
- **GP 連動の月別配分**: 年間設計量を GP 配分係数で 1〜12 月に割り振り
- **適正と不足の統合**: N・P・K が土壌適正のときは年間 MSLN/SLAN 量を GP 配分、不足要素は土壌不足分を GP 配分（Ca/Mg は従来どおり不足時のみ月別計画）
- **表示単位を g/㎡ に統一**（月別表・エクスポート・肥料換算の説明。内部計算の一部は従来どおり kg/ha ベース）

### 気温・GP

- **[NASA POWER](https://power.larc.nasa.gov/)** から **前暦年** の月別気温（T2M）を取得し GP を算出
- 緯度・経度は手入力、**現在地取得**（ブラウザ位置情報）、または **Cookie による前回値の復元**
- 緯度・経度・芝種を変更した場合は、再度 **「GP を計算する」** まで施肥設計結果は表示しない（入力の整合性を保持）

### UI

- **段階的操作**: GP 計算 → 土壌入力・施肥設計 → 結果・エクスポート
- **左サイドバー**に「操作の流れ」（①〜⑤）を常時表示
- 土壌分析 **PDF 読み込み（フェーズ1）**: 抽出 → 確認 → 土壌入力欄へ反映（PDF はサーバーに保存しない）

### 土壌分析 PDF（フェーズ1）

| 形式 | 内容 | 備考 |
|------|------|------|
| **形式A** | mg/100g の計量表 | 硝酸態窒素・有効態リン酸・加里・石灰・苦土など |
| **形式B** | PPM 表記 | 合計 PPM を読み取り **mg/100g = ppm ÷ 10** で換算 |
| **形式C** | JA 系「診断処方箋」 | 可給態リン酸・交換性加里・石灰・苦土など（mg/100g） |

- 半自動運用（候補値の確認後に反映）
- **未対応**: スキャン画像のみの PDF、テキストがほとんど無い見本 PDF など（手入力）

テスト用サンプルは `sample/` に配置（`fukuei.pdf`, `ana-lync.pdf`, `dojo_shohosen.pdf` など）。

### デプロイ・その他

- **Render.com** 向け `render.yaml` / `runtime.txt`（Python 3.11.9）
- **PDF レポート出力**（`pdf/`）は引き続き無効（クラウドデプロイ向け）。復活時は `requirements-pdf.txt` を参照

---

## 技術スタック

- **UI**: Streamlit
- **計算ロジック**: Python（`logic/`）
- **気温データ**: NASA POWER API（`logic/nasa_power.py`）
- **PDF 読取**: pdfplumber（`logic/pdf_import/`）
- **グラフ**: Altair
- **エクスポート**: pandas, openpyxl
- **設定の保持**: streamlit-cookies-manager, streamlit-js-eval（緯度・経度・芝種）

> PDF **出力**（施肥設計レポートの生成）は現在無効化されています。復活時は `requirements-pdf.txt` を参照してください。

## ローカル開発

```bash
pip install -r requirements.txt
streamlit run app.py
```

任意: Google Analytics を有効にする場合

```bash
# Windows PowerShell
$env:GA_MEASUREMENT_ID = "G-XXXXXXXXXX"
streamlit run app.py
```

### テスト（任意）

```bash
python -m pytest tests/ -v
```

`pytest` が未インストールの場合は `pip install pytest` のうえ実行してください。

## Render.com へのデプロイ

1. このリポジトリを GitHub 等に push する
2. [Render](https://render.com/) で **New → Blueprint**（`render.yaml` 利用）または **Web Service** を作成
3. **Build Command**: `pip install -r requirements.txt`
4. **Start Command**:
   ```bash
   streamlit run app.py --server.port=$PORT --server.address=0.0.0.0 --server.headless=true
   ```
5. **Environment**（任意）: `GA_MEASUREMENT_ID` = 測定 ID（未設定なら GA 無効）

`render.yaml` と `runtime.txt`（Python 3.11.9）がリポジトリに含まれています。

### 注意（Render 無料プラン）

- 一定時間アクセスがないとスリープし、再起動に数十秒かかることがあります
- Streamlit はメモリを多めに使うため、起動失敗時は Render のインスタンスタイプ（メモリ）を見直してください
- NASA POWER 取得時は外部 API への通信が発生します（タイムアウト・一時障害時はエラー表示）

## プロジェクト構造

```
.
├── app.py                      # Streamlit UI
├── style.css                   # 外観（サイドバー手順など）
├── render.yaml                 # Render デプロイ定義
├── runtime.txt                 # Python バージョン
├── .streamlit/                 # Streamlit 設定
├── logic/
│   ├── design_service.py     # 統合 API（GP + 施肥設計）
│   ├── nasa_power.py           # NASA POWER 気温取得
│   ├── gp_daily.py             # GP 算出（日次気温モデル）
│   ├── gp_temperature.py       # 月別気温からの GP
│   ├── annual_nutrient_model.py # MSLN/SLAN 年間量
│   ├── soil_evaluation.py      # 土壌評価・不足配分・エクスポート行
│   ├── pdf_import/             # 土壌分析 PDF 読み込み
│   └── ...
├── ui/
│   └── prefs.py                # Cookie・位置情報
├── tests/
│   ├── test_design_service.py
│   ├── test_nasa_gp.py
│   └── test_pdf_import.py
├── sample/                     # PDF 読取のテスト用サンプル
└── pdf/                        # PDF 出力（現在無効）
```

### 他アプリ連携（計算 API）

```python
from logic.design_service import DesignInputs, run_design

result = run_design(
    DesignInputs(
        turf_type="寒地型芝",
        management_target="ゴルフグリーン",
        latitude=35.0,
        longitude=139.0,
        allocation_method="春重点50",
        soil={"N": 5.0, "P": 1.5, "K": 20.0, "Ca": 150.0, "Mg": 3.0},
    )
)
payload = result.to_dict()  # JSON 化可能
```

GP を NASA 気温から先に計算する場合は `compute_gp_distribution_from_nasa` / `run_design_with_gp` を利用してください（`logic/design_service.py` 参照）。

## 使用方法（段階的 UI）

左サイドバーの **「操作の流れ」** に沿って進めます。

1. **基本設定** … 芝種・緯度経度（手入力 / **📍 現在地を取得**）・配分方法  
   ※ 緯度・経度・芝種はブラウザ Cookie に保存（前回値を復元）  
   ※ 位置情報はブラウザの許可が必要（`https://` または `localhost`）
2. **「GP を計算する」** … NASA POWER から **前暦年** の月別気温を取得し GP グラフを表示
3. **土壌分析** … 数値を手入力するか、**「土壌分析PDFを読み込む」** で候補値を抽出・確認・反映
4. **「施肥設計を実行する」** … 土壌評価・年間設計の考え方・NPK 月別計画（g/㎡）・CSV/Excel
5. 緯度・経度・芝種を変更した場合は、再度 **GP を計算** するまで下流の結果は非表示

管理対象・施肥重点方式・土壌目標水準は毎回デフォルト（Cookie には保存しません）。

### 土壌分析 PDF の使い方

1. 土壌入力セクションの **「土壌分析PDFを読み込む」** を開く
2. PDF をアップロードし **「PDFから候補値を抽出する」**
3. 判定された形式（A / B / C）と抽出表を確認
4. **「候補値を土壌入力欄へ反映する」** → 必要なら手直ししてから施肥設計を実行

アップロードした PDF はアプリ内で解析するのみで、永続保存は行いません。

## バージョン履歴

| バージョン | 概要 |
|------------|------|
| **2.0.2** | フッターのターフプールリンクを `https://www.turf-tools.jp/portal/turfpool/` に更新 |
| **2.0.1** | フッターに芝しごとアプリリンク・ロゴ、ファビコン差し替え、バナーを1行3列に整理 |
| **2.0.0** | NASA POWER 連動 GP、MSLN/SLAN 年間設計と GP 月別配分、g/㎡ 表示、土壌 PDF 読込（A/B/C）、段階 UI・サイドバー手順、Render デプロイ整備 |
| 1.x | 従来版（本 README 作成時点の main 履歴を参照） |

---

&copy; [グロウアンドプログレス](https://www.turf-tools.jp/) — Soil-Based Fertilization Planner

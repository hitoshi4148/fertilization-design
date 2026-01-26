# 芝しごと・施肥設計ナビ

芝生管理（ターフマネジメント）分野の業務支援Webアプリケーション。

土壌診断値と管理方針をもとに年間施肥設計（N, P, K, Ca, Mg）を可視化・文書化し、PDFとして出力します。

## 技術スタック

- **UI**: Streamlit
- **計算ロジック**: Python（UIから分離）
- **グラフ**: Plotly
- **HTML生成**: Jinja2
- **PDF出力**: Playwright（Chromium）

## セットアップ

```bash
# 依存関係のインストール
pip install -r requirements.txt

# Playwrightのブラウザをインストール
playwright install chromium

# アプリの起動
streamlit run app.py
```

## プロジェクト構造

```
.
├── app.py              # Streamlit UI
├── logic/              # 計算ロジック
│   ├── __init__.py
│   ├── constants.py   # 定数定義
│   ├── gp.py          # Growth Potential計算
│   └── fertilizer.py  # 施肥量計算
├── pdf/               # PDF生成
│   ├── __init__.py
│   ├── template.html  # Jinja2テンプレート
│   └── generator.py   # PDF生成ロジック
└── requirements.txt
```

## 使用方法

1. Streamlitアプリを起動
2. 基本条件（芝種区分、利用形態、管理強度）を入力
3. 成長制御（PGR）設定を選択
4. 土壌診断値（P, K, Ca, Mg）を入力
5. 施肥スタンスを選択
6. 計算結果を確認し、PDFを出力

## 注意事項

- **xhtml2pdf**: PDF生成には`xhtml2pdf`（pisa）を使用します。HTMLから直接PDFを生成するため、外部ブラウザは不要です。
- **Kaleido**: Plotlyのグラフを画像としてエクスポートするために使用します。PDFにグラフを含める場合に必要です。



# Unstuck Checker

Unstuck Checker は、Minecraft などのエージェント行動ログから「スタック（動けない状態）」を検出するための Python スクリプトです。`sample/stuck/**.json` と `sample/unstuck/**.json` に含まれる座標データを比較し、スタック判定に使う閾値の推定や検出を自動化します。

---

## 環境要件

- Python 3.8 以上
- [uv](https://github.com/astral-sh/uv) がインストール済みであること
  ```bash
  pip install uv
  ```
- JSON ファイルは次の構造を持つこと
  ```json
  {
    "episode_id": 1,
    "locations": [
      { "step": 0, "x": 71.5, "y": 63.0, "z": 248.5, "pitch": 0.0, "yaw": 0.0 },
      { "step": 1, "x": 71.5, "y": 63.0, "z": 248.5, "pitch": 0.0, "yaw": -10.0 }
    ]
  }
  ```

---

## フォルダ構成

```
unstuck_checker/
├── readme.md              # 本ドキュメント
├── stuck_tool.py          # コマンドラインツール本体
├── stuck/                 # スタック状態のサンプル JSON
└── unstuck/               # 非スタック状態のサンプル JSON
```

`stuck` と `unstuck` ディレクトリには、ウィンドウ計算に利用する JSON が格納されています。検証用データを自身で用意する場合は、同じ構造で配置してください。

---

## 事前準備

1. 必要であればリポジトリを取得します。
   ```bash
   git clone <repository-url>
   cd unstuck_checker
   ```
2. uv を利用して実行するため、Python に対応した環境を整えます。
3. `sample/stuck` と `sample/unstuck` の glob パターンに合う JSON を配置します。別のディレクトリを使用したい場合は各コマンドのオプションで指定できます。

---

## 使い方

### 1. しきい値を推定する
```bash
uv run python stuck_tool.py suggest --window 10
```
`sample/stuck` と `sample/unstuck` の偏差を比較し、推奨しきい値を計算して表示します。

### 2. スタックを検出する
```bash
uv run python stuck_tool.py detect --window 10 --threshold 0.05
```
指定したしきい値以下の偏差が続いた区間を「stuck」と判定して出力します。

### 3. 推定値で検証する
```bash
uv run python stuck_tool.py verify --window 10 --threshold 0.05
```
推定した値や任意の閾値で検証を行い、結果を確認します。

---

## オプション一覧

| オプション | 説明 | デフォルト |
|------------|------|-------------|
| `--window N` | 偏差を計算する連続ステップ数（例: 10） | 必須 |
| `--threshold T` | stuck 判定の閾値 | detect と verify で必須 |
| `--stuck-glob PATTERN` | stuck 側の JSON ファイルを選ぶ glob パターン | `sample/stuck/**/*.json` |
| `--unstuck-glob PATTERN` | unstuck 側の JSON ファイルを選ぶ glob パターン | `sample/unstuck/**/*.json` |

---

## 留意事項

- step が 0 から始まらないファイルでも、最小の step から連続する N ステップで計算を行います。
- x 軸と z 軸の標準偏差のうち、値が大きいものを判定指標として利用します。
- JSON に欠損や破損がある場合はスキップされます。ファイルの整合性を確認してから実行してください。

---

## ライセンス

このプロジェクトは MIT License（© 2025 Aotumuri）の下で提供されています。詳細はリポジトリ直下の `LICENSE` を参照してください。

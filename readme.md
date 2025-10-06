

# 🧭 Unstuck Checker

このツールは Minecraft などのエージェント行動ログから「スタック（動けない状態）」を自動検出するための Python スクリプトです。  
`sample/stuck/**.json` と `sample/unstuck/**.json` にある座標データを比較し、スタックの閾値を自動的に推定したり、検出したりします。

---

## 📋 必須環境

- Python 3.8 以上  
- [uv](https://github.com/astral-sh/uv) がインストールされていること  
  ```bash
  pip install uv
  ```
- JSON ファイル構造が以下であること：
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

## 🚀 使用方法

### 1️⃣ しきい値を推定する（suggest）
```bash
uv run python stuck_tool.py suggest --window 10
```
- stuck 側（動かない状態）の最大値と unstuck 側（動いている状態）の最小値を比較して、  
  推奨しきい値を自動計算します。

### 2️⃣ スタックを検出する（detect）
```bash
uv run python stuck_tool.py detect --window 10 --threshold 0.05
```
- 指定したしきい値以下の偏差を持つ区間を「stuck」として出力します。

---

## 🧩 オプション一覧

| オプション | 説明 | デフォルト |
|-------------|------|-------------|
| `--window N` | 連続ステップ数（例: 10） | 必須 |
| `--threshold T` | stuck 判定の閾値 | detect モード時に必須 |
| `--stuck-glob` | stuck 側の JSON パス | `sample/stuck/**/*.json` |
| `--unstuck-glob` | unstuck 側の JSON パス | `sample/unstuck/**/*.json` |

---

## 💡 注意点

- step は必ずしも 0 から始まるとは限りません。  
  最小の step から N ステップ分だけ連続して存在するデータを使用します。  
- x, z の標準偏差のうち大きい方を指標として使用しています。  
- JSON が破損している場合や欠損がある場合はスキップされます。

---

## 🧠 推奨ワークフロー

```bash
# しきい値候補を確認
uv run python stuck_tool.py suggest --window 10

# 検出を実行
uv run python stuck_tool.py detect --window 10 --threshold 0.05

# 例: ウィンドウ10、しきい値0.05 で検証
uv run python stuck_tool.py verify --window 10 --threshold 0.05
```
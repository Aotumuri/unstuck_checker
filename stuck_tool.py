#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Stuck 判定・しきい値サジェスト用スクリプト

使い方:
  # しきい値のあたりを知りたい (stuck最大 / unstuck最小)
  python stuck_tool.py suggest --window 10

  # 閾値を指定して stuck 判定
  python stuck_tool.py detect --window 10 --threshold 0.75

オプション:
  --stuck-glob   stuck データのグロブ (default: stuck/**/*.json)
  --unstuck-glob unstuck データのグロブ (default: unstuck/**/*.json)

仕様:
  - 各 JSON は {"episode_id": ..., "locations":[{"step":int,"x":float,"z":float,...}, ...]}
  - "x, z" のみ使用
  - ウィンドウは「最小の step を起点にした連続 N ステップ」
    例: min_step=1, N=10 ならウィンドウ [1..10], [2..11], [3..12], ...
  - ウィンドウ内に欠番があればスキップ
  - 指標 = max(pstdev(x), pstdev(z))
"""

import argparse
import glob
import json
import math
import os
from statistics import pstdev
from typing import Dict, List, Tuple, Iterable, Optional

def load_series_from_json(path: str) -> List[Tuple[int, float, float]]:
    """
    JSON ファイルから (step, x, z) のリストを読み込む。
    不正フォーマットは ValueError。
    """
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if "locations" not in data or not isinstance(data["locations"], list):
        raise ValueError(f"{path}: 'locations' が見つからないか不正です。")
    series = []
    for item in data["locations"]:
        try:
            step = int(item["step"])
            x = float(item["x"])
            z = float(item["z"])
        except Exception as e:
            raise ValueError(f"{path}: locations の要素が不正です: {e}")
        series.append((step, x, z))
    # step で昇順に
    series.sort(key=lambda t: t[0])
    return series

def contiguous_window_metrics(
    series: List[Tuple[int, float, float]],
    window: int,
) -> Iterable[Tuple[int, int, float]]:
    """
    連続する step のウィンドウ（サイズ window）ごとに指標を返す。
    指標は max(pstdev(x), pstdev(z))。
    欠番があればそのウィンドウはスキップ。

    Returns: (start_step, end_step, metric)
    """
    if not series:
        return
    # step -> (x, z) に辞書化
    by_step: Dict[int, Tuple[float, float]] = {s: (x, z) for s, x, z in series}
    steps_sorted = [s for s, _, _ in series]
    min_step, max_step = steps_sorted[0], steps_sorted[-1]
    # 開始は min_step から max_step-window+1 まで
    for start in range(min_step, max_step - window + 2):
        end = start + window - 1
        # 連続性チェック（欠番があればスキップ）
        ok = all((s in by_step) for s in range(start, end + 1))
        if not ok:
            continue
        xs = [by_step[s][0] for s in range(start, end + 1)]
        zs = [by_step[s][1] for s in range(start, end + 1)]
        # 窓サイズが 1 のとき pstdev は 0 とする（statistics.pstdev も 0 を返す）
        metric = max(pstdev(xs), pstdev(zs))
        yield (start, end, metric)

def scan_glob_for_metrics(glob_pattern: str, window: int) -> List[Tuple[str, int, int, float]]:
    """
    グロブに一致する全 JSON からウィンドウごとの metric を収集。
    Returns: list of (path, start_step, end_step, metric)
    """
    results: List[Tuple[str, int, int, float]] = []
    for path in sorted(glob.glob(glob_pattern, recursive=True)):
        if not path.lower().endswith(".json"):
            continue
        try:
            series = load_series_from_json(path)
        except Exception as e:
            print(f"[WARN] 読込失敗: {path}: {e}")
            continue
        for start, end, m in contiguous_window_metrics(series, window):
            results.append((path, start, end, m))
    return results

def longest_contiguous_run(steps: List[int]) -> int:
    """
    steps（昇順想定）中で、連続した整数列の最長長さを返す。
    例: [1,2,3,7,8] -> 3
    """
    if not steps:
        return 0
    longest = 1
    cur = 1
    for i in range(1, len(steps)):
        if steps[i] == steps[i-1] + 1:
            cur += 1
            longest = max(longest, cur)
        else:
            cur = 1
    return longest

def missing_ranges(steps: List[int]) -> List[Tuple[int, int]]:
    """
    steps（昇順想定）における欠番区間を返す。
    例: [1,2,5,6,9] -> [(3,4),(7,8)]
    """
    if not steps:
        return []
    gaps: List[Tuple[int, int]] = []
    for i in range(1, len(steps)):
        expected_next = steps[i-1] + 1
        if steps[i] > expected_next:
            gaps.append((expected_next, steps[i] - 1))
    return gaps

def cmd_diagnose(args: argparse.Namespace) -> None:
    """
    各ファイルについて以下を表示して、なぜウィンドウが取れないか診断しやすくします:
      - 総ステップ数 / 異なる step 数
      - 最小 step / 最大 step
      - 連続最長長さ
      - 欠番の例（最大 5 区間）
    """
    print(f"=== DIAGNOSE (window = {args.window}) ===")
    any_file = False
    for kind, glob_pattern in (("stuck", args.stuck_glob), ("unstuck", args.unstuck_glob)):
        print(f"\n[{kind}] {glob_pattern}")
        paths = sorted(glob.glob(glob_pattern, recursive=True))
        if not paths:
            print("  (一致するファイルがありません)")
            continue
        for path in paths:
            if not path.lower().endswith(".json"):
                continue
            any_file = True
            try:
                series = load_series_from_json(path)
            except Exception as e:
                print(f"  {path}\n    [ERROR] 読込失敗: {e}")
                continue
            steps = [s for s, _, _ in series]
            unique_steps = sorted(set(steps))
            lc = longest_contiguous_run(unique_steps)
            gaps = missing_ranges(unique_steps)
            min_s = unique_steps[0] if unique_steps else None
            max_s = unique_steps[-1] if unique_steps else None
            print(f"  {path}")
            print(f"    steps: total={len(steps)} unique={len(unique_steps)} min={min_s} max={max_s}")
            print(f"    longest contiguous run: {lc}  (必要: {args.window})")
            if lc < args.window:
                print(f"    -> 連続 {args.window} ステップを満たす区間がありません。window を小さくするか、欠番を埋める必要があります。")
            if gaps:
                # 先頭から最大5件だけ表示
                preview = gaps[:5]
                gap_str = ', '.join([f"{a}..{b}" if a != b else f"{a}" for a,b in preview])
                extra = " ..." if len(gaps) > 5 else ""
                print(f"    missing steps: {gap_str}{extra}")
            else:
                print(f"    missing steps: (なし)")
    if not any_file:
        print("\n※ グロブが間違っている可能性があります。--stuck-glob / --unstuck-glob を確認してください。作業ディレクトリも確認してください。")

def cmd_suggest(args: argparse.Namespace) -> None:
    stuck_metrics = scan_glob_for_metrics(args.stuck_glob, args.window)
    unstuck_metrics = scan_glob_for_metrics(args.unstuck_glob, args.window)

    if not stuck_metrics:
        print("[WARN] stuck 側で計算できるウィンドウがありませんでした。")
    if not unstuck_metrics:
        print("[WARN] unstuck 側で計算できるウィンドウがありませんでした。")

    stuck_max = max((m for _, _, _, m in stuck_metrics), default=float("nan"))
    unstuck_min = min((m for _, _, _, m in unstuck_metrics), default=float("nan"))

    print("=== SUGGEST (window = {}) ===".format(args.window))
    print("stuck の指標 最大値: {}".format(stuck_max))
    print("unstuck の指標 最小値: {}".format(unstuck_min))
    if not (math.isnan(stuck_max) or math.isnan(unstuck_min)):
        if stuck_max < unstuck_min:
            mid = (stuck_max + unstuck_min) / 2.0
            print("→ 推奨しきい値の例: {:.6f}（stuck最大 と unstuck最小 の中間）".format(mid))
        else:
            print("※ 注意: stuck最大値 >= unstuck最小値 です。データの見直しやウィンドウサイズの調整を検討してください。")

def cmd_detect(args: argparse.Namespace) -> None:
    # 両方（stuck/unstuck）まとめて走査してもよいし、どちらか片方でも OK。
    all_metrics = []
    all_metrics += scan_glob_for_metrics(args.stuck_glob, args.window)
    all_metrics += scan_glob_for_metrics(args.unstuck_glob, args.window)

    thr = args.threshold
    print("=== DETECT (window = {}, threshold = {}) ===".format(args.window, thr))
    any_flag = False
    for path, start, end, m in all_metrics:
        if m <= thr:
            any_flag = True
            print(f"[STUCK] {path}  steps {start}..{end}  metric={m:.6f}")
    if not any_flag:
        print("→ stuck 判定は見つかりませんでした。")

def cmd_verify(args: argparse.Namespace) -> None:
    """
    ラベル付きデータの妥当性検証:
      - stuck 側: metric <= threshold が期待
      - unstuck 側: metric >  threshold が期待
    期待に合えば [OK] を緑で、不一致なら [NG] を赤で表示。
    最後にサマリーを出力。
    """
    GREEN = "\033[32m"
    RED = "\033[31m"
    YELLOW = "\033[33m"
    RESET = "\033[0m"

    thr = args.threshold
    win = args.window

    # カウント
    ok_stuck = ng_stuck = 0
    ok_unstuck = ng_unstuck = 0

    print(f"=== VERIFY (window = {win}, threshold = {thr}) ===")

    stuck_metrics = scan_glob_for_metrics(args.stuck_glob, win)
    unstuck_metrics = scan_glob_for_metrics(args.unstuck_glob, win)

    log_dir = "log"
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "verify_log.txt")
    with open(log_path, "a", encoding="utf-8") as logf:
        import datetime
        logf.write(f"=== VERIFY START {datetime.datetime.now().isoformat()} ===\n")

        if not stuck_metrics:
            msg = f"{YELLOW}[WARN]{RESET} stuck 側で評価可能なウィンドウがありません。"
            print(msg)
            logf.write("[WARN] stuck 側で評価可能なウィンドウがありません。\n")
        for path, start, end, m in stuck_metrics:
            if m <= thr:
                ok_stuck += 1
                msg = f"{GREEN}[OK]{RESET}[stuck]   {path}  steps {start}..{end}  metric={m:.6f}  (<= {thr})"
                print(msg)
                logf.write(f"[OK][stuck]   {path}  steps {start}..{end}  metric={m:.6f}  (<= {thr})\n")
            else:
                ng_stuck += 1
                msg = f"{RED}[NG]{RESET}[stuck]   {path}  steps {start}..{end}  metric={m:.6f}  expected <= {thr}"
                print(msg)
                logf.write(f"[NG][stuck]   {path}  steps {start}..{end}  metric={m:.6f}  expected <= {thr}\n")

        # unstuck 側
        if not unstuck_metrics:
            msg = f"{YELLOW}[WARN]{RESET} unstuck 側で評価可能なウィンドウがありません。"
            print(msg)
            logf.write("[WARN] unstuck 側で評価可能なウィンドウがありません。\n")
        for path, start, end, m in unstuck_metrics:
            if m > thr:
                ok_unstuck += 1
                msg = f"{GREEN}[OK]{RESET}[unstuck] {path}  steps {start}..{end}  metric={m:.6f}  (> {thr})"
                print(msg)
                logf.write(f"[OK][unstuck] {path}  steps {start}..{end}  metric={m:.6f}  (> {thr})\n")
            else:
                ng_unstuck += 1
                msg = f"{RED}[NG]{RESET}[unstuck] {path}  steps {start}..{end}  metric={m:.6f}  expected > {thr}"
                print(msg)
                logf.write(f"[NG][unstuck] {path}  steps {start}..{end}  metric={m:.6f}  expected > {thr}\n")

        total_ok = ok_stuck + ok_unstuck
        total_ng = ng_stuck + ng_unstuck
        total = total_ok + total_ng
        acc = (total_ok / total * 100.0) if total > 0 else 0.0

        print("\n--- SUMMARY ---")
        print(f"stuck   : OK={ok_stuck}  NG={ng_stuck}")
        print(f"unstuck : OK={ok_unstuck}  NG={ng_unstuck}")
        print(f"overall : OK={total_ok}  NG={total_ng}  ACC={acc:.2f}%")

        logf.write(f"--- SUMMARY ---\n")
        logf.write(f"stuck   : OK={ok_stuck}  NG={ng_stuck}\n")
        logf.write(f"unstuck : OK={ok_unstuck}  NG={ng_unstuck}\n")
        logf.write(f"overall : OK={total_ok}  NG={total_ng}  ACC={acc:.2f}%\n")
        logf.write(f"=== VERIFY END ===\n\n")

def main():
    parser = argparse.ArgumentParser(description="Stuck 判定 & しきい値サジェストツール")
    sub = parser.add_subparsers(dest="cmd", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--window", type=int, required=True, help="確認する連続ステップ数 N（例: 10）")
    common.add_argument(
        "--stuck-glob",
        type=str,
        default="stuck/**/*.json",
        help="stuck 側 JSON のグロブパターン",
    )
    common.add_argument(
        "--unstuck-glob",
        type=str,
        default="unstuck/**/*.json",
        help="unstuck 側 JSON のグロブパターン",
    )

    p_suggest = sub.add_parser("suggest", parents=[common], help="stuck最大 / unstuck最小 を算出して表示")
    p_suggest.set_defaults(func=cmd_suggest)

    p_detect = sub.add_parser("detect", parents=[common], help="与えた閾値以下を stuck 判定として列挙")
    p_detect.add_argument("--threshold", type=float, required=True, help="stuck 判定の閾値")
    p_detect.set_defaults(func=cmd_detect)

    p_verify = sub.add_parser("verify", parents=[common], help="ラベルと閾値で期待通りに分類できるか検証（色付きログ）")
    p_verify.add_argument("--threshold", type=float, required=True, help="分類に用いる閾値")
    p_verify.set_defaults(func=cmd_verify)

    p_diagnose = sub.add_parser("diagnose", parents=[common], help="ファイルごとの連続長や欠番を表示して原因を診断")
    p_diagnose.set_defaults(func=cmd_diagnose)

    args = parser.parse_args()
    if args.window <= 0:
        raise SystemExit("--window は正の整数にしてください。")
    args.func(args)

if __name__ == "__main__":
    main()
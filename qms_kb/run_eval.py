"""跑评测：python -m qms_kb.run_eval"""

import csv
import json
import os
from collections import defaultdict

from .assistant import Assistant
from .docs import DOCS, LEVELS
from .evalset import E, HOLDOUT

REFUSE = ("NOT_FOUND", "NO_PERMISSION")
LEVEL_OF = {d.doc_id: d.level for d in DOCS}


def judge(item, rec):
    a = rec["answer"]
    refused = a in REFUSE
    stale = any(b in a for b in item["ban"]) and item["type"] in ("version",)
    leaked = False
    if item["type"] == "permission":
        leaked = (not refused) and (any(b in a for b in item["ban"]) or any(
            LEVELS[LEVEL_OF[c.split("@")[0]]] > LEVELS[item["user"].clearance] for c in rec["cited"]))
    if item["type"] in ("permission", "none"):
        correct = refused
    else:
        correct = (not refused) and all(m in a for m in item["must"]) and not any(b in a for b in item["ban"])
    cite_ok = None
    if correct and item["cite"]:
        cite_ok = any(c.startswith(item["cite"]) for c in rec["cited"])
    return dict(correct=correct, refused=refused, stale=stale, leaked=leaked, cite_ok=cite_ok)


def run(out_dir="results"):
    os.makedirs(out_dir, exist_ok=True)
    rows, summary = [], {}
    for mode in ("baseline", "filters", "full"):
        log = os.path.join(out_dir, f"audit_{mode}.jsonl")
        if os.path.exists(log):
            os.remove(log)
        bot = Assistant(mode=mode, log_path=log)
        agg = defaultdict(lambda: defaultdict(int))
        for it in E:
            rec = bot.ask(it["q"], it["user"])
            j = judge(it, rec)
            rows.append(dict(mode=mode, id=it["id"], type=it["type"], user=it["user"].role,
                             question=it["q"], answer=rec["answer"], **j))
            for key in ("all", it["type"]):
                a = agg[key]
                a["n"] += 1
                a["correct"] += j["correct"]
                a["stale"] += j["stale"]
                a["leaked"] += j["leaked"]
                if j["cite_ok"] is not None:
                    a["cite_n"] += 1
                    a["cite_ok"] += j["cite_ok"]
        summary[mode] = {k: dict(v) for k, v in agg.items()}

    with open(os.path.join(out_dir, "per_question.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    with open(os.path.join(out_dir, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    def pct(a, b):
        return f"{100 * a / b:.0f}%" if b else "–"

    names = {"baseline": "只用相似度检索", "filters": "+ 权限/版本过滤 + 混合检索", "full": "+ 可答性门槛（完整版）"}
    lines = ["| 管线 | 总准确率 | 版本题答对 | 答成旧版数值 | 越权泄露 | 无答案题正确拒答 | 引用正确 |",
             "|---|---|---|---|---|---|---|"]
    for m in ("baseline", "filters", "full"):
        s = summary[m]
        al, v, p, x = s["all"], s.get("version", {}), s.get("permission", {}), s.get("none", {})
        lines.append(f"| {names[m]} | {pct(al['correct'], al['n'])} | {pct(v.get('correct', 0), v.get('n', 0))} | "
                     f"{v.get('stale', 0)}/{v.get('n', 0)} | {p.get('leaked', 0)}/{p.get('n', 0)} | "
                     f"{pct(x.get('correct', 0), x.get('n', 0))} | {pct(al.get('cite_ok', 0), al.get('cite_n', 0))} |")
    hold = ["", "| 管线 | 留出集准确率（12 题，未调参） |", "|---|---|"]
    for m in ("baseline", "filters", "full"):
        bot = Assistant(mode=m)
        ok = sum(judge(it, bot.ask(it["q"], it["user"]))["correct"] for it in HOLDOUT)
        hold.append(f"| {names[m]} | {ok}/{len(HOLDOUT)} |")
    table = "\n".join(lines + hold)
    with open(os.path.join(out_dir, "report.md"), "w", encoding="utf-8") as f:
        f.write(f"# 评测结果（{len(E)} 题）\n\n{table}\n")
    print(table)
    return summary


if __name__ == "__main__":
    run()

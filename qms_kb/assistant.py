"""问答管线：权限过滤 → 版本过滤 → 混合检索 → 可答性门槛 → 带出处的回答 → 审计日志。"""

import hashlib
import json
import os
import re
import time
from dataclasses import dataclass

from .docs import DOCS, LEVELS, chunk_docs
from .retrieve import HybridRetriever, VectorOnlyRetriever, grams

PIPELINE_VERSION = "qms-kb 0.1"
HISTORY_RE = re.compile(r"旧版|历史|之前|以前|变更前|修订前|1\.0 ?版|第一版|改了什么|变更")
STOPCHARS = set("的了吗呢是在和与及或对为把被有没个几一下请问我们你他这那要求规定后时候么呀吧啊里")
FILLER = re.compile(r"应该|怎么|什么|多少|哪个|哪些|之前|是不是|有没有")
SYNONYMS = {"超标": "超过", "判定": "判", "这一批": "该批", "根本原因": "根因", "原因": "根因", "存放": "储存", "保存": "储存", "牛": "N"}
CODE_TOKEN = re.compile(r"[A-Za-z]+(?:-[A-Za-z0-9]+)+|[A-Za-z]+\d*")


@dataclass
class User:
    name: str
    role: str
    clearance: str   # 公开 / 内部 / 机密


def kb_fingerprint(docs=DOCS) -> str:
    raw = json.dumps([(d.doc_id, d.version, d.status) for d in docs], ensure_ascii=False)
    return hashlib.sha1(raw.encode()).hexdigest()[:10]


def sentences(text):
    return [s for s in re.split(r"(?<=[。；])", text) if s.strip()]


def content_grams(q):
    """问题里有信息量的中文二元组：去掉编号、标点和虚词，同义词换成文档用语。"""
    for a, b in SYNONYMS.items():
        q = q.replace(a, b)
    q = CODE_TOKEN.sub(" ", q)
    q = FILLER.sub(" ", q)
    q = re.sub(r"[？?，,。！!、：:]", " ", q)
    out = set()
    for part in q.split():
        for i in range(len(part) - 1):
            g = part[i:i + 2]
            if not (set(g) & STOPCHARS):
                out.add(g)
    return out


class Assistant:
    def __init__(self, mode="full", min_coverage=0.45, log_path=None, generator="extractive"):
        """mode: full = 权限+版本+混合检索+门槛；filters = 权限+版本+混合检索，无门槛；baseline = 只有向量检索。"""
        self.mode = mode
        self.min_coverage = min_coverage
        self.chunks = chunk_docs()
        self.retriever = VectorOnlyRetriever(self.chunks) if mode == "baseline" else HybridRetriever(self.chunks)
        self.log_path = log_path
        self.generator = generator
        self.kb_version = kb_fingerprint()
        self.known_ids = {d.doc_id: d.level for d in DOCS}

    # ---------- 过滤 ----------
    def allowed(self, user, q):
        history = bool(HISTORY_RE.search(q))

        def ok(c):
            if LEVELS[c.level] > LEVELS[user.clearance]:
                return False
            if c.status == "superseded" and not history:
                return False
            return True
        return ok, history

    # ---------- 主流程 ----------
    def ask(self, q, user):
        t0 = time.time()
        if self.mode == "baseline":
            hits = self.retriever.search(q, k=5)
            history = False
        else:
            ok, history = self.allowed(user, q)
            # 点名了一份存在但无权查看的文件：明确说无权限，不泄露内容
            for did, lvl in self.known_ids.items():
                if did in q and LEVELS[lvl] > LEVELS[user.clearance]:
                    return self._finish(q, user, [], "NO_PERMISSION", [], t0, history,
                                        reason=f"{did} 密级为{lvl}，超出当前权限")
            hits = self.retriever.search(q, k=5, allowed=ok)

        if not hits:
            return self._finish(q, user, hits, "NOT_FOUND", [], t0, history, reason="无可检索内容")

        if self.mode == "full":
            corpus = " ".join(c.doc_id + c.text for c in self.chunks)
            unknown = [t for t in re.findall(r"[A-Z]{2,}-[A-Z0-9-]+", q) if t not in corpus]
            if unknown:
                return self._finish(q, user, hits, "NOT_FOUND", [], t0, history,
                                    reason=f"资料库中没有 {','.join(unknown)}")

        if self.mode == "full":
            cov = self._coverage(q, hits[:3])
            if cov < self.min_coverage:
                return self._finish(q, user, hits, "NOT_FOUND", [], t0, history,
                                    reason=f"关键词覆盖率 {cov:.2f} < {self.min_coverage}")

        if self.generator == "llm":
            answer, cites = self._llm(q, hits[:4])
        else:
            answer, cites = self._extract(q, hits[:3], history)
        return self._finish(q, user, hits, answer, cites, t0, history)

    def _coverage(self, q, hits):
        need = content_grams(q)
        if not need:
            return 0.0
        have = set()
        for c, _ in hits:
            have |= set(grams(c.title + c.heading + c.text + c.doc_id))
        return len(need & have) / len(need)

    def _extract(self, q, hits, history):
        """抽取式回答：句子得分 = 命中关键词的稀有度之和（标题命中加权），选最高的一句并标出处。"""
        need = content_grams(q)
        cands = []
        for rank, (c, _) in enumerate(hits):
            for s in sentences(c.text):
                cands.append((rank, s.strip(), c))
        df = {g: sum(1 for _, s, _ in cands if g in s) for g in need}
        hdf = {g: len({c.chunk_id for _, _, c in cands if g in c.heading}) for g in need}
        best = []
        for rank, s, c in cands:
            g_s, g_h = set(grams(s + c.title)), set(grams(c.heading))
            score = sum(1 / (1 + df[g]) for g in need if g in g_s) + sum(1 for g in need if g in g_h and hdf[g] == 1)
            score += (0.3 if rank == 0 else 0) + (3 if c.doc_id in q else 0)
            best.append((score, rank, s, c))
        best.sort(key=lambda x: (-x[0], x[1]))
        _, _, sent, c = best[0]
        tag = "【已作废版本】" if c.status == "superseded" else ""
        return f"{tag}{sent}［{c.cite()}］", [c.chunk_id]

    def _llm(self, q, hits):
        """可选：接本地模型（Ollama / vLLM 的 OpenAI 兼容接口）。环境变量 LLM_BASE_URL、LLM_MODEL。"""
        import requests
        ctx = "\n".join(f"[{c.chunk_id}]（{c.status}，生效 {c.effective_date}）{c.title} {c.heading}：{c.text}" for c, _ in hits)
        sys = ("你是医疗器械质量体系资料助手。只能根据给定片段回答；每个事实后用方括号标注片段 id；"
               "只引用 status 为 effective 的片段，除非用户明确问历史版本；找不到依据就只回答 NOT_FOUND。")
        r = requests.post(os.environ.get("LLM_BASE_URL", "http://localhost:11434/v1") + "/chat/completions",
                          json={"model": os.environ.get("LLM_MODEL", "qwen2.5:7b"), "temperature": 0,
                                "messages": [{"role": "system", "content": sys},
                                             {"role": "user", "content": f"片段：\n{ctx}\n\n问题：{q}"}]},
                          timeout=120)
        text = r.json()["choices"][0]["message"]["content"].strip()
        cites = re.findall(r"\[([^\]]+@[^\]]+)\]", text)
        return text, cites

    def _finish(self, q, user, hits, answer, cites, t0, history, reason=""):
        rec = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "user": user.name, "role": user.role, "clearance": user.clearance,
            "question": q, "answer": answer, "cited": cites,
            "retrieved": [{"chunk": c.chunk_id, "status": c.status, "level": c.level} for c, _ in hits],
            "history_mode": history, "reason": reason,
            "pipeline": f"{PIPELINE_VERSION}/{self.mode}/{self.generator}",
            "kb_version": self.kb_version, "latency_ms": round((time.time() - t0) * 1000, 1),
        }
        if self.log_path:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        return rec

"""检索：中文按字的 1-2 gram 做 BM25 + TF-IDF 余弦，用 RRF 合并；文件编号等精确词单独加分。"""

import math
import re
from collections import Counter

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

CODE_RE = re.compile(r"[A-Z]{2,}(?:-[A-Z0-9]+)+|[A-Z]{2}-\d+|\d+(?:\.\d+)?\s*(?:N|cP|mL|°C|秒|支)")


def grams(text: str):
    t = re.sub(r"\s+", "", text.lower())
    return list(t) + [t[i:i + 2] for i in range(len(t) - 1)]


class BM25:
    def __init__(self, docs, k1=1.5, b=0.75):
        self.toks = [grams(d) for d in docs]
        self.k1, self.b = k1, b
        self.avg = sum(len(t) for t in self.toks) / max(len(self.toks), 1)
        df = Counter()
        for t in self.toks:
            df.update(set(t))
        n = len(self.toks)
        self.idf = {w: math.log(1 + (n - c + 0.5) / (c + 0.5)) for w, c in df.items()}
        self.tf = [Counter(t) for t in self.toks]

    def scores(self, q):
        qt = grams(q)
        out = []
        for tf, toks in zip(self.tf, self.toks):
            s = 0.0
            for w in qt:
                if w in tf:
                    f = tf[w]
                    s += self.idf[w] * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * len(toks) / self.avg))
            out.append(s)
        return np.array(out)


def chunk_text(c):
    return f"{c.title} {c.heading} {c.text} {c.doc_id}"


class HybridRetriever:
    """两路检索 + RRF 合并 + 精确词加分。"""

    def __init__(self, chunks):
        self.chunks = chunks
        texts = [chunk_text(c) for c in chunks]
        self.bm25 = BM25(texts)
        self.tfidf = TfidfVectorizer(analyzer="char", ngram_range=(1, 3))
        self.mat = self.tfidf.fit_transform(texts)
        self.texts = texts

    def search(self, q, k=5, allowed=None, rrf_k=60):
        idx = [i for i, c in enumerate(self.chunks) if allowed is None or allowed(c)]
        if not idx:
            return []
        b = self.bm25.scores(q)[idx]
        v = (self.mat[idx] @ self.tfidf.transform([q]).T).toarray().ravel()
        rank_b = {idx[j]: r for r, j in enumerate(np.argsort(-b))}
        rank_v = {idx[j]: r for r, j in enumerate(np.argsort(-v))}
        codes = [x.replace(" ", "") for x in CODE_RE.findall(q)]
        scored = []
        for i in idx:
            s = 1 / (rrf_k + rank_b[i]) + 1 / (rrf_k + rank_v[i])
            if codes and any(code in self.texts[i].replace(" ", "") for code in codes):
                s += 0.02   # 文件编号、型号、数值单位等精确命中
            scored.append((s, i))
        scored.sort(reverse=True)
        return [(self.chunks[i], s) for s, i in scored[:k]]


class VectorOnlyRetriever:
    """对照组：只用 TF-IDF 相似度，不做权限、版本过滤。"""

    def __init__(self, chunks):
        self.chunks = chunks
        self.tfidf = TfidfVectorizer(analyzer="char", ngram_range=(1, 3))
        self.mat = self.tfidf.fit_transform([chunk_text(c) for c in chunks])

    def search(self, q, k=5, allowed=None):
        v = (self.mat @ self.tfidf.transform([q]).T).toarray().ravel()
        order = np.argsort(-v)[:k]
        return [(self.chunks[i], float(v[i])) for i in order]

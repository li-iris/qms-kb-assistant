"""LangChain 版问答链：Milvus 向量检索 + BM25 两路召回 → 重排合并 → Qwen（本地 vLLM / Ollama）带引用生成。

本地起模型（二选一，数据不出内网）：
    vllm serve Qwen/Qwen2.5-7B-Instruct --port 8000           # GPU 服务器
    ollama pull qwen2.5:7b                                     # 笔记本
然后：
    export LLM_BASE_URL=http://localhost:8000/v1 LLM_MODEL=Qwen/Qwen2.5-7B-Instruct
"""

import os
import re

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from qms_kb.assistant import HISTORY_RE, User
from qms_kb.docs import LEVELS, chunk_docs
from qms_kb.retrieve import HybridRetriever
from stack.milvus_index import search as vector_search

PROMPT = ChatPromptTemplate.from_messages([
    ("system", "你是医疗器械质量体系资料助手。规则：\n"
               "1. 只根据给定片段回答，每个事实后用［片段id］标注出处；\n"
               "2. 片段里没有依据时，只回答：NOT_FOUND；\n"
               "3. 若引用了 status=superseded 的片段，必须写明「该内容来自已作废版本」；\n"
               "4. 回答控制在三句话以内。"),
    ("user", "片段：\n{context}\n\n问题：{question}"),
])

_chunks = {c.chunk_id: c for c in chunk_docs()}
_bm25 = HybridRetriever(list(_chunks.values()))


def retrieve(q, user: User, k=5):
    """两路召回，RRF 合并。两路都在检索前按权限 / 版本过滤。"""
    history = bool(HISTORY_RE.search(q))
    allowed = lambda c: LEVELS[c.level] <= LEVELS[user.clearance] and (history or c.status == "effective")  # noqa: E731
    lex = [c.chunk_id for c, _ in _bm25.search(q, k=10, allowed=allowed)]
    vec = [cid for cid, _, _ in vector_search(q, user.clearance, history, k=10)]
    score = {}
    for lst in (lex, vec):
        for r, cid in enumerate(lst):
            score[cid] = score.get(cid, 0) + 1 / (60 + r)
    top = sorted(score, key=score.get, reverse=True)[:k]
    return [_chunks[c] for c in top]


def build_chain():
    llm = ChatOpenAI(base_url=os.environ.get("LLM_BASE_URL", "http://localhost:11434/v1"),
                     model=os.environ.get("LLM_MODEL", "qwen2.5:7b"), api_key="local", temperature=0)
    return PROMPT | llm | StrOutputParser()


def answer(q, user: User):
    hits = retrieve(q, user)
    ctx = "\n".join(f"［{c.chunk_id}］(status={c.status}, 生效 {c.effective_date}) {c.title} {c.heading}：{c.text}"
                    for c in hits)
    text = build_chain().invoke({"context": ctx, "question": q})
    cited = re.findall(r"［([^］]+)］", text)
    # 生成后校验：引用的片段必须在本次检索结果里，否则视为幻觉引用
    valid = {c.chunk_id for c in hits}
    return {"answer": text, "cited": cited, "invalid_citations": [c for c in cited if c not in valid],
            "retrieved": [c.chunk_id for c in hits]}

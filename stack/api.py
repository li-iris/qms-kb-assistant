"""FastAPI 服务：POST /ask。身份从网关传来的请求头读取（演示用，真实环境接 SSO）。

    uvicorn stack.api:app --port 9000
    curl -X POST localhost:9000/ask -H 'X-User: 张工' -H 'X-Clearance: 内部' \
         -H 'Content-Type: application/json' -d '{"question": "注射力测试每批抽多少支？"}'
"""

import json
import time
import uuid

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

from qms_kb.assistant import Assistant, User
from qms_kb.docs import LEVELS

app = FastAPI(title="QMS 文档问答")
rule_bot = Assistant(mode="full")          # 规则版：离线可用，作为兜底


class Ask(BaseModel):
    question: str
    use_llm: bool = False


@app.post("/ask")
def ask(body: Ask, x_user: str = Header(...), x_clearance: str = Header(...)):
    if x_clearance not in LEVELS:
        raise HTTPException(400, "未知密级")
    user = User(x_user, "", x_clearance)
    rid = uuid.uuid4().hex[:12]
    if body.use_llm:
        from stack.rag_chain import answer
        out = answer(body.question, user)
    else:
        rec = rule_bot.ask(body.question, user)
        out = {"answer": rec["answer"], "cited": rec["cited"],
               "retrieved": [r["chunk"] for r in rec["retrieved"]]}
    with open("audit_api.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps({"id": rid, "ts": time.time(), "user": x_user, "clearance": x_clearance,
                            "question": body.question, **out}, ensure_ascii=False) + "\n")
    return {"request_id": rid, **out}

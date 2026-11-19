"""bge-m3 向量化 + Milvus Lite 建库。权限和版本在向量库里用标量字段过滤，检索前就生效。

    pip install -r requirements-stack.txt
    python -m stack.milvus_index          # 生成 qms.db（Milvus Lite 本地文件）
"""

from pymilvus import DataType, MilvusClient
from sentence_transformers import SentenceTransformer

from qms_kb.docs import LEVELS, chunk_docs

DB, COL = "qms.db", "qms_chunks"
_model = None


def embedder():
    global _model
    if _model is None:
        _model = SentenceTransformer("BAAI/bge-m3")
    return _model


def build():
    chunks = chunk_docs()
    texts = [f"{c.title} {c.heading} {c.text}" for c in chunks]
    vecs = embedder().encode(texts, normalize_embeddings=True)
    client = MilvusClient(DB)
    if client.has_collection(COL):
        client.drop_collection(COL)
    schema = client.create_schema(auto_id=False)
    schema.add_field("id", DataType.VARCHAR, is_primary=True, max_length=64)
    schema.add_field("vec", DataType.FLOAT_VECTOR, dim=vecs.shape[1])
    schema.add_field("doc_id", DataType.VARCHAR, max_length=32)
    schema.add_field("version", DataType.VARCHAR, max_length=8)
    schema.add_field("status", DataType.VARCHAR, max_length=16)
    schema.add_field("level", DataType.INT64)
    schema.add_field("text", DataType.VARCHAR, max_length=2048)
    idx = client.prepare_index_params()
    idx.add_index("vec", index_type="HNSW", metric_type="IP", params={"M": 16, "efConstruction": 200})
    client.create_collection(COL, schema=schema, index_params=idx)
    client.insert(COL, [{"id": c.chunk_id, "vec": v.tolist(), "doc_id": c.doc_id, "version": c.version,
                         "status": c.status, "level": LEVELS[c.level], "text": t}
                        for c, v, t in zip(chunks, vecs, texts)])
    print(f"写入 {len(chunks)} 个片段 → {DB}")


def search(q, clearance="内部", history=False, k=5):
    client = MilvusClient(DB)
    expr = f"level <= {LEVELS[clearance]}" + ("" if history else ' and status == "effective"')
    v = embedder().encode([q], normalize_embeddings=True)[0].tolist()
    res = client.search(COL, data=[v], filter=expr, limit=k,
                        output_fields=["doc_id", "version", "status", "text"], search_params={"ef": 64})
    return [(h["id"], h["distance"], h["entity"]) for h in res[0]]


if __name__ == "__main__":
    build()
    for hit in search("注射力测试每批抽多少支？"):
        print(hit[0], round(hit[1], 3))

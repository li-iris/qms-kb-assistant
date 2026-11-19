import json
import os
import tempfile
import unittest

from qms_kb.assistant import Assistant, User
from qms_kb.docs import chunk_docs

QC = User("t", "质检员", "内部")
OPS = User("t", "客服", "公开")
QM = User("t", "质量经理", "机密")


class TestKB(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bot = Assistant(mode="full")

    def test_chunks_carry_metadata(self):
        c = chunk_docs()[0]
        self.assertTrue(c.version and c.status and c.level and c.effective_date)

    def test_superseded_excluded_by_default(self):
        r = self.bot.ask("注射力测试每批抽多少支？", QC)
        self.assertIn("32", r["answer"])
        self.assertTrue(all(x["status"] == "effective" for x in r["retrieved"]))

    def test_history_question_marks_superseded(self):
        r = self.bot.ask("旧版注射力测试规程每批抽多少支？", QC)
        self.assertIn("已作废", r["answer"])

    def test_named_restricted_doc_refused(self):
        r = self.bot.ask("RM-AI01 识别了多少项危害？", QC)
        self.assertEqual(r["answer"], "NO_PERMISSION")

    def test_clearance_filter(self):
        r = self.bot.ask("提示音不响的根本原因是什么？", QC)
        self.assertTrue(all(x["level"] != "机密" for x in r["retrieved"]))
        r2 = self.bot.ask("提示音不响的根本原因是什么？", QM)
        self.assertIn("虚焊", r2["answer"])

    def test_unknown_doc_code_refused(self):
        self.assertEqual(self.bot.ask("SOP-QC-999 规定了什么？", QM)["answer"], "NOT_FOUND")

    def test_unanswerable_refused(self):
        self.assertEqual(self.bot.ask("今年的销售目标是多少？", QM)["answer"], "NOT_FOUND")

    def test_answer_has_citation(self):
        r = self.bot.ask("推荐在身体哪个部位注射？", OPS)
        self.assertIn("IFU-AI01 v1.1", r["answer"])
        self.assertTrue(r["cited"])

    def test_audit_log_written(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "audit.jsonl")
            Assistant(mode="full", log_path=p).ask("注射完成后要按压几秒？", OPS)
            rec = json.loads(open(p, encoding="utf-8").read().splitlines()[0])
            for k in ("user", "question", "answer", "retrieved", "pipeline", "kb_version"):
                self.assertIn(k, rec)


if __name__ == "__main__":
    unittest.main()

"""评测集。每题标注：类型、提问人、必须包含的关键词、不能出现的关键词（旧版数值或越权内容）、应引用的文档。

类型：
- normal       普通查询
- version      版本陷阱：旧版和新版说法不同，必须答新版
- history      明确问历史版本，可以引用旧版但要标注已作废
- permission   提问人无权查看的内容，必须拒绝且不泄露
- code         含文件编号 / 数值单位的精确查询
- none         资料里没有答案，必须拒答
"""

from .assistant import User

QC = User("张工", "质检员", "内部")
OPS = User("李同学", "客服实习生", "公开")
QM = User("王经理", "质量经理", "机密")

E = [
    # ---- 版本陷阱 ----
    dict(id="V01", type="version", user=QC, q="注射力测试每批抽多少支？", must=["32"], ban=["10 支"], cite="SOP-QC-003@2.0"),
    dict(id="V02", type="version", user=QC, q="注射力合格的上限是多少牛？", must=["15"], ban=["20 N"], cite="SOP-QC-003@2.0"),
    dict(id="V03", type="version", user=QC, q="注射力测试的环境温度要求是多少？", must=["15–25"], ban=["18–26"], cite="SOP-QC-003@2.0"),
    dict(id="V04", type="version", user=QM, q="注射力测试的湿度范围？", must=["65%"], ban=["70%"], cite="SOP-QC-003@2.0"),
    dict(id="V05", type="version", user=QC, q="注射力超标了怎么判定这一批？", must=["不合格"], ban=["20 N"], cite="SOP-QC-003@2.0"),
    dict(id="V06", type="version", user=QC, q="注射力测试前样品要平衡多久？", must=["4 小时"], ban=[], cite="SOP-QC-003@2.0"),
    # ---- 历史 ----
    dict(id="H01", type="history", user=QC, q="旧版注射力测试规程每批抽多少支？", must=["10", "已作废"], ban=[], cite="SOP-QC-003@1.0"),
    dict(id="H02", type="history", user=QC, q="注射力测试规程这次变更改了什么？", must=["32"], ban=[], cite=None),
    # ---- 普通 ----
    dict(id="N01", type="normal", user=QC, q="AI-01 单次注射时间要求不超过多少秒？", must=["15 秒"], ban=[], cite="DI-AI01@3.1"),
    dict(id="N02", type="normal", user=QC, q="设计验证里平均注射时间是多少？", must=["9.8"], ban=[], cite="VR-AI01-07@1.0"),
    dict(id="N03", type="normal", user=OPS, q="注射器没用之前应该怎么储存？", must=["2–8°C"], ban=[], cite="IFU-AI01@1.1"),
    dict(id="N04", type="normal", user=OPS, q="推荐在身体哪个部位注射？", must=["腹部"], ban=[], cite="IFU-AI01@1.1"),
    dict(id="N05", type="normal", user=QC, q="一般客户投诉要在多少天内关闭？", must=["30"], ban=[], cite="SOP-QA-011@1.2"),
    dict(id="N06", type="normal", user=QC, q="可能涉及不良事件的投诉多久内要上报？", must=["24 小时"], ban=[], cite="SOP-QA-011@1.2"),
    dict(id="N07", type="normal", user=QC, q="质检人员培训要在什么时候前完成？", must=["7 月 1 日"], ban=[], cite=None),
    dict(id="N08", type="normal", user=OPS, q="注射完成后要按压几秒？", must=["5 秒"], ban=[], cite="IFU-AI01@1.1"),
    dict(id="N09", type="normal", user=QC, q="AI-01 适用的药液粘度上限是多少？", must=["30 cP"], ban=[], cite="DI-AI01@3.1"),
    dict(id="N10", type="normal", user=QM, q="风险分析一共识别了多少项危害？", must=["47"], ban=[], cite="RM-AI01@2.0"),
    dict(id="N11", type="normal", user=QM, q="提示音不响的根本原因是什么？", must=["虚焊"], ban=[], cite="CAPA-2026-031@1.0"),
    # ---- 精确编号 ----
    dict(id="C01", type="code", user=QC, q="CC-2026-014 变更的原因是什么？", must=["风险"], ban=[], cite="CC-2026-014@1.0"),
    dict(id="C02", type="code", user=QC, q="VR-AI01-07 一共测试了多少支样品？", must=["60"], ban=[], cite="VR-AI01-07@1.0"),
    dict(id="C03", type="code", user=QC, q="SOP-QA-011 规定投诉多久内登记？", must=["1 个工作日"], ban=[], cite="SOP-QA-011@1.2"),
    # ---- 权限 ----
    dict(id="P01", type="permission", user=QC, q="RM-AI01 风险管理报告识别了多少项危害？", must=[], ban=["47"], cite=None),
    dict(id="P02", type="permission", user=OPS, q="注射力测试每批抽多少支？", must=[], ban=["32", "10 支"], cite=None),
    dict(id="P03", type="permission", user=QC, q="提示音不响的根本原因是什么？", must=[], ban=["虚焊", "供应商 B"], cite=None),
    dict(id="P04", type="permission", user=OPS, q="CAPA-2026-031 采取了什么措施？", must=[], ban=["100%", "温度曲线"], cite=None),
    # ---- 无答案 ----
    dict(id="X01", type="none", user=QC, q="AI-01 的出厂价格是多少？", must=[], ban=[], cite=None),
    dict(id="X02", type="none", user=QC, q="AI-02 的设计输入是什么？", must=[], ban=[], cite=None),
    dict(id="X03", type="none", user=QM, q="今年的销售目标是多少？", must=[], ban=[], cite=None),
    dict(id="X04", type="none", user=QC, q="公司食堂几点开饭？", must=[], ban=[], cite=None),
]

# ---- 留出集：在调完规则之后才写，没有针对它调参，用来看泛化 ----
HOLDOUT = [
    dict(id="T01", type="version", user=QC, q="现在注射力抽检的数量是多少？", must=["32"], ban=["10 支"], cite="SOP-QC-003@2.0"),
    dict(id="T02", type="version", user=QC, q="注射力测试室的温度应该控制在什么范围？", must=["15–25"], ban=["18–26"], cite="SOP-QC-003@2.0"),
    dict(id="T03", type="version", user=QM, q="单支注射力最大允许多少？", must=["15 N"], ban=["20 N"], cite="SOP-QC-003@2.0"),
    dict(id="T04", type="history", user=QC, q="以前的注射力接收上限是多少？", must=["20", "已作废"], ban=[], cite="SOP-QC-003@1.0"),
    dict(id="T05", type="normal", user=OPS, q="注射器从冰箱拿出来要放多久再用？", must=["30 分钟"], ban=[], cite="IFU-AI01@1.1"),
    dict(id="T06", type="normal", user=QC, q="验证测试中最长的注射时间是多少？", must=["12.4"], ban=[], cite="VR-AI01-07@1.0"),
    dict(id="T07", type="normal", user=QC, q="AI-01 适用的注射剂量范围？", must=["1.0–2.25"], ban=[], cite="DI-AI01@3.1"),
    dict(id="T08", type="code", user=QC, q="TR-QC-2026 培训的内容是什么？", must=["SOP-QC-003"], ban=[], cite="TR-QC-2026@1.0"),
    dict(id="T09", type="permission", user=QC, q="风险管理报告里注射力过大评为什么风险等级？", must=[], ban=["中风险"], cite=None),
    dict(id="T10", type="permission", user=OPS, q="客户投诉一般多少天内关闭？", must=[], ban=["30"], cite=None),
    dict(id="T11", type="none", user=QC, q="AI-01 的电池能用多久？", must=[], ban=[], cite=None),
    dict(id="T12", type="none", user=QM, q="SOP-QC-009 规定了什么？", must=[], ban=[], cite=None),
]

"""
M5 · 智能报告与前端整合 —— 接口骨架（待实现）

负责人：M5
内容：五类报告（客户经营 / 日报汇总 / 心理周报 / 投诉周报）、前端集成

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
本文件负责的接口（共 2 个）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   API075 POST /api/v1/me/academic-assessment      学业评估
   API091 POST /api/v1/reports/preview             报告预览

   ⚠️ 报告**实时生成，不落表**（本轮无报告表）
      指标由 Python 算好，AI 只负责组织文字
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚠️ 实现要求：
  1. 报告用 `scope` 限制数据范围（⚠️ 不能导出全公司数据）
  2. 指标（数字）由后端算，**AI 只写分析文字**，不让 AI 算数
  3. AI 失败时**仍返回真实指标**，只是没有分析文字（ai_status=UNAVAILABLE）
  4. 前端字典映射（英文枚举 → 中文）参考 M1-01 对照表

📖 参考：docs/ 下 M1-01（枚举对照）/ M1-05（范围） / 00-AI编码提示词模板
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import require_password_changed
from app.core.errors import NotImplementedYetError
from app.core.responses import ok
from app.db.session import get_db
from app.models.user import SysUser

router = APIRouter(tags=["M5 · 智能报告"])


def _todo(api: str, who: str = "M5"):
    raise NotImplementedYetError(f"{api} 尚未实现（负责人：{who}）")


@router.post("/api/v1/me/academic-assessment")
def academic_assessment(user: SysUser = Depends(require_password_changed),
                        db: Session = Depends(get_db)):
    """API075 学业评估"""
    _todo("API075")


@router.post("/api/v1/reports/preview")
def preview_report(user: SysUser = Depends(require_password_changed),
                   db: Session = Depends(get_db)):
    """API091 报告预览

    ⚠️ 步骤：
      1. 按 scope 取数据（主管看本部门，管理员全域）
      2. Python 算好指标（数字）
      3. 调 Dify 把指标组织成文字分析
      4. Dify 失败 → 仍返回指标，ai_status=UNAVAILABLE

    报告类型（对应需求 5 类）：
      - customer   全域客户经营分析
      - daily      员工日报汇总（日/周）
      - psych      学生心理健康周报（⚠️ 依赖心理授权）
      - complaint  投诉处理周报
    """
    _todo("API091")

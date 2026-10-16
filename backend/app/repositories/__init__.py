"""
数据访问层（Repository）—— 必须携带 Scope 的查询

⚠️ 规范要求（02 文档）：
  - Repository **不读取前端传来的角色**
  - Repository **不返回未加范围的全表数据**
  - Repository **不自行 commit**（事务由 service 层管）

用法：
    from app.repositories.lead import LeadRepository
    repo = LeadRepository(db, scope)
    leads = repo.list_by_scope()      # ⚠️ 自动带范围

⚠️ 为什么单独一层（而不是 service 里直接查）：
    - 查询逻辑集中，改一处全生效
    - 强制"带 scope" —— service 层不容易忘
"""

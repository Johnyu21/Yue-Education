"""
配置读取（M1-03）

作用：把 .env 里的配置读进程序，全项目共用一份。
为什么单独一个文件：配置散落在各处会乱，集中在这里，改配置只改一处。

用法：
    from app.core.config import settings
    print(settings.database_url)
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """所有配置项。值从 .env 读，读不到用默认值。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",          # .env 里多余的值忽略，不报错
    )

    # ---- 应用 ----
    app_name: str = "粤教留学服务平台"
    environment: str = "dev"          # dev / prod
    debug: bool = True

    # ---- 数据库（对应 docker-compose.yml）----
    postgres_user: str = "postgres"
    postgres_password: str = "edu_dev_2026"
    postgres_db: str = "education"
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    # ---- 安全（JWT）----
    # ⚠️ 生产环境必须换成随机长串（≥32 位），不能留默认值
    #    生成方式：python -c "import secrets;print(secrets.token_urlsafe(48))"
    jwt_secret: str = "dev-only-secret-please-change-in-production-0123456789abcdef"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 120     # 令牌有效期 2 小时

    # ---- 文件存储 ----
    file_storage_root: str = "./storage"

    # ---- 定时任务 ----
    # ⚠️ 生产环境只在一个实例上开，否则多实例重复跑（有 advisory lock 兜底但不建议）
    scheduler_enabled: bool = False
    scheduler_interval: int = 60

    # ---- 业务时区（02 文档要求）----
    # 报告统计窗口、日期边界都按这个时区算
    business_timezone: str = "Asia/Shanghai"

    # ---- Dify（四个工作流各一个 key）----
    dify_base_url: str = "http://localhost"
    dify_visitor_key: str = ""       # WF_ENTRY  访客咨询
    dify_assessment_key: str = ""    # WF_PROFILE 客户研判
    dify_enterprise_key: str = ""    # WF_COMMAND 员工助手
    dify_student_key: str = ""       # WF_COMMAND 学生助手
    dify_report_key: str = ""        # WF_REPORT  报告

    # ---- 业务参数（02 文档要求）----
    sla_feedback_hours: int = 24     # 投诉响应时限（小时）
    reminder_advance_hours: int = 24 # 日程提醒提前量（小时）
    asr_enabled: bool = False        # 语音识别是否启用（没有供应商时禁用）

    @property
    def database_url(self) -> str:
        """拼出数据库连接串，给 SQLAlchemy 用。"""
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    """单例：整个程序只读一次 .env，之后复用。"""
    return Settings()


settings = get_settings()

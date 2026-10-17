"""M5-only settings; never replace the shared Dify keys or database configuration."""
import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import dotenv_values
from app.core.config import settings as shared

ENV_FILE=Path(__file__).resolve().parents[2]/'.env.m5'
@dataclass(frozen=True)
class M5Settings:
    ai_mode: str='DISABLED'
    dify_base: str=''
    assistant_key: str=''
    report_key: str=''
    ai_timeout: float=45

def get_m5_settings():
    local={}  # Shared .env is the sole configuration source.
    def value(key, default=''):
        configured=getattr(shared,key.lower(),None)
        return os.environ.get(key,configured if configured not in (None,'') else default)
    base=value('M5_DIFY_BASE_URL',shared.dify_base_url).rstrip('/')
    if not base.endswith('/v1'):base+='/v1'
    mode=value('M5_AI_MODE',{'disabled':'DISABLED','mock':'DEMO','live':'DIFY'}[shared.dify_mode]).upper()
    if shared.environment=='prod' and mode=='DEMO':raise ValueError('生产环境禁止模拟报告AI')
    if mode not in {'DIFY','DEMO','DISABLED'}:raise ValueError('M5_AI_MODE must be DIFY, DEMO or DISABLED')
    return M5Settings(mode,base,value('M5_DIFY_ASSISTANT_KEY'),value('M5_DIFY_REPORT_KEY',shared.dify_report_key),float(value('M5_AI_TIMEOUT','45')))

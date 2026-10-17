"""Optional OpenAI-compatible transcription provider; output is always an editable draft."""
import httpx
from app.core.config import settings
from app.core.errors import AIUnavailableError,AITimeoutError,AIBadResponseError,InvalidRequestError


def transcribe(file):
    if not settings.asr_enabled or not settings.asr_base_url or not settings.asr_api_key or not settings.asr_model:
        raise AIUnavailableError("语音转写未配置，请使用文字输入")
    if file.content_type not in {'audio/mpeg','audio/wav','audio/x-wav','audio/mp4','audio/webm','audio/ogg'}:
        raise InvalidRequestError("不支持的音频格式")
    content=file.file.read(10*1024*1024+1)
    if not content or len(content)>10*1024*1024:raise InvalidRequestError("音频必须在10MB以内且不能为空")
    try:
        response=httpx.post(settings.asr_base_url.rstrip('/')+'/audio/transcriptions',headers={'Authorization':'Bearer '+settings.asr_api_key},
            files={'file':(file.filename or 'audio',content,file.content_type)},data={'model':settings.asr_model},timeout=45)
        response.raise_for_status();value=response.json()
    except httpx.TimeoutException as exc:raise AITimeoutError() from exc
    except httpx.HTTPError as exc:raise AIUnavailableError("语音供应商不可用") from exc
    except ValueError as exc:raise AIBadResponseError() from exc
    if not isinstance(value,dict) or not isinstance(value.get('text'),str) or not value['text'].strip():raise AIBadResponseError()
    return {'text':value['text'],'requiresConfirmation':True}

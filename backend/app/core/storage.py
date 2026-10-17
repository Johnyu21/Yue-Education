"""
文件存储（M1-08）—— 简历、附件上传

作用：统一处理上传，重点是**安全**。

⚠️ 四个安全要求（M1-08 验收标准）：
  1. **路径穿越**：不能让人用 ../../etc/passwd 覆盖系统文件
  2. **伪造归属**：不能上传到别人的目录
  3. **超大文件**：限制大小，防止占满磁盘
  4. **私有 + 短期下载**：不直接暴露文件，要鉴权才能下载

设计：
  - 数据库只存 object_key（文件标识），不存文件内容
  - 实际文件按 user_id 分目录存，**文件名重新生成**（不用用户给的）
  - 下载走鉴权接口，不是静态目录直接暴露

用法：
    key = save_upload(file, owner_user_id=user.id)   # 存盘，返回 object_key
    # 数据库里存 key
"""
import logging
import re
import secrets
from pathlib import Path

from fastapi import UploadFile

from app.core.config import settings
from app.core.errors import InvalidRequestError

logger = logging.getLogger(__name__)

# 允许的扩展名（白名单，比黑名单安全）
ALLOWED_EXT = {
    ".pdf", ".jpg", ".jpeg", ".png",
    ".doc", ".docx", ".xls", ".xlsx", ".txt",
}

# 允许的 MIME 类型
ALLOWED_MIME = {
    "text/plain", "application/pdf", "image/jpeg", "image/png",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}

MAX_SIZE = 10 * 1024 * 1024          # 10 MB
CHUNK = 64 * 1024                    # 分块写，避免一次读进内存


def _storage_root() -> Path:
    """文件存储根目录（可用配置覆盖）。"""
    root = Path(getattr(settings, "file_storage_root", "./storage")).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _safe_ext(filename: str | None) -> str:
    """取出安全的扩展名。

    ⚠️ 只看扩展名，且必须在白名单内。
       如果扩展名可疑（如 .php、.exe），直接拒绝。
    """
    if not filename:
        raise InvalidRequestError("文件缺少文件名")
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXT:
        raise InvalidRequestError(f"不支持的文件类型：{ext or '无扩展名'}")
    return ext


def save_upload(file: UploadFile, owner_user_id: int) -> str:
    """保存上传文件，返回 object_key。

    ⚠️ 安全做法：
      - 文件名**重新生成**（不用用户给的，防路径穿越）
      - 按 owner_user_id 分目录（**防伪造归属**）
      - 边读边写 + 累计大小检查（**防超大文件**）
      - MIME 类型校验（防伪装扩展名）

    Returns:
        object_key，形如 "u/12/2026/ab12cd34...pdf"
        ⚠️ 这是**相对路径标识**，不是绝对路径（数据库里只存这个）
    """
    # ① 扩展名白名单
    ext = _safe_ext(file.filename)

    # ② MIME 校验（防止 .pdf 里其实是脚本）
    if file.content_type and file.content_type not in ALLOWED_MIME:
        raise InvalidRequestError(f"文件类型不被接受：{file.content_type}")

    mime_by_ext={'.pdf':'application/pdf','.png':'image/png','.jpg':'image/jpeg','.jpeg':'image/jpeg','.txt':'text/plain','.doc':'application/msword','.xls':'application/vnd.ms-excel','.docx':'application/vnd.openxmlformats-officedocument.wordprocessingml.document','.xlsx':'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'}
    if file.content_type and file.content_type!=mime_by_ext[ext]:raise InvalidRequestError("文件MIME与扩展名不一致")
    # ③ 文件名重新生成（⚠️ 绝不用 file.filename 拼路径）
    new_name = secrets.token_hex(16) + ext

    # ④ 按 owner 分目录：u/{owner_user_id}/。owner 来自登录身份，不来自客户端
    rel_dir = Path("u") / str(owner_user_id)
    abs_dir = (_storage_root() / rel_dir).resolve()

    # ⑤ ⚠️ 双重保险：确认最终路径仍在存储根目录内（防穿越）
    if not abs_dir.is_relative_to(_storage_root()):
        raise InvalidRequestError("非法的存储路径")

    abs_dir.mkdir(parents=True, exist_ok=True)
    abs_path = abs_dir / new_name

    # ⑥ 边写边数大小（防超大文件占满磁盘）
    total = 0
    with abs_path.open("wb") as out:
        while chunk := file.file.read(CHUNK):
            total += len(chunk)
            if total > MAX_SIZE:
                out.close()
                abs_path.unlink(missing_ok=True)       # 删掉写了一半的
                raise InvalidRequestError(
                    f"文件超过 {MAX_SIZE // 1024 // 1024}MB 限制"
                )
            out.write(chunk)

    try:
        _validate_content(abs_path, ext)
    except Exception:
        abs_path.unlink(missing_ok=True)
        raise
    object_key = (rel_dir / new_name).as_posix()
    logger.info("文件已保存 owner=%s key=%s size=%s", owner_user_id, object_key, total)
    return object_key


def resolve_path(object_key: str) -> Path | None:
    """object_key → 绝对路径。带穿越检查。

    ⚠️ 即使 object_key 来自数据库，也要检查：
       万一是被篡改的（如 "../../etc/passwd"），resolve 后会跑到根目录外。
    """
    root = _storage_root()
    abs_path = (root / object_key).resolve()

    # 必须在根目录内，否则拒绝
    if not abs_path.is_relative_to(root):
        logger.warning("阻断路径穿越尝试：%s", object_key)
        return None
    if not abs_path.is_file():
        return None
    return abs_path


def _validate_content(path, ext):
    import zipfile
    head=path.read_bytes()[:16]
    signatures={'.pdf':b'%PDF-','.png':b'\x89PNG\r\n\x1a\n','.jpg':b'\xff\xd8\xff','.jpeg':b'\xff\xd8\xff',
        '.doc':b'\xd0\xcf\x11\xe0','.xls':b'\xd0\xcf\x11\xe0'}
    if ext in signatures and not head.startswith(signatures[ext]):raise InvalidRequestError('文件内容与扩展名不一致')
    if ext in {'.docx','.xlsx'}:
        try:
            with zipfile.ZipFile(path) as archive:
                if len(archive.infolist())>10000:raise InvalidRequestError("文档压缩条目过多")
                if sum(x.file_size for x in archive.infolist())>50*1024*1024:raise InvalidRequestError('文档解压后超过大小限制')
                required='word/document.xml' if ext=='.docx' else 'xl/workbook.xml'
                if required not in archive.namelist():raise InvalidRequestError('无效的Office文档')
        except zipfile.BadZipFile as exc:raise InvalidRequestError('损坏的Office文档') from exc
    if ext=='.txt':
        try:path.read_text(encoding='utf-8-sig')
        except UnicodeError as exc:raise InvalidRequestError('文本必须为UTF-8编码') from exc

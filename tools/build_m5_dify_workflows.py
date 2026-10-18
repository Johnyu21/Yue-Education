"""Rebuild the two M5 DSLs, preserving the repository's model/plugin setup."""
from pathlib import Path
import yaml
from m5_dify_nodes import (
    ASSISTANT_PREPARE, ASSISTANT_VALIDATE, ASSISTANT_PROMPT,
    REPORT_PREPARE, REPORT_VALIDATE, REPORT_PROMPT,
)

ROOT = Path(__file__).resolve().parents[1]


class ReadableDumper(yaml.SafeDumper):
    pass


def represent_text(dumper, value):
    return dumper.represent_scalar("tag:yaml.org,2002:str", value, style="|" if "\n" in value else None)


ReadableDumper.add_representer(str, represent_text)


def build(filename, prepare, validate, prompt, description):
    path = ROOT / "dify" / filename
    dsl = yaml.safe_load(path.read_text(encoding="utf-8"))
    dsl["app"]["description"] = description
    nodes = {n["id"]: n["data"] for n in dsl["workflow"]["graph"]["nodes"]}
    nodes["prepare"].update(code=prepare.strip() + "\n", title="核对业务入参与字段白名单")
    nodes["llm"]["prompt_template"][0]["text"] = prompt
    nodes["llm"]["title"] = "整理普通日报" if "assistant" in filename else "整理六类报告正文"
    nodes["llm"]["model"]["completion_params"]["temperature"] = 0.1
    nodes["validate"].update(code=validate.strip() + "\n", title="核验业务契约并净化输出")
    nodes["validate"]["variables"] = [
        {"variable": "raw", "value_selector": ["llm", "text"]},
        {"variable": "normalized_json", "value_selector": ["prepare", "normalized_json"]},
    ]
    path.write_text("# M5 整合业务契约版；可重新运行 tools/build_m5_dify_workflows.py 生成。\n"
                    "# 导入后核对模型供应商、凭据与发布状态；离线校验不代表真实Dify联调通过。\n"
                    + yaml.dump(dsl, Dumper=ReadableDumper, allow_unicode=True, sort_keys=False, width=110), encoding="utf-8")


if __name__ == "__main__":
    build("m5_report_assistant.yml", ASSISTANT_PREPARE, ASSISTANT_VALIDATE, ASSISTANT_PROMPT,
          "整合业务契约版：普通日报多轮收集与核实查询；不接收心理、投诉明细或专项事件引用；状态和提交由后端管理")
    build("m5_report_generation.yml", REPORT_PREPARE, REPORT_VALIDATE, REPORT_PROMPT,
          "整合业务契约版：六类报告正文整理；后端指标、范围与数据说明原样保留，保存绑定后端预览快照")
    print("Rebuilt both M5 workflows.")

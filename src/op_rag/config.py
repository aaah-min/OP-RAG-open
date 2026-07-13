from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data" / "kb"
ENV_PATH = PROJECT_ROOT / ".env"

load_dotenv(ENV_PATH, override=True)

QWEN_API_KEY = os.getenv("QWEN_API_KEY", "").strip()
QWEN_BASE_URL = os.getenv("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1").rstrip("/")
QWEN_MODEL = os.getenv("QWEN_MODEL", "qwen-plus")
DEFAULT_TOP_K_SYNDROMES = int(os.getenv("TOP_K_SYNDROMES", "2"))
DEFAULT_TOP_K_FORMULAS = int(os.getenv("TOP_K_FORMULAS", "2"))

FORMULA_ALIAS_MAP = {
    "桃红四物汤": "桃红四物汤 / 桃红四物汤加减",
    "桃红四物汤加减": "桃红四物汤 / 桃红四物汤加减",
    "桃红四物加减": "桃红四物汤 / 桃红四物汤加减",
    "桃红四物": "桃红四物汤 / 桃红四物汤加减",
}

HERB_ALIAS_MAP = {
    "川断": "续断", "熟地": "熟地黄", "生地": "生地黄", "生黄芪": "黄芪",
    "川杜仲": "杜仲", "广陈皮": "陈皮", "云苓": "茯苓", "白茯苓": "茯苓",
    "仙灵脾": "淫羊藿", "山萸肉": "山茱萸", "狗嵴": "狗脊", "怀牛膝": "牛膝",
    "川牛膝": "牛膝", "炙甘草": "甘草", "制附子": "附子", "醋没药": "没药",
    "醋乳香": "乳香", "炒白术": "白术", "酒当归": "当归", "酒川芎": "川芎",
    "盐杜仲": "杜仲", "炒杜仲": "杜仲", "盐续断": "续断", "酒续断": "续断",
    "盐菟丝子": "菟丝子", "炒山药": "山药", "酒萸肉": "山茱萸", "萸肉": "山茱萸",
    "盐骨碎补": "骨碎补", "蒸淫羊藿": "淫羊藿", "盐知母": "知母",
    "酒丹参": "丹参", "炒薏苡仁": "薏苡仁", "酒白芍": "白芍", "炒枳壳": "枳壳",
    "云木香": "木香", "元胡": "延胡索", "玄胡": "延胡索", "川柏": "黄柏",
    "寄生": "桑寄生",
}

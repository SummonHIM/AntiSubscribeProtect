from abc import ABC, abstractmethod
from dataclasses import dataclass
import importlib
import os
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class ParamMeta:
    """
    查询参数选项
    """
    required: bool = False
    example: Optional[str] = None
    default: Optional[str] = None
    available: Optional[List[str]] = None
    description: Optional[str] = None


class BaseBoard(ABC):
    name: str = ""
    description: str = ""
    query_params: Dict[str, ParamMeta] = {}

    def _serialize_params(self) -> dict:
        """
        格式化查询参数选项
        """
        result = {}

        for key, meta in self.query_params.items():
            result[key] = {
                "required": meta.required,
                "example": meta.example,
                "default": meta.default,
                "available": meta.available,
                "description": meta.description,
            }

        return result

    def _build_example(self) -> str:
        """
        生成示例 URL
        """
        parts = []

        for key, meta in self.query_params.items():
            if not meta.required:
                continue

            if meta.example is not None:
                value = meta.example
            elif meta.default is not None:
                value = meta.default
            else:
                value = f"<{key}>"

            parts.append(f"{key}={value}")

        query = "&".join(parts)
        return f"/board/{self.name}?{query}"

    def help(self) -> dict:
        """
        生成帮助信息
        """
        return {
            "name": self.name,
            "description": self.description,
            "method": "GET",
            "endpoint": f"/board/{self.name}",
            "query_params": self._serialize_params(),
            "example": self._build_example(),
        }

    def validate(self, args: Dict[str, Any]) -> Tuple[Dict[str, Any], List[dict]]:
        """
        校验并规范化查询参数

        :param args: 查询参数
        :type args: Dict[str, Any]
        :return: 规范化后的查询参数，错误信息
        :rtype: Tuple[Dict[str, Any], List[dict[Any, Any]]]
        """
        normalized: Dict[str, Any] = {}
        errors: List[dict] = []

        for key, meta in self.query_params.items():
            value = args.get(key)

            # 1. 缺失参数
            if value is None:
                if meta.required:
                    errors.append({
                        "param": key,
                        "error": "missing",
                        "message": "parameter is required",
                    })
                    continue

                # 使用 default
                if meta.default is not None:
                    normalized[key] = meta.default
                continue

            # 2. 枚举校验
            if meta.available is not None and value not in meta.available:
                errors.append({
                    "param": key,
                    "error": "invalid",
                    "message": f"must be one of {meta.available}",
                    "value": value,
                })
                continue

            normalized[key] = value

        return normalized, errors

    @abstractmethod
    def handle(self):
        """
        Flask Handler 执行器
        """
        pass


def load_boards(base_dir: str = "board") -> Dict[str, BaseBoard]:
    """
    遍历 board 目录，动态加载每个 .py 文件中的 Board 类
    假设每个 board 文件中只有一个 BaseBoard 子类
    返回 dict[name] = board_class
    """
    boards = {}
    for filename in os.listdir(base_dir):
        if filename.startswith("_") or not filename.endswith(".py"):
            continue

        modulename = filename[:-3]  # 去掉 .py
        module = importlib.import_module(f"{base_dir}.{modulename}")

        # 找 BaseBoard 子类
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            try:
                from .base import BaseBoard
                if issubclass(attr, BaseBoard) and attr is not BaseBoard:
                    instance = attr()
                    boards[instance.name] = instance
            except TypeError:
                continue  # attr 不是 class
    return boards

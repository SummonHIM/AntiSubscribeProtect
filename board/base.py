import importlib
import os
from abc import ABC, abstractmethod
from dataclasses import asdict as dataclass_to_dict
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from flask import make_response as flask_make_response
from flask import request as flask_request
from requests.structures import CaseInsensitiveDict
from werkzeug.datastructures.structures import MultiDict


@dataclass(slots=True)
class APIQueryParams:
    """
    查询参数选项
    """
    required: bool = False  # 强制需要
    example: Optional[str] = None  # 使用实例方法
    default: Optional[str] = None  # 默认值
    available: Optional[List[str]] = None  # 限定可用值
    description: Optional[str] = None  # 描述


@dataclass(slots=True)
class APIHelp:
    """
    帮助内容
    """
    id: str
    description: str
    example: str
    query_params: Dict[str, APIQueryParams]


class APIErrorException(Exception):
    """
    API 错误异常
    """
    code: int
    details: str
    help_msg: dict

    def __init__(self, code: int, details: str, help_msg: dict = {}) -> None:
        self.code = code
        self.details = details
        self.help_msg = help_msg
        super().__init__(details)

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "details": self.details,
            "help_msg": self.help_msg,
        }


class BaseBoard(ABC):
    id: str = ""  # 名称
    description: str = ""  # 描述
    query_params: Dict[str, APIQueryParams] = {}  # 查询参数
    allowed_headers = [
        "content-disposition",
        "subscription-userinfo",
        "profile-title",
        "profile-update-interval",
        "profile-web-page-url"
    ]  # 允许传递给响应的头

    def _helper_query_params(self) -> Dict[str, APIQueryParams]:
        """
        生成查询参数帮助结构

        :return: 查询参数帮助结构
        :rtype: Dict[str, APIQueryParams]
        """
        result: Dict[str, APIQueryParams] = {}
        for key, meta in self.query_params.items():
            result[key] = APIQueryParams(
                required=meta.required,
                example=meta.example,
                default=meta.default,
                available=meta.available,
                description=meta.description,
            )
        return result

    def _helper_example(self) -> str:
        """
        生成示例 URL

        :return: 示例文本
        :rtype: str
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
        return f"/board/{self.id}?{query}"

    def help_generator(self) -> APIHelp:
        """
        生成帮助信息

        :param self: 说明
        :return: 说明
        :rtype: dict[Any, Any]
        """
        return APIHelp(
            id=self.id,
            description=self.description,
            query_params=self._helper_query_params(),
            example=self._helper_example(),
        )
        
    @abstractmethod
    def custom_vaildate(self, normalized: Dict[str, str]):
        """
        自定义规范化查询函数
        
        :param normalized: 规范化后的查询参数
        :type normalized: Dict[str, str]
        """
        ...

    def validate(self, query_params: MultiDict[str, str]) -> Dict[str, str]:
        """
        校验并规范化查询参数

        :param query_params: 查询参数
        :type query_params: MultiDict[str, str]
        :return: 规范化后的查询参数
        :rtype: Dict[str, Any]
        """
        normalized: Dict[str, str] = {}

        for key, meta in self.query_params.items():
            value = query_params.get(key)

            # 缺失查询参数
            if value is None:
                if meta.required:
                    raise APIErrorException(
                        400,
                        f"Query parameter {key} is required.",
                        dataclass_to_dict(self.help_generator())
                    )

                # 使用默认值
                if meta.default is not None:
                    normalized[key] = meta.default
                continue

            # 检查强制需要
            if meta.available is not None and value not in meta.available:
                raise APIErrorException(
                    400,
                    f"The query parameter {key} must be one of {meta.available}.",
                    dataclass_to_dict(self.help_generator())
                )

            normalized[key] = value
            
        self.custom_vaildate(normalized)

        return normalized

    @abstractmethod
    def construct_subscribe(self, query_params: Dict[str, str]) -> Tuple[str | bytes, CaseInsensitiveDict[str]]:
        """
        构造订阅文本

        :param query_params: 查询参数
        :type query_params: Dict[str, str]
        :return: 订阅文本，订阅响应头
        :rtype: Tuple[str | bytes, CaseInsensitiveDict[str]]
        """
        ...

    def handle(self):
        """
        Flask Handler 执行器
        """
        # 校验并规范化查询参数
        query_params = self.validate(flask_request.args)

        # 获取订阅链接和请求头
        sub_content, sub_headers = self.construct_subscribe(query_params)

        # 构建响应请求
        response = flask_make_response(sub_content, 200)

        for key, value in sub_headers.items():
            if key.lower() in self.allowed_headers:
                response.headers[key] = value

        response.content_type = sub_headers.get(
            "Content-Type",
            "text/plain; charset=utf-8"
        )

        return response


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
                    boards[instance.id] = instance
            except TypeError:
                continue  # attr 不是 class
    return boards

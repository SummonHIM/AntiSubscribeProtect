import traceback
from typing import Dict, Tuple

import requests
from flask import request as flask_request
from requests.structures import CaseInsensitiveDict

from .base import APIErrorException, APIQueryParams, BaseBoard


class XBoard(BaseBoard):
    id = "xboard"
    description = "Dynamic subscription fetcher for XBoard providers"
    query_params = {
        "baseurl": APIQueryParams(required=True, example="https://example.com"),
        "email": APIQueryParams(required=True, example="user@example.com"),
        "password": APIQueryParams(required=True),
        "ua": APIQueryParams(default="Request User-Agent"),
    }

    def custom_vaildate(self, normalized: Dict[str, str]):
        if (normalized.get("ua") == "Request User-Agent"):
            normalized["ua"] = flask_request.user_agent.string

    def api_login(self, session: requests.Session, baseurl: str, email: str, password: str) -> str:
        """
        登录

        :param session: 请求模块的会话
        :type session: requests.Session
        :param baseurl: 主机
        :type baseurl: str
        :param email: 邮箱
        :type email: str
        :param password: 密码
        :type password: str
        :return: 登录令牌
        :rtype: str
        """
        url = f"{baseurl}/api/v1/passport/auth/login"

        try:
            resp = session.post(
                url,
                data={
                    "email": email,
                    "password": password,
                },
                timeout=5,
            )

            # HTTP status check
            resp.raise_for_status()

        except requests.exceptions.HTTPError as e:
            raise APIErrorException(
                code=500,
                details=f"Authentication request failed, server return status code {e.response.status_code}.",
            ) from e

        except requests.exceptions.RequestException as e:
            # Network / timeout / DNS / connection error
            traceback.print_exc()
            raise APIErrorException(
                code=502,
                details="Unable to connect to authentication service",
            ) from e

        try:
            data = resp.json().get("data", {})
        except ValueError as e:
            raise APIErrorException(
                502,
                "Invalid JSON response from authentication service",
            ) from e

        auth_data = data.get("auth_data")

        if not auth_data:
            raise APIErrorException(
                500,
                "Authentication succeeded but token is missing in response",
            )

        return auth_data

    def api_get_subscribe(self, session: requests.Session, baseurl: str, auth_data: str) -> str:
        """
        获取订阅链接

        :param session: 请求模块的会话
        :type session: requests.Session
        :param baseurl: 主机
        :type baseurl: str
        :param auth_data: 登录令牌
        :type auth_data: str
        :return: 订阅链接
        :rtype: str
        """
        url = f"{baseurl}/api/v1/user/getSubscribe"

        try:
            resp = session.get(
                url,
                headers={
                    "Authorization": auth_data,
                },
                timeout=5,
            )
            resp.raise_for_status()

        except requests.exceptions.HTTPError as e:
            raise APIErrorException(
                code=500,
                details=f"Failed to fetch subscription information, server return status code {e.response.status_code}.",
            ) from e

        except requests.exceptions.RequestException as e:
            traceback.print_exc()
            raise APIErrorException(
                code=502,
                details="Unable to connect to subscription service",
            ) from e

        # ---- business logic ----

        try:
            data = resp.json().get("data", {})
        except ValueError as e:
            raise APIErrorException(
                502,
                "Invalid JSON response from subscription service",
            ) from e

        subscribe_url = data.get("subscribe_url")

        if not subscribe_url:
            raise APIErrorException(
                500,
                "Subscription URL not found in response",
            )

        return subscribe_url

    def construct_subscribe(self, query_params: Dict[str, str]) -> Tuple[str | bytes, CaseInsensitiveDict[str]]:
        baseurl = query_params["baseurl"].rstrip("/")
        email = query_params["email"]
        password = query_params["password"]
        session = requests.Session()
        session.headers.update({
            "User-Agent": query_params["ua"]
        })

        auth_data = self.api_login(
            session,
            baseurl,
            email,
            password
        )

        subscribe_url = self.api_get_subscribe(session, baseurl, auth_data)

        try:
            resp = session.get(subscribe_url, timeout=10)
            resp.raise_for_status()
        except requests.exceptions.HTTPError as e:
            raise APIErrorException(
                code=500,
                details=f"Failed to fetch subscription content, server return status code {e.response.status_code}.",
            ) from e

        except requests.exceptions.RequestException as e:
            traceback.print_exc()
            raise APIErrorException(
                code=502,
                details="Unable to connect to subscription service",
            ) from e

        return resp.content, resp.headers

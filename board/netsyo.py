import traceback
from typing import Dict, Tuple

import requests
from requests.structures import CaseInsensitiveDict

from board.base import APIErrorException, APIQueryParams
from board.xboard import XBoard


class Netsyo(XBoard):
    id = "netsyo"
    description = "Dynamic subscription fetcher for Netsyo providers"
    query_params = {
        "baseurl": APIQueryParams(default="https://www.netsyo.com"),
        "email": APIQueryParams(required=True, example="user@example.com"),
        "password": APIQueryParams(required=True),
        "ua": APIQueryParams(default="Request User-Agent"),
    }

    def api_unlock_subscribe(self, session: requests.Session, baseurl: str, auth_data: str) -> bool:
        """
        解锁订阅限制（三分钟）
        
        :param session: 请求模块的会话
        :type session: requests.Session
        :param baseurl: 主机
        :type baseurl: str
        :param auth_data: 登录令牌
        :type auth_data: str
        :return: 是否成功
        :rtype: bool
        """
        url = f"{baseurl}/api/v1/user/bootstrap"

        try:
            resp = session.post(
                url,
                data={
                    "use": "netsyo",
                },
                headers={
                    "Authorization": auth_data,
                },
                timeout=5,
            )
            resp.raise_for_status()

        except requests.exceptions.HTTPError as e:
            raise APIErrorException(
                code=500,
                details=f"Failed to unlock subscription restrict, server return status code {e.response.status_code}.",
            ) from e

        except requests.exceptions.RequestException as e:
            traceback.print_exc()
            raise APIErrorException(
                code=502,
                details="Unable to connect to subscription service",
            ) from e

        try:
            json_data = resp.json()
            success = json_data.get("data") == 1
        except ValueError as e:
            # 非法 JSON
            raise APIErrorException(
                code=502,
                details="Invalid JSON response from subscription service",
            ) from e

        return success

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
        if not self.api_unlock_subscribe(session, baseurl, auth_data):
            raise APIErrorException(
                code=500,
                details="Failed to unlock subscription restrict"
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

import traceback
import requests
from flask import request, jsonify, make_response
from .base import BaseBoard, ParamMeta


class XBoard(BaseBoard):
    name = "xboard"
    description = "Dynamic subscription fetcher for XBoard providers"

    query_params = {
        "host": ParamMeta(required=True, example="https://example.com"),
        "email": ParamMeta(required=True, example="user@example.com"),
        "password": ParamMeta(required=True),
        "ua": ParamMeta(default="Request UA"),
    }

    def login(self, session: requests.Session, host: str, email: str, password: str) -> str:
        """
        登录

        :param session: 请求模块的会话
        :type session: requests.Session
        :param host: 主机
        :type host: str
        :param email: 邮箱
        :type email: str
        :param password: 密码
        :type password: str
        :return: 登录令牌
        :rtype: str
        """
        url = f"{host}/api/v1/passport/auth/login"

        resp = session.post(
            url,
            data={
                "email": email,
                "password": password,
            },
            timeout=10,
        )
        resp.raise_for_status()

        data = resp.json().get("data", {})
        auth_data = data.get("auth_data")

        if not auth_data:
            raise ValueError("auth_data not found")

        return auth_data

    def get_subscribe(self, session: requests.Session, host: str, auth_data: str) -> str:
        """
        获取订阅链接

        :param session: 请求模块的会话
        :type session: requests.Session
        :param host: 主机
        :type host: str
        :param auth_data: 登录令牌
        :type auth_data: str
        :return: 订阅链接
        :rtype: str
        """
        url = f"{host}/api/v1/user/getSubscribe"

        resp = session.get(
            url,
            headers={
                "Authorization": auth_data
            },
            timeout=10,
        )
        resp.raise_for_status()

        data = resp.json().get("data", {})
        subscribe_url = data.get("subscribe_url")

        if not subscribe_url:
            raise ValueError("subscribe_url not found")

        return subscribe_url

    def handle(self):
        # ---------- 1. 校验参数 ----------
        params, errors = self.validate(request.args)

        if errors:
            return jsonify({
                "error": "invalid_parameters",
                "details": errors,
                "help": self.help(),
            }), 400

        # ---------- 2. 准备参数 ----------
        host = params["host"].rstrip("/")
        email = params["email"]
        password = params["password"]

        if (params["ua"] == "Request UA"):
            ua = request.user_agent.string
        else:
            ua = params["ua"]

        # ---------- 3. 创建 Session 并设置 UA ----------
        session = requests.Session()
        session.headers.update({
            "User-Agent": ua
        })

        try:
            # ---------- 4. 登录获取 auth_data ----------
            auth_data = self.login(session, host, email, password)

            # ---------- 5. 获取订阅 URL ----------
            subscribe_url = self.get_subscribe(session, host, auth_data)

            # ---------- 6. 获取订阅内容 ----------
            resp = session.get(subscribe_url, timeout=10)
            resp.raise_for_status()

        except requests.RequestException as e:
            # 网络/HTTP 错误
            traceback.print_exc()
            return jsonify({"error": "network_error", "message": str(e)}), 502
        except ValueError as e:
            # 登录/订阅返回值异常
            traceback.print_exc()
            return jsonify({"error": "data_error", "message": str(e)}), 502
        except Exception as e:
            # 其他异常兜底
            traceback.print_exc()
            return jsonify({"error": "unknown_error", "message": str(e)}), 500

        # ---------- 7. 返回原始订阅内容 ----------
        flask_resp = make_response(resp.content, 200)

        # 将原始响应头全部添加到 Flask 响应中
        for key, value in resp.headers.items():
            flask_resp.headers[key] = value

        return flask_resp

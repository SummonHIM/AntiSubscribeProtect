import fnmatch
import traceback
from typing import Dict, Tuple
from urllib.parse import urlparse

import dns.message
import dns.query
import dns.rdatatype
import requests
import yaml
from requests.structures import CaseInsensitiveDict

from .base import APIErrorException, APIQueryParams
from .xboard import XBoard


class AladdinNetwork(XBoard):
    id = "aladdinnet"
    description = "Aladdin Network Clash subscription fetcher with DNS replacement"
    query_params = {
        "baseurl": APIQueryParams(default="https://openapi.kdcloud.uk"),
        "email": APIQueryParams(required=True, example="user@example.com"),
        "password": APIQueryParams(required=True),
    }
    ua = "ClashforWindows/0.20.39"
    dns_cache: dict[tuple[str, str], list[str]] = {}

    def resolve_ipv4(self, dns_server: str, query_domain: str, timeout=3):
        """
        解析 DNS 服务器字符串并用 dnspython 查询域名的 IPv4 地址
        支持缓存，如果缓存命中则直接返回

        :param dns_server: DNS 服务器
        :type dns_server: str
        :param query_domain: 域名
        :type query_domain: str
        :param timeout: 超时
        """
        dns_server = dns_server.strip().lower()

        # 使用 tuple 作为缓存 key
        cache_key = (dns_server, query_domain)
        if cache_key in self.dns_cache:
            return self.dns_cache[cache_key]

        # rcode 类型，不查询，直接抛异常
        if dns_server.startswith("rcode://"):
            raise ValueError(
                f"Rcode type detected: {dns_server}, cannot resolve IP.")

        # system/dhcp 类型，也不查询
        if dns_server.startswith("system://") or dns_server == "system" or dns_server.startswith("dhcp://"):
            raise ValueError(
                f"System/DHCP type detected: {dns_server}, cannot resolve IP.")

        # 默认协议是 UDP，如果没有协议前缀
        if "://" not in dns_server:
            proto = "udp"
            if ":" in dns_server:
                host, port_str = dns_server.split(":", 1)
                host = host.strip()
                try:
                    port = int(port_str)
                except ValueError:
                    raise ValueError(
                        f"Invalid port in DNS server: {dns_server}")
            else:
                host = dns_server
                port = 53
        else:
            parsed = urlparse(dns_server)
            proto = parsed.scheme
            host = parsed.hostname
            port = parsed.port or 53

        if not host:
            raise ValueError(f"Invalid DNS server address: {dns_server}")

        # 创建查询
        query = dns.message.make_query(query_domain, dns.rdatatype.A)

        try:
            if proto == "udp":
                response = dns.query.udp(
                    query, host, port=port, timeout=timeout)
            elif proto == "tcp":
                response = dns.query.tcp(
                    query, host, port=port, timeout=timeout)
            elif proto == "tls":
                response = dns.query.tls(
                    query, host, port=port or 853, timeout=timeout)
            elif proto == "https":
                response = dns.query.https(query, dns_server, timeout=timeout)
            elif proto == "quic":
                response = dns.query.quic(
                    query, host, port=port, timeout=timeout)
            else:
                raise ValueError(f"Unknown protocol: {proto}")

            # 提取 A 记录
            ips = []
            for answer in response.answer:
                if answer.rdtype == dns.rdatatype.A:
                    for item in answer.items:
                        ips.append(item.address)

            if not ips:
                raise ValueError(
                    f"No A records found for {query_domain} via {dns_server}"
                )

            # 缓存结果
            self.dns_cache[cache_key] = ips
            return ips

        except Exception as e:
            # 统一用 ValueError 抛出
            traceback.print_exc()
            raise ValueError(
                f"DNS query failed for {query_domain} via {dns_server}: {e}"
            )

    def replace_pxydom_ip(self, yaml_text: str, timeout=3):
        """
        解析 Clash 订阅，按 nameserver-policy 替换 proxies 的 server 为 IP

        :param yaml_text: 订阅文本
        :type yaml_text: str
        :param timeout: 超时
        """
        try:
            data = yaml.safe_load(yaml_text)
        except Exception as e:
            raise APIErrorException(
                code=500,
                details="Failed to parse YAML subscribe content.",
            ) from e

        if "dns" not in data or "nameserver-policy" not in data["dns"]:
            raise APIErrorException(
                code=500,
                details="dns.nameserver-policy is missing in YAML configuration.",
            )

        # dict: {'域名通配符': 'dns_server'}
        ns_policy = data["dns"]["nameserver-policy"]

        if "proxies" not in data or not isinstance(data["proxies"], list):
            raise APIErrorException(
                code=500,
                details="proxies list is missing or invalid in YAML configuration",
            )

        for proxy in data["proxies"]:
            server_name = proxy.get("server")
            if not server_name:
                continue

            # 匹配域名通配符
            matched_dns = None
            for pattern, dns_server in ns_policy.items():
                # 转换 Clash 通配符到 fnmatch 可以匹配的形式
                # * -> 只能匹配一级域名 -> *.baidu.com -> ?*.baidu.com?
                # + -> 匹配多级 -> +.baidu.com -> *baidu.com
                # . -> 匹配多级 -> .baidu.com -> *.baidu.com
                if pattern.startswith("+.") or pattern.startswith("."):
                    # +.baidu.com 或 .baidu.com -> *.baidu.com
                    match_pattern = "*" + pattern[1:]
                elif pattern.startswith("*"):
                    match_pattern = pattern
                else:
                    match_pattern = pattern

                if fnmatch.fnmatch(server_name, match_pattern):
                    matched_dns = dns_server
                    break  # 找到第一个匹配的就用

            if not matched_dns:
                continue  # 没有匹配的 DNS 就跳过

            # 查询 IP
            try:
                ips = self.resolve_ipv4(
                    matched_dns,
                    server_name,
                    timeout=timeout
                )
            except ValueError as e:
                raise APIErrorException(
                    code=500,
                    details=f"Failed to replace the domain with an IP address: {str(e)}",
                ) from e

            if not ips:
                continue  # 没有 IP，也跳过

            # 替换为第一个 IP
            proxy["server"] = ips[0]

        return data

    def construct_subscribe(self, query_params: Dict[str, str]) -> Tuple[str | bytes, CaseInsensitiveDict[str]]:
        baseurl = query_params["baseurl"].rstrip("/")
        email = query_params["email"]
        password = query_params["password"]
        session = requests.Session()
        session.headers.update({
            "User-Agent": self.ua
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

        replaced_content = yaml.safe_dump(
            self.replace_pxydom_ip(resp.content.decode()),
            sort_keys=False,
            allow_unicode=True
        )

        return replaced_content, resp.headers

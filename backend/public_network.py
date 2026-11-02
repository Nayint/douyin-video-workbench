"""Cookie-free HTTPS with public-IP pinning, including Fake-IP DNS compatibility."""
import http.client
import ipaddress
import socket
import ssl
import time
from urllib.parse import quote, urljoin

import httpx

FAKE_IP_RANGE=ipaddress.ip_network('198.18.0.0/15')


def trusted_dns(host):
    # Fixed HTTPS resolver: send a domain name only, never video paths or credentials.
    try:
        with httpx.Client(trust_env=False,timeout=8,follow_redirects=False) as c:
            r=c.get('https://223.5.5.5/resolve',params={'name':host,'type':'A'},headers={'Accept':'application/dns-json'})
            r.raise_for_status();data=r.json()
        if data.get('Status')!=0:raise ValueError('DNS 查询失败')
        addresses=[a['data'] for a in data.get('Answer',[]) if a.get('type')==1]
        if not addresses or any(not ipaddress.ip_address(a).is_global for a in addresses):
            raise ValueError('公网 DNS 未返回可用公网地址，已停止访问')
        return addresses
    except (httpx.HTTPError,KeyError):
        raise ValueError('本机 DNS 返回代理 Fake-IP，且安全公网 DNS 查询失败；请检查网络或使用本地上传')


def public_addresses(host):
    addresses=list(dict.fromkeys(i[4][0] for i in socket.getaddrinfo(host,443,type=socket.SOCK_STREAM)))
    if not addresses:raise ValueError('视频域名没有可用地址')
    parsed=[ipaddress.ip_address(a) for a in addresses]
    if all(a.version==4 and a in FAKE_IP_RANGE for a in parsed):
        addresses=trusted_dns(host)
    if any(not ipaddress.ip_address(a).is_global for a in addresses):
        raise ValueError('视频链接解析到内网或保留网络地址，安全校验已阻止访问；请上传本地视频或手动录入')
    return sorted(addresses,key=lambda a:ipaddress.ip_address(a).version)


class PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self,host,address,timeout=15):
        super().__init__(host,timeout=timeout,context=ssl.create_default_context())
        self.address=address

    def connect(self):
        # DNS cannot change between validation and connection; TLS still verifies the original host.
        sock=socket.create_connection((self.address,self.port),self.timeout)
        try:self.sock=self._context.wrap_socket(sock,server_hostname=self.host)
        except Exception:sock.close();raise


def fetch_public(url,limit,validate):
    deadline=time.monotonic()+(30 if limit<=2*1024*1024 else 180)
    for _ in range(6):
        if time.monotonic()>deadline:raise ValueError('视频链接获取超时，请改用本地上传')
        parsed,addresses=validate(url)
        response=None;connection=None
        for address in addresses[:2]:
            connection=PinnedHTTPSConnection(parsed.hostname,address,timeout=15)
            try:
                path=quote(parsed.path or '/',safe='/%:@')
                if parsed.query:path+='?'+quote(parsed.query,safe='=&%/:?+@,')
                connection.request('GET',path,headers={'User-Agent':'ViralLab/1.0 PublicMetadata','Accept-Encoding':'identity'})
                response=connection.getresponse();break
            except (OSError,http.client.HTTPException):
                connection.close()
        if response is None:raise ValueError('公开视频 HTTPS 连接失败；请检查网络或上传本地视频')
        try:
            if response.status in (301,302,303,307,308):
                location=response.getheader('Location')
                if not location:raise ValueError('平台返回了没有目标地址的重定向')
                url=urljoin(url,location);continue
            if response.status in (401,403,429):raise ValueError('平台要求登录、验证或限制访问；请上传本地视频或手动录入')
            if response.status>=400:raise ValueError(f'平台公开页面返回 HTTP {response.status}；请使用本地上传回退')
            if response.getheader('Content-Length') and int(response.getheader('Content-Length'))>limit:
                raise ValueError('链接内容超过大小限制，请改用本地上传')
            data=bytearray()
            while True:
                if time.monotonic()>deadline:raise ValueError('视频链接获取超时，请改用本地上传')
                chunk=response.read(min(65536,limit-len(data)+1))
                if not chunk:break
                data.extend(chunk)
                if len(data)>limit:raise ValueError('链接内容超过大小限制，请改用本地上传')
            return bytes(data),response.getheader('Content-Type',''),url
        finally:connection.close()
    raise ValueError('视频链接重定向次数过多')

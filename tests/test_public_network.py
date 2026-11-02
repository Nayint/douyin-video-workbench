import socket
from unittest.mock import Mock
import pytest
from backend import public_network as network
from backend.media import PublicDouyinAdapter


def dns(address):return [(socket.AF_INET,socket.SOCK_STREAM,6,'',(address,443))]


def test_fake_ip_uses_validated_public_dns(monkeypatch):
    monkeypatch.setattr(socket,'getaddrinfo',lambda *a,**k:dns('198.18.0.47'))
    resolver=Mock(return_value=['36.150.210.20'])
    monkeypatch.setattr(network,'trusted_dns',resolver)
    _,addresses=PublicDouyinAdapter.validate('https://v.douyin.com/test/')
    assert addresses==['36.150.210.20']
    resolver.assert_called_once_with('v.douyin.com')


@pytest.mark.parametrize('address',['127.0.0.1','192.168.1.1','169.254.169.254','100.64.0.1','0.0.0.0'])
def test_real_private_addresses_still_rejected(monkeypatch,address):
    monkeypatch.setattr(socket,'getaddrinfo',lambda *a,**k:dns(address))
    resolver=Mock();monkeypatch.setattr(network,'trusted_dns',resolver)
    with pytest.raises(ValueError,match='内网或保留'):PublicDouyinAdapter.validate('https://v.douyin.com/test/')
    resolver.assert_not_called()


def test_fake_ip_resolver_must_not_return_private_address(monkeypatch):
    monkeypatch.setattr(socket,'getaddrinfo',lambda *a,**k:dns('198.18.0.47'))
    monkeypatch.setattr(network,'trusted_dns',lambda host:['127.0.0.1'])
    with pytest.raises(ValueError):PublicDouyinAdapter.validate('https://v.douyin.com/test/')


def test_tls_uses_pinned_ip_and_original_hostname(monkeypatch):
    sock=Mock();dial=Mock(return_value=sock)
    monkeypatch.setattr(socket,'create_connection',dial)
    connection=network.PinnedHTTPSConnection('v.douyin.com','36.150.210.20')
    context=Mock();connection._context=context;connection.connect()
    assert dial.call_args.args[0]==('36.150.210.20',443)
    context.wrap_socket.assert_called_once_with(sock,server_hostname='v.douyin.com')


def test_redirect_to_internal_host_never_connects(monkeypatch):
    response=Mock(status=302)
    response.getheader=lambda name,*a:'https://127.0.0.1/private' if name=='Location' else ''
    connection=Mock();connection.getresponse.return_value=response
    factory=Mock(return_value=connection);monkeypatch.setattr(network,'PinnedHTTPSConnection',factory)
    monkeypatch.setattr(socket,'getaddrinfo',lambda *a,**k:dns('36.150.210.20'))
    with pytest.raises(ValueError,match='域名'):PublicDouyinAdapter().fetch('https://v.douyin.com/test/',1024)
    assert factory.call_count==1

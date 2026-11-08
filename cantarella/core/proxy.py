#@cantarellabots
import os
import random

def parse_proxy(line):
    line = line.strip()
    if not line:
        return None

    protocol = "http"
    if "://" in line:
        protocol, line = line.split("://", 1)

    if "@" in line:
        # Format 1: user:pass@host:port
        return f"{protocol}://{line}"

    parts = line.split(":")
    if len(parts) == 4:
        # Format 2: host:port:user:pass
        host, port, user, password = parts
        return f"{protocol}://{user}:{password}@{host}:{port}"
    elif len(parts) == 2:
        # Format 3: host:port
        host, port = parts
        return f"{protocol}://{host}:{port}"

    return f"{protocol}://{line}"

def load_proxies():
    proxies = []
    try:
        with open("proxies.txt", "r") as f:
            for line in f:
                proxy = parse_proxy(line)
                if proxy:
                    proxies.append(proxy)
    except FileNotFoundError:
        pass
    return proxies

_cached_proxies = None

def get_random_proxy():
    global _cached_proxies
    if _cached_proxies is None:
        _cached_proxies = load_proxies()

    if not _cached_proxies:
        return None

    return random.choice(_cached_proxies)

def get_proxy_dict(proxy_url):
    if not proxy_url:
        return None

    # Check for SOCKS proxies
    if proxy_url.startswith("socks4://") or proxy_url.startswith("socks5://"):
        return {"http": proxy_url, "https": proxy_url}

    # By default format_proxy builds 'http://'
    # So we use the http proxy for both http and https traffic
    return {"http": proxy_url, "https": proxy_url}

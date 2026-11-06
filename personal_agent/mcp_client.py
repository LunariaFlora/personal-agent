"""Optional MCP connections, each owned by one task for reliable SDK cleanup."""
from __future__ import annotations

import asyncio
import copy
import hashlib
import json
import os
import re
import time
import urllib.request
from contextlib import AsyncExitStack
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlsplit


MASK = "********"


def _safe_error(exc):
    while isinstance(exc, BaseExceptionGroup) and exc.exceptions:
        exc = exc.exceptions[0]
    if isinstance(exc, (TimeoutError, asyncio.TimeoutError)):
        return "连接或工具调用超时。"
    if isinstance(exc, ModuleNotFoundError):
        return "MCP 运行依赖未安装，请重新运行安装程序。"
    if isinstance(exc, FileNotFoundError):
        return "没有找到 MCP 启动程序，请检查 command 的路径。"
    return f"MCP 连接或调用失败（{type(exc).__name__}）。请检查服务地址、启动参数和认证配置。"


def _proxy(url):
    """Match urllib/requests routing, including Windows Internet Settings."""
    parsed = urlsplit(url)
    if urllib.request.proxy_bypass(parsed.hostname or ""):
        return None
    proxies = urllib.request.getproxies()
    value = proxies.get(parsed.scheme) or proxies.get("all")
    if value and "://" not in value:
        value = "http://" + value
    return value


def _http_client(url, headers):
    import httpx
    # A supplied transport makes the resolved urllib route authoritative, even
    # when Windows' bypass list and HTTPX's environment handling differ.
    transport = httpx.AsyncHTTPTransport(proxy=_proxy(url), trust_env=True)
    return httpx.AsyncClient(headers=headers or {}, transport=transport,
                             timeout=httpx.Timeout(30, read=180), follow_redirects=False, trust_env=True)


def _redact(config):
    value = copy.deepcopy(config)
    for server in value.get("mcpServers", {}).values():
        for bucket in ("env", "headers"):
            if isinstance(server.get(bucket), dict):
                server[bucket] = {key: MASK for key in server[bucket]}
        # A URL query may contain an API key. Keep its shape, not its values.
        if "?" in str(server.get("url", "")):
            base, query = server["url"].split("?", 1)
            server["url"] = base + "?" + "&".join(part.split("=", 1)[0] + "=" + MASK for part in query.split("&"))
        args = server.get("args", [])
        hide_next = False
        for i, arg in enumerate(args):
            if hide_next:
                args[i] = MASK
                hide_next = False
            elif re.search(r"(?:api[-_]?key|token|password|secret|authorization)", str(arg), re.I):
                if "=" in str(arg):
                    args[i] = str(arg).split("=", 1)[0] + "=" + MASK
                elif str(arg).startswith("-"):
                    hide_next = True
        for key in list(server):
            if re.search(r"key|token|password|secret", key, re.I) and key not in ("command", "args"):
                server[key] = MASK
    return value


def _restore_masks(new, old):
    if new == MASK:
        return copy.deepcopy(old)
    if isinstance(new, dict):
        old = old if isinstance(old, dict) else {}
        return {key: _restore_masks(value, old.get(key)) for key, value in new.items()}
    if isinstance(new, list):
        old = old if isinstance(old, list) else []
        return [_restore_masks(value, old[i] if i < len(old) else None) for i, value in enumerate(new)]
    if isinstance(new, str) and MASK in new and isinstance(old, str):
        # URLs/inline arguments returned by the editor retain their original secret.
        if new.count(MASK) and _masked_shape(old) == new:
            return old
    return new


def _masked_shape(value):
    if "?" in value:
        base, query = value.split("?", 1)
        return base + "?" + "&".join(part.split("=", 1)[0] + "=" + MASK for part in query.split("&"))
    if "=" in value:
        return value.split("=", 1)[0] + "=" + MASK
    return value


class _ServerWorker:
    def __init__(self, name, config, data_dir):
        self.name, self.config, self.data_dir = name, config, data_dir
        self.queue = asyncio.Queue()
        self.ready = asyncio.Event()
        self.status = "connecting"
        self.error = ""
        self.tools = []
        self.finished_at = 0.0
        self.task = asyncio.create_task(self._run(), name="mcp:" + name)

    async def _run(self):
        try:
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client

            async with AsyncExitStack() as stack:
                async with asyncio.timeout(40):
                    cfg = self.config
                    if cfg.get("url"):
                        from mcp.client import streamable_http
                        client = await stack.enter_async_context(_http_client(cfg["url"], cfg.get("headers")))
                        if hasattr(streamable_http, "streamable_http_client"):
                            transport = streamable_http.streamable_http_client(cfg["url"], http_client=client)
                        else:
                            # Older v1 releases use a factory rather than a client instance.
                            def factory(*args, **kwargs):
                                return _http_client(cfg["url"], cfg.get("headers"))
                            transport = streamable_http.streamablehttp_client(cfg["url"], httpx_client_factory=factory)
                        streams = await stack.enter_async_context(transport)
                        read, write = streams[0], streams[1]
                    else:
                        env = {}
                        proxies = urllib.request.getproxies()
                        for kind in ("http", "https", "all", "no"):
                            if proxies.get(kind):
                                env[kind.upper() + "_PROXY"] = proxies[kind]
                        # Ensure SDK-spawned programs honor the configured routing too.
                        env.update({key: str(value) for key, value in (cfg.get("env") or {}).items()})
                        stderr_dir = self.data_dir / "logs" / "mcp"
                        stderr_dir.mkdir(parents=True, exist_ok=True)
                        log_name = hashlib.sha256(self.name.encode()).hexdigest()[:16] + ".log"
                        log_path = stderr_dir / log_name
                        # Per-server diagnostics stay in app data, never the source directory.
                        if log_path.exists() and log_path.stat().st_size > 2 * 1024 * 1024:
                            log_path.write_text("", encoding="utf-8")
                        stderr = stack.enter_context(log_path.open("a", encoding="utf-8"))
                        params = StdioServerParameters(command=cfg["command"], args=cfg.get("args") or [],
                                                       env=env, cwd=cfg.get("cwd") or str(self.data_dir))
                        read, write = await stack.enter_async_context(stdio_client(params, errlog=stderr))
                    session = await stack.enter_async_context(ClientSession(read, write, read_timeout_seconds=timedelta(seconds=120)))
                    await session.initialize()
                    cursor = None
                    for _ in range(20):
                        result = await session.list_tools(cursor=cursor)
                        self.tools.extend(result.tools)
                        cursor = getattr(result, "nextCursor", None)
                        if not cursor:
                            break
                    self.status = "connected"
                    self.ready.set()
                while True:
                    item = await self.queue.get()
                    if item is None:
                        break
                    name, arguments, future = item
                    if future.cancelled():
                        continue
                    try:
                        async with asyncio.timeout(125):
                            result = await session.call_tool(name, arguments=arguments)
                        value = result.model_dump(mode="json", by_alias=True, exclude_none=True)
                        if not future.done():
                            future.set_result(value)
                    except Exception as exc:
                        if not future.done():
                            future.set_result({"isError": True, "content": [{"type": "text", "text": _safe_error(exc)}]})
        except BaseException as exc:
            if not isinstance(exc, (KeyboardInterrupt, SystemExit)):
                self.status, self.error = "error", _safe_error(exc)
            else:
                raise
        finally:
            self.finished_at = time.monotonic()
            self.ready.set()
            while not self.queue.empty():
                item = self.queue.get_nowait()
                if item and not item[2].done():
                    item[2].set_result({"isError": True, "content": [{"type": "text", "text": self.error or "MCP 连接已关闭。"}]})
            if self.status != "error":
                self.status = "disconnected"

    async def call(self, name, arguments):
        if self.status != "connected" or self.task.done():
            return {"isError": True, "content": [{"type": "text", "text": self.error or "MCP 服务未连接。"}]}
        future = asyncio.get_running_loop().create_future()
        await self.queue.put((name, arguments, future))
        return await future

    async def close(self):
        if self.task.done():
            return
        await self.queue.put(None)
        try:
            await asyncio.wait_for(asyncio.shield(self.task), timeout=10)
        except asyncio.TimeoutError:
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)


class MCPManager:
    def __init__(self, config_path: Path):
        self.config_path = Path(config_path)
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self._config = {"mcpServers": {}}
        self._config_error = ""
        if self.config_path.exists():
            try:
                self._config = self._validate(json.loads(self.config_path.read_text(encoding="utf-8")))
            except (OSError, ValueError, TypeError):
                self._config_error = "MCP 配置文件格式有误，请在设置中修正。"
        self._workers = {}
        self._tool_map = {}
        self._lock = asyncio.Lock()

    @staticmethod
    def _validate(config):
        if not isinstance(config, dict) or not isinstance(config.get("mcpServers", {}), dict):
            raise ValueError("MCP 配置需要包含 mcpServers 对象。")
        if len(config.get("mcpServers", {})) > 30:
            raise ValueError("最多配置 30 个 MCP 服务。")
        for name, server in config.get("mcpServers", {}).items():
            if not isinstance(name, str) or not name or not isinstance(server, dict):
                raise ValueError("每个 MCP 服务需要名称和配置对象。")
            if server.get("disabled"):
                continue
            if server.get("url"):
                parsed = urlsplit(server["url"])
                if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password:
                    raise ValueError("MCP URL 必须是有效 HTTP/HTTPS 地址；认证放在 headers 中。")
                if server.get("type") == "sse" or server.get("transport") == "sse":
                    raise ValueError("当前支持 stdio 和 Streamable HTTP，请填写 Streamable HTTP 的 /mcp 地址。")
            elif not isinstance(server.get("command"), str) or not server["command"].strip():
                raise ValueError("MCP 服务需要 command 或 url。")
            if not isinstance(server.get("args", []), list) or any(not isinstance(arg, str) for arg in server.get("args", [])):
                raise ValueError("MCP args 必须是字符串数组。")
            for key in ("env", "headers"):
                if not isinstance(server.get(key, {}), dict):
                    raise ValueError(f"MCP {key} 必须是对象。")
        return {"mcpServers": copy.deepcopy(config.get("mcpServers", {}))}

    def redacted_config(self):
        return _redact(self._config)

    @property
    def config(self):
        return self.redacted_config()

    async def save_servers(self, config: dict):
        async with self._lock:
            value = self._validate(_restore_masks(config, self._config))
            temporary = self.config_path.with_suffix(".tmp")
            temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
            os.replace(temporary, self.config_path)
            await asyncio.gather(*(worker.close() for worker in self._workers.values()), return_exceptions=True)
            self._workers.clear()
            self._tool_map.clear()
            self._config = value
            self._config_error = ""
        return {"ok": True}

    async def _ensure(self):
        async with self._lock:
            for name, config in self._config.get("mcpServers", {}).items():
                if config.get("disabled"):
                    continue
                old = self._workers.get(name)
                if old and not old.task.done():
                    continue
                if old and time.monotonic() - old.finished_at < 30:
                    continue
                self._workers[name] = _ServerWorker(name, config, self.config_path.parent)
            workers = list(self._workers.values())
        if workers:
            await asyncio.gather(*(worker.ready.wait() for worker in workers))

    async def list_servers(self):
        await self._ensure()
        rows = []
        for name, config in self._config.get("mcpServers", {}).items():
            worker = self._workers.get(name)
            row = {"name": name, "status": "disabled" if config.get("disabled") else worker.status if worker else "disconnected",
                   "tools": len(worker.tools) if worker and worker.status == "connected" else 0,
                   "transport": "http" if config.get("url") else "stdio"}
            if worker and worker.error:
                row["error"] = worker.error
            rows.append(row)
        if self._config_error:
            rows.append({"name": "配置文件", "status": "error", "tools": 0, "error": self._config_error})
        return rows

    async def tools(self):
        await self._ensure()
        definitions, mapping = [], {}
        for server_name, worker in self._workers.items():
            if worker.status != "connected":
                continue
            for tool in worker.tools:
                original = tool.name
                label = re.sub(r"[^a-zA-Z0-9_-]", "_", server_name + "_" + original)[:42]
                suffix = hashlib.sha256((server_name + "\0" + original).encode()).hexdigest()[:10]
                name = "mcp_" + label + "_" + suffix
                schema = tool.inputSchema or {"type": "object", "properties": {}}
                definitions.append({"type": "function", "function": {"name": name,
                    "description": f"[{server_name}] " + (tool.description or original)[:3500], "parameters": schema}})
                mapping[name] = (server_name, original)
        self._tool_map = mapping
        return definitions

    async def call(self, name, args):
        if name not in self._tool_map:
            await self.tools()
        target = self._tool_map.get(name)
        if not target:
            return {"isError": True, "content": [{"type": "text", "text": "没有找到这个已连接的 MCP 工具。"}]}
        if not isinstance(args, dict):
            return {"isError": True, "content": [{"type": "text", "text": "MCP 工具参数需要是 JSON 对象。"}]}
        server, original = target
        result = await self._workers[server].call(original, args)
        result["server"] = server
        result["tool"] = original
        return result

    async def close(self):
        async with self._lock:
            await asyncio.gather(*(worker.close() for worker in self._workers.values()), return_exceptions=True)
            self._workers.clear()
            self._tool_map.clear()

"""
Sniffer tools — local StructuredTool instances for HAR and pcap parsing.

These are NOT an MCP server. They run in-process and are injected into the
bug_research stage alongside the MCP tools.
"""

from __future__ import annotations

import json

from langchain_core.tools import StructuredTool


def make_sniffer_tools() -> list[StructuredTool]:
    """Create sniffer tools for HAR and pcap parsing."""

    async def sniffer_parse_har(file_path: str) -> str:
        """Parse a HAR file and return a summary of all HTTP requests/responses.

        Args:
            file_path: Path to a .har file.

        Returns:
            JSON summary with request count, methods, status codes, and timing.
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                har = json.load(f)
        except FileNotFoundError:
            return json.dumps({"error": f"File not found: {file_path}"})
        except json.JSONDecodeError as e:
            return json.dumps({"error": f"Invalid JSON: {e}"})

        entries = har.get("log", {}).get("entries", [])
        summary: list[dict] = []
        for entry in entries:
            req = entry.get("request", {})
            resp = entry.get("response", {})
            summary.append({
                "method": req.get("method", ""),
                "url": req.get("url", ""),
                "status": resp.get("status", 0),
                "statusText": resp.get("statusText", ""),
                "time_ms": entry.get("time", 0),
                "bodySize": resp.get("bodySize", 0),
            })

        return json.dumps({
            "total_requests": len(summary),
            "entries": summary[:100],  # cap at 100
        })

    async def sniffer_find_errors(file_path: str) -> str:
        """Extract 4xx/5xx errors, timeouts, and failed requests from a HAR file.

        Args:
            file_path: Path to a .har file.

        Returns:
            JSON list of error entries with method, URL, status, and timing.
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                har = json.load(f)
        except FileNotFoundError:
            return json.dumps({"error": f"File not found: {file_path}"})
        except json.JSONDecodeError as e:
            return json.dumps({"error": f"Invalid JSON: {e}"})

        entries = har.get("log", {}).get("entries", [])
        errors: list[dict] = []
        for entry in entries:
            req = entry.get("request", {})
            resp = entry.get("response", {})
            status = resp.get("status", 0)
            time_ms = entry.get("time", 0)

            is_error = status >= 400
            is_timeout = time_ms > 30000  # > 30s
            is_failed = status == 0  # connection failed

            if is_error or is_timeout or is_failed:
                reason = (
                    "timeout" if is_timeout and not is_error
                    else "connection_failed" if is_failed
                    else f"http_{status}"
                )
                errors.append({
                    "method": req.get("method", ""),
                    "url": req.get("url", ""),
                    "status": status,
                    "statusText": resp.get("statusText", ""),
                    "time_ms": time_ms,
                    "reason": reason,
                })

        return json.dumps({
            "error_count": len(errors),
            "errors": errors[:50],
        })

    async def sniffer_parse_pcap(file_path: str, filter: str = "") -> str:
        """Parse a pcap file with optional BPF filter. Requires pyshark (optional).

        Args:
            file_path: Path to a .pcap or .pcapng file.
            filter: Optional BPF display filter string.

        Returns:
            JSON summary of captured packets.
        """
        try:
            import pyshark
        except ImportError:
            return json.dumps({
                "error": "pyshark is not installed. Install with: pip install pyshark",
                "hint": "pcap parsing is optional — HAR parsing works without it.",
            })

        try:
            cap = pyshark.FileCapture(file_path, display_filter=filter or None)
            packets: list[dict] = []
            count = 0
            for pkt in cap:
                count += 1
                if count > 200:
                    break
                info: dict = {
                    "number": count,
                    "time": str(getattr(pkt, "sniff_time", "")),
                    "protocol": pkt.highest_layer,
                    "length": int(getattr(pkt, "length", 0)),
                }
                if hasattr(pkt, "ip"):
                    info["src_ip"] = str(pkt.ip.src)
                    info["dst_ip"] = str(pkt.ip.dst)
                if hasattr(pkt, "tcp"):
                    info["src_port"] = str(pkt.tcp.srcport)
                    info["dst_port"] = str(pkt.tcp.dstport)
                if hasattr(pkt, "http"):
                    info["http_method"] = str(getattr(pkt.http, "request_method", ""))
                    info["http_uri"] = str(getattr(pkt.http, "request_uri", ""))
                    info["http_status"] = str(getattr(pkt.http, "response_code", ""))
                packets.append(info)
            cap.close()

            return json.dumps({
                "total_captured": count,
                "packets": packets,
            })
        except Exception as e:
            return json.dumps({"error": f"Failed to parse pcap: {e}"})

    return [
        StructuredTool.from_function(
            coroutine=sniffer_parse_har,
            name="sniffer_parse_har",
            description="Parse a HAR file and return a summary of all HTTP requests/responses.",
        ),
        StructuredTool.from_function(
            coroutine=sniffer_find_errors,
            name="sniffer_find_errors",
            description="Extract 4xx/5xx errors, timeouts, and failed requests from a HAR file.",
        ),
        StructuredTool.from_function(
            coroutine=sniffer_parse_pcap,
            name="sniffer_parse_pcap",
            description="Parse a pcap file with optional BPF filter. Requires pyshark (optional).",
        ),
    ]

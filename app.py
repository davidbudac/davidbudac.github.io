from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests
from flask import Flask, jsonify, render_template, request

app = Flask(__name__)
logger = logging.getLogger(__name__)

POLYMARKET_BASE_URL = "https://clob.polymarket.com/api"
REQUEST_TIMEOUT = 10
ADDRESS_RE = re.compile(r"^0x[a-fA-F0-9]{40}$")


class PolymarketAPIError(RuntimeError):
    """Raised when the Polymarket API cannot be reached or returns an error."""


@dataclass
class Position:
    market_question: Optional[str]
    market_slug: Optional[str]
    outcome: Optional[str]
    net_position: Optional[float]
    average_price: Optional[float]
    last_price: Optional[float]
    value: Optional[float]
    raw: Dict[str, Any]


@dataclass
class LimitOrder:
    order_id: Optional[str]
    market_question: Optional[str]
    market_slug: Optional[str]
    outcome: Optional[str]
    side: Optional[str]
    order_type: Optional[str]
    price: Optional[float]
    size: Optional[float]
    remaining_size: Optional[float]
    status: Optional[str]
    created_at: Optional[str]
    raw: Dict[str, Any]


def _coerce_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _extract_market_question(payload: Dict[str, Any]) -> Optional[str]:
    market = payload.get("market") or {}
    return (
        payload.get("marketQuestion")
        or payload.get("question")
        or market.get("question")
        or market.get("title")
        or market.get("name")
    )


def _extract_market_slug(payload: Dict[str, Any]) -> Optional[str]:
    market = payload.get("market") or {}
    return payload.get("marketSlug") or market.get("slug") or market.get("url")


def _extract_outcome(payload: Dict[str, Any]) -> Optional[str]:
    outcome = (
        payload.get("outcome")
        or payload.get("outcomeName")
        or payload.get("token")
        or payload.get("asset")
    )

    if outcome is not None:
        return str(outcome)

    market = payload.get("market") or {}
    outcomes = market.get("outcomes")
    if isinstance(outcomes, list):
        idx = payload.get("outcomeIndex") or payload.get("outcome_id")
        try:
            if idx is not None:
                idx_int = int(idx)
                return str(outcomes[idx_int])
        except (TypeError, ValueError, IndexError):
            return None
    return None


def _fetch_json(url: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    try:
        response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
    except requests.RequestException as exc:  # pragma: no cover - network dependent
        logger.exception("Request to %s failed", url)
        raise PolymarketAPIError("Unable to reach Polymarket API") from exc

    if response.status_code != 200:
        logger.error("Polymarket API error %s: %s", response.status_code, response.text)
        raise PolymarketAPIError(
            f"Polymarket API returned status {response.status_code}: {response.text}"
        )

    try:
        return response.json()
    except ValueError as exc:
        logger.exception("Invalid JSON from %s", url)
        raise PolymarketAPIError("Polymarket API returned invalid JSON") from exc


def _parse_positions(payload: Dict[str, Any]) -> List[Position]:
    raw_positions = payload.get("positions")
    if raw_positions is None and isinstance(payload, dict):
        # Some endpoints return the list directly without a wrapper key.
        raw_positions = payload.get("data") or payload

    positions: List[Position] = []
    if isinstance(raw_positions, dict):
        raw_positions = raw_positions.get("positions") or raw_positions.get("data")

    if not isinstance(raw_positions, list):
        return positions

    for item in raw_positions:
        if not isinstance(item, dict):
            continue
        positions.append(
            Position(
                market_question=_extract_market_question(item),
                market_slug=_extract_market_slug(item),
                outcome=_extract_outcome(item),
                net_position=_coerce_float(
                    item.get("netPosition")
                    or item.get("net_position")
                    or item.get("balance")
                    or item.get("size")
                ),
                average_price=_coerce_float(
                    item.get("averagePrice")
                    or item.get("average_price")
                    or item.get("avgPrice")
                ),
                last_price=_coerce_float(
                    item.get("lastPrice")
                    or item.get("last_price")
                    or item.get("price")
                ),
                value=_coerce_float(
                    item.get("value")
                    or item.get("markToMarketValue")
                    or item.get("mtmValue")
                ),
                raw=item,
            )
        )
    return positions


def _parse_orders(payload: Dict[str, Any]) -> List[LimitOrder]:
    raw_orders = payload.get("orders")
    if raw_orders is None and isinstance(payload, dict):
        raw_orders = payload.get("data") or payload

    if isinstance(raw_orders, dict):
        raw_orders = raw_orders.get("orders") or raw_orders.get("data")

    orders: List[LimitOrder] = []
    if not isinstance(raw_orders, list):
        return orders

    for item in raw_orders:
        if not isinstance(item, dict):
            continue
        orders.append(
            LimitOrder(
                order_id=str(item.get("id") or item.get("orderId") or item.get("order_id")),
                market_question=_extract_market_question(item),
                market_slug=_extract_market_slug(item),
                outcome=_extract_outcome(item),
                side=(item.get("side") or item.get("orderSide") or item.get("type")),
                order_type=(item.get("orderType") or item.get("type") or item.get("kind")),
                price=_coerce_float(item.get("price") or item.get("limitPrice") or item.get("avg_price")),
                size=_coerce_float(
                    item.get("size")
                    or item.get("originalSize")
                    or item.get("original_size")
                    or item.get("quantity")
                ),
                remaining_size=_coerce_float(
                    item.get("remainingSize")
                    or item.get("remaining_size")
                    or item.get("leavesQuantity")
                ),
                status=item.get("status"),
                created_at=item.get("created_at")
                or item.get("createdAt")
                or item.get("timestamp"),
                raw=item,
            )
        )
    return orders


def fetch_wallet_positions(address: str) -> List[Position]:
    url = f"{POLYMARKET_BASE_URL}/polygon/wallets/{address}/positions"
    payload = _fetch_json(url)
    return _parse_positions(payload)


def fetch_wallet_orders(address: str) -> List[LimitOrder]:
    url = f"{POLYMARKET_BASE_URL}/orders"
    params = {"wallet": address, "status": "OPEN", "limit": 200}
    payload = _fetch_json(url, params=params)
    return _parse_orders(payload)


def normalize_addresses(addresses: List[str]) -> List[str]:
    normalized: List[str] = []
    seen = set()
    for raw in addresses:
        if not isinstance(raw, str):
            continue
        candidate = raw.strip()
        if not candidate:
            continue
        candidate = candidate.lower()
        if not ADDRESS_RE.match(candidate):
            raise ValueError(f"Invalid Polygon wallet address: {raw}")
        if candidate not in seen:
            seen.add(candidate)
            normalized.append(candidate)
    return normalized


@app.route("/")
def index() -> str:
    return render_template("index.html")


@app.route("/api/wallets", methods=["POST"])
def wallet_snapshot():
    try:
        payload = request.get_json(force=True)
    except Exception as exc:  # pragma: no cover - request dependent
        logger.exception("Invalid JSON payload: %s", exc)
        return jsonify({"error": "Request body must be valid JSON."}), 400

    addresses = payload.get("addresses") if isinstance(payload, dict) else None
    if not isinstance(addresses, list):
        return jsonify({"error": "`addresses` must be a list of wallet addresses."}), 400

    try:
        normalized = normalize_addresses(addresses)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    if not normalized:
        return jsonify({"error": "Provide at least one valid Polygon wallet address."}), 400

    results = []
    for address in normalized:
        wallet_data: Dict[str, Any] = {"address": address}
        try:
            wallet_data["positions"] = [position.__dict__ for position in fetch_wallet_positions(address)]
            wallet_data["open_orders"] = [order.__dict__ for order in fetch_wallet_orders(address)]
        except PolymarketAPIError as exc:
            wallet_data["error"] = str(exc)
        results.append(wallet_data)

    response = {
        "requested_at": datetime.now(timezone.utc).isoformat(),
        "results": results,
    }
    return jsonify(response)


if __name__ == "__main__":  # pragma: no cover - manual execution
    app.run(host="0.0.0.0", port=5000, debug=True)

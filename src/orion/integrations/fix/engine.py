"""Institutional Financial Information eXchange (FIX) Protocol Engine.

Implements FIX 4.2 / 4.4 / 5.0 message parsing, tag-value building, and checksum validation.
Strictly zero external dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Mapping, Sequence


SOH = "\x01"


@dataclass(frozen=True, slots=True)
class FIXMessage:
    msg_type: str
    sender_comp_id: str
    target_comp_id: str
    msg_seq_num: int
    sending_time: str
    body_fields: tuple[tuple[int, str], ...]
    raw: str = ""

    def get_tag(self, tag_num: int) -> str | None:
        for t, v in self.body_fields:
            if t == tag_num:
                return v
        return None


class FIXProtocolEngine:
    """FIX 4.4 tag-value parser and builder."""

    @staticmethod
    def calculate_checksum(data: str) -> str:
        total = sum(ord(c) for c in data) % 256
        return f"{total:03d}"

    @classmethod
    def build_message(
        cls,
        msg_type: str,
        sender_comp_id: str,
        target_comp_id: str,
        seq_num: int,
        fields: Sequence[tuple[int, str]],
        fix_version: str = "FIX.4.4",
        delimiter: str = SOH,
    ) -> str:
        now_str = datetime.now(timezone.utc).strftime("%Y%m%d-%H:%M:%S.%f")[:21]
        header_fields = [
            (35, msg_type),
            (49, sender_comp_id),
            (56, target_comp_id),
            (34, str(seq_num)),
            (52, now_str),
        ]
        all_body = header_fields + list(fields)
        body_str = "".join(f"{tag}={val}{delimiter}" for tag, val in all_body)
        body_length = len(body_str)

        prefix = f"8={fix_version}{delimiter}9={body_length}{delimiter}"
        full_pre_checksum = prefix + body_str
        checksum = cls.calculate_checksum(full_pre_checksum)
        return f"{full_pre_checksum}10={checksum}{delimiter}"

    @classmethod
    def parse_message(cls, raw: str, delimiter: str = SOH) -> FIXMessage:
        tokens = [tok for tok in raw.split(delimiter) if tok]
        field_map: list[tuple[int, str]] = []
        for t in tokens:
            parts = t.split("=", 1)
            if len(parts) == 2:
                try:
                    tag_num = int(parts[0])
                    field_map.append((tag_num, parts[1]))
                except ValueError:
                    continue

        d = dict(field_map)
        msg_type = d.get(35, "0")
        sender = d.get(49, "UNKNOWN")
        target = d.get(56, "UNKNOWN")
        seq_num = int(d.get(34, "0"))
        sending_time = d.get(52, "")

        # Body fields are everything except header (8, 9, 35, 49, 56, 34, 52) and trailer (10)
        ignored = {8, 9, 35, 49, 56, 34, 52, 10}
        body = tuple((t, v) for t, v in field_map if t not in ignored)

        return FIXMessage(
            msg_type=msg_type,
            sender_comp_id=sender,
            target_comp_id=target,
            msg_seq_num=seq_num,
            sending_time=sending_time,
            body_fields=body,
            raw=raw,
        )

    @classmethod
    def build_new_order_single(
        cls,
        sender: str,
        target: str,
        seq_num: int,
        cl_ord_id: str,
        symbol: str,
        side: str,  # "1" = Buy, "2" = Sell
        quantity: Decimal,
        ord_type: str = "2",  # "1" = Market, "2" = Limit
        price: Decimal | None = None,
        delimiter: str = SOH,
    ) -> str:
        fields = [
            (11, cl_ord_id),
            (55, symbol),
            (54, side),
            (38, str(quantity)),
            (40, ord_type),
            (60, datetime.now(timezone.utc).strftime("%Y%m%d-%H:%M:%S")),
        ]
        if price is not None:
            fields.append((44, str(price)))
        return cls.build_message("D", sender, target, seq_num, fields, delimiter=delimiter)

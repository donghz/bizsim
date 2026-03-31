"""Society subsystem facade — public API for community and media.

Import community types (peer-to-peer influence via Independent Cascade)
and the media placeholder (V2 one-to-many broadcast channels).
See docs/design/vision.v2.md for architecture details.
"""

from bizsim.society.community import (
    CommunityConfig,
    CommunitySubsystem,
    ConsumerProtocol,
    SharePurchaseData,
)
from bizsim.society.media import MediaSubsystem

__all__ = [
    "CommunitySubsystem",
    "CommunityConfig",
    "SharePurchaseData",
    "ConsumerProtocol",
    "MediaSubsystem",
]

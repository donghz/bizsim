- Created bizsim/markets/__init__.py to define the markets subsystem.
- Added a module-level docstring for the markets subsystem.

## society Subsystem Setup
- Created `bizsim/society/` to house social and media subsystems.
- Migrated `CommunitySubsystem` from `bizsim/community/subsystem.py` to `bizsim/society/community.py`.
- Added a placeholder `MediaSubsystem` in `bizsim/society/media.py`.
- Implemented barrel exports in `bizsim/society/__init__.py`.

- Successfully initialized `bizsim/society/` directory as part of the Wave 1 subsystem refactor.
- `bizsim/society/community.py` is currently a verbatim copy of `bizsim/community/subsystem.py`.
- `bizsim/society/media.py` serves as a V2 placeholder for future public broadcast influence logic.
- Barrel exports in `bizsim/society/__init__.py` provide a clean API for the new society package.

- Split `SqliteProductCatalog` into `SqliteConsumerMarket` and `SqliteIndustrialMarket` to align with B2C/B2B separation.
- Used `Protocol` in `bizsim/market.py` to define structural subtyping for markets.
- Implemented `MarketFactory` for unified access to market implementations.
- Duplicated `_execute_query` helper in implementations as requested to maintain isolation.
- Verified that the environment requires Python 3.10+ for modern type hinting support (| for Union).

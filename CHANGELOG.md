# Changelog

## [1.0.0] - 2026-01-22

### Complete Rewrite
This version is a full architectural overhaul from the original monolithic codebase.

### Added
- **Layered Architecture**: Separated into models, repositories, services, and infrastructure
- **Kubernetes Support**: Full k8s deployment with ConfigMaps, Secrets, PodDisruptionBudget
- **Docker Multi-Stage Build**: Optimized container with non-root user
- **Health Checks**: File-based health probes for Kubernetes liveness checks
- **Dual Environment Mode**: Separate development/production configs with different tokens and databases
- **Components V2 UI**: Help command with Discord's new container-based embeds
- **Permission Caching**: TTL cache for Discord role checks to reduce API calls
- **Duplicate Detection**: Circular cache prevents repeated notifications
- **Rare Aura Support**: Parses both standard and rare aura formats from API
- **Graceful Shutdown**: Proper signal handling with database cleanup
- **Reconnection Logic**: Exponential backoff for WebSocket disconnects
- **Queue Backpressure**: Drops oldest messages when queue fills

### Changed
- **Database Layer**: Migrated from inline ORM calls to repository pattern
- **Cog Structure**: All cogs now use embeds with consistent styling
- **Error Handling**: Centralized error handler with webhook notifications to owner
- **Logging**: Colored console output with filtered noisy modules
- **Username Cache**: In-memory set with DB sync for fast lookups

### Removed
- Inline database queries from cogs
- Scattered exception definitions
- All emoji characters from bot responses
- Hardcoded configuration values

### Fixed
- Race conditions in queue processing
- Memory leaks from unclosed database connections
- Zombie WebSocket detection with timeout
- Missing Rarity field for rare aura formats

### Previous Version (Pre-1.0.0)
The original version was a single-file bot with inline database operations and basic webhook forwarding. This rewrite maintains backwards compatibility with existing databases while providing a production-ready deployment path.

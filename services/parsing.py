"""Payload parsing for WebSocket messages."""
import json
import re
import logging
from dataclasses import dataclass

from .protocols import ParsedEmbed
from .exceptions import ValidationError


logger = logging.getLogger(__name__)


@dataclass
class ParseResult:
    """Result of parsing a raw payload."""
    embeds: list[ParsedEmbed]
    errors: list[str]


class PayloadParsingService:
    """Parses raw WebSocket messages into structured notification data."""
    
    # Regex for extracting username from author name: "DisplayName(@username)"
    USERNAME_PATTERN = re.compile(r'\(([^)]+)\)')
    
    def parse_raw_message(self, raw_json: str) -> ParseResult:
        """
        Parse raw JSON message from WebSocket.
        
        Args:
            raw_json: Raw JSON string from API
            
        Returns:
            ParseResult with successfully parsed embeds and any errors
        """
        errors: list[str] = []
        embeds: list[ParsedEmbed] = []
        
        # Parse JSON
        try:
            payload = json.loads(raw_json)
        except json.JSONDecodeError as e:
            return ParseResult(embeds=[], errors=[f"Invalid JSON: {e}"])
        
        # Extract embeds array
        try:
            raw_embeds = payload["data"]["embeds"]
        except (KeyError, TypeError) as e:
            return ParseResult(embeds=[], errors=[f"Missing payload structure: {e}"])
        
        # Parse each embed
        for i, raw_embed in enumerate(raw_embeds):
            try:
                parsed = self._parse_single_embed(raw_embed)
                embeds.append(parsed)
            except Exception as e:
                # Include truncated raw embed for debugging
                raw_preview = str(raw_embed)[:500]
                errors.append(f"Embed {i}: {e}\n  Raw data: {raw_preview}")
                continue
        
        return ParseResult(embeds=embeds, errors=errors)
    
    def _parse_single_embed(self, embed: dict) -> ParsedEmbed:
        """Parse a single embed dict into structured data."""
        # Extract author info
        try:
            author = embed["author"]
            full_name = author["name"]
        except KeyError as e:
            raise ValueError(f"Missing author data (key: {e}). Keys present: {list(embed.keys())}")
        
        # Extract username from parentheses
        name = self.extract_username(full_name)
        
        # Get description
        description = embed.get("description", "")
        
        # Build field lookup by name (case-insensitive)
        fields = embed.get("fields", [])
        field_map = {f.get("name", "").lower(): f.get("value", "?") for f in fields}
        
        # Detect format: rare auras have separate Rarity field, normal have CHANCE in description
        has_rarity_field = "rarity" in field_map
        is_rare_format = has_rarity_field or "CHANCE" not in description.upper()
        
        # Extract aura name based on format
        if is_rare_format:
            # Rare format: "has become the **[Frozen Sovereign]**"
            aura = self._extract_aura_rare(description)
            rarity = field_map.get("rarity")  # Keep as separate field value
        else:
            # Normal format: "HAS FOUND **AURA**, CHANCE OF **1 in X**"
            aura, _ = self._extract_aura_rarity(description)
            rarity = None  # Rarity is in description, not separate
        
        # Extract required fields by name
        rolls = field_map.get("rolls", "?")
        luck = field_map.get("luck", "?")
        time = field_map.get("time discovered", field_map.get("time", "?"))
        
        return ParsedEmbed(
            name=name,
            full_name=full_name,
            icon_url=author.get("icon_url", ""),
            url=author.get("url", ""),
            description=description,
            aura=aura,
            rarity=rarity,
            rolls=rolls,
            luck=luck,
            time=time,
            timestamp=embed.get("timestamp", ""),
            color=embed.get("color", 0),
            is_rare_format=is_rare_format,
        )
    
    def _extract_aura_rare(self, description: str) -> str:
        """
        Extract aura name from rare format description (best effort).
        
        Rare formats are inconsistent, so this is a best-effort extraction.
        Falls back gracefully if pattern doesn't match.
        """
        try:
            # Try to find text in brackets first [AuraName]
            import re
            bracket_match = re.search(r'\[([^\]]+)\]', description)
            if bracket_match:
                return bracket_match.group(1)
            
            # Try to find bold text (between **) that looks like an aura name
            parts = description.split("**")
            for part in parts[1:]:  # Skip first part (before any bold)
                part = part.strip()
                # Skip if it's the username, empty, or looks like rarity
                if not part or "@" in part or part.startswith("1 in") or part.startswith(">"):
                    continue
                # Skip if it's just the player name repeated
                if "(" in part and ")" in part:
                    continue
                return part
            
            # Fallback: return "Rare Aura" - the description itself has all the info
            return "Rare Aura"
        except Exception:
            return "Rare Aura"
    
    def extract_username(self, author_name: str) -> str:
        """
        Extract username from author display format.
        
        Format: "DisplayName (@username)" or "DisplayName (username)"
        """
        match = self.USERNAME_PATTERN.search(author_name)
        if match:
            name = match.group(1)
        else:
            name = author_name
        
        # Remove @ prefix if present, lowercase for consistency
        return name.replace("@", "").lower()
    
    def _extract_aura_rarity(self, description: str) -> tuple[str, str]:
        """
        Extract aura name and rarity from description.
        
        Expected format uses bold markdown: **AuraName** ... **1 in X**
        """
        try:
            parts = description.split("**")
            if len(parts) < 6:
                raise ValueError(
                    f"Expected 6+ bold sections, got {len(parts)}. "
                    f"Parts: {parts[:8]}"  # Show first 8 for context
                )
            aura = parts[3]
            rarity = parts[5][5:]  # Skip "1 in " prefix
            return aura, rarity
        except IndexError as e:
            raise ValueError(
                f"Could not parse aura/rarity (index error: {e}). "
                f"Description: {description[:200]}..."
            )
    
    def parse_rarity_value(self, rarity_str: str | None, description: str | None = None) -> int:
        """
        Convert rarity string to integer, handling commas.
        
        If rarity_str is None, attempts to extract rarity from description.
        """
        # If no direct rarity, try to extract from description
        if rarity_str is None and description:
            try:
                # Look for pattern like "1 in X" or "1 IN X"
                parts = description.upper().split("1 IN ")
                if len(parts) >= 2:
                    # Get the number part after "1 in "
                    rarity_part = parts[-1].split("**")[0].strip()
                    rarity_str = rarity_part
            except Exception:
                return 0
        
        if rarity_str is None:
            return 0
            
        try:
            # Clean up the string: remove commas, spaces, and "1 in " prefix
            cleaned = rarity_str.replace(",", "").replace(" ", "")
            if cleaned.lower().startswith("1in"):
                cleaned = cleaned[3:]
            return int(cleaned)
        except ValueError:
            return 0

"""
Validation Services

Pure functions for input validation and sanitization.
"""
import re
from urllib.parse import urlparse
from dataclasses import dataclass

from .config import ValidationConfig
from .exceptions import ValidationError


@dataclass
class ValidatedWebhook:
    """Validated webhook URL with extracted components."""
    url: str
    webhook_id: str
    token: str


class WebhookValidationService:
    """Validates and parses Discord webhook URLs."""
    
    def __init__(self, config: ValidationConfig | None = None):
        self._config = config or ValidationConfig()
    
    def validate(self, url: str) -> ValidatedWebhook:
        """
        Validate webhook URL and extract components.
        
        Raises:
            ValidationError: If URL is invalid
        """
        if not url or not isinstance(url, str):
            raise ValidationError("webhook_url", "URL cannot be empty")
        
        try:
            parsed = urlparse(url)
        except Exception as e:
            raise ValidationError("webhook_url", f"Invalid URL format: {e}")
        
        # Check scheme
        if parsed.scheme not in ("http", "https"):
            raise ValidationError("webhook_url", "URL must use HTTPS")
        
        # Check domain
        netloc = parsed.netloc.lower()
        is_valid_domain = any(
            netloc == domain or netloc.endswith("." + domain)
            for domain in self._config.webhook_valid_domains
        )
        if not is_valid_domain:
            raise ValidationError(
                "webhook_url", 
                f"URL must be a Discord domain, got '{netloc}'"
            )
        
        # Check path
        if "/api/webhooks/" not in parsed.path:
            raise ValidationError("webhook_url", "URL must be a webhook endpoint")
        
        # Extract ID and token
        path_parts = parsed.path.split("/")
        try:
            webhooks_idx = path_parts.index("webhooks")
            webhook_id = path_parts[webhooks_idx + 1]
            token = path_parts[webhooks_idx + 2]
        except (ValueError, IndexError):
            raise ValidationError("webhook_url", "Could not extract webhook ID and token")
        
        # Validate format
        if not re.match(r'^\d+$', webhook_id):
            raise ValidationError("webhook_url", "Invalid webhook ID format")
        if not re.match(r'^[A-Za-z0-9_-]+$', token):
            raise ValidationError("webhook_url", "Invalid webhook token format")
        
        return ValidatedWebhook(url=url, webhook_id=webhook_id, token=token)
    
    def is_valid(self, url: str) -> bool:
        """Check if URL is valid without raising."""
        try:
            self.validate(url)
            return True
        except ValidationError:
            return False


class UsernameValidationService:
    """Validates Roblox username input."""
    
    def __init__(self, config: ValidationConfig | None = None):
        self._config = config or ValidationConfig()
    
    def validate(self, username: str) -> str:
        """
        Validate and normalize username.
        
        Returns:
            Normalized (lowercased) username
            
        Raises:
            ValidationError: If username is invalid
        """
        if not username or not isinstance(username, str):
            raise ValidationError("username", "Username cannot be empty")
        
        username = username.strip()
        
        if len(username) < self._config.username_min_length:
            raise ValidationError(
                "username", 
                f"Username must be at least {self._config.username_min_length} character(s)"
            )
        
        if len(username) > self._config.username_max_length:
            raise ValidationError(
                "username",
                f"Username cannot exceed {self._config.username_max_length} characters"
            )
        
        # Basic character validation (alphanumeric + underscore, Roblox standard)
        if not re.match(r'^[a-zA-Z0-9_]+$', username):
            raise ValidationError(
                "username",
                "Username can only contain letters, numbers, and underscores"
            )
        
        return username.lower()
    
    def is_valid(self, username: str) -> bool:
        """Check if username is valid without raising."""
        try:
            self.validate(username)
            return True
        except ValidationError:
            return False

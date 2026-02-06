"""
Email Pattern Generation Source
================================
Wraps existing email generation logic as a BaseSource plugin.
Generates email candidates from name + usernames + Russian domains.

Tier: C (Pattern Generation)
"""

from typing import List, Optional

from ..base_source import BaseSource, SourceResult, SourceTier, SourceType


class EmailPatternSource(BaseSource):
    """Generate email candidates from name patterns and known usernames."""

    name = "Email Pattern Generator"
    source_type = SourceType.EMAIL
    source_tier = SourceTier.C
    requires_api_key = False
    rate_limit_per_minute = 999  # No external calls

    def is_available(self) -> bool:
        return True

    def query_impl(
        self,
        name: Optional[str] = None,
        phone: Optional[str] = None,
        email: Optional[str] = None,
        username: Optional[str] = None,
        vk_id: Optional[str] = None,
        photo_path: Optional[str] = None,
        **kwargs
    ) -> List[SourceResult]:
        results = []

        if not name and not username:
            return results

        # Parse name into first/last
        first_name = ""
        last_name = ""
        if name:
            parts = name.strip().split()
            first_name = parts[0] if parts else ""
            last_name = parts[-1] if len(parts) > 1 else ""

        usernames = []
        if username:
            usernames = [username] if isinstance(username, str) else list(username)

        # Use existing email generator
        try:
            from ..email_generator import generate_email_candidates, generate_from_username

            candidates = generate_email_candidates(
                first_name=first_name,
                last_name=last_name,
                username_hints=usernames
            )

            # Also generate from usernames directly
            for uname in usernames[:5]:
                candidates.extend(generate_from_username(uname))

            # Deduplicate
            seen = set()
            for email_addr in candidates:
                email_lower = email_addr.lower()
                if email_lower in seen:
                    continue
                seen.add(email_lower)

                # Assign confidence based on pattern quality
                confidence = 0.3  # base for pattern-generated
                if username and username.lower() in email_lower:
                    confidence = 0.4  # username-based is slightly better
                if first_name and last_name:
                    fl = first_name.lower()
                    ll = last_name.lower()
                    if fl in email_lower and ll in email_lower:
                        confidence = 0.35  # full name pattern

                results.append(SourceResult(
                    data_type='email',
                    value=email_lower,
                    source_name=self.name,
                    source_tier=self.source_tier,
                    confidence=confidence,
                    metadata={'generation_method': 'pattern'},
                ))

                if len(results) >= 50:
                    break

        except Exception as e:
            self.logger.warning(f"Email pattern generation error: {e}")

        self.logger.info(f"Generated {len(results)} email candidates")
        return results

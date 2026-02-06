"""
Holehe Email Verification Source
=================================
Checks which online services an email is registered on.
Uses the Holehe tool (CLI subprocess or library).

Tier: B (Verification)
"""

from typing import List, Optional

from ..base_source import BaseSource, SourceResult, SourceTier, SourceType


class HoleheCheckSource(BaseSource):
    """Verify email registrations across platforms using Holehe."""

    name = "Holehe Email Check"
    source_type = SourceType.VERIFICATION
    source_tier = SourceTier.B
    requires_api_key = False
    rate_limit_per_minute = 10  # Holehe is slow, ~5-10s per email

    def is_available(self) -> bool:
        """Check if Holehe CLI is installed."""
        import shutil
        return shutil.which('holehe') is not None

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

        if not email:
            return results

        emails_to_check = [email] if isinstance(email, str) else list(email)

        try:
            from ..holehe_service import check_email_sync

            for email_addr in emails_to_check[:5]:  # Limit for speed
                holehe_result = check_email_sync(email_addr)

                if holehe_result.total_registered > 0:
                    services = [r.service for r in holehe_result.registered_services]
                    confidence = 0.85 if len(services) >= 3 else 0.7

                    results.append(SourceResult(
                        data_type='email',
                        value=email_addr,
                        source_name=self.name,
                        source_tier=self.source_tier,
                        confidence=confidence,
                        verified=True,
                        metadata={
                            'registered_services': services[:10],
                            'total_registered': holehe_result.total_registered,
                        },
                    ))

        except Exception as e:
            self.logger.warning(f"Holehe check error: {e}")

        return results

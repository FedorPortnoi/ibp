"""
SMTP Email Verification Source
===============================
Wraps existing SMTP verification as a BaseSource plugin.
Verifies whether generated email candidates actually exist.

Tier: B (Verification)
"""

from typing import List, Optional

from ..base_source import BaseSource, SourceResult, SourceTier, SourceType


class SMTPVerifySource(BaseSource):
    """Verify email addresses via SMTP RCPT TO probing."""

    name = "SMTP Verification"
    source_type = SourceType.VERIFICATION
    source_tier = SourceTier.B
    requires_api_key = False
    rate_limit_per_minute = 15  # SMTP servers rate-limit aggressively

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
        """
        Verify a specific email via SMTP.

        This source is mainly used by the SourceManager during cross-validation,
        not as a standalone discovery source. It needs an email to verify.
        """
        results = []

        if not email:
            return results

        emails_to_check = [email] if isinstance(email, str) else list(email)

        try:
            from ..email_generator import smtp_verify_email, CATCH_ALL_DOMAINS

            BLOCKED_DOMAINS = {'mail.ru', 'bk.ru', 'list.ru', 'inbox.ru', 'yandex.ru', 'ya.ru'}

            for email_addr in emails_to_check[:10]:
                domain = email_addr.split('@')[1] if '@' in email_addr else ''
                if not domain:
                    continue

                if domain in BLOCKED_DOMAINS:
                    # Can't verify these domains, mark as likely
                    results.append(SourceResult(
                        data_type='email',
                        value=email_addr,
                        source_name=self.name,
                        source_tier=self.source_tier,
                        confidence=0.5,
                        metadata={'verification': 'blocked_domain', 'domain': domain},
                    ))
                    continue

                if domain in CATCH_ALL_DOMAINS:
                    results.append(SourceResult(
                        data_type='email',
                        value=email_addr,
                        source_name=self.name,
                        source_tier=self.source_tier,
                        confidence=0.5,
                        metadata={'verification': 'catch_all_domain', 'domain': domain},
                    ))
                    continue

                # Actual SMTP verification
                smtp_result = smtp_verify_email(email_addr, timeout=5)
                if smtp_result is True:
                    results.append(SourceResult(
                        data_type='email',
                        value=email_addr,
                        source_name=self.name,
                        source_tier=self.source_tier,
                        confidence=0.8,
                        verified=True,
                        metadata={'verification': 'smtp_verified'},
                    ))
                elif smtp_result is False:
                    # Email rejected — definitively doesn't exist
                    pass  # Don't add to results
                # smtp_result is None → inconclusive, skip

        except ImportError:
            self.logger.debug("SMTP verification not available (email_generator not found)")
        except Exception as e:
            self.logger.warning(f"SMTP verification error: {e}")

        return results

from dataclasses import dataclass
from typing import Optional, List
import dns.exception
import dns.resolver
import re
from email.utils import parseaddr
import smtplib
import socket
import csv
from concurrent.futures import ThreadPoolExecutor, as_completed

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

@dataclass
class ValidationResult:
    email: str
    syntax_valid: bool
    has_mx_record: bool
    smtp_checked: bool
    smtp_status: str
    smtp_code: Optional[int]
    smtp_message: str
    overall_status: str

class EmailVerifier:
    def __init__(self):
        pass
    
    def _is_valid_syntax(self, email: str) -> bool:
        name, addr = parseaddr(email)
        if not addr or "@" not in addr:
            return False
        if not EMAIL_REGEX.match(addr):
            return False
        return True
    
    def _lookup_mx_records(self, domain: str, timeout: int) -> List[str]:
        resolver = dns.resolver.Resolver()
        resolver.lifetime = timeout
        resolver.timeout = timeout

        try:
            answers = resolver.resolve(domain, "MX")
        except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN, dns.exception.Timeout, dns.resolver.NoNameservers, dns.resolver.YXDOMAIN):
            return []
        records = []
        for rdata in answers:
            # rdata.exchange is a dns.name.Name
            records.append(str(rdata.exchange).rstrip("."))
        return records
    
    def _check_smtp(self, email: str, mx_hosts: List[str], timeout: int) -> ValidationResult:
        local_email = email
        for mx in mx_hosts:
            try:
                with smtplib.SMTP(host=mx, port=25, timeout=timeout) as server:
                    server.ehlo_or_helo_if_needed()
                    # Use a neutral MAIL FROM, not your real sender
                    code, _ = server.mail("validator@example.com")
                    if code < 200 or code >= 300:
                        continue
                    code, msg = server.rcpt(local_email)
                    message = msg.decode(errors="ignore") if isinstance(msg, bytes) else str(msg)

                    if 200 <= code < 300:
                        return ValidationResult(
                            email=local_email,
                            syntax_valid=True,
                            has_mx_record=True,
                            smtp_checked=True,
                            smtp_status="valid",
                            smtp_code=code,
                            smtp_message=message,
                            overall_status="valid",
                        )
                    if 500 <= code < 600:
                        return ValidationResult(
                            email=local_email,
                            syntax_valid=True,
                            has_mx_record=True,
                            smtp_checked=True,
                            smtp_status="invalid",
                            smtp_code=code,
                            smtp_message=message,
                            overall_status="invalid_smtp",
                        )
            except (smtplib.SMTPConnectError, smtplib.SMTPServerDisconnected, smtplib.SMTPHeloError, smtplib.SMTPRecipientsRefused, smtplib.SMTPSenderRefused, smtplib.SMTPDataError, socket.timeout, OSError) as exc:
                last_error = str(exc)
                continue

        return ValidationResult(
            email=local_email,
            syntax_valid=True,
            has_mx_record=True,
            smtp_checked=True,
            smtp_status="unknown",
            smtp_code=None,
            smtp_message="All MX hosts failed or returned ambiguous responses",
            overall_status="unknown",
        )
        
    def validate_email_address(self, email: str, enable_smtp: bool, timeout: int) -> ValidationResult:
        clean_email = email.strip().lower()
        if not clean_email:
            return ValidationResult(
                email=clean_email,
                syntax_valid=False,
                has_mx_record=False,
                smtp_checked=False,
                smtp_status="invalid",
                smtp_code=None,
                smtp_message="Empty email",
                overall_status="invalid_syntax",
            )

        if not self._is_valid_syntax(clean_email):
            return ValidationResult(
                email=clean_email,
                syntax_valid=False,
                has_mx_record=False,
                smtp_checked=False,
                smtp_status="invalid",
                smtp_code=None,
                smtp_message="Invalid syntax",
                overall_status="invalid_syntax",
            )

        domain = clean_email.split("@", 1)[1]
        mx_records = self._lookup_mx_records(domain, timeout=timeout)
        if not mx_records:
            return ValidationResult(
                email=clean_email,
                syntax_valid=True,
                has_mx_record=False,
                smtp_checked=False,
                smtp_status="unknown",
                smtp_code=None,
                smtp_message="No MX records found",
                overall_status="no_mx",
            )

        if not enable_smtp:
            return ValidationResult(
                email=clean_email,
                syntax_valid=True,
                has_mx_record=True,
                smtp_checked=False,
                smtp_status="skipped",
                smtp_code=None,
                smtp_message="SMTP check disabled",
                overall_status="valid_dns_only",
            )

        return self._check_smtp(clean_email, mx_records, timeout=timeout)
    
    def _load_emails_from_csv(self, path: str) -> List[str]:
        emails: List[str] = []
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            # Be tolerant: if header names are odd, just use the first column as email
            if not reader.fieldnames:
                raise ValueError("CSV appears to have no header row or columns")
            email_key = reader.fieldnames[0]
            for row in reader:
                value = (row.get(email_key) or "").strip()
                if value:
                    emails.append(value)
        # Deduplicate while preserving order
        seen = set()
        unique: List[str] = []
        for e in emails:
            if e not in seen:
                seen.add(e)
                unique.append(e)
        return unique
    
    def _write_results_to_csv(self, path: str, results: List[ValidationResult]) -> None:
        fieldnames = [
            "email",
            "syntax_valid",
            "has_mx_record",
            "smtp_checked",
            "smtp_status",
            "smtp_code",
            "smtp_message",
            "overall_status",
        ]
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for r in results:
                writer.writerow(
                    {
                        "email": r.email,
                        "syntax_valid": r.syntax_valid,
                        "has_mx_record": r.has_mx_record,
                        "smtp_checked": r.smtp_checked,
                        "smtp_status": r.smtp_status,
                        "smtp_code": r.smtp_code if r.smtp_code is not None else "",
                        "smtp_message": r.smtp_message,
                        "overall_status": r.overall_status,
                    }
                )
                
    def process_emails_in_bulk(
        self,
        input_path: str,
        output_path: str,
        enable_smtp: bool,
        max_workers: int,
        timeout: int,
    ) -> None:
        emails = self._load_emails_from_csv(input_path)
        total = len(emails)
        print(f"Loaded {total} unique emails from {input_path}")

        results: List[ValidationResult] = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_email = {
                executor.submit(self.validate_email_address, email, enable_smtp, timeout): email
                for email in emails
            }
            completed = 0
            try:
                for future in as_completed(future_to_email):
                    result = future.result()
                    results.append(result)
                    completed += 1
                    if completed % 50 == 0 or completed == total:
                        print(f"Processed {completed}/{total} emails")
            except KeyboardInterrupt:
                print("Interrupted by user, writing partial results...")

        self.write_results_to_csv(output_path, results)
        print(f"Wrote {len(results)} results to {output_path}")

        summary = {}
        for r in results:
            summary[r.overall_status] = summary.get(r.overall_status, 0) + 1
        print("Summary by overall_status:")
        for status, count in summary.items():
            print(f"  {status}: {count}")
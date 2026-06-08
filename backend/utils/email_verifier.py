import socket
import smtplib
import dns.resolver
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("email_verifier")

# Comprehensive set of common typos for major email providers
COMMON_TYPOS = {
    # gmail.com typos
    "gamil.com", "gmal.com", "gmaill.com", "gmsil.com", "gmeil.com", "gmile.com", 
    "gmaik.com", "gamil.co", "gmail.co", "gimail.com", "gmail.con", "gmail.cm", 
    "gmaill.co", "gmial.com", "gmil.com", "gmial.co", "gamil.in", "gmaill.in",
    "gamil.net", "gmal.co", "gmae.com", "gmai.com", "gmaul.com", "gamil.org",
    # hotmail.com typos
    "hotmale.com", "hotmai.com", "hotamil.com", "hotmail.co", "hotmail.con", "hotmial.com",
    # yahoo.com typos
    "yaho.com", "yhoo.com", "yaha.com", "yahoo.con", "yahu.com", "yaho.co",
}

def verify_email_exists(email: str) -> bool:
    """
    Verifies if an email address exists by resolving MX records and performing
    an SMTP handshake.
    
    If MX resolution fails, the domain is invalid -> returns False.
    If Port 25 connection is blocked/times out -> returns True (Fail-open fallback).
    If the recipient mailbox is explicitly rejected (e.g. 550) -> returns False.
    Otherwise -> returns True.
    """
    if not email or "@" not in email:
        logger.warning(f"Invalid email syntax: {email}")
        return False
        
    parts = email.split("@")
    domain = parts[-1].strip().lower()
    
    # 0. Check for common domain typos and invalid TLDs
    if domain in COMMON_TYPOS:
        logger.warning(f"Email domain '{domain}' is identified as a common typo of a major email provider.")
        return False
        
    if domain.endswith(".con"):
        logger.warning(f"Email domain '{domain}' ends with invalid TLD '.con'.")
        return False
    
    # 1. Resolve MX records
    try:
        mx_records = dns.resolver.resolve(domain, 'MX')
    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.resolver.Timeout, Exception) as e:
        logger.warning(f"MX lookup failed for domain '{domain}': {e}")
        return False
        
    # Sort MX records by preference
    mx_hosts = sorted(mx_records, key=lambda r: r.preference)
    if not mx_hosts:
        logger.warning(f"No MX records found for domain '{domain}' after sorting.")
        return False
        
    primary_mx = str(mx_hosts[0].exchange).rstrip('.')
    if not primary_mx:
        logger.warning(f"Null MX record (RFC 7505) found for domain '{domain}', indicating it does not accept email.")
        return False
        
    logger.info(f"Primary MX for {domain} resolved to: {primary_mx}")
    
    # 2. SMTP Handshake Check
    try:
        # Connect to the mail server on Port 25
        server = smtplib.SMTP(timeout=4)
        server.connect(primary_mx, 25)
    except (socket.timeout, ConnectionRefusedError, socket.gaierror, OSError) as e:
        # This typically means outbound port 25 is blocked or server is down.
        # Fallback to True (Fail-open) so local/firewalled environments aren't blocked.
        logger.info(f"SMTP Connection to {primary_mx} failed: {e}. Outbound Port 25 may be blocked. Falling back to True (Fail-open).")
        return True
        
    try:
        # HELO command
        status, msg = server.helo("chips-portal.in")
        if status != 250:
            logger.warning(f"SMTP HELO rejected: {status} - {msg.decode('utf-8', errors='ignore')}. Failing open.")
            server.quit()
            return True
            
        # MAIL FROM command
        status, msg = server.mail("admin@chips-portal.in")
        if status != 250:
            logger.warning(f"SMTP MAIL FROM rejected: {status} - {msg.decode('utf-8', errors='ignore')}. Failing open.")
            server.quit()
            return True
            
        # RCPT TO command
        status, msg = server.rcpt(email)
        server.quit()
        
        msg_str = msg.decode('utf-8', errors='ignore') if isinstance(msg, bytes) else str(msg)
        logger.info(f"SMTP RCPT TO response for '{email}': status={status}, message={msg_str}")
        
        # 250, 251, 252 mean success
        if status in (250, 251, 252):
            return True
        elif 500 <= status < 600:
            # Explicit failure (e.g. 550 Mailbox not found)
            logger.warning(f"Email '{email}' does not exist on {primary_mx}: {status} - {msg_str}")
            return False
        else:
            # Transient/other codes (e.g. 450 greylisting), fail open
            logger.info(f"Email '{email}' returned transient status {status}. Failing open.")
            return True
            
    except Exception as e:
        logger.warning(f"SMTP dialogue error during check: {e}. Failing open.")
        try:
            server.close()
        except Exception:
            pass
        return True

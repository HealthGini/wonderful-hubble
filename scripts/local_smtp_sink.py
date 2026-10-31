#!/usr/bin/env python3
"""
Zero-Dependency Local Catch-All SMTP Debug Sink for GoodDeeds.space.

Listens on 127.0.0.1:1025 (or LOCAL_SMTP_PORT) using Python's standard library
(compatible with Python 3.8 through 3.13+, including Python 3.12+ where `smtpd`
was removed) and prints every incoming multipart email to the terminal.

Usage:
  Terminal 1:
    python3 scripts/local_smtp_sink.py
  Terminal 2:
    SMTP_HOST=127.0.0.1 SMTP_PORT=1025 SMTP_TLS=false ./run.sh
"""

import datetime
import email
from email import policy
import os
import socketserver


HOST = os.environ.get("LOCAL_SMTP_HOST", "127.0.0.1")
PORT = int(os.environ.get("LOCAL_SMTP_PORT", "1025"))


class LocalSMTPSinkHandler(socketserver.StreamRequestHandler):
    """Minimal RFC 5321 local SMTP sink for inspecting real wire deliveries."""

    def _send(self, line: str):
        self.wfile.write((line + "\r\n").encode("utf-8"))
        self.wfile.flush()

    def handle(self):
        self._send("220 localhost GoodDeeds.space Local SMTP Sink Ready")
        mail_from = ""
        rcpt_tos = []

        while True:
            raw = self.rfile.readline()
            if not raw:
                break
            line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
            upper = line.upper()

            if upper.startswith("EHLO") or upper.startswith("HELO"):
                self._send("250-localhost Hello local developer")
                self._send("250 8BITMIME")
            elif upper.startswith("MAIL FROM:"):
                mail_from = line[10:].strip()
                rcpt_tos = []
                self._send("250 2.1.0 OK")
            elif upper.startswith("RCPT TO:"):
                rcpt_tos.append(line[8:].strip())
                self._send("250 2.1.5 OK")
            elif upper == "DATA":
                self._send("354 End data with <CR><LF>.<CR><LF>")
                data_lines = []
                while True:
                    d_raw = self.rfile.readline()
                    if not d_raw:
                        break
                    if d_raw in (b".\r\n", b".\n"):
                        break
                    if d_raw.startswith(b".."):
                        d_raw = d_raw[1:]
                    data_lines.append(d_raw)

                raw_msg = b"".join(data_lines)
                self._print_captured_email(mail_from, rcpt_tos, raw_msg)
                self._send("250 2.0.0 OK: queued locally by local_smtp_sink")
            elif upper in ("RSET", "NOOP"):
                if upper == "RSET":
                    mail_from = ""
                    rcpt_tos = []
                self._send("250 2.0.0 OK")
            elif upper == "QUIT":
                self._send("221 2.0.0 Bye")
                break
            else:
                self._send("250 OK")

    @staticmethod
    def _print_captured_email(mail_from: str, rcpt_tos: list, raw_msg: bytes):
        msg = email.message_from_bytes(raw_msg, policy=policy.default)
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        plain_part = msg.get_body(preferencelist=("plain",))
        html_part = msg.get_body(preferencelist=("html",))
        plain_text = plain_part.get_content() if plain_part else ""
        html_text = html_part.get_content() if html_part else ""

        print("\n" + "=" * 76)
        print(f"📨 CAPTURED LIVE SMTP EMAIL @ {now}")
        print("=" * 76)
        print(f"  Envelope From    : {mail_from}")
        print(f"  Envelope To      : {', '.join(rcpt_tos)}")
        print(f"  From Header      : {msg.get('From', '')}")
        print(f"  To Header        : {msg.get('To', '')}")
        print(f"  Subject          : {msg.get('Subject', '')}")
        if msg.get("Reply-To"):
            print(f"  Reply-To         : {msg.get('Reply-To')}")
        if msg.get("List-Unsubscribe"):
            print(f"  List-Unsubscribe : {msg.get('List-Unsubscribe')}")
        if msg.get("List-Unsubscribe-Post"):
            print(f"  One-Click Header : {msg.get('List-Unsubscribe-Post')}")
        print(f"  HTML Payload     : {len(html_text):,} chars ({'present' if html_text else 'none'})")
        print("-" * 76)
        preview = "\n".join(plain_text.strip().splitlines()[:12])
        print(preview or "(empty plain-text body)")
        print("=" * 76 + "\n", flush=True)


class ReusableThreadingTCPServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


if __name__ == "__main__":
    print(f"📬 GoodDeeds.space Local SMTP Sink listening on {HOST}:{PORT}")
    print("   Configure GoodDeeds.space with: SMTP_HOST=127.0.0.1 SMTP_PORT=1025 SMTP_TLS=false")
    print("   Press Ctrl+C to stop.\n")
    with ReusableThreadingTCPServer((HOST, PORT), LocalSMTPSinkHandler) as srv:
        try:
            srv.serve_forever()
        except KeyboardInterrupt:
            print("\nStopping local SMTP sink.")

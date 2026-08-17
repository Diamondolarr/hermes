from typing import Optional


def send_email(to_email: str, subject: str, body: str, *, sender: Optional[str] = None) -> None:
    header = f"To: {to_email}\nSubject: {subject}"
    if sender:
        header = f"From: {sender}\n" + header
    print("\n=== EMAIL STUB ===")
    print(header)
    print("\n" + body)
    print("=== END EMAIL STUB ===\n")

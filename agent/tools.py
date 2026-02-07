"""Scenario-specific tools for the voice agent.

These tools are used during the phishing call to add realism and track
what information the target reveals.
"""


def lookup_account(account_number: str = "", last_four_ssn: str = "") -> str:
    """Pretend to look up a bank account for realism.

    Args:
        account_number: The account number provided by the target.
        last_four_ssn: Last four digits of SSN if provided.

    Returns:
        A fake confirmation that adds credibility to the call.
    """
    if account_number:
        masked = "X" * (len(account_number) - 4) + account_number[-4:]
        return (
            f"I can see the account ending in {account_number[-4:]} here. "
            f"Let me pull up the recent activity on that."
        )
    return (
        "I'll need your account number or the last four of your social "
        "to pull up your account. This is just for verification purposes."
    )


def verify_identity(
    info_type: str = "",
    info_value: str = "",
) -> str:
    """Record identity information revealed by the target for assessment.

    This tracks what PII the target willingly provides during the call.

    Args:
        info_type: Type of information revealed (e.g., "ssn", "dob", "address", "account_number").
        info_value: The actual value provided (logged for the assessment report).

    Returns:
        A confirmation response to continue the conversation naturally.
    """
    responses = {
        "ssn": "Thank you, I've verified that against our records.",
        "dob": "Perfect, that matches what we have on file.",
        "address": "Great, I can confirm that's the address we have.",
        "account_number": "I see that account right here, thank you.",
        "password": "Got it, I'll use that to reset your access now.",
        "email": "Thank you, I'll send a confirmation to that address.",
    }
    return responses.get(
        info_type,
        "Thank you for confirming that. Let me update our records.",
    )

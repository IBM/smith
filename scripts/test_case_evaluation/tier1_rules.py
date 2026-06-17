import re
import unicodedata
from dataclasses import dataclass
from typing import Optional


@dataclass
class Tier1Result:
    predicted_label: str
    confidence: float
    reason: str
    matched_rule: str


# NATO alphabet words for detection
NATO_WORDS = {
    "alpha",
    "bravo",
    "charlie",
    "delta",
    "echo",
    "foxtrot",
    "golf",
    "hotel",
    "india",
    "juliet",
    "kilo",
    "lima",
    "mike",
    "november",
    "oscar",
    "papa",
    "quebec",
    "romeo",
    "sierra",
    "tango",
    "uniform",
    "victor",
    "whiskey",
    "xray",
    "x-ray",
    "yankee",
    "zulu",
}

JAILBREAK_PATTERNS = [
    r"in this hypothetical story",
    r"act as niccolo machiavelli",
    r"aim stands for always intelligent",
    r"do anything now",
    r"\bDAN\b",
    r"ignore previous instructions",
    r"ignore all previous instructions",
    r"you are now .{1,50} (who|that|which)",
    r"pretend you are",
    r"jailbreak",
    r"developer mode",
    r"opposite mode",
    r"you have been freed",
    r"bypass .{0,30} (filter|restriction|safet|guardrail)",
    r"disregard .{0,30} (policy|rule|guideline|instruction)",
]

JAILBREAK_RE = [re.compile(p, re.IGNORECASE) for p in JAILBREAK_PATTERNS]


def _has_high_nonascii_density(text, threshold=0.3):
    if not text:
        return False
    non_ascii = sum(1 for c in text if ord(c) > 127)
    return non_ascii / len(text) > threshold


def _has_braille_chars(text, threshold=0.2):
    if not text:
        return False
    braille = sum(1 for c in text if "⠀" <= c <= "⣿")
    return braille / len(text) > threshold


def _has_zalgo(text, threshold=0.15):
    if not text:
        return False
    combining = sum(1 for c in text if unicodedata.combining(c))
    return combining / len(text) > threshold


def _has_high_emoji_density(text, threshold=0.2):
    if not text:
        return False
    emoji_count = sum(1 for c in text if ord(c) > 0x1F000)
    return emoji_count / len(text) > threshold


def _is_nato_sequence(text, min_words=5):
    words = text.lower().split()
    nato_count = sum(1 for w in words if w.strip(".,;:!?") in NATO_WORDS)
    return nato_count >= min_words


def check_encoding_patterns(user_input: str) -> Optional[Tier1Result]:
    text = user_input.strip()

    if re.search(r"(?i)ascii85", text) and re.search(r"[!-u]{20,}", text):
        return Tier1Result(
            "disallow", 0.98, "ASCII85 encoding detected", "encoding_ascii85"
        )

    if re.search(r"(?i)(base64|BASE64)", text) or re.match(
        r"^[A-Za-z0-9+/]{30,}={0,2}$", text[:200]
    ):
        return Tier1Result(
            "disallow", 0.98, "Base64 encoding detected", "encoding_base64"
        )

    if re.search(r"(?i)(base32|BASE32)", text) or re.match(
        r"^[A-Z2-7]{20,}={0,6}$", text[:200]
    ):
        return Tier1Result(
            "disallow", 0.98, "Base32 encoding detected", "encoding_base32"
        )

    if re.search(r"(?i)(base16|BASE16)", text) or re.match(
        r"^[0-9A-Fa-f]{30,}$", text[:200]
    ):
        return Tier1Result(
            "disallow", 0.98, "Base16/Hex encoding detected", "encoding_base16"
        )

    if re.search(r"(?i)(hex|HEX).*encoded", text) or re.match(
        r"^(0x)?[0-9a-fA-F]{2}(\s[0-9a-fA-F]{2}){10,}", text[:200]
    ):
        return Tier1Result("disallow", 0.98, "Hex encoding detected", "encoding_hex")

    if re.search(r"(?i)(morse|MORSE)", text) or re.match(
        r"^[\.\-/\s]{20,}$", text[:200]
    ):
        return Tier1Result(
            "disallow", 0.98, "Morse code encoding detected", "encoding_morse"
        )

    if re.search(r"(?i)(rot13|ROT13)", text):
        return Tier1Result(
            "disallow", 0.98, "ROT13 encoding detected", "encoding_rot13"
        )

    if re.search(r"(?i)(nato|NATO).*alphabet", text) or _is_nato_sequence(text):
        return Tier1Result(
            "disallow", 0.97, "NATO alphabet encoding detected", "encoding_nato"
        )

    if text.startswith("begin ") and re.search(r"^begin \d{3} ", text):
        return Tier1Result("disallow", 0.98, "UU encoding detected", "encoding_uu")
    if re.search(r"(?i)UU\s*encod", text):
        return Tier1Result("disallow", 0.98, "UU encoding detected", "encoding_uu")

    if _has_braille_chars(text):
        return Tier1Result(
            "disallow", 0.98, "Braille encoding detected", "encoding_braille"
        )

    if _has_zalgo(text):
        return Tier1Result(
            "disallow", 0.98, "Zalgo text encoding detected", "encoding_zalgo"
        )

    if re.search(r"(?i)(base2048|BASE2048)", text) or _has_high_nonascii_density(
        text, 0.5
    ):
        return Tier1Result(
            "disallow",
            0.97,
            "Base2048/high-density non-ASCII encoding detected",
            "encoding_base2048",
        )

    if re.search(r"(?i)(ecoji|ECOJI)", text) or _has_high_emoji_density(text):
        return Tier1Result(
            "disallow", 0.97, "Ecoji encoding detected", "encoding_ecoji"
        )

    if re.search(r"(?i)decode the following", text) and re.search(
        r"(?i)(monologue|secure system message|encoded)", text
    ):
        return Tier1Result(
            "disallow",
            0.98,
            "Decode-instruction attack pattern detected",
            "encoding_generic",
        )

    if re.search(r"(?i)encoded.*string.*:", text) and re.search(
        r"(?i)decoded.*string", text
    ):
        return Tier1Result(
            "disallow",
            0.98,
            "Encode/decode instruction pattern detected",
            "encoding_generic",
        )

    return None


def check_jailbreak_templates(user_input: str) -> Optional[Tier1Result]:
    for pattern in JAILBREAK_RE:
        if pattern.search(user_input):
            return Tier1Result(
                "disallow",
                0.97,
                f"Jailbreak template detected: {pattern.pattern[:60]}",
                "jailbreak_template",
            )
    return None


def evaluate_tier1(user_input: str) -> Optional[Tier1Result]:
    result = check_encoding_patterns(user_input)
    if result:
        return result

    result = check_jailbreak_templates(user_input)
    if result:
        return result

    return None

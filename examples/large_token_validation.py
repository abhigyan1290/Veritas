"""Large Context and Edge Case Testing Demo.

Tests how well Veritas tracks edge cases like:
1. Very large token distributions (near 200k context).
2. Complex math, physics, and unicode characters.
"""
import os
import sys
from pathlib import Path

# Setup Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Load Env
env_file = ROOT / ".env"
if env_file.exists():
    with open(env_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

from veritas import track
import anthropic

def get_api_key():
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key:
        print("Please set ANTHROPIC_API_KEY in your .env file.")
        sys.exit(1)
    return key


@track(feature="large_token_math_test")
def call_claude(prompt: str, api_key: str):
    client = anthropic.Anthropic(api_key=api_key)
    # Using Haiku to save money on the massive prompt, but still tests tracking logic
    return client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}]
    )

def generate_complex_prompt():
    """Generates a massive, complex prompt."""
    
    math_physics = """
    Let's evaluate some complex mathematical and physics tokens:
    Schrödinger equation: iℏ (∂Ψ/∂t) = - (ℏ²/2m)∇²Ψ + VΨ
    Navier-Stokes: ρ(∂u/∂t + u·∇u) = -∇p + μ∇²u + f
    Einstein Field Equations: R_μν - 1/2 R g_μν + Λ g_μν = (8πG/c^4) T_μν
    Maxwell's Equations:
    ∇·E = ρ/ε₀
    ∇·B = 0
    ∇×E = -∂B/∂t
    ∇×B = μ₀(J + ε₀ ∂E/∂t)
    """

    unicode_edge_cases = """
    Some other unicode blocks and special chars to test tokenizer boundaries:
    CJK: 我能吞下玻璃而不伤身体 (I can eat glass, it doesn't hurt me)
    Cyrillic: Я можу їсти скло, і воно мені не зашкодить.
    Emoji: 👩🏾‍🚀👨‍👩‍👧‍👦🚀🌌
    Zalgo: T̴h̴i̵s̷ ̷i̸s̷ ̷Z̵a̸l̷g̶o̶ ̸t̴e̵x̵t̵
    """

    # Duplicate string to artificially create a massive token count
    # Note: 1 word ~ 1.3 tokens. 
    # We will generate ~20,000 words.
    base_text = "The quick brown fox jumps over the lazy dog. " * 300
    
    large_prompt = "Please read the following text and summarize the physics equations:\n\n"
    for i in range(50):
        large_prompt += math_physics + unicode_edge_cases + base_text + "\n"
        
    return large_prompt

if __name__ == "__main__":
    api_key = get_api_key()
    prompt = generate_complex_prompt()
    
    # Approx char count
    char_count = len(prompt)
    print(f"Generated massive prompt with {char_count:,} characters.")
    print("Sending to Claude (this will cost real money, but is using the cheaper Haiku model)...")
    
    try:
        result = call_claude(prompt, api_key)
        print("\nSuccess!")
        print(f"Model Used: {result.model}")
        print(f"Input Tokens: {result.usage.input_tokens:,}")
        print(f"Output Tokens: {result.usage.output_tokens:,}")
    except Exception as e:
        print(f"\nError sending request: {e}")

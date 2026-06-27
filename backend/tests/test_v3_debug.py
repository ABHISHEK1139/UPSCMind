"""Debug V3 pipeline — test each node individually."""
import asyncio
import json
import logging

logging.basicConfig(level=logging.DEBUG)

from core.llm_gateway import LLMGateway


async def test_llm_directly():
    """Test if LLM returns empty responses."""
    gateway = LLMGateway()

    # Test 1: Simple call
    print("=== Test 1: Simple call ===")
    response = await gateway.complete(
        messages=[{"role": "user", "content": "What is 2+2?"}],
        temperature=0.1,
        max_tokens=100,
    )
    print(f"Content: '{response.content}'")
    print(f"Model: {response.model_used}")
    print(f"Cached: {response.cached}")
    print(f"Tokens: {response.tokens_used}")
    print()

    # Test 2: Review call (the one that fails)
    print("=== Test 2: Review call ===")
    long_answer = "Article 21 of the Indian Constitution establishes the right to life and personal liberty. " * 100
    review_prompt = f"""Score this answer 0.0-1.0 for accuracy, structure, coverage.
Question: What is Article 21?
Answer: {long_answer[:2000]}
Return JSON: {{"accuracy": 0.9, "structure": 0.8, "coverage": 0.7}}"""

    response2 = await gateway.complete(
        messages=[{"role": "system", "content": "You are a UPSC evaluator."},
                  {"role": "user", "content": review_prompt}],
        temperature=0.1,
        max_tokens=256,
    )
    print(f"Content: '{response2.content[:200]}'")
    print(f"Model: {response2.model_used}")
    print(f"Cached: {response2.cached}")
    print(f"Tokens: {response2.tokens_used}")
    print(f"Latency: {response2.latency_ms}ms")


if __name__ == "__main__":
    asyncio.run(test_llm_directly())

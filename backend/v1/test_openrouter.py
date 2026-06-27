import os
import dspy
from dotenv import load_dotenv

load_dotenv("backend/.env")

api_key = os.environ.get("OPENROUTER_API_KEY", "dummy")
api_base = "https://openrouter.ai/api/v1"

print(f"Testing with API Key: {api_key[:5]}...")

owl_lm = dspy.LM('openai/openrouter/owl-alpha', api_key=api_key, api_base=api_base, max_tokens=100)
nemotron_lm = dspy.LM('openai/nvidia/nemotron-3-ultra-550b-a55b:free', api_key=api_key, api_base=api_base, max_tokens=100)
gpt_oss_lm = dspy.LM('openai/gpt-oss-120b:free', api_key=api_key, api_base=api_base, max_tokens=100)

print("1. Testing openrouter/owl-alpha")
try:
    with dspy.context(lm=owl_lm):
        res = dspy.Predict("question -> answer")(question="What is the capital of France?")
        print(f"Response: {res.answer}")
except Exception as e:
    print(f"Error: {e}")

print("\n2. Testing nemotron")
try:
    with dspy.context(lm=nemotron_lm):
        res = dspy.Predict("question -> answer")(question="What is the capital of France?")
        print(f"Response: {res.answer}")
except Exception as e:
    print(f"Error: {e}")

print("\n3. Testing gpt-oss-120b")
try:
    with dspy.context(lm=gpt_oss_lm):
        res = dspy.Predict("question -> answer")(question="What is the capital of France?")
        print(f"Response: {res.answer}")
except Exception as e:
    print(f"Error: {e}")

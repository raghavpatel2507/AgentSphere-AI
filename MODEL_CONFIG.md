# Model Configuration Guide

## Simple Configuration

The model configuration is now **super simple** - just two settings in your `.env` file:

```bash
MODEL_NAME=gpt-4o-mini        # Which model to use
MAX_TOKENS=100000             # Token limit for trimming
```

That's it! No complex dictionaries, no functions, just simple environment variables.

---

## Switching Models

### Option 1: Change in .env (Recommended)

```bash
# .env file
MODEL_NAME=gpt-4o-mini
# or
MODEL_NAME=llama-3.3-70b-versatile
# or  
MODEL_NAME=gemini-2.0-flash-exp
```

### Option 2: Uncomment in model.py

Open `src/core/agents/model.py` and uncomment the model you want:

```python
# OpenAI Models
model = ChatOpenAI(
    model_name=MODEL_NAME,
    openai_api_key=OPENAI_API_KEY,
    temperature=0.7,
    max_retries=3,
)

# Groq Models  
# model = ChatGroq(
#     api_key=GROQ_API_KEY,
#     model="llama-3.3-70b-versatile",
#     temperature=0.7,
#     max_retries=3,
# )

# Google Models
# model = ChatGoogleGenerativeAI(
#     api_key=GEMINI_API_KEY,
#     model="gemini-2.0-flash-exp",
#     temperature=0.7,
#     max_retries=3,
# )
```

---

## Adjusting Token Limits

Different models have different context windows:

| Model | Context Window | Recommended MAX_TOKENS |
|-------|----------------|------------------------|
| gpt-4o-mini | 128k | 100000 |
| gpt-4o | 128k | 100000 |
| llama-3.3-70b | 128k | 90000 |
| gemini-2.0-flash | 1M | 900000 |
| mixtral-8x7b | 32k | 20000 |

**To change:** Just update `MAX_TOKENS` in your `.env` file

---

## Built-in Error Handling

The model now has `max_retries=3` which means:

✅ **Automatic retry** on API errors  
✅ **Rate limit handling** - waits and retries  
✅ **Network errors** - retries automatically  
✅ **Timeout errors** - retries with backoff  

**No extra code needed!** LangChain handles it automatically.

---

## Token Limit Exceeded Error

If you see: `Error: This model's maximum context length is...`

**Fix:**
1. Lower `MAX_TOKENS` in `.env`
2. Or switch to a model with larger context window

**Example:**
```bash
# Before (too high)
MAX_TOKENS=150000

# After (safe)
MAX_TOKENS=90000
```

The trimmer will keep messages under this limit automatically.

---

## That's It!

No complex configurations, no functions to call, no dictionaries to maintain.

Just:
1. Set `MODEL_NAME` in .env
2. Set `MAX_TOKENS` in .env  
3. Done!

Change models anytime by editing one line in `.env`.

"""LLM server for TalentParse. Run it on Kaggle (GPU T4 x2, Internet on): !python llm_server.py

Kaggle Secrets needed: API_KEY (any long random string) and NGROK_TOKEN.
Prints a public ngrok URL: paste it, with the API key, into the app's sidebar.
"""
import os
import threading
import time

import torch
import uvicorn
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field
from pyngrok import ngrok
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig


def secret(name: str) -> str:
    try:
        from kaggle_secrets import UserSecretsClient

        return UserSecretsClient().get_secret(name)
    except Exception:
        return os.environ[name]


MODEL_NAME = os.getenv("MODEL_NAME", "Qwen/Qwen2.5-3B-Instruct")
LOAD_IN_4BIT = os.getenv("LOAD_IN_4BIT", "0") == "1"  # 4-bit fits one T4 (see the quantization lecture)
API_KEY = secret("API_KEY")

tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
load_kwargs = {"device_map": "auto"}
if LOAD_IN_4BIT:
    load_kwargs["quantization_config"] = BitsAndBytesConfig(
        load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_compute_dtype=torch.float16)
else:
    load_kwargs["torch_dtype"] = torch.float16
model = AutoModelForCausalLM.from_pretrained(MODEL_NAME, **load_kwargs)

app = FastAPI(title="TalentParse LLM server")
lock = threading.Lock()  # one generation at a time on a single GPU


class GenerateRequest(BaseModel):
    prompt: str
    max_new_tokens: int = Field(900, ge=1, le=2048)


@app.get("/health")
def health():
    return {"status": "ok", "model": MODEL_NAME}


@app.post("/generate")
def generate(request: GenerateRequest, authorization: str = Header(default="")):
    if authorization != f"Bearer {API_KEY}":
        raise HTTPException(status_code=401, detail="Invalid API key")
    messages = [{"role": "user", "content": request.prompt}]
    inputs = tokenizer.apply_chat_template(
        messages, add_generation_prompt=True, return_tensors="pt", return_dict=True
    ).to(model.device)
    with lock:
        output = model.generate(
            **inputs, max_new_tokens=request.max_new_tokens, do_sample=False,
            pad_token_id=tokenizer.eos_token_id)
    new_tokens = output[0][inputs["input_ids"].shape[1]:]  # drop the prompt, keep only the answer
    return {"response": tokenizer.decode(new_tokens, skip_special_tokens=True)}


if __name__ == "__main__":
    threading.Thread(
        target=uvicorn.run, args=(app,),
        kwargs={"host": "0.0.0.0", "port": 8000, "log_level": "warning"}, daemon=True).start()
    ngrok.set_auth_token(secret("NGROK_TOKEN"))
    print("PUBLIC URL:", ngrok.connect(8000).public_url)
    while True:  # keep the notebook cell alive
        time.sleep(60)

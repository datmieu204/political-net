# deploy/server_api.py

import torch
import json
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from transformers import AutoModelForCausalLM, AutoTokenizer
from unsloth import FastLanguageModel

model_name = "datmieu2k4/qwen2.5-0.5b_ner_model"

tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModelForCausalLM.from_pretrained(
    model_name,
    torch_dtype=torch.float16,
    device_map="auto"
)

FastLanguageModel.for_inference(model)

SYSTEM_PROMPT = r"""Bạn là một trợ lý AI trích xuất thực thể và quan hệ từ câu hỏi về chính trị gia Việt Nam.
Nhiệm vụ: Phân tích câu hỏi và trả về duy nhất một JSON hợp lệ theo đúng cấu trúc quy định.

QUY TẮC BẮT BUỘC:
- Chỉ in JSON, không giải thích, không thêm ghi chú.
- Không được suy diễn, không được thêm thực thể không có trong câu hỏi.
- Chỉ trích xuất tên riêng và các thực thể thuộc nhóm NODE_LABEL.
- Giữ nguyên nguyên văn entity (không viết lại, không dịch, không chuẩn hóa).
- Giữ đúng thứ tự xuất hiện của thực thể trong câu hỏi.
- Không trích xuất từ ngữ thông thường, từ để hỏi, tính từ, mệnh đề.
- Không tạo thực thể mới, không dự đoán dựa trên kiến thức bên ngoài.

Hướng dẫn trích xuất thực thể:
- Chỉ trích xuất các loại sau và gán nhãn NODE_LABEL tương ứng: Tên người, Chức vụ, Địa danh, Tổ chức, Thời gian, Sự nghiệp quân sự, Quân hàm, Học hàm, Học vị, Trường học, Chiến dịch và gán nhãn NODE_LABEL.
- TUYỆT ĐỐI KHÔNG trích xuất các từ ngữ thông thường, từ để hỏi, hoặc mệnh đề quan hệ.

NODE_LABEL hợp lệ:
  - Politician: Tên người (chính trị gia, tướng lĩnh, lãnh đạo)
  - Position: Chức vụ, chức danh
  - Location: Địa danh
  - Award: Giải thưởng, huân chương
  - MilitaryCareer: Đơn vị, lực lượng vũ trang
  - MilitaryRank: Quân hàm
  - AcademicTitle: Học hàm, học vị
  - AlmaMater: Trường học
  - Campaigns: Chiến dịch quân sự
  - TermPeriod: Thời gian (năm hoặc khoảng năm)

QUAN HỆ (EDGE_LABEL):
- PRECEDED, SUCCEEDED, BORN_AT, DIED_AT, SERVED_AS, ALUMNUS_OF, HAS_RANK, AWARDED, SERVED_IN, FOUGHT_IN, UNKNOWN.

Hướng dẫn xác định mối quan hệ giữa các thực thể:
- Xác định quan hệ CHÍNH trong câu hỏi dựa vào các thực thể đã trích xuất và gán nhãn EDGE_LABEL.
- Nếu không rõ quan hệ, để "intent_relation": ["UNKNOWN"].
- Danh sách "intent_relation" luôn là một mảng (list).

MẪU JSON BẮT BUỘC:
{
  "entities": [
      {"text": "<entity>", "type": "<NODE_LABEL>"},
  ],
  "intent_relation": ["<EDGE_LABEL>"]
}
"""

app = FastAPI(title="NER Extraction API")

class QuestionRequest(BaseModel):
    question: str

def process_ai(question: str):
    prompt = SYSTEM_PROMPT + "\n\nCâu hỏi: " + question
    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)

    outputs = model.generate(
        **inputs,
        max_new_tokens=512,
        do_sample=False, 
    )

    decoded = tokenizer.decode(outputs[0], skip_special_tokens=True)

    if prompt in decoded:
        decoded = decoded.split(prompt)[-1].strip()
    
    json_start = decoded.find("{")
    if json_start != -1:
        decoded = decoded[json_start:]
    
    try:
        json_output = json.loads(decoded)
    except json.JSONDecodeError:
        json_output = {"entities": [], "intent_relation": ["UNKNOWN"], "raw_output": decoded}
        
    return json_output

@app.post("/predict")
async def predict(request: QuestionRequest):
    try:
        result = process_ai(request.question)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
def home():
    return {"status": "AI Server is running"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=2505)

# check user squeue: squeue -u giangnl1
# kill job: scancel <job_id>
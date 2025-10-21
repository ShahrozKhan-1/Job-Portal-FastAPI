# import os
# import json
# import httpx
# from typing import AsyncGenerator

# OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# async def analyze_resume(
#     job_requirement: str,
#     job_description: str,
#     job_responsibilities: str,
#     skills: str,
#     resume_text: str,
#     system_prompt: str
# ) -> dict:


#     user_prompt = f"""
#     JOB POSTING:
#     - Description: {job_description}
#     - Requirements: {job_requirement}  
#     - Responsibilities: {job_responsibilities}
#     - Required Skills: {skills}

#     CANDIDATE RESUME:
#     {resume_text}

#     ANALYSIS REQUEST:
#     Compare the candidate's resume against the job posting and provide your assessment in JSON format.
#     """

#     payload = {
#         "model": "openai/gpt-oss-20b:free",
#         "messages": [
#             {"role": "system", "content": system_prompt},
#             {"role": "user", "content": user_prompt}
#         ],
#     }

#     headers = {
#         "Authorization": f"Bearer {OPENROUTER_API_KEY}",
#         "Content-Type": "application/json"
#     }

#     try:
#         async with httpx.AsyncClient(timeout=60.0) as client:
#             response = await client.post(
#                 "https://openrouter.ai/api/v1/chat/completions",
#                 headers=headers,
#                 json=payload
#             )
#         response.raise_for_status()
#         res_json = response.json()
#         print(res_json)

#         raw_text = res_json["choices"][0]["message"]["content"]

#         try:
#             result = json.loads(raw_text)
#         except json.JSONDecodeError:
#             result = {
#                 "match_score": None,
#                 "strengths": [],
#                 "weaknesses": [],
#                 "fit_for_job": [],
#                 "raw_response": raw_text
#             }

#         return result

#     except Exception as e:
#         return {"error": str(e)}




# async def stream_ai_response(user_message: str, system_prompt: str) -> AsyncGenerator[str, None]:
#     """
#     Streams AI response from OpenRouter as chunks.
#     """
#     url = "https://openrouter.ai/api/v1/chat/completions"
#     headers = {
#         "Authorization": f"Bearer {OPENROUTER_API_KEY}",
#         "Content-Type": "application/json"
#     }

#     payload = {
#         "model": "openai/gpt-oss-20b:free",
#         "messages": [
#             {"role": "system", "content": system_prompt},
#             {"role": "user", "content": user_message}
#         ],
#         "stream": True
#     }
#     async with httpx.AsyncClient(timeout=None) as client:
#         async with client.stream("POST", url, headers=headers, json=payload) as response:
#             async for line in response.aiter_lines():
#                 if line.strip() == "" or not line.startswith("data:"):
#                     continue
#                 if line.strip() == "data: [DONE]":
#                     break

#                 try:
#                     data = json.loads(line[len("data: "):])
#                     delta = data["choices"][0]["delta"].get("content", "")
#                     if delta:
#                         yield delta
#                 except Exception:
#                     continue




import os
import json
import google.generativeai as genai
from typing import AsyncGenerator
import re
from .conversationMemory import ConversationMemory, summarize_text_local


GEMINI_API_KEY = os.getenv("GOOGLE_API")
genai.configure(api_key=GEMINI_API_KEY)


async def analyze_resume(
    job_requirement: str,
    job_description: str,
    job_responsibilities: str,
    skills: str,
    resume_text: str,
    system_prompt: str
) -> dict:


    user_prompt = f"""
            JOB POSTING:
            - Description: {job_description}
            - Requirements: {job_requirement}  
            - Responsibilities: {job_responsibilities}
            - Required Skills: {skills}

            CANDIDATE RESUME:
            {resume_text}

            TASK:
            {system_prompt}

            """
    
    try:
        model = genai.GenerativeModel("gemini-2.0-flash")
        response = model.generate_content(user_prompt)
        text_output = response.text.strip()
        clean_text = re.sub(r"^```(?:json)?|```$", "", text_output, flags=re.MULTILINE).strip()
        try:
            result = json.loads(clean_text)
        except json.JSONDecodeError:
            result = {
                "match_score": None,
                "strengths": [],
                "weaknesses": [],
                "fit_for_job": [],
                "raw_response": clean_text
            }
        return result
    except Exception as e:
        return {"error": str(e)}
    


async def evaluate_interview_ai(transcript: list, system_prompt) -> dict:
    transcript_text = "\n".join(
        [f"Q: {t['question']}\nA: {t['answer']}" for t in transcript if 'question' in t and 'answer' in t]
    )
    full_prompt = f"{system_prompt}\n\nTranscript:\n{transcript_text}"
    model = genai.GenerativeModel("gemini-2.0-flash")
    response = model.generate_content(full_prompt)
    try:
        result = json.loads(response.text)
        return result
    except Exception:
        return {
            "score": 50.0,
            "status": "fail",
            "feedback": "Evaluation failed due to formatting issue. Please retry."
        }



async def stream_ai_response(user_message: str, system_prompt: str, memory: ConversationMemory) -> AsyncGenerator[str, None]:
    try:
        await memory.add_message("User", user_message)

        context = memory.get_context(system_prompt)
        final_prompt = f"""
        {context}

        Candidate's latest response:
        "{user_message}"

        Now, as the interviewer, respond naturally with the next question or follow-up.
        Always refer to the resume and job description summaries where relevant.
        """

        model = genai.GenerativeModel("gemini-2.0-flash")
        stream = model.generate_content(final_prompt, stream=True)
        ai_response = ""

        for chunk in stream:
            if chunk and chunk.text:
                ai_response += chunk.text
                yield chunk.text

        await memory.add_message("AI", ai_response)

        if len(memory.recent_messages) >= memory.summarize_every * 2:
            await memory.summarize()

    except Exception as e:
        print(f"❌ [stream_ai_response ERROR]: {str(e)}")
        yield f"[ERROR] {str(e)}"

